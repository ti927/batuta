"""Materialização do rascunho da IA criadora (Fase 9, MIGRACAO §6.4).

Este é o ÚNICO ponto em que a criação escreve nas tabelas de negócio, e só é
chamado após a aprovação humana explícita. Transforma o documento `Rascunho`
(montado pela IA, validado por Pydantic, guardado em JSONB) em linhas reais —
Time, Instrumentos, Agentes, cinto e Automação — numa ÚNICA transação: ou tudo
entra, ou nada entra (`rollback` em qualquer erro). É o cerne do "a IA propõe / o
consultor confirma": antes daqui, nada existe no banco.

Reusa a mesma lógica de insert das rotas CRUD (`encaixe.preparar_config`,
`validar_cadeia`) para nascer coerente com o resto do sistema. Os `ref`s locais do
rascunho são traduzidos nos uuids reais recém-criados; a cadeia é revalidada já
com os uuids (defesa em profundidade).
"""

import uuid

import auditoria
import instrumentos as encaixe
from criacao.rascunho import Rascunho
from modelos import Agente, AgenteInstrumento, Automacao, ConversaCriacao, Instrumento, Time, Usuario
from orquestracao.cadeia import _DESTINOS_FIM, validar_cadeia


class ErroMaterializacao(Exception):
    """Base das falhas de materialização (a rota traduz para HTTP)."""


class RascunhoInvalido(ErroMaterializacao):
    """O rascunho não está completo/coerente o bastante para virar um time real.
    Carrega a lista de problemas, em português, para mostrar ao consultor."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__("; ".join(problemas))


class ConflitoMaterializacao(ErroMaterializacao):
    """A conversa não está mais em rascunho (já materializada ou descartada)."""


def validar_materializavel(rascunho: Rascunho) -> list[str]:
    """Lista os problemas que impedem materializar (vazia = pode materializar).

    Checa o mínimo viável: time com nome, ≥1 agente nomeado, no máximo um líder,
    tipos/config de instrumento válidos, refs do cinto existentes e — se houver
    cadeia — que ela seja válida e referencie só agentes do rascunho."""
    problemas: list[str] = []

    if not (rascunho.time_nome and rascunho.time_nome.strip()):
        problemas.append("O time precisa de um nome.")
    if not rascunho.agentes:
        problemas.append("O time precisa de pelo menos um agente.")

    lideres = [a for a in rascunho.agentes if a.papel == "lider"]
    if len(lideres) > 1:
        problemas.append("Só pode haver um líder no time.")

    for a in rascunho.agentes:
        if not (a.nome and a.nome.strip()):
            problemas.append("Há um agente sem nome.")

    refs_instrumento = {i.ref for i in rascunho.instrumentos}
    for i in rascunho.instrumentos:
        if encaixe.obter_tipo(i.tipo) is None:
            problemas.append(
                f"Instrumento '{i.nome}': tipo desconhecido ({i.tipo})."
            )
        else:
            try:
                encaixe.preparar_config(i.tipo, i.configuracao)
            except ValueError as e:
                problemas.append(f"Instrumento '{i.nome}': {e}")

    for a in rascunho.agentes:
        for ref in a.cinto:
            if ref not in refs_instrumento:
                problemas.append(
                    f"Agente '{a.nome}': um instrumento do cinto não existe no rascunho."
                )

    if rascunho.automacao and rascunho.automacao.cadeia:
        try:
            validar_cadeia(
                rascunho.automacao.cadeia, {a.ref for a in rascunho.agentes}
            )
        except ValueError as e:
            problemas.append(f"Cadeia: {e}")

    return problemas


def _traduzir_cadeia(cadeia: dict, ref_para_id: dict[str, uuid.UUID]) -> dict:
    """Reescreve o grafo da cadeia trocando os `ref`s locais dos agentes pelos
    uuids reais criados. Destinos de fim (None/""/"fim") são preservados; demais
    chaves de nó e destinos são agentes válidos (já garantido por validação)."""
    if not cadeia:
        return {}

    def tid(ref: str) -> str:
        return str(ref_para_id[ref])

    nos_traduzidos: dict[str, dict] = {}
    for no_ref, no in (cadeia.get("nos") or {}).items():
        saidas = []
        for s in (no or {}).get("saidas") or []:
            destino = s.get("destino")
            novo_destino = destino if destino in _DESTINOS_FIM else tid(destino)
            saidas.append({**s, "destino": novo_destino})
        nos_traduzidos[tid(no_ref)] = {**(no or {}), "saidas": saidas}

    resultado: dict = {"nos": nos_traduzidos}
    inicio = cadeia.get("inicio")
    if inicio:
        resultado["inicio"] = tid(inicio)
    return resultado


def materializar(
    sessao, conversa: ConversaCriacao, usuario: Usuario | None
) -> dict:
    """Transforma o rascunho da conversa num time real, em uma transação.

    Levanta `ConflitoMaterializacao` se a conversa não estiver em rascunho, e
    `RascunhoInvalido` (sem escrever nada) se o rascunho não passar na validação.
    Qualquer erro durante a escrita desfaz tudo (`rollback`). Devolve um resumo do
    que foi criado, para o card de sucesso."""
    if conversa.estado != "rascunho":
        raise ConflitoMaterializacao(
            "Esta conversa já foi materializada ou descartada."
        )

    rascunho = Rascunho.model_validate(conversa.rascunho or {})
    problemas = validar_materializavel(rascunho)
    if problemas:
        raise RascunhoInvalido(problemas)

    try:
        # 1. O time.
        time = Time(
            organizacao_id=conversa.organizacao_id,
            nome=rascunho.time_nome,
            descricao=rascunho.time_descricao,
        )
        sessao.add(time)
        sessao.flush()

        # 2. Instrumentos (config pública; segredos ficam pendentes para o humano).
        ref_para_instrumento: dict[str, uuid.UUID] = {}
        for i in rascunho.instrumentos:
            config_limpa, _segredos = encaixe.preparar_config(i.tipo, i.configuracao)
            inst = Instrumento(
                time_id=time.id, nome=i.nome, tipo=i.tipo, configuracao=config_limpa
            )
            sessao.add(inst)
            sessao.flush()
            ref_para_instrumento[i.ref] = inst.id

        # 3. Agentes (a invariante "um líder só" é garantida pela validação acima
        #    e, em última instância, pelo índice parcial do banco).
        ref_para_agente: dict[str, uuid.UUID] = {}
        for a in rascunho.agentes:
            agente = Agente(
                time_id=time.id,
                nome=a.nome,
                papel=a.papel,
                agent_md=a.agent_md,
                skill_md=a.skill_md,
                tools_md=a.tools_md,
                soul_md=a.soul_md,
                modelo_ia=a.modelo_ia,
            )
            sessao.add(agente)
            sessao.flush()
            ref_para_agente[a.ref] = agente.id

        # 4. O cinto (vínculo agente↔instrumento).
        for a in rascunho.agentes:
            for ref in a.cinto:
                sessao.add(
                    AgenteInstrumento(
                        agente_id=ref_para_agente[a.ref],
                        instrumento_id=ref_para_instrumento[ref],
                    )
                )

        # 5. A automação (só se houver cadeia). Nasce SEMPRE inativa: o consultor
        #    a ativa depois, conscientemente — a criação não dispara nada sozinha.
        criou_automacao = False
        if rascunho.automacao and rascunho.automacao.cadeia:
            cadeia_real = _traduzir_cadeia(
                rascunho.automacao.cadeia, ref_para_agente
            )
            validar_cadeia(cadeia_real, {str(v) for v in ref_para_agente.values()})
            gatilho = rascunho.automacao.gatilho
            auto = Automacao(
                time_id=time.id,
                nome=rascunho.automacao.nome or f"Automação — {time.nome}",
                tipo_gatilho=gatilho.tipo_gatilho,
                configuracao_gatilho=gatilho.configuracao_gatilho,
                cadeia=cadeia_real,
                ativa=False,
            )
            sessao.add(auto)
            sessao.flush()
            criou_automacao = True

        # 6. Fecha a conversa e registra o rastro, na MESMA transação.
        conversa.estado = "materializada"
        conversa.time_id = time.id
        resumo = {
            "time_id": str(time.id),
            "agentes": len(rascunho.agentes),
            "instrumentos": len(rascunho.instrumentos),
            "automacao": criou_automacao,
        }
        auditoria.registrar(
            sessao,
            usuario=usuario,
            acao="criacao.materializada",
            recurso_tipo="time",
            recurso_id=time.id,
            organizacao_id=conversa.organizacao_id,
            detalhe=resumo,
        )

        sessao.commit()
        return resumo
    except Exception:
        # Qualquer falha desfaz tudo: nem o time, nem agentes, nem nada persiste.
        sessao.rollback()
        raise
