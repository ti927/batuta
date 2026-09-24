"""Instrumento `quadro` — o agente lê e grava num quadro do Cérebro da organização.

Um instrumento por quadro e por acesso: é isso que torna o compartilhamento entre times
EXPLÍCITO. O time do RH só enxerga o quadro de admissões se tiver um instrumento
apontando para ele, visível no cinto como qualquer outro.

O instrumento se abre em várias ferramentas (como o conector):

| ação               | acesso         | o que faz                                               |
|--------------------|----------------|---------------------------------------------------------|
| consultar          | ler            | linhas com filtro, ordem, "só a mais recente de"        |
| totais             | ler            | contar/somar/média/mínimo/máximo, calculados pelo banco |
| ja_existe          | ler            | quais destes valores já estão gravados                  |
| acrescentar        | ler_e_escrever | linhas novas                                            |
| gravar_pela_chave  | ler_e_escrever | cria ou substitui pela chave do quadro                  |
| atualizar          | ler_e_escrever | muda colunas das linhas achadas por filtro              |

**A ferramenta se descreve sozinha:** as colunas, os tipos, as opções e a descrição do
quadro entram na descrição que o modelo vê. O markdown do agente não precisa (e não
deve) ensinar formato de dado.

Toda regra (tipos, tudo-ou-nada, chave, histórico) mora em `quadros.servico`; aqui só
se traduz a chamada da IA e o resultado. Uma recusa volta como DADO (`ok: false` com o
motivo por linha) — a borda (`agente._com_rastro_de_resposta`) já registra isso no que
aconteceu na execução, então "o agente disse que gravou" nunca vira prova.

Segurança: a organização vem do TIME DONO DO INSTRUMENTO (lido do banco a cada
chamada), nunca da configuração. Um instrumento que aponta para um quadro de outra
organização simplesmente não acha o quadro.
"""

import json
import re
import unicodedata
import uuid
from contextlib import contextmanager
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from modelos import Agente, Execucao, Time
from quadros import servico as qs
from quadros.filtros import OPERADORES
from quadros.servico import Autor, ErroQuadro
from quadros.tipos import TIPOS
from sessao import CriadorDeSessao

# Linhas mostradas na descrição da ferramenta? Não: a descrição traz só a ESTRUTURA do
# quadro (colunas, tipos, chave) — dado vai por consulta, para não pesar em todo turno.


@contextmanager
def _sessao():
    """Sessão própria da ferramenta (o instrumento não recebe a da execução, como o
    `agendar_automacao`). Isolada numa função para os testes poderem trocá-la."""
    s = CriadorDeSessao()
    try:
        yield s
    finally:
        s.close()


def _org_do_instrumento(sessao, instrumento_time_id) -> uuid.UUID:
    time = sessao.get(Time, instrumento_time_id)
    if time is None:
        raise ErroQuadro("O time deste instrumento não existe mais.")
    return time.organizacao_id


def _slug(texto: str, n: int) -> str:
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_")[:n] or "quadro"


def _json_se_texto(v):
    """A IA às vezes manda a lista/objeto como TEXTO JSON — aceita as duas formas."""
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in ("[", "{"):
            try:
                return json.loads(s)
            except ValueError:
                pass
    return v


class _Base(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _aceita_json_em_texto(cls, v):
        return _json_se_texto(v)


_FILTROS_DESC = (
    "Filtros (todos valem juntos): lista de {\"coluna\": <nome>, \"operador\": <op>, "
    "\"valor\": <valor>}. Operadores: " + ", ".join(OPERADORES) + ". Para `em`, "
    "`valor` é uma lista; `vazio`/`nao_vazio` não usam valor. Também dá para filtrar "
    "por _criado_em, _origem e _execucao_id."
)


class ArgsConsultar(_Base):
    filtros: list[dict] | None = Field(default=None, description=_FILTROS_DESC)
    ordem: list[str] | None = Field(
        default=None,
        description="Colunas para ordenar; \"-\" na frente = decrescente (ex.: [\"-Data\"]). "
        "Sem ordem: mais recentes primeiro.",
    )
    colunas: list[str] | None = Field(
        default=None, description="Só estas colunas na resposta (economiza). Sem = todas."
    )
    limite: int | None = Field(default=None, description="Quantas linhas devolver (padrão 50).")
    deslocamento: int = Field(
        default=0, description="Pular estas linhas (use o `proximo` da resposta anterior)."
    )
    so_o_mais_recente_de: str | None = Field(
        default=None,
        description="Coluna de data/número: devolve só as linhas com o MAIOR valor dela entre "
        "as que casam com os filtros (ex.: \"Data\" = só a rodada mais recente).",
    )


class ArgsTotais(_Base):
    metricas: list[dict] | None = Field(
        default=None,
        description="Lista de {\"funcao\": contar|soma|media|minimo|maximo, \"coluna\": <nome>}. "
        "Sem = contar linhas. Os números são calculados pelo sistema — use-os como vêm.",
    )
    agrupar_por: list[str] | None = Field(
        default=None, description="Até 3 colunas para agrupar (ex.: [\"Tema\"])."
    )
    filtros: list[dict] | None = Field(default=None, description=_FILTROS_DESC)
    so_o_mais_recente_de: str | None = Field(
        default=None, description="Como na consulta: só as linhas com o maior valor desta coluna."
    )


class ArgsJaExiste(_Base):
    coluna: str = Field(description="A coluna a conferir.")
    valores: list[Any] = Field(
        description="Os valores candidatos. A resposta diz quais JÁ existem e quais FALTAM — "
        "use isto em vez de ler o quadro inteiro para descobrir o que falta."
    )


class ArgsLinhas(_Base):
    linhas: list[dict] = Field(
        description="Lista de linhas; cada linha é {\"<nome da coluna>\": valor}. Datas como "
        "2026-09-21 ou 21/09/2026; números sem separador de milhar. Se QUALQUER linha tiver "
        "problema, nada é gravado e a resposta diz qual linha e coluna corrigir."
    )


class ArgsAtualizar(_Base):
    filtros: list[dict] = Field(description="Quais linhas mudar. " + _FILTROS_DESC)
    campos: dict = Field(
        description="{\"<coluna>\": novo valor}. Valor vazio (\"\") apaga o campo."
    )


class ConfigQuadro(BaseModel):
    quadro: str = Field(
        description="O quadro da organização que este instrumento usa (nome ou id).",
    )
    acesso: Literal["ler", "ler_e_escrever"] = Field(
        default="ler",
        description="“ler”: o agente só consulta. “ler_e_escrever”: também grava e muda linhas.",
    )


class ArgsQuadro(BaseModel):
    pass


def _descricao_do_quadro(desc: dict) -> str:
    """A estrutura do quadro em texto curto, para a descrição da ferramenta."""
    cols = []
    for c in desc["colunas"]:
        extra = []
        if c.get("obrigatoria"):
            extra.append("obrigatória")
        if c.get("opcoes"):
            extra.append("opções: " + " | ".join(c["opcoes"]))
        if c.get("descricao"):
            extra.append(c["descricao"])
        cols.append(
            f"- {c['nome']} ({TIPOS.get(c['tipo'], c['tipo']).lower()}"
            + (f"; {'; '.join(extra)}" if extra else "") + ")"
        )
    chave = (
        "Cada linha é identificada por: " + ", ".join(desc["chave"]) + "."
        if desc["chave"]
        else "O quadro não tem chave: cada gravação acrescenta linhas."
    )
    return (
        f"Quadro “{desc['nome']}”"
        + (f": {desc['descricao']}" if desc.get("descricao") else "")
        + f"\nColunas:\n" + "\n".join(cols) + f"\n{chave}"
    )


def _resposta(fn) -> str:
    """Roda a chamada ao serviço e devolve o JSON para a IA; recusa vira `ok: false`
    com o motivo (e as linhas problemáticas)."""
    try:
        return json.dumps({"ok": True, **fn()}, ensure_ascii=False, default=str)
    except ErroQuadro as e:
        corpo = {"ok": False, "erro": e.mensagem}
        if e.detalhes:
            corpo["detalhes"] = e.detalhes
        return json.dumps(corpo, ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001 — falha do banco: honesta, registrada, nunca muda
        from observabilidade.escritor import registrar_evento

        registrar_evento(
            categoria="instrumento", acao="quadro.falhou", nivel="error",
            resultado="falha", erro=e, recurso_tipo="quadro",
        )
        return json.dumps(
            {
                "ok": False,
                "erro": "O quadro não respondeu agora (falha do sistema, não dos seus dados). "
                "Nada foi gravado. Tente de novo; se repetir, siga sem o quadro e diga isso "
                "na sua resposta — não invente o dado.",
            },
            ensure_ascii=False,
        )


def _compacto(resultado: dict) -> dict:
    """A consulta em forma de TABELA (cabeçalho + linhas como listas) — bem mais barata
    em tokens que um objeto por linha repetindo os nomes das colunas."""
    colunas = resultado["colunas"]
    return {
        "quadro": resultado["quadro"],
        "total": resultado["total"],
        "devolvidas": resultado["devolvidas"],
        "proximo": resultado["proximo"],
        "colunas": colunas,
        "linhas": [[ln["valores"].get(c) for c in colunas] for ln in resultado["linhas"]],
        **({"aviso": resultado["aviso"]} if resultado.get("aviso") else {}),
    }


def _autor(sessao) -> Autor:
    """Quem está gravando: o agente e a execução do contexto de quem-fez (fixados pela
    borda e pelo `executar_agente`). Id que não existe (ou falta) vira vazio — o carimbo
    nunca derruba a gravação."""
    from observabilidade.contexto import contexto_atual

    ctx = contexto_atual()

    def _existe(modelo, valor):
        try:
            uid = uuid.UUID(str(valor))
        except (ValueError, TypeError):
            return None
        return uid if sessao.get(modelo, uid) is not None else None

    return Autor(
        origem="agente",
        agente_id=_existe(Agente, ctx.get("agente_id")) if ctx.get("agente_id") else None,
        execucao_id=_existe(Execucao, ctx.get("execucao_id")) if ctx.get("execucao_id") else None,
    )


def _atividade(texto: str) -> None:
    from orquestracao import atividade

    atividade.registrar(texto)


class InstrumentoQuadro(TipoInstrumento):
    tipo = "quadro"
    categoria = "Cérebro da organização"
    nome_exibicao = "Quadro"
    descricao = (
        "Lê (e, se permitido, grava) num quadro do cérebro da organização — o lugar onde "
        "os agentes deixam informação para outros agentes, inclusive de outros times."
    )
    Config = ConfigQuadro
    Args = ArgsQuadro
    # Gravar num quadro NÃO é irreversível: há histórico e dá para desfazer (apagar o
    # que uma execução gravou). Não pede aprovação.
    acao_irreversivel = False
    # Fora do dropdown da tela até a Entrega 4 (o formulário cru pediria o nome do quadro
    # num campo de texto e, ao editar, mostraria o id). A IA criadora e o MCP já criam.
    oculto_na_tela = True

    def resolver_config(self, sessao, organizacao_id, config_publica: dict) -> dict:
        """Guarda o ID do quadro (renomear o quadro não pode quebrar o instrumento) e
        recusa na hora um quadro que não existe nesta organização."""
        try:
            q = qs.obter_quadro(sessao, organizacao_id, config_publica.get("quadro"))
        except ErroQuadro as e:
            raise ValueError(e.mensagem) from None
        return {**config_publica, "quadro": str(q.id)}

    def executar(self, config: ConfigQuadro, args: ArgsQuadro) -> dict:
        """Acionamento isolado (o "Acionar" da tela): diz o que o instrumento oferece.
        As ações de verdade são as ferramentas de `expandir_ferramentas_da_instancia`."""
        acoes = ["consultar", "totais", "ja_existe"]
        if config.acesso == "ler_e_escrever":
            acoes += ["acrescentar", "gravar_pela_chave", "atualizar"]
        return {"ok": True, "quadro": config.quadro, "acesso": config.acesso, "acoes": acoes}

    def expandir_ferramentas(self, config: ConfigQuadro) -> list:
        # Sem a instância não há como saber a organização — e sem ela nenhum quadro é
        # alcançável. Nunca deveria acontecer: o motor chama a versão com instância.
        raise FalhaInstrumento(
            "o quadro precisa saber de qual time é o instrumento.", retentavel=False
        )

    def expandir_ferramentas_da_instancia(self, instrumento, config: ConfigQuadro) -> list:
        time_id = instrumento.time_id
        with _sessao() as s:
            try:
                org = _org_do_instrumento(s, time_id)
                q = qs.obter_quadro(s, org, config.quadro)
                desc = qs.descrever_quadro(q)
            except ErroQuadro as e:
                # Levanta: o motor tira o instrumento do cinto COM aviso (evento no banco
                # de logs + recado ao agente) — `agente._cinto_sem`. Nunca some calado.
                raise FalhaInstrumento(e.mensagem, retentavel=False) from None
        quadro_id = str(q.id)
        estrutura = _descricao_do_quadro(desc)
        sufixo = f"{_slug(desc['nome'], 28)}_{instrumento.id.hex[:4]}"
        nome_q = desc["nome"]

        def em_sessao(fn, *, grava: bool):
            def rodar():
                with _sessao() as s:
                    org_ = _org_do_instrumento(s, time_id)
                    r = fn(s, org_)
                    if grava and not r.get("simulado"):
                        s.commit()
                    return r
            return _resposta(rodar)

        def consultar(**kw) -> str:
            a = ArgsConsultar.model_validate(kw)
            _atividade(f"Consultando o quadro “{nome_q}”…")
            return em_sessao(
                lambda s, org: _compacto(qs.consultar(
                    s, org, quadro_id, filtros=a.filtros, ordem=a.ordem, colunas=a.colunas,
                    limite=a.limite, deslocamento=a.deslocamento,
                    so_o_mais_recente_de=a.so_o_mais_recente_de,
                )),
                grava=False,
            )

        def totais(**kw) -> str:
            a = ArgsTotais.model_validate(kw)
            _atividade(f"Somando no quadro “{nome_q}”…")
            return em_sessao(
                lambda s, org: qs.totais(
                    s, org, quadro_id, metricas=a.metricas, agrupar_por=a.agrupar_por,
                    filtros=a.filtros, so_o_mais_recente_de=a.so_o_mais_recente_de,
                ),
                grava=False,
            )

        def ja_existe(**kw) -> str:
            a = ArgsJaExiste.model_validate(kw)
            _atividade(f"Conferindo o quadro “{nome_q}”…")
            return em_sessao(
                lambda s, org: qs.ja_existe(s, org, quadro_id, coluna=a.coluna, valores=a.valores),
                grava=False,
            )

        def gravar(modo: str):
            def _gravar(**kw) -> str:
                a = ArgsLinhas.model_validate(kw)
                _atividade(f"Gravando {len(a.linhas)} linha(s) no quadro “{nome_q}”…")
                return em_sessao(
                    lambda s, org: qs.gravar_linhas(
                        s, org, quadro_id, a.linhas, autor=_autor(s), modo=modo,
                    ),
                    grava=True,
                )
            return _gravar

        def atualizar(**kw) -> str:
            a = ArgsAtualizar.model_validate(kw)
            _atividade(f"Atualizando o quadro “{nome_q}”…")
            return em_sessao(
                lambda s, org: qs.editar_linhas(
                    s, org, quadro_id, campos=a.campos, filtros=a.filtros, autor=_autor(s),
                ),
                grava=True,
            )

        def ferramenta(nome, func, args, o_que):
            return StructuredTool.from_function(
                func=func,
                name=f"{nome}_{sufixo}"[:64],
                description=f"{o_que}\n\n{estrutura}",
                args_schema=args,
                metadata={"irreversivel": False},
            )

        ferramentas = [
            ferramenta(
                "consultar", consultar, ArgsConsultar,
                "Consulta linhas deste quadro. A resposta traz o TOTAL de linhas que casam e, "
                "se vier só parte, o `proximo` deslocamento para continuar.",
            ),
            ferramenta(
                "totais", totais, ArgsTotais,
                "Conta, soma, tira média, mínimo ou máximo neste quadro (calculado pelo sistema; "
                "não some de cabeça).",
            ),
            ferramenta(
                "ja_existe", ja_existe, ArgsJaExiste,
                "Confere quais valores de uma coluna já estão gravados neste quadro.",
            ),
        ]
        if config.acesso == "ler_e_escrever":
            ferramentas += [
                ferramenta(
                    "acrescentar", gravar("acrescentar"), ArgsLinhas,
                    "Acrescenta linhas novas neste quadro. Tudo ou nada: com qualquer problema, "
                    "nada é gravado e a resposta diz o que corrigir."
                    + (" Linha cuja identificação já existe é recusada — use gravar_pela_chave "
                       "para substituir." if desc["chave"] else ""),
                ),
                ferramenta(
                    "atualizar", atualizar, ArgsAtualizar,
                    "Muda colunas das linhas deste quadro achadas pelos filtros.",
                ),
            ]
            if desc["chave"]:
                ferramentas.append(
                    ferramenta(
                        "gravar_pela_chave", gravar("pela_chave"), ArgsLinhas,
                        "Cria a linha se ela ainda não existe; se existe (mesma identificação), "
                        "muda só as colunas informadas. Use para manter UMA linha por "
                        + ", ".join(desc["chave"]) + ".",
                    )
                )
        return ferramentas


registrar(InstrumentoQuadro())
