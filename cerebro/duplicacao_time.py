"""Duplicação de um time inteiro (mesma organização).

Análogo ao "duplicar automação" (`rotas/automacoes.py::duplicar`), mas um nível
acima: recria o GRAFO DE PROPRIEDADE inteiro de um time — agentes, instrumentos,
cinto (N:N), automações e a memória da IA companheira — com **ids NOVOS**. Como a
`automacoes.cadeia` referencia agentes/instrumentos por id POR DENTRO (JSONB), o
trabalho central é **remapear** essas referências dos ids velhos para os novos
(senão a cópia apontaria para o time original — `validar_cadeia` rejeita ou, pior,
o portão por canal vaza cross-time).

Decisões de produto (maestro, 2026-06-20):
- **Escopo = mesma organização** (credenciais e memória continuam válidas).
- **Memória da IA = herdar** (a cópia já "sabe" as decisões lembradas).

Princípios herdados do molde:
- A cópia das automações nasce **inativa** (`ativa=False`) — não dispara em dobro.
- Dados de runtime (execuções, conversas de atendimento, uso) **não** são copiados.
- Instrumentos de **canal** (Telegram/WhatsApp) nascem **desconectados** — sem
  token, sem `webhook_secret`, sem credencial — para dois times nunca brigarem pelo
  mesmo bot (um webhook por bot). O usuário pluga um bot novo na cópia.

Tudo em UMA transação (a rota dá o commit): se um passo falhar, nada é gravado.
Não toca o núcleo de orquestração — só reusa `grafo.normalizar`/`validar_cadeia`.
"""

import copy
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import agendador
import duplicacao_comum
from mensageria.aprovacao import CANAIS_TIPOS
from modelos import (
    Agente,
    AgenteInstrumento,
    Automacao,
    ConversaCriacao,
    Instrumento,
    MemoriaProjeto,
    SegredoInstrumento,
    Time,
)
from orquestracao import grafo
from orquestracao.cadeia import validar_cadeia


def _remapear_cadeia(
    cadeia: dict | None, map_ag: dict[str, str], map_inst: dict[str, str]
) -> dict:
    """Reescreve as referências internas da cadeia (deep-copy) dos ids velhos para
    os novos. Cobre os DOIS formatos: o novo (nó com `id` próprio + `ref` = agente)
    e o legado (o `id` do nó É o próprio `agente_id` — `grafo.converter_linear_*`),
    em que `inicial` e `destino` também são ids de agente. Depois o chamador
    normaliza/valida."""
    cadeia = copy.deepcopy(cadeia or {})
    if not cadeia:
        return {}

    def ag(valor):  # traduz um id-de-agente (id de nó, ref, inicial, destino)
        return map_ag.get(str(valor), valor) if valor is not None else valor

    if cadeia.get("inicial") is not None:
        cadeia["inicial"] = ag(cadeia["inicial"])
    for no in cadeia.get("nos") or []:
        if no.get("id") is not None:
            no["id"] = ag(no["id"])
        if no.get("ref") is not None:
            no["ref"] = ag(no["ref"])
        aprov = no.get("aprovacao")
        if isinstance(aprov, dict) and aprov.get("instrumento_id") is not None:
            aprov["instrumento_id"] = map_inst.get(
                str(aprov["instrumento_id"]), aprov["instrumento_id"]
            )
        for saida in no.get("saidas") or []:
            # O id da saída é um handle derivado do id do nó (`{id}-{j}`). Descarta-o
            # para a normalização seguinte re-derivar do id NOVO — senão sobraria um
            # id de agente antigo no handle (cosmético, mas evitamos vazamento).
            saida.pop("id", None)
            if saida.get("destino") is not None:
                saida["destino"] = ag(saida["destino"])
    return cadeia


def duplicar_time(
    sessao: Session, original: Time, nome: str, criada_por_id: uuid.UUID | None
) -> Time:
    """Cria uma cópia independente de `original` na MESMA organização, com o `nome`
    dado. Faz flush dos novos registros (sem commit — quem chama commita). Levanta
    `ValueError` se alguma cadeia remapeada não validar (não deveria, defensivo)."""
    novo = Time(
        organizacao_id=original.organizacao_id,
        nome=nome,
        descricao=original.descricao,
    )
    sessao.add(novo)
    sessao.flush()

    # 1) Agentes → mapa {agente_velho → agente_novo}.
    map_ag_obj: dict[uuid.UUID, Agente] = {}
    for ag in sessao.scalars(
        select(Agente).where(Agente.time_id == original.id)
    ):
        copia = Agente(
            time_id=novo.id,
            nome=ag.nome,
            papel=ag.papel,
            agent_md=ag.agent_md,
            skill_md=ag.skill_md,
            tools_md=ag.tools_md,
            soul_md=ag.soul_md,
            modelo_ia=ag.modelo_ia,
        )
        sessao.add(copia)
        map_ag_obj[ag.id] = copia
    sessao.flush()

    # 2) Instrumentos → mapa {instrumento_velho → instrumento_novo}. Canais nascem
    #    desconectados (sem token/segredo/webhook/credencial).
    map_inst_obj: dict[uuid.UUID, Instrumento] = {}
    for inst in sessao.scalars(
        select(Instrumento).where(Instrumento.time_id == original.id)
    ):
        eh_canal = inst.tipo in CANAIS_TIPOS
        config = copy.deepcopy(inst.configuracao or {})
        if eh_canal:
            config.pop("webhook_secret", None)  # nasce "a conectar"
        copia = Instrumento(
            time_id=novo.id,
            nome=inst.nome,
            tipo=inst.tipo,
            configuracao=config,
            icone=inst.icone,
            # canal: zera a credencial p/ não resolver o mesmo bot; senão mantém.
            credencial_id=None if eh_canal else inst.credencial_id,
        )
        sessao.add(copia)
        map_inst_obj[inst.id] = copia
    sessao.flush()

    # 3) Segredos inline (cifrados): copia o `valor_cifrado` direto (a chave-mestra é
    #    a mesma → decifra). PULA os de canal (a cópia do canal fica sem token).
    velhos_canal = {
        i_id for i_id, novo_i in map_inst_obj.items() if novo_i.tipo in CANAIS_TIPOS
    }
    ids_nao_canal = [i for i in map_inst_obj if i not in velhos_canal]
    if ids_nao_canal:
        for seg in sessao.scalars(
            select(SegredoInstrumento).where(
                SegredoInstrumento.instrumento_id.in_(ids_nao_canal)
            )
        ):
            sessao.add(
                SegredoInstrumento(
                    instrumento_id=map_inst_obj[seg.instrumento_id].id,
                    campo=seg.campo,
                    valor_cifrado=seg.valor_cifrado,
                    ultimos4=seg.ultimos4,
                )
            )

    # 4) Cinto (N:N): recria cada ligação com os ids novos.
    for aid, iid in sessao.execute(
        select(AgenteInstrumento.agente_id, AgenteInstrumento.instrumento_id)
        .join(Agente, Agente.id == AgenteInstrumento.agente_id)
        .where(Agente.time_id == original.id)
    ).all():
        sessao.add(
            AgenteInstrumento(
                agente_id=map_ag_obj[aid].id,
                instrumento_id=map_inst_obj[iid].id,
            )
        )

    # 5) Automações: remapeia a cadeia, normaliza, valida contra o time NOVO; inativa.
    map_ag_str = {str(velho): str(novo_a.id) for velho, novo_a in map_ag_obj.items()}
    map_inst_str = {
        str(velho): str(novo_i.id) for velho, novo_i in map_inst_obj.items()
    }
    ids_agentes_novos = {str(a.id) for a in map_ag_obj.values()}
    map_auto_str: dict[str, str] = {}  # {automacao_velha → nova} p/ o remap do agendar_automacao
    for auto in sessao.scalars(
        select(Automacao).where(Automacao.time_id == original.id)
    ):
        # Normaliza ANTES de remapear: no formato legado o `nos` é um DICT e o id do
        # nó é o próprio agente_id — normalizar canoniza (lista) para o remapeamento
        # enxergar `id`/`ref`/`destino`/`inicial` de forma uniforme. Normaliza DE NOVO
        # depois (re-deriva ids de saída a partir dos ids novos; idempotente).
        cadeia = grafo.normalizar(
            _remapear_cadeia(
                grafo.normalizar(auto.cadeia or {}), map_ag_str, map_inst_str
            )
        )
        validar_cadeia(cadeia or {}, ids_agentes_novos)  # defensivo
        copia = Automacao(
            time_id=novo.id,
            nome=auto.nome,
            tipo_gatilho=auto.tipo_gatilho,
            # Gatilho de entrada (ex.: comentário do Instagram) nasce "a conectar" —
            # some a conta, como o canal nasce sem token — para a cópia não disparar
            # na conta do original. Filtros preservados.
            configuracao_gatilho=duplicacao_comum.sanear_gatilho_duplicado(
                auto.tipo_gatilho, auto.configuracao_gatilho
            ),
            cadeia=cadeia,
            ativa=False,
            configuracao=copy.deepcopy(auto.configuracao or {}),
        )
        sessao.add(copia)
        sessao.flush()
        map_auto_str[str(auto.id)] = str(copia.id)
        agendador.sincronizar(copia)  # inativa → garante que nenhum job fica no relógio

    # 5b) Instrumento `agendar_automacao`: se o ALVO era uma automação DESTE time
    #     (agora copiada), re-aponta para a cópia; se apontava para FORA, mantém — assim
    #     a cópia reprograma a si mesma, não o original (footgun do id stale, análogo ao
    #     canal que nasce sem token).
    for novo_i in map_inst_obj.values():
        if novo_i.tipo != "agendar_automacao":
            continue
        alvo = (novo_i.configuracao or {}).get("automacao_alvo_id")
        if alvo and str(alvo) in map_auto_str:
            cfg = dict(novo_i.configuracao or {})
            cfg["automacao_alvo_id"] = map_auto_str[str(alvo)]
            novo_i.configuracao = cfg

    # 6) Memória da IA companheira. Cria uma conversa nova amarrada ao time novo. A
    #    conversa RECOMEÇA LIMPA (mensagens=[]): o histórico literal carrega os IDs do
    #    time ORIGINAL (agentes/automações) embutidos nas chamadas de ferramenta, e a IA
    #    se confundiria no time novo ("criei X" e não acha). Herdamos a MEMÓRIA durável
    #    (fatos/decisões/preferências — texto, sem id) e gravamos uma memória de
    #    proveniência, para a IA saber a origem sem os ids stale.
    conversa = sessao.scalars(
        select(ConversaCriacao)
        .where(ConversaCriacao.time_id == original.id)
        .order_by(ConversaCriacao.atualizado_em.desc())
    ).first()
    if conversa is not None:
        nova_conversa = ConversaCriacao(
            organizacao_id=novo.organizacao_id,
            criada_por_id=criada_por_id,
            titulo=nome,
            mensagens=[],
            time_id=novo.id,
        )
        sessao.add(nova_conversa)
        sessao.flush()
        sessao.add(
            MemoriaProjeto(
                conversa_id=nova_conversa.id,
                organizacao_id=novo.organizacao_id,
                categoria="fato",
                conteudo=f"Este time foi duplicado de '{original.nome}'.",
            )
        )
        for mem in sessao.scalars(
            select(MemoriaProjeto).where(MemoriaProjeto.conversa_id == conversa.id)
        ):
            sessao.add(
                MemoriaProjeto(
                    conversa_id=nova_conversa.id,
                    organizacao_id=novo.organizacao_id,
                    categoria=mem.categoria,
                    conteudo=mem.conteudo,
                )
            )

    sessao.flush()
    return novo
