"""O serviço ÚNICO dos quadros. Agente, tela, IA criadora e MCP passam por aqui.

Regras que valem para toda operação:

- **Isolamento:** toda função recebe `organizacao_id` e só enxerga quadros dela.
- **Tudo ou nada:** uma gravação com qualquer recusa não grava NADA (savepoint). O agente
  nunca precisa adivinhar o que entrou pela metade.
- **Simular:** toda escrita aceita `simular=True` — roda de verdade dentro de um savepoint,
  devolve o que aconteceria e desfaz. Um caminho de código só, então a simulação não
  mente.
- **Carimbo:** quem grava é dito EXPLICITAMENTE (`Autor`) por quem chama — o serviço não
  adivinha contexto. É a porta (ferramenta do agente, rota, MCP) que sabe quem está
  agindo.
- **Não comita:** quem chama controla a transação (mesmo molde de `memoria_agente`).

Toda recusa levanta `ErroQuadro` com a frase para a pessoa e, quando for por linha, a
lista `detalhes` ({linha, coluna, motivo}).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import false, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modelos import Quadro, QuadroAlteracao, QuadroLinha
from quadros import filtros as filtros_mod
from quadros import limites as limites_mod
from quadros import tipos
from quadros.filtros import FiltroInvalido, resolver_coluna
from quadros.tipos import ValorInvalido

ORIGENS = filtros_mod.ORIGENS
MAX_NOME_QUADRO = 120
MAX_NOME_COLUNA = 80
MAX_OPCOES = 100
LIMITE_CONSULTA_PADRAO = 50
FUNCOES_TOTAIS = ("contar", "soma", "media", "minimo", "maximo")
_ROTULO_FUNCAO = {"soma": "soma", "media": "média", "minimo": "mínimo", "maximo": "máximo"}
_APELIDOS_FUNCAO = {
    "contar": "contar", "contagem": "contar", "count": "contar", "quantidade": "contar",
    "soma": "soma", "somar": "soma", "sum": "soma", "total": "soma",
    "media": "media", "média": "media", "avg": "media",
    "minimo": "minimo", "mínimo": "minimo", "min": "minimo", "menor": "minimo",
    "maximo": "maximo", "máximo": "maximo", "max": "maximo", "maior": "maximo",
}


class ErroQuadro(ValueError):
    """Recusa com motivo em português. `detalhes` = [{linha, coluna, motivo}] quando a
    recusa é por linha (a gravação inteira foi recusada por causa delas)."""

    def __init__(self, mensagem: str, detalhes: list[dict] | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes or []


@dataclass(frozen=True)
class Autor:
    """Quem está gravando. É o carimbo — não editável depois."""

    origem: str
    agente_id: uuid.UUID | None = None
    execucao_id: uuid.UUID | None = None
    usuario_id: uuid.UUID | None = None

    def __post_init__(self):
        if self.origem not in ORIGENS:
            raise ValueError(f"origem inválida: {self.origem}")


class _Simulado(Exception):
    """Sinal interno: desfaz o savepoint e devolve o relatório."""

    def __init__(self, resultado: dict):
        self.resultado = resultado


def _em_savepoint(sessao: Session, simular: bool, trabalho) -> dict:
    """Roda `trabalho()` num savepoint. Recusa → desfaz e propaga. Simulação → desfaz e
    devolve o relatório com `simulado: True`."""
    try:
        with sessao.begin_nested():
            resultado = trabalho()
            if simular:
                raise _Simulado(resultado)
    except _Simulado as s:
        return {**s.resultado, "simulado": True}
    return {**resultado, "simulado": False}


# ───────────────────────────── quadros ─────────────────────────────


def _uuid(valor) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


def listar_quadros(sessao: Session, organizacao_id: uuid.UUID) -> list[Quadro]:
    return list(
        sessao.scalars(
            select(Quadro)
            .where(Quadro.organizacao_id == organizacao_id)
            .order_by(func.lower(Quadro.nome))
        ).all()
    )


def obter_quadro(sessao: Session, organizacao_id: uuid.UUID, ref) -> Quadro:
    """O quadro pelo id ou pelo nome (sem diferenciar maiúscula), só desta organização."""
    q = None
    qid = _uuid(ref)
    if qid is not None:
        q = sessao.scalar(
            select(Quadro).where(Quadro.id == qid, Quadro.organizacao_id == organizacao_id)
        )
    if q is None and isinstance(ref, str) and ref.strip():
        q = sessao.scalar(
            select(Quadro).where(
                Quadro.organizacao_id == organizacao_id,
                func.lower(Quadro.nome) == ref.strip().lower(),
            )
        )
    if q is None:
        nomes = [x.nome for x in listar_quadros(sessao, organizacao_id)]
        dica = f" Os quadros desta organização são: {', '.join(nomes)}." if nomes else (
            " Esta organização ainda não tem nenhum quadro."
        )
        raise ErroQuadro(f"Não achei o quadro “{ref}”.{dica}")
    return q


def contar_linhas(sessao: Session, quadro_id: uuid.UUID) -> int:
    return sessao.scalar(
        select(func.count()).select_from(QuadroLinha).where(QuadroLinha.quadro_id == quadro_id)
    ) or 0


def _validar_nome_quadro(sessao, organizacao_id, nome, ignorar_id=None) -> str:
    nome = (nome or "").strip()
    if not nome:
        raise ErroQuadro("O quadro precisa de um nome.")
    if len(nome) > MAX_NOME_QUADRO:
        raise ErroQuadro(f"O nome do quadro aceita até {MAX_NOME_QUADRO} caracteres.")
    cond = [Quadro.organizacao_id == organizacao_id, func.lower(Quadro.nome) == nome.lower()]
    if ignorar_id is not None:
        cond.append(Quadro.id != ignorar_id)
    if sessao.scalar(select(Quadro.id).where(*cond)) is not None:
        raise ErroQuadro(f"Já existe um quadro chamado “{nome}” nesta organização.")
    return nome


def _opcoes_validas(opcoes, nome_coluna: str) -> list[str]:
    if not isinstance(opcoes, list) or not opcoes:
        raise ErroQuadro(f"A coluna “{nome_coluna}” é de opção e precisa da lista de opções.")
    limpas: list[str] = []
    vistas: set[str] = set()
    for o in opcoes:
        s = str(o).strip() if o is not None else ""
        if not s:
            continue
        chave = tipos.sem_acento(s.lower())
        if chave in vistas:
            raise ErroQuadro(f"A opção “{s}” aparece duas vezes na coluna “{nome_coluna}”.")
        vistas.add(chave)
        limpas.append(s[:MAX_NOME_COLUNA])
    if not limpas:
        raise ErroQuadro(f"A coluna “{nome_coluna}” é de opção e precisa da lista de opções.")
    if len(limpas) > MAX_OPCOES:
        raise ErroQuadro(f"Uma coluna de opção aceita até {MAX_OPCOES} opções.")
    return limpas


def _nova_coluna(dado, existentes: list[dict]) -> dict:
    if not isinstance(dado, dict):
        raise ErroQuadro("Cada coluna é um objeto com pelo menos “nome” e “tipo”.")
    nome = str(dado.get("nome") or "").strip()
    if not nome:
        raise ErroQuadro("Toda coluna precisa de um nome.")
    if len(nome) > MAX_NOME_COLUNA:
        raise ErroQuadro(f"O nome de coluna aceita até {MAX_NOME_COLUNA} caracteres (“{nome[:30]}…”).")
    if nome.startswith("_"):
        raise ErroQuadro(f"O nome de coluna não pode começar com “_” (“{nome}”): é reservado ao carimbo.")
    alvo = tipos.sem_acento(nome.lower())
    if any(tipos.sem_acento(c["nome"].lower()) == alvo for c in existentes):
        raise ErroQuadro(f"Já existe uma coluna chamada “{nome}”.")
    tipo = str(dado.get("tipo") or "").strip().lower()
    if tipo not in tipos.TIPOS:
        raise ErroQuadro(
            f"A coluna “{nome}” tem o tipo “{dado.get('tipo')}”, que não existe. "
            f"Os tipos são: {', '.join(tipos.TIPOS)}."
        )
    coluna = {
        "id": tipos.id_de_coluna(nome, {c["id"] for c in existentes}),
        "nome": nome,
        "tipo": tipo,
        "obrigatoria": bool(dado.get("obrigatoria", False)),
        "descricao": (str(dado.get("descricao")).strip() if dado.get("descricao") else None),
    }
    if tipo == "opcao":
        coluna["opcoes"] = _opcoes_validas(dado.get("opcoes"), nome)
    return coluna


def _resolver_chave(quadro_colunas: list[dict], refs) -> list[str]:
    if refs in (None, "", []):
        return []
    if isinstance(refs, str):
        refs = [refs]
    fake = Quadro(nome="", colunas=quadro_colunas)
    ids: list[str] = []
    for r in refs:
        col = resolver_coluna(fake, r)
        if col is None:
            raise ErroQuadro(f"A chave cita a coluna “{r}”, que não existe no quadro.")
        if col["tipo"] not in tipos.TIPOS_DE_CHAVE:
            raise ErroQuadro(
                f"A coluna “{col['nome']}” é de {tipos.TIPOS[col['tipo']].lower()} e não pode "
                "fazer parte da chave."
            )
        if col["id"] not in ids:
            ids.append(col["id"])
    return ids


def _validar_limites(ajustes) -> dict:
    if ajustes in (None, {}):
        return {}
    if not isinstance(ajustes, dict):
        raise ErroQuadro("Os limites são um objeto {nome_do_limite: número}.")
    limpos = {}
    for chave, valor in ajustes.items():
        motivo = limites_mod.validar_ajuste(chave, valor)
        if motivo:
            raise ErroQuadro(f"Limite recusado: {motivo}.")
        if valor is not None:
            limpos[chave] = valor
    return limpos


def criar_quadro(
    sessao: Session,
    organizacao_id: uuid.UUID,
    *,
    nome: str,
    colunas: list[dict],
    chave=None,
    descricao: str | None = None,
    limites: dict | None = None,
    criado_por_id: uuid.UUID | None = None,
    simular: bool = False,
) -> dict:
    """Cria um quadro. `chave` = nomes das colunas que identificam uma linha (vazia =
    registro que só acumula). Colunas da chave ficam obrigatórias."""

    def trabalho():
        nome_ok = _validar_nome_quadro(sessao, organizacao_id, nome)
        if not isinstance(colunas, list) or not colunas:
            raise ErroQuadro("O quadro precisa de pelo menos uma coluna.")
        ajustes = _validar_limites(limites)
        teto_colunas = int(ajustes.get("colunas") or limites_mod.LIMITES["colunas"][0])
        if len(colunas) > teto_colunas:
            raise ErroQuadro(
                f"São {len(colunas)} colunas e o quadro aceita até {teto_colunas}. "
                f"{limites_mod.ONDE_MUDAR}"
            )
        cols: list[dict] = []
        for dado in colunas:
            cols.append(_nova_coluna(dado, cols))
        ids_chave = _resolver_chave(cols, chave)
        for c in cols:
            if c["id"] in ids_chave:
                c["obrigatoria"] = True
        q = Quadro(
            organizacao_id=organizacao_id,
            nome=nome_ok,
            descricao=(descricao or "").strip() or None,
            colunas=cols,
            chave=ids_chave,
            limites=ajustes,
            criado_por_id=criado_por_id,
        )
        sessao.add(q)
        sessao.flush()
        return {"quadro_id": str(q.id), "quadro": descrever_quadro(q)}

    return _em_savepoint(sessao, simular, trabalho)


def descrever_quadro(quadro: Quadro, total_linhas: int | None = None) -> dict:
    """O quadro como a tela e as IAs leem: colunas por NOME, tipos por extenso, chave,
    limites efetivos (com padrão e teto)."""
    chave = set(quadro.chave or [])
    return {
        "id": str(quadro.id) if quadro.id else None,
        "nome": quadro.nome,
        "descricao": quadro.descricao,
        "colunas": [
            {
                "nome": c["nome"],
                "id": c["id"],
                "tipo": c["tipo"],
                "tipo_rotulo": tipos.TIPOS.get(c["tipo"], c["tipo"]),
                "obrigatoria": bool(c.get("obrigatoria")),
                "faz_parte_da_chave": c["id"] in chave,
                **({"opcoes": c["opcoes"]} if c.get("opcoes") else {}),
                **({"descricao": c["descricao"]} if c.get("descricao") else {}),
            }
            for c in quadro.colunas or []
        ],
        "chave": [c["nome"] for c in quadro.colunas or [] if c["id"] in chave],
        "limites": limites_mod.descrever(quadro),
        **({"total_linhas": total_linhas} if total_linhas is not None else {}),
    }


def _coluna_ou_erro(quadro: Quadro, cols: list[dict], ref) -> dict:
    col = resolver_coluna(Quadro(nome=quadro.nome, colunas=cols), ref)
    if col is None:
        nomes = ", ".join(f"“{c['nome']}”" for c in cols)
        raise ErroQuadro(f"O quadro não tem a coluna “{ref}”. As colunas são: {nomes}.")
    return col


def alterar_quadro(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    operacoes: list[dict],
    *,
    simular: bool = False,
) -> dict:
    """Aplica uma lista de mudanças de estrutura, na ordem, tudo ou nada.

    Ações: renomear{nome} · descrever{descricao} · adicionar_coluna{coluna} ·
    renomear_coluna{coluna,nome} · descrever_coluna{coluna,descricao} ·
    trocar_tipo{coluna,tipo,opcoes?,esvaziar_invalidos?} · mudar_opcoes{coluna,opcoes,
    esvaziar_invalidos?} · obrigatoria{coluna,valor} · remover_coluna{coluna} ·
    mudar_chave{colunas} · ajustar_limite{limite,valor(None=padrão)}.

    Trocar tipo ou opções CONVERTE os valores que já existem; valor que não se converte
    recusa a mudança (com a lista do que falhou), a menos que `esvaziar_invalidos`."""

    def trabalho():
        q = obter_quadro(sessao, organizacao_id, ref)
        if not isinstance(operacoes, list) or not operacoes:
            raise ErroQuadro("Diga ao menos uma mudança (lista de operações).")
        cols = [dict(c) for c in q.colunas or []]
        chave = list(q.chave or [])
        ajustes = dict(q.limites or {})
        feitas: list[str] = []
        linhas = None  # carregadas sob demanda
        mudaram_linhas: set[uuid.UUID] = set()

        def carregar_linhas():
            nonlocal linhas
            if linhas is None:
                linhas = list(
                    sessao.scalars(
                        select(QuadroLinha).where(QuadroLinha.quadro_id == q.id).with_for_update()
                    ).all()
                )
                for ln in linhas:
                    ln.valores = dict(ln.valores or {})
            return linhas

        tam = int(ajustes.get("tamanho_texto_longo") or limites_mod.LIMITES["tamanho_texto_longo"][0])

        def converter(col_nova: dict, esvaziar: bool) -> int:
            problemas, n = [], 0
            for ln in carregar_linhas():
                if col_nova["id"] not in ln.valores or ln.valores[col_nova["id"]] is None:
                    continue
                antigo = ln.valores[col_nova["id"]]
                try:
                    novo = tipos.normalizar(col_nova, antigo, tamanho_texto_longo=tam)
                except ValorInvalido as e:
                    if esvaziar:
                        novo = None
                    else:
                        problemas.append({"linha_id": str(ln.id), "coluna": col_nova["nome"], "valor": antigo, "motivo": str(e)})
                        continue
                if novo != antigo:
                    ln.valores = {**ln.valores, col_nova["id"]: novo}
                    mudaram_linhas.add(ln.id)
                    n += 1
            if problemas:
                raise ErroQuadro(
                    f"{len(problemas)} valor(es) da coluna “{col_nova['nome']}” não se "
                    "convertem. Corrija-os ou peça para esvaziar os que não servem "
                    "(esvaziar_invalidos).",
                    problemas[:50],
                )
            return n

        for op in operacoes:
            if not isinstance(op, dict):
                raise ErroQuadro("Cada operação é um objeto com “acao”.")
            acao = str(op.get("acao") or "").strip().lower()
            if acao == "renomear":
                q.nome = _validar_nome_quadro(sessao, organizacao_id, op.get("nome"), ignorar_id=q.id)
                feitas.append(f"quadro renomeado para “{q.nome}”")
            elif acao == "descrever":
                q.descricao = (str(op.get("descricao") or "")).strip() or None
                feitas.append("descrição do quadro atualizada")
            elif acao == "adicionar_coluna":
                teto = int(ajustes.get("colunas") or limites_mod.LIMITES["colunas"][0])
                if len(cols) >= teto:
                    raise ErroQuadro(f"O quadro já tem {len(cols)} colunas, o limite. {limites_mod.ONDE_MUDAR}")
                nova = _nova_coluna(op.get("coluna"), cols)
                if nova["obrigatoria"] and carregar_linhas():
                    raise ErroQuadro(
                        f"A coluna “{nova['nome']}” não pode nascer obrigatória: o quadro já "
                        "tem linhas, e elas ficariam sem valor. Crie como opcional, preencha "
                        "e depois torne obrigatória."
                    )
                cols.append(nova)
                feitas.append(f"coluna “{nova['nome']}” adicionada")
            elif acao == "renomear_coluna":
                col = _coluna_ou_erro(q, cols, op.get("coluna"))
                novo = str(op.get("nome") or "").strip()
                if not novo or novo.startswith("_") or len(novo) > MAX_NOME_COLUNA:
                    raise ErroQuadro("Nome de coluna inválido (vazio, começa com “_” ou longo demais).")
                alvo = tipos.sem_acento(novo.lower())
                if any(c["id"] != col["id"] and tipos.sem_acento(c["nome"].lower()) == alvo for c in cols):
                    raise ErroQuadro(f"Já existe uma coluna chamada “{novo}”.")
                antigo = col["nome"]
                col["nome"] = novo
                feitas.append(f"coluna “{antigo}” renomeada para “{novo}”")
            elif acao == "descrever_coluna":
                col = _coluna_ou_erro(q, cols, op.get("coluna"))
                col["descricao"] = (str(op.get("descricao") or "")).strip() or None
                feitas.append(f"descrição da coluna “{col['nome']}” atualizada")
            elif acao in ("trocar_tipo", "mudar_opcoes"):
                col = _coluna_ou_erro(q, cols, op.get("coluna"))
                tipo = str(op.get("tipo") or col["tipo"]).strip().lower() if acao == "trocar_tipo" else col["tipo"]
                if tipo not in tipos.TIPOS:
                    raise ErroQuadro(f"O tipo “{op.get('tipo')}” não existe. Os tipos são: {', '.join(tipos.TIPOS)}.")
                if col["id"] in chave and tipo not in tipos.TIPOS_DE_CHAVE:
                    raise ErroQuadro(f"A coluna “{col['nome']}” faz parte da chave e não pode virar {tipos.TIPOS[tipo].lower()}.")
                nova = {**col, "tipo": tipo}
                if tipo == "opcao":
                    nova["opcoes"] = _opcoes_validas(op.get("opcoes") or col.get("opcoes"), col["nome"])
                else:
                    nova.pop("opcoes", None)
                n = converter(nova, bool(op.get("esvaziar_invalidos")))
                col.clear()
                col.update(nova)
                feitas.append(
                    f"coluna “{col['nome']}” agora é {tipos.TIPOS[tipo].lower()}"
                    + (f" ({n} valor(es) convertido(s))" if n else "")
                )
            elif acao == "obrigatoria":
                col = _coluna_ou_erro(q, cols, op.get("coluna"))
                valor = bool(op.get("valor", True))
                if not valor and col["id"] in chave:
                    raise ErroQuadro(f"A coluna “{col['nome']}” faz parte da chave e precisa continuar obrigatória.")
                if valor:
                    vazias = sum(1 for ln in carregar_linhas() if ln.valores.get(col["id"]) is None)
                    if vazias:
                        raise ErroQuadro(
                            f"{vazias} linha(s) estão com “{col['nome']}” vazia. Preencha antes "
                            "de tornar a coluna obrigatória."
                        )
                col["obrigatoria"] = valor
                feitas.append(f"coluna “{col['nome']}” {'obrigatória' if valor else 'opcional'}")
            elif acao == "remover_coluna":
                col = _coluna_ou_erro(q, cols, op.get("coluna"))
                if col["id"] in chave:
                    raise ErroQuadro(f"A coluna “{col['nome']}” faz parte da chave. Mude a chave antes de removê-la.")
                if len(cols) == 1:
                    raise ErroQuadro("O quadro precisa de pelo menos uma coluna.")
                for ln in carregar_linhas():
                    if col["id"] in ln.valores:
                        ln.valores = {k: v for k, v in ln.valores.items() if k != col["id"]}
                        mudaram_linhas.add(ln.id)
                cols = [c for c in cols if c["id"] != col["id"]]
                feitas.append(f"coluna “{col['nome']}” removida (e os valores dela)")
            elif acao == "mudar_chave":
                chave = _resolver_chave(cols, op.get("colunas"))
                for c in cols:
                    if c["id"] in chave:
                        c["obrigatoria"] = True
                vistas: dict[str, uuid.UUID] = {}
                for ln in carregar_linhas():
                    try:
                        kv = _chave_da_linha(chave, cols, ln.valores)
                    except ErroQuadro:
                        raise ErroQuadro(
                            "Há linhas sem valor numa coluna da nova chave. Preencha antes de mudar a chave."
                        ) from None
                    if kv is not None and kv in vistas:
                        raise ErroQuadro("Com a nova chave, duas linhas ficariam com a mesma identificação. Resolva as repetidas antes.")
                    if kv is not None:
                        vistas[kv] = ln.id
                    ln.chave_valor = kv
                    mudaram_linhas.add(ln.id)
                nomes = [c["nome"] for c in cols if c["id"] in chave]
                feitas.append("chave agora é " + (", ".join(f"“{n}”" for n in nomes) if nomes else "nenhuma (o quadro só acumula)"))
            elif acao == "ajustar_limite":
                nome_lim = str(op.get("limite") or "")
                motivo = limites_mod.validar_ajuste(nome_lim, op.get("valor"))
                if motivo:
                    raise ErroQuadro(f"Limite recusado: {motivo}.")
                if op.get("valor") is None:
                    ajustes.pop(nome_lim, None)
                    feitas.append(f"limite “{nome_lim}” voltou ao padrão")
                else:
                    ajustes[nome_lim] = op["valor"]
                    feitas.append(f"limite “{nome_lim}” ajustado para {op['valor']}")
            else:
                raise ErroQuadro(
                    f"Não conheço a ação “{op.get('acao')}”. As ações são: renomear, descrever, "
                    "adicionar_coluna, renomear_coluna, descrever_coluna, trocar_tipo, "
                    "mudar_opcoes, obrigatoria, remover_coluna, mudar_chave, ajustar_limite."
                )

        q.colunas = cols
        q.chave = chave
        q.limites = ajustes
        sessao.flush()
        return {"feitas": feitas, "linhas_afetadas": len(mudaram_linhas), "quadro": descrever_quadro(q)}

    return _em_savepoint(sessao, simular, trabalho)


def excluir_quadro(sessao: Session, organizacao_id: uuid.UUID, ref, *, simular: bool = False) -> dict:
    """Apaga o quadro, as linhas e o histórico. Irreversível — a porta confirma antes."""

    def trabalho():
        q = obter_quadro(sessao, organizacao_id, ref)
        total = contar_linhas(sessao, q.id)
        nome = q.nome
        sessao.delete(q)
        sessao.flush()
        return {"quadro": nome, "linhas_apagadas": total}

    return _em_savepoint(sessao, simular, trabalho)


# ───────────────────────────── linhas ─────────────────────────────


def _chave_da_linha(chave: list[str], cols: list[dict], valores: dict) -> str | None:
    if not chave:
        return None
    partes = []
    for cid in chave:
        v = valores.get(cid)
        if v is None:
            nome = next((c["nome"] for c in cols if c["id"] == cid), cid)
            raise ErroQuadro(f"falta “{nome}”, que faz parte da chave")
        partes.append(tipos.texto_da_chave(v))
    return "\x1f".join(partes)


def _normalizar_linha(q: Quadro, dado, n: int, tam: int, erros: list[dict]) -> dict | None:
    """{coluna_id: valor} de uma linha de entrada (por nome ou id). Acumula erros."""
    if not isinstance(dado, dict):
        erros.append({"linha": n, "coluna": None, "motivo": "a linha precisa ser um objeto {coluna: valor}"})
        return None
    saida: dict = {}
    ok = True
    for ref, valor in dado.items():
        col = resolver_coluna(q, ref)
        if col is None:
            erros.append({
                "linha": n, "coluna": ref,
                "motivo": f"o quadro não tem a coluna “{ref}” (as colunas são: {filtros_mod.nomes_das_colunas(q)})",
            })
            ok = False
            continue
        if col["id"] in saida:
            erros.append({"linha": n, "coluna": col["nome"], "motivo": "a coluna aparece duas vezes na linha"})
            ok = False
            continue
        try:
            saida[col["id"]] = tipos.normalizar(col, valor, tamanho_texto_longo=tam)
        except ValorInvalido as e:
            erros.append({"linha": n, "coluna": col["nome"], "motivo": str(e)})
            ok = False
    return saida if ok else None


def _faltando_obrigatorias(q: Quadro, valores: dict) -> list[str]:
    return [c["nome"] for c in q.colunas or [] if c.get("obrigatoria") and valores.get(c["id"]) is None]


def _alteracao(sessao, q: Quadro, linha_id, acao, antes, depois, autor: Autor):
    sessao.add(
        QuadroAlteracao(
            quadro_id=q.id, linha_id=linha_id, acao=acao, antes=antes, depois=depois,
            origem=autor.origem, agente_id=autor.agente_id,
            execucao_id=autor.execucao_id, usuario_id=autor.usuario_id,
        )
    )


def _carimbar(ln: QuadroLinha, autor: Autor):
    ln.origem = autor.origem
    ln.agente_id = autor.agente_id
    ln.execucao_id = autor.execucao_id
    ln.usuario_id = autor.usuario_id


def _recusar_se_erros(erros: list[dict], total: int):
    if erros:
        linhas = sorted({e["linha"] for e in erros if e.get("linha")})
        raise ErroQuadro(
            f"Nada foi gravado: {len(linhas) or 1} de {total} linha(s) têm problema. "
            "Corrija e mande de novo (a gravação é tudo ou nada).",
            erros[:100],
        )


def gravar_linhas(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    linhas: list[dict],
    *,
    autor: Autor,
    modo: str = "acrescentar",
    simular: bool = False,
) -> dict:
    """Grava linhas, tudo ou nada.

    - `acrescentar`: cria linhas novas. Em quadro com chave, chave que já existe é recusada
      (use `pela_chave` para substituir).
    - `pela_chave`: cria a linha se a chave não existe; se existe, atualiza SÓ as colunas
      informadas (as outras ficam como estavam; valor vazio apaga aquele campo)."""
    modo = str(modo or "acrescentar").strip().lower().replace(" ", "_")
    if modo not in ("acrescentar", "pela_chave"):
        raise ErroQuadro("O modo de gravação é “acrescentar” ou “pela_chave”.")

    def trabalho():
        q = obter_quadro(sessao, organizacao_id, ref)
        lim = limites_mod.efetivos(q)
        if not isinstance(linhas, list) or not linhas:
            raise ErroQuadro("Mande ao menos uma linha (lista de objetos {coluna: valor}).")
        if len(linhas) > lim["linhas_por_gravacao"]:
            raise ErroQuadro(
                f"São {len(linhas)} linhas e uma gravação aceita até {lim['linhas_por_gravacao']}. "
                f"Divida em partes. {limites_mod.ONDE_MUDAR}"
            )
        if modo == "pela_chave" and not q.chave:
            raise ErroQuadro(
                f"O quadro “{q.nome}” não tem chave, então não dá para gravar pela chave. "
                "Use “acrescentar”, ou defina a chave do quadro."
            )
        erros: list[dict] = []
        preparadas: list[tuple[int, dict, str | None]] = []
        vistas: dict[str, int] = {}
        for i, dado in enumerate(linhas, start=1):
            valores = _normalizar_linha(q, dado, i, lim["tamanho_texto_longo"], erros)
            if valores is None:
                continue
            try:
                kv = _chave_da_linha(q.chave or [], q.colunas, valores)
            except ErroQuadro as e:
                erros.append({"linha": i, "coluna": None, "motivo": e.mensagem})
                continue
            if kv is not None:
                if kv in vistas:
                    erros.append({"linha": i, "coluna": None, "motivo": f"a mesma chave já aparece na linha {vistas[kv]} desta gravação"})
                    continue
                vistas[kv] = i
            preparadas.append((i, valores, kv))
        _recusar_se_erros(erros, len(linhas))

        existentes: dict[str, QuadroLinha] = {}
        chaves = [kv for _i, _v, kv in preparadas if kv is not None]
        if chaves:
            for ln in sessao.scalars(
                select(QuadroLinha)
                .where(QuadroLinha.quadro_id == q.id, QuadroLinha.chave_valor.in_(chaves))
                .with_for_update()
            ).all():
                existentes[ln.chave_valor] = ln

        criar: list[tuple[int, dict, str | None]] = []
        atualizar: list[tuple[int, dict, QuadroLinha]] = []
        for i, valores, kv in preparadas:
            atual = existentes.get(kv) if kv is not None else None
            if atual is not None:
                if modo == "acrescentar":
                    nomes = ", ".join(c["nome"] for c in q.colunas if c["id"] in (q.chave or []))
                    erros.append({
                        "linha": i, "coluna": None,
                        "motivo": f"já existe uma linha com esta chave ({nomes}); para substituir, grave no modo “pela_chave”",
                    })
                    continue
                atualizar.append((i, valores, atual))
            else:
                faltam = _faltando_obrigatorias(q, valores)
                if faltam:
                    erros.append({"linha": i, "coluna": faltam[0], "motivo": "faltam colunas obrigatórias: " + ", ".join(f"“{f}”" for f in faltam)})
                    continue
                criar.append((i, valores, kv))
        _recusar_se_erros(erros, len(linhas))

        if criar:
            total = contar_linhas(sessao, q.id)
            if total + len(criar) > lim["linhas_no_quadro"]:
                raise ErroQuadro(
                    f"O quadro tem {total} linhas e esta gravação passaria do limite de "
                    f"{lim['linhas_no_quadro']}. {limites_mod.ONDE_MUDAR}"
                )

        ids_criados, ids_atualizados, sem_mudanca = [], [], 0
        for _i, valores, kv in criar:
            limpos = {k: v for k, v in valores.items() if v is not None}
            ln = QuadroLinha(
                id=uuid.uuid4(), quadro_id=q.id, organizacao_id=q.organizacao_id,
                valores=limpos, chave_valor=kv, versao=1, origem=autor.origem,
            )
            _carimbar(ln, autor)
            sessao.add(ln)
            _alteracao(sessao, q, ln.id, "criou", None, limpos, autor)
            ids_criados.append(str(ln.id))
        for i, valores, ln in atualizar:
            antes = dict(ln.valores or {})
            depois = {**antes, **valores}
            depois = {k: v for k, v in depois.items() if v is not None}
            faltam = _faltando_obrigatorias(q, depois)
            if faltam:
                erros.append({"linha": i, "coluna": faltam[0], "motivo": "a gravação esvaziaria colunas obrigatórias: " + ", ".join(f"“{f}”" for f in faltam)})
                continue
            if depois == antes:
                sem_mudanca += 1
                continue
            ln.valores = depois
            ln.versao = (ln.versao or 1) + 1
            _carimbar(ln, autor)
            _alteracao(sessao, q, ln.id, "mudou", antes, depois, autor)
            ids_atualizados.append(str(ln.id))
        _recusar_se_erros(erros, len(linhas))
        try:
            sessao.flush()
        except IntegrityError:
            raise ErroQuadro(
                "Outra gravação criou a mesma chave ao mesmo tempo. Nada foi gravado; mande de novo."
            ) from None
        return {
            "quadro": q.nome,
            "criadas": len(ids_criados),
            "atualizadas": len(ids_atualizados),
            "sem_mudanca": sem_mudanca,
            "ids_criados": ids_criados,
            "ids_atualizados": ids_atualizados,
        }

    return _em_savepoint(sessao, simular, trabalho)


def _selecao(sessao: Session, q: Quadro, filtros, ids, execucao_id, so_o_mais_recente_de, tam):
    """As condições de uma seleção de linhas (filtro + ids + execução + mais recente).

    "Só a mais recente de X" = entre as linhas que casam com o resto, só as que têm o
    MAIOR X (ex.: as lacunas da rodada mais recente). O máximo é buscado numa consulta
    à parte — como subconsulta na mesma tabela, ele se correlacionaria com a linha de
    fora e deixaria de ser o máximo do conjunto."""
    try:
        conds = [QuadroLinha.quadro_id == q.id]
        conds += filtros_mod.condicoes(q, filtros, tam)
        if ids:
            uids = [_uuid(i) for i in ids]
            if any(u is None for u in uids):
                raise ErroQuadro("Algum id de linha não é válido.")
            conds.append(QuadroLinha.id.in_(uids))
        if execucao_id is not None:
            eid = _uuid(execucao_id)
            if eid is None:
                raise ErroQuadro("O id da execução não é válido.")
            conds.append(QuadroLinha.execucao_id == eid)
        if so_o_mais_recente_de not in (None, ""):
            expr = filtros_mod.expressao_do_mais_recente(q, so_o_mais_recente_de)
            maximo = sessao.scalar(select(func.max(expr)).where(*conds))
            # Nenhuma linha com valor nessa coluna → nenhuma é "a mais recente".
            conds.append(expr == maximo if maximo is not None else false())
        return conds
    except FiltroInvalido as e:
        raise ErroQuadro(str(e)[0].upper() + str(e)[1:] + ".") from None


def _serializar_linha(q: Quadro, ln: QuadroLinha, so: list[str] | None = None) -> dict:
    cols = [c for c in q.colunas or [] if so is None or c["id"] in so]
    return {
        "id": str(ln.id),
        "valores": {c["nome"]: (ln.valores or {}).get(c["id"]) for c in cols},
        "carimbo": {
            "origem": ln.origem,
            "agente_id": str(ln.agente_id) if ln.agente_id else None,
            "execucao_id": str(ln.execucao_id) if ln.execucao_id else None,
            "usuario_id": str(ln.usuario_id) if ln.usuario_id else None,
            "criado_em": ln.criado_em.isoformat() if ln.criado_em else None,
            "atualizado_em": ln.atualizado_em.isoformat() if ln.atualizado_em else None,
            "versao": ln.versao,
        },
    }


def consultar(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    *,
    filtros=None,
    ordem=None,
    colunas=None,
    limite: int | None = None,
    deslocamento: int = 0,
    so_o_mais_recente_de=None,
    ids=None,
    execucao_id=None,
) -> dict:
    """Linhas que casam com os filtros. Sempre diz o TOTAL e, se houver mais, o
    `proximo` deslocamento — nunca corta calado. Ordem padrão: mais recentes primeiro."""
    q = obter_quadro(sessao, organizacao_id, ref)
    lim = limites_mod.efetivos(q)
    teto = lim["linhas_por_consulta"]
    if limite is None:
        limite = min(LIMITE_CONSULTA_PADRAO, teto)
    if isinstance(limite, bool) or not isinstance(limite, int) or limite < 1:
        raise ErroQuadro("O limite da consulta é um número inteiro a partir de 1.")
    cortado = limite > teto
    limite = min(limite, teto)
    if isinstance(deslocamento, bool) or not isinstance(deslocamento, int) or deslocamento < 0:
        raise ErroQuadro("O deslocamento é um número inteiro a partir de 0.")
    so_ids = None
    if colunas:
        if isinstance(colunas, str):
            colunas = [colunas]
        so_ids = [_coluna_ou_erro(q, q.colunas, c)["id"] for c in colunas]
    conds = _selecao(sessao, q, filtros, ids, execucao_id, so_o_mais_recente_de, lim["tamanho_texto_longo"])
    try:
        itens = ordem if isinstance(ordem, list) else ([ordem] if ordem else [])
        ordens = [filtros_mod.expressao_de_ordem(q, o) for o in itens]
    except FiltroInvalido as e:
        raise ErroQuadro(str(e)[0].upper() + str(e)[1:] + ".") from None
    ordens += [QuadroLinha.criado_em.desc(), QuadroLinha.id]
    total = sessao.scalar(select(func.count()).select_from(QuadroLinha).where(*conds)) or 0
    linhas = sessao.scalars(
        select(QuadroLinha).where(*conds).order_by(*ordens).offset(deslocamento).limit(limite)
    ).all()
    proximo = deslocamento + len(linhas)
    resultado = {
        "quadro": q.nome,
        "total": total,
        "devolvidas": len(linhas),
        "deslocamento": deslocamento,
        "proximo": proximo if proximo < total else None,
        "colunas": [c["nome"] for c in q.colunas if so_ids is None or c["id"] in so_ids],
        "linhas": [_serializar_linha(q, ln, so_ids) for ln in linhas],
    }
    if cortado:
        resultado["aviso"] = (
            f"Pediu mais linhas do que uma consulta devolve ({teto}). {limites_mod.ONDE_MUDAR}"
        )
    return resultado


def _num(v):
    if isinstance(v, Decimal):
        f = float(v)
        return int(f) if f.is_integer() else round(f, 6)
    return v


def totais(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    *,
    metricas=None,
    agrupar_por=None,
    filtros=None,
    so_o_mais_recente_de=None,
) -> dict:
    """Totais calculados PELO BANCO (a IA não soma): contar, soma, media, minimo, maximo,
    opcionalmente agrupados por até 3 colunas."""
    q = obter_quadro(sessao, organizacao_id, ref)
    lim = limites_mod.efetivos(q)
    conds = _selecao(sessao, q, filtros, None, None, so_o_mais_recente_de, lim["tamanho_texto_longo"])
    metricas = metricas or [{"funcao": "contar"}]
    if isinstance(metricas, dict):
        metricas = [metricas]
    if not isinstance(metricas, list):
        raise ErroQuadro("As métricas são uma lista de {\"funcao\": …, \"coluna\": …}.")
    selecionados, rotulos = [], []
    for m in metricas:
        if not isinstance(m, dict):
            raise ErroQuadro("Cada métrica é um objeto {\"funcao\": …, \"coluna\": …}.")
        fn = _APELIDOS_FUNCAO.get(str(m.get("funcao") or "").strip().lower())
        if fn is None:
            raise ErroQuadro(f"A função “{m.get('funcao')}” não existe. Use: {', '.join(FUNCOES_TOTAIS)}.")
        if fn == "contar" and not m.get("coluna"):
            selecionados.append(func.count())
            rotulos.append("quantidade")
            continue
        col = _coluna_ou_erro(q, q.colunas, m.get("coluna"))
        texto = QuadroLinha.valores[col["id"]].astext
        if fn == "contar":
            selecionados.append(func.count(texto))
            rotulos.append(f"quantidade de {col['nome']}")
            continue
        if fn in ("soma", "media") and col["tipo"] not in tipos.TIPOS_NUMERICOS:
            raise ErroQuadro(f"Só dá para somar ou tirar média de número ou dinheiro; “{col['nome']}” é {tipos.TIPOS[col['tipo']].lower()}.")
        if fn in ("minimo", "maximo") and col["tipo"] not in tipos.TIPOS_ORDENAVEIS:
            raise ErroQuadro(f"Mínimo e máximo não valem para “{col['nome']}” ({tipos.TIPOS[col['tipo']].lower()}).")
        expr = filtros_mod._alvo(q, col["id"])[1]
        agregado = {"soma": func.sum, "media": func.avg, "minimo": func.min, "maximo": func.max}[fn](expr)
        selecionados.append(agregado)
        rotulos.append(f"{_ROTULO_FUNCAO[fn]} de {col['nome']}")
    grupos_cols = []
    if agrupar_por:
        if isinstance(agrupar_por, str):
            agrupar_por = [agrupar_por]
        if len(agrupar_por) > 3:
            raise ErroQuadro("Dá para agrupar por até 3 colunas.")
        grupos_cols = [_coluna_ou_erro(q, q.colunas, g) for g in agrupar_por]
    exprs_grupo = [QuadroLinha.valores[c["id"]].astext for c in grupos_cols]
    teto = lim["linhas_por_consulta"]
    stmt = select(*exprs_grupo, *selecionados).where(*conds)
    if exprs_grupo:
        stmt = stmt.group_by(*exprs_grupo).order_by(*[e.asc().nulls_last() for e in exprs_grupo]).limit(teto + 1)
    linhas = sessao.execute(stmt).all()
    mais = len(linhas) > teto
    linhas = linhas[:teto]
    grupos = []
    for row in linhas:
        g = {c["nome"]: row[i] for i, c in enumerate(grupos_cols)}
        vals = {r: _num(row[len(grupos_cols) + j]) for j, r in enumerate(rotulos)}
        grupos.append({"grupo": g, "valores": vals} if grupos_cols else {"valores": vals})
    resultado = {"quadro": q.nome, "agrupado_por": [c["nome"] for c in grupos_cols], "resultados": grupos}
    if mais:
        resultado["aviso"] = f"Há mais de {teto} grupos; mostrando os {teto} primeiros. {limites_mod.ONDE_MUDAR}"
    return resultado


def ja_existe(sessao: Session, organizacao_id: uuid.UUID, ref, *, coluna, valores: list) -> dict:
    """Quais destes valores JÁ estão gravados na coluna? Substitui "ler o quadro inteiro
    para descobrir o que falta" — o agente manda os candidatos e recebe os que faltam."""
    q = obter_quadro(sessao, organizacao_id, ref)
    lim = limites_mod.efetivos(q)
    col = _coluna_ou_erro(q, q.colunas, coluna)
    if not isinstance(valores, list) or not valores:
        raise ErroQuadro("Mande a lista de valores a conferir.")
    if len(valores) > lim["linhas_por_consulta"]:
        raise ErroQuadro(f"Dá para conferir até {lim['linhas_por_consulta']} valores por vez. {limites_mod.ONDE_MUDAR}")
    erros, normais = [], []
    for i, v in enumerate(valores, start=1):
        try:
            normais.append((v, tipos.normalizar(col, v, tamanho_texto_longo=lim["tamanho_texto_longo"])))
        except ValorInvalido as e:
            erros.append({"linha": i, "coluna": col["nome"], "motivo": str(e)})
    if erros:
        raise ErroQuadro("Algum valor não serve para a coluna.", erros)
    try:
        cond = filtros_mod.condicao(q, {"coluna": col["id"], "operador": "em", "valor": [n for _o, n in normais if n is not None]}, lim["tamanho_texto_longo"])
    except FiltroInvalido as e:
        raise ErroQuadro(str(e)) from None
    presentes = {
        tipos.texto_da_chave(v)
        for (v,) in sessao.execute(
            select(QuadroLinha.valores[col["id"]]).where(QuadroLinha.quadro_id == q.id, cond)
        ).all()
        if v is not None
    }
    existem = [o for o, n in normais if n is not None and tipos.texto_da_chave(n) in presentes]
    faltam = [o for o, n in normais if n is None or tipos.texto_da_chave(n) not in presentes]
    return {"quadro": q.nome, "coluna": col["nome"], "existem": existem, "faltam": faltam}


def editar_linhas(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    *,
    campos: dict,
    autor: Autor,
    ids=None,
    filtros=None,
    simular: bool = False,
) -> dict:
    """Muda as colunas informadas em `campos` nas linhas achadas por `ids` ou `filtros`.
    Exige um dos dois (não existe "mudar tudo" sem querer)."""

    def trabalho():
        q = obter_quadro(sessao, organizacao_id, ref)
        lim = limites_mod.efetivos(q)
        if not ids and not filtros:
            raise ErroQuadro("Diga quais linhas mudar: por ids ou por filtros.")
        erros: list[dict] = []
        novos = _normalizar_linha(q, campos, 1, lim["tamanho_texto_longo"], erros)
        if not erros and not novos:
            raise ErroQuadro("Diga o que mudar (campos {coluna: novo valor}).")
        if erros:
            raise ErroQuadro("Algum campo não serve.", erros)
        conds = _selecao(sessao, q, filtros, ids, None, None, lim["tamanho_texto_longo"])
        alvo = sessao.scalars(select(QuadroLinha).where(*conds).with_for_update()).all()
        mudadas = 0
        for ln in alvo:
            antes = dict(ln.valores or {})
            depois = {k: v for k, v in {**antes, **novos}.items() if v is not None}
            faltam = _faltando_obrigatorias(q, depois)
            if faltam:
                raise ErroQuadro("A mudança esvaziaria colunas obrigatórias: " + ", ".join(f"“{f}”" for f in faltam) + ".")
            if depois == antes:
                continue
            ln.valores = depois
            ln.chave_valor = _chave_da_linha(q.chave or [], q.colunas, depois)
            ln.versao = (ln.versao or 1) + 1
            _carimbar(ln, autor)
            _alteracao(sessao, q, ln.id, "mudou", antes, depois, autor)
            mudadas += 1
        try:
            sessao.flush()
        except IntegrityError:
            raise ErroQuadro("A mudança deixaria duas linhas com a mesma chave. Nada foi mudado.") from None
        return {"quadro": q.nome, "encontradas": len(alvo), "mudadas": mudadas}

    return _em_savepoint(sessao, simular, trabalho)


def apagar_linhas(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    *,
    autor: Autor,
    ids=None,
    filtros=None,
    execucao_id=None,
    simular: bool = False,
) -> dict:
    """Apaga as linhas achadas por ids, filtros e/ou execução (desfazer o que uma rodada
    gravou). Exige ao menos um critério. O histórico guarda o que existia."""

    def trabalho():
        q = obter_quadro(sessao, organizacao_id, ref)
        lim = limites_mod.efetivos(q)
        if not ids and not filtros and execucao_id is None:
            raise ErroQuadro("Diga quais linhas apagar: por ids, por filtros ou pela execução que as gravou.")
        conds = _selecao(sessao, q, filtros, ids, execucao_id, None, lim["tamanho_texto_longo"])
        alvo = sessao.scalars(select(QuadroLinha).where(*conds).with_for_update()).all()
        for ln in alvo:
            _alteracao(sessao, q, ln.id, "apagou", dict(ln.valores or {}), None, autor)
            sessao.delete(ln)
        sessao.flush()
        return {"quadro": q.nome, "apagadas": len(alvo)}

    return _em_savepoint(sessao, simular, trabalho)


def historico_linha(sessao: Session, organizacao_id: uuid.UUID, ref, linha_id) -> dict:
    """Todas as mudanças de uma linha (inclusive de linha já apagada), mais antiga primeiro,
    com os valores por NOME de coluna."""
    q = obter_quadro(sessao, organizacao_id, ref)
    lid = _uuid(linha_id)
    if lid is None:
        raise ErroQuadro("O id da linha não é válido.")
    nomes = {c["id"]: c["nome"] for c in q.colunas or []}

    def por_nome(d):
        return None if d is None else {nomes.get(k, k): v for k, v in d.items()}

    eventos = sessao.scalars(
        select(QuadroAlteracao)
        .where(QuadroAlteracao.quadro_id == q.id, QuadroAlteracao.linha_id == lid)
        .order_by(QuadroAlteracao.seq)
    ).all()
    return {
        "quadro": q.nome,
        "linha_id": str(lid),
        "alteracoes": [
            {
                "acao": e.acao,
                "quando": e.quando.isoformat() if e.quando else None,
                "antes": por_nome(e.antes),
                "depois": por_nome(e.depois),
                "origem": e.origem,
                "agente_id": str(e.agente_id) if e.agente_id else None,
                "execucao_id": str(e.execucao_id) if e.execucao_id else None,
                "usuario_id": str(e.usuario_id) if e.usuario_id else None,
            }
            for e in eventos
        ],
    }


__all__ = [
    "Autor", "ErroQuadro", "listar_quadros", "obter_quadro", "contar_linhas",
    "criar_quadro", "descrever_quadro", "alterar_quadro", "excluir_quadro",
    "gravar_linhas", "consultar", "totais", "ja_existe", "editar_linhas",
    "apagar_linhas", "historico_linha",
]
