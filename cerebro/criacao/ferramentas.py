"""As ferramentas da IA criadora (Fase 9).

Mesmo encaixe de tool-use do motor (`orquestracao.agente`): cada operação vira uma
`StructuredTool` que a IA aciona. A diferença essencial do modo rascunho: estas
ferramentas mutam APENAS um documento `Rascunho` em memória — nenhuma sessão de
banco, nenhuma escrita em tabela de negócio. A IA propõe aqui; o consultor
confirma depois (em `materializar`). Erros viram texto de volta para a IA (como
em `orquestracao.agente`), que corrige na conversa em vez de quebrar.

`montar_ferramentas(estado)` constrói as ferramentas fechadas sobre um
`EstadoCriacao` (o rascunho corrente + os chips sugeridos), para o laço de
conversa ler o resultado depois de a IA agir.
"""

import json
from dataclasses import dataclass, field

from langchain_core.tools import StructuredTool

import instrumentos as encaixe
import precos
from criacao.rascunho import (
    AgenteRascunho,
    AutomacaoRascunho,
    CustoEstimado,
    InstrumentoRascunho,
    Rascunho,
)
from orquestracao.cadeia import validar_cadeia
from orquestracao.llm import MODELO_PADRAO


@dataclass
class EstadoCriacao:
    """O que as ferramentas mutam durante um turno da conversa."""

    rascunho: Rascunho = field(default_factory=Rascunho)
    chips: list[str] = field(default_factory=list)


def catalogo_de_instrumentos() -> list[dict]:
    """O catálogo de tipos de instrumento COM os campos de configuração de cada um.

    É o que destrava a IA criadora: sem saber que o WordPress precisa de `site_url`
    e `usuario`, ela não tem como PERGUNTAR ao consultor por eles. Para cada tipo,
    lista os campos da `Config` marcando `obrigatorio` (no `required` do schema) e
    `secreto` (em `campos_secretos`) — os secretos NÃO são preenchidos pela IA
    (ficam pendentes para o cofre); os públicos a IA deve perguntar e preencher.
    Usado pela ferramenta `listar_tipos_instrumento` e injetado no prompt."""
    catalogo: list[dict] = []
    for tipo in encaixe.tipos_disponiveis():
        esquema = tipo.Config.model_json_schema()
        obrigatorios = set(esquema.get("required", []))
        secretos = set(tipo.campos_secretos)
        campos = [
            {
                "nome": nome,
                "descricao": prop.get("description", ""),
                "obrigatorio": nome in obrigatorios,
                "secreto": nome in secretos,
            }
            for nome, prop in (esquema.get("properties") or {}).items()
        ]
        catalogo.append(
            {
                "tipo": tipo.tipo,
                "nome": tipo.nome_exibicao,
                "descricao": tipo.descricao,
                "campos": campos,
                # Ação irreversível (publicar/enviar/gravar externo): a IA precisa
                # saber para pôr o portão humano antes na cadeia, e o app valida na
                # ativação. Ver instrumentos/base.py e a parede de ativação.
                "acao_irreversivel": tipo.acao_irreversivel,
            }
        )
    return catalogo


def _ok(mensagem: str, **extra) -> str:
    return json.dumps({"ok": True, "mensagem": mensagem, **extra}, ensure_ascii=False)


def _erro(mensagem: str) -> str:
    return json.dumps({"ok": False, "erro": mensagem}, ensure_ascii=False)


# Tipos de gatilho e o formato EXATO da config de agendamento que o `agendador`
# espera (agendador._trigger_da_config). A IA erra por não conhecer este formato —
# por isso ele é documentado aqui, injetado no prompt e validado em definir_gatilho.
TIPOS_GATILHO = ("manual", "agendamento", "webhook")
FORMATO_GATILHO = (
    "Tipos de gatilho:\n"
    "- 'manual': sem config. Você dispara quando quiser.\n"
    "- 'webhook': sem config. Uma chamada externa (URL pública) dispara o fluxo.\n"
    "- 'agendamento': roda no relógio. config = {frequencia: 'diaria'|'semanal'|"
    "'mensal', hora: 0-23, minuto: 0-59, dia_semana: 0-6 (0=segunda, SÓ p/ semanal), "
    "dia_mes: 1-31 (SÓ p/ mensal), entrada?: texto que vira a entrada do fluxo}. "
    "Ex. semanal: {frequencia:'semanal', dia_semana:0, hora:8, minuto:0}."
)


def _inteiro_no_intervalo(valor, minimo: int, maximo: int) -> bool:
    try:
        return minimo <= int(valor) <= maximo
    except (TypeError, ValueError):
        return False


def _validar_gatilho(tipo: str, config: dict) -> str | None:
    """Devolve uma mensagem de erro se o gatilho estiver malformado (None = ok).
    Garante que um 'agendamento' siga o formato que o agendador entende."""
    if tipo not in TIPOS_GATILHO:
        return f"Gatilho desconhecido: '{tipo}'. Use um de: {', '.join(TIPOS_GATILHO)}."
    if tipo != "agendamento":
        return None
    freq = config.get("frequencia")
    if freq not in ("diaria", "semanal", "mensal"):
        return "Agendamento exige frequencia 'diaria', 'semanal' ou 'mensal'."
    if not _inteiro_no_intervalo(config.get("hora", 0), 0, 23):
        return "Agendamento exige 'hora' inteiro de 0 a 23."
    if not _inteiro_no_intervalo(config.get("minuto", 0), 0, 59):
        return "Agendamento exige 'minuto' inteiro de 0 a 59."
    if freq == "semanal" and not _inteiro_no_intervalo(config.get("dia_semana"), 0, 6):
        return "Agendamento semanal exige 'dia_semana' inteiro de 0 (segunda) a 6 (domingo)."
    if freq == "mensal" and not _inteiro_no_intervalo(config.get("dia_mes"), 1, 31):
        return "Agendamento mensal exige 'dia_mes' inteiro de 1 a 31."
    return None


def montar_ferramentas(estado: EstadoCriacao) -> list[StructuredTool]:
    """Cria as ferramentas da IA criadora ligadas a `estado`. Cada uma muta
    `estado.rascunho` (ou `estado.chips`) e devolve um JSON com o resultado."""
    r = estado.rascunho

    def definir_time(nome: str, descricao: str | None = None) -> str:
        """Define o nome e a descrição do time que está sendo criado."""
        r.time_nome = nome
        if descricao is not None:
            r.time_descricao = descricao
        return _ok(f"Time '{nome}' definido.")

    def adicionar_agente(
        nome: str,
        papel: str = "agente",
        agent_md: str | None = None,
        skill_md: str | None = None,
        tools_md: str | None = None,
        soul_md: str | None = None,
        modelo_ia: str | None = None,
    ) -> str:
        """Adiciona um agente ao time. `papel` é 'lider' ou 'agente' (no máximo um
        líder por time). Os quatro markdowns documentam o agente: agent_md (quem
        é), skill_md (habilidades), tools_md (cinto), soul_md (personalidade).
        Devolve o `ref` do agente, usado para o cinto e a cadeia."""
        if papel not in ("lider", "agente"):
            return _erro("O papel precisa ser 'lider' ou 'agente'.")
        if papel == "lider" and r.tem_lider():
            return _erro("Já existe um líder no time; só pode haver um.")
        agente = AgenteRascunho(
            nome=nome,
            papel=papel,
            agent_md=agent_md,
            skill_md=skill_md,
            tools_md=tools_md,
            soul_md=soul_md,
            modelo_ia=modelo_ia,
        )
        r.agentes.append(agente)
        return _ok(f"Agente '{nome}' adicionado.", ref=agente.ref)

    def editar_agente(
        ref: str,
        nome: str | None = None,
        papel: str | None = None,
        agent_md: str | None = None,
        skill_md: str | None = None,
        tools_md: str | None = None,
        soul_md: str | None = None,
        modelo_ia: str | None = None,
    ) -> str:
        """Edita um agente já existente (pelo `ref`). Só os campos informados
        mudam."""
        agente = r.agente_por_ref(ref)
        if agente is None:
            return _erro(f"Não há agente com ref {ref}.")
        if papel is not None:
            if papel not in ("lider", "agente"):
                return _erro("O papel precisa ser 'lider' ou 'agente'.")
            if papel == "lider" and r.tem_lider(exceto_ref=ref):
                return _erro("Já existe outro líder no time.")
            agente.papel = papel
        for campo, valor in {
            "nome": nome,
            "agent_md": agent_md,
            "skill_md": skill_md,
            "tools_md": tools_md,
            "soul_md": soul_md,
            "modelo_ia": modelo_ia,
        }.items():
            if valor is not None:
                setattr(agente, campo, valor)
        return _ok(f"Agente '{agente.nome}' atualizado.")

    def remover_agente(ref: str) -> str:
        """Remove um agente do time (pelo `ref`) e limpa as referências a ele na
        cadeia."""
        agente = r.agente_por_ref(ref)
        if agente is None:
            return _erro(f"Não há agente com ref {ref}.")
        r.agentes.remove(agente)
        # limpa o agente da cadeia, se estiver lá
        if r.automacao and r.automacao.cadeia:
            nos = r.automacao.cadeia.get("nos") or {}
            nos.pop(ref, None)
            for no in nos.values():
                no["saidas"] = [
                    s for s in (no.get("saidas") or []) if s.get("destino") != ref
                ]
            if r.automacao.cadeia.get("inicio") == ref:
                r.automacao.cadeia["inicio"] = None
        return _ok(f"Agente '{agente.nome}' removido.")

    def configurar_instrumento(
        nome: str, tipo: str, configuracao: dict | None = None
    ) -> str:
        """Configura um instrumento para o time. `tipo` precisa ser um dos tipos
        do catálogo (use listar_tipos_instrumento para ver os CAMPOS de cada um).
        Em `configuracao`, passe os campos PÚBLICOS de conexão que você já coletou
        do consultor (ex.: para o WordPress, `site_url` e `usuario`) — não deixe em
        branco um campo que o instrumento precisa para funcionar. NÃO passe os
        campos secretos (senhas, tokens): eles ficam pendentes e o consultor os
        cadastra no cofre depois de aprovar. Devolve o `ref` (para o cinto) e a
        lista de segredos pendentes."""
        if encaixe.obter_tipo(tipo) is None:
            return _erro(
                f"Tipo de instrumento desconhecido: {tipo}. "
                "Use listar_tipos_instrumento para ver os tipos válidos."
            )
        try:
            config_publica, _segredos = encaixe.preparar_config(tipo, configuracao or {})
        except ValueError as e:
            return _erro(f"Configuração inválida: {e}")
        instrumento = InstrumentoRascunho(
            nome=nome,
            tipo=tipo,
            configuracao=config_publica,
            segredos_pendentes=list(encaixe.campos_secretos(tipo)),
        )
        r.instrumentos.append(instrumento)
        return _ok(
            f"Instrumento '{nome}' configurado.",
            ref=instrumento.ref,
            segredos_pendentes=instrumento.segredos_pendentes,
        )

    def encaixar_instrumento(agente_ref: str, instrumento_ref: str) -> str:
        """Pendura um instrumento no cinto de um agente (ambos pelo `ref`)."""
        agente = r.agente_por_ref(agente_ref)
        if agente is None:
            return _erro(f"Não há agente com ref {agente_ref}.")
        if r.instrumento_por_ref(instrumento_ref) is None:
            return _erro(f"Não há instrumento com ref {instrumento_ref}.")
        if instrumento_ref not in agente.cinto:
            agente.cinto.append(instrumento_ref)
        return _ok(f"Instrumento encaixado no cinto de '{agente.nome}'.")

    def montar_cadeia(cadeia: dict) -> str:
        """Define a cadeia (o fluxo) da automação. Formato de grafo:
        {"inicio": "<ref de agente>", "nos": {"<ref>": {"saidas": [{"rotulo":
        "1", "quando": "descrição de quando seguir", "destino": "<ref ou null
        para fim>", "pausa_humano": false}]}}}. Use os `ref`s dos agentes. Marque
        "pausa_humano": true num nó que deve esperar uma aprovação humana."""
        try:
            validar_cadeia(cadeia, {a.ref for a in r.agentes})
        except ValueError as e:
            return _erro(f"Cadeia inválida: {e}")
        if r.automacao is None:
            r.automacao = AutomacaoRascunho()
        r.automacao.cadeia = cadeia
        return _ok("Cadeia montada.")

    def definir_gatilho(
        tipo_gatilho: str, configuracao_gatilho: dict | None = None
    ) -> str:
        """Define o gatilho da automação. Tipos e formato EXATO da config:
        - 'manual': sem config (o consultor dispara quando quiser).
        - 'webhook': sem config (uma chamada externa dispara).
        - 'agendamento': config = {frequencia: 'diaria'|'semanal'|'mensal',
          hora: 0-23, minuto: 0-59, dia_semana: 0-6 (0=segunda, só semanal),
          dia_mes: 1-31 (só mensal), entrada?: texto}. Use INTEIROS para
          hora/minuto/dia_semana/dia_mes — não nomes de dia."""
        config = configuracao_gatilho or {}
        erro = _validar_gatilho(tipo_gatilho, config)
        if erro:
            return _erro(erro)
        if r.automacao is None:
            r.automacao = AutomacaoRascunho()
        r.automacao.gatilho.tipo_gatilho = tipo_gatilho
        if configuracao_gatilho is not None:
            r.automacao.gatilho.configuracao_gatilho = config
        return _ok(f"Gatilho '{tipo_gatilho}' definido.")

    def estimar_custo(
        execucoes_por_mes: int,
        tokens_entrada_por_execucao: int,
        tokens_saida_por_execucao: int,
        modelo: str | None = None,
    ) -> str:
        """Estima o custo do time, em dólares, por execução e por mês. Informe sua
        estimativa de tokens de entrada e de saída por execução (somando a cadeia)
        e quantas execuções por mês. O `modelo` padrão é o do líder."""
        if modelo is None:
            lider = next((a for a in r.agentes if a.papel == "lider"), None)
            modelo = (lider.modelo_ia if lider else None) or MODELO_PADRAO
        por_execucao = precos.custo_usd(
            modelo, tokens_entrada_por_execucao, tokens_saida_por_execucao
        )
        por_mes = por_execucao * execucoes_por_mes
        r.custo_estimado = CustoEstimado(
            por_execucao_usd=round(por_execucao, 4),
            por_mes_usd=round(por_mes, 2),
            detalhe={
                "execucoes_por_mes": execucoes_por_mes,
                "tokens_entrada_por_execucao": tokens_entrada_por_execucao,
                "tokens_saida_por_execucao": tokens_saida_por_execucao,
                "modelo": modelo,
            },
        )
        return _ok(
            "Custo estimado.",
            por_execucao_usd=r.custo_estimado.por_execucao_usd,
            por_mes_usd=r.custo_estimado.por_mes_usd,
        )

    def ver_rascunho() -> str:
        """Mostra o rascunho atual do time inteiro (para a IA se situar)."""
        return json.dumps(r.model_dump(mode="json"), ensure_ascii=False)

    def listar_tipos_instrumento() -> str:
        """Lista os tipos de instrumento disponíveis, com o que cada um faz e —
        importante — os CAMPOS de configuração de cada um (obrigatório/secreto).
        Use isto para saber o que PERGUNTAR ao consultor: os campos públicos você
        coleta e preenche; os secretos ele cadastra no cofre depois de aprovar."""
        return json.dumps(catalogo_de_instrumentos(), ensure_ascii=False)

    def sugerir_proximos_passos(chips: list[str]) -> str:
        """Sugere de 1 a 4 respostas curtas que o consultor pode escolher para
        seguir a conversa (os 'chips' de sugestão). Chame ao fim de cada turno."""
        estado.chips = list(chips)[:4]
        return _ok("Sugestões registradas.")

    funcoes = [
        definir_time,
        adicionar_agente,
        editar_agente,
        remover_agente,
        configurar_instrumento,
        encaixar_instrumento,
        montar_cadeia,
        definir_gatilho,
        estimar_custo,
        ver_rascunho,
        listar_tipos_instrumento,
        sugerir_proximos_passos,
    ]
    return [
        StructuredTool.from_function(func=f, name=f.__name__, description=f.__doc__)
        for f in funcoes
    ]


def ferramenta_por_nome(estado: EstadoCriacao) -> dict[str, StructuredTool]:
    """Conveniência para os testes: as ferramentas indexadas por nome."""
    return {t.name: t for t in montar_ferramentas(estado)}
