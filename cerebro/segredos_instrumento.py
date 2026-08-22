"""Cofre de segredos de instrumentos (Fase 7-B, PRODUTO §26).

Guarda cifradas as credenciais de cada instrumento (senha de app do WordPress,
chave da busca web, token de webhook…), separadas da `instrumentos.configuracao`
(JSONB em claro). Reusa a criptografia do cofre (`cofre.py`). Os valores nunca
voltam à interface — só os 4 últimos dígitos (`resumo`).

Na execução, os segredos são DECIFRADOS e injetados na config do instrumento
(via atributo transitório `segredos_decifrados`, que o SQLAlchemy não persiste).
"""

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import chaves
import cofre
from modelos import SegredoInstrumento


def salvar_segredos(
    sessao: Session, instrumento_id: uuid.UUID, segredos: dict[str, str]
) -> list[str]:
    """Cadastra/troca os segredos informados de um instrumento (upsert, cifrando).
    Só mexe nos campos presentes em `segredos`; um campo ausente preserva o valor
    atual (padrão de campo de senha). Devolve a lista de campos alterados."""
    if not segredos:
        return []
    existentes = {
        s.campo: s
        for s in sessao.scalars(
            select(SegredoInstrumento).where(
                SegredoInstrumento.instrumento_id == instrumento_id
            )
        )
    }
    alterados: list[str] = []
    for campo, valor in segredos.items():
        registro = existentes.get(campo)
        if registro is None:
            registro = SegredoInstrumento(
                instrumento_id=instrumento_id, campo=campo
            )
            sessao.add(registro)
        registro.valor_cifrado = cofre.cifrar(valor)
        registro.ultimos4 = cofre.ultimos4(valor)
        alterados.append(campo)
    sessao.flush()
    return alterados


def resumo(sessao: Session, instrumento_id: uuid.UUID) -> dict[str, str]:
    """{campo: ultimos4} dos segredos guardados — para a interface mostrar o que
    está configurado sem nunca reexibir o valor."""
    return {
        s.campo: (s.ultimos4 or "")
        for s in sessao.scalars(
            select(SegredoInstrumento).where(
                SegredoInstrumento.instrumento_id == instrumento_id
            )
        )
    }


def decifrar(sessao: Session, instrumento_id: uuid.UUID) -> dict[str, str]:
    """{campo: valor decifrado} dos segredos de um instrumento — usado só na
    execução, em memória."""
    return {
        s.campo: cofre.decifrar(s.valor_cifrado)
        for s in sessao.scalars(
            select(SegredoInstrumento).where(
                SegredoInstrumento.instrumento_id == instrumento_id
            )
        )
    }


def anexar_aos_instrumentos(sessao: Session, instrumentos: list) -> None:
    """Decifra os segredos de cada instrumento e os anexa num atributo
    transitório `segredos_decifrados` (não-mapeado: o SQLAlchemy não o grava).
    A orquestração mescla esses valores na config antes de acionar o instrumento.
    Faz uma consulta única para todos os instrumentos.

    Chave de serviço COMPARTILHADA: para um instrumento que reusa uma chave do pool
    da organização (declara `chave_compartilhada` no tipo, ex.: gerar_imagem→openai)
    e NÃO tem a chave própria, injeta a chave resolvida do contexto da execução
    (`usar_chaves`). Tudo em memória; nunca grava. Como esta função é chamada pelos
    DOIS caminhos (execução `cadeia._carregar_cinto` e atendimento
    `mensageria._cinto_sem_canais`), a injeção cobre ambos sem tocar o núcleo."""
    # Imports locais para evitar qualquer ciclo de importação no carregamento.
    from instrumentos.base import obter_tipo
    from orquestracao.llm import chaves_atuais

    import credenciais_cofre
    from modelos import Credencial

    ids = [inst.id for inst in instrumentos]
    por_instrumento: dict[uuid.UUID, dict[str, str]] = {}
    if ids:
        for s in sessao.scalars(
            select(SegredoInstrumento).where(
                SegredoInstrumento.instrumento_id.in_(ids)
            )
        ):
            por_instrumento.setdefault(s.instrumento_id, {})[s.campo] = cofre.decifrar(
                s.valor_cifrado
            )

    # Caixa-forte: decifra (em memória) as credenciais nomeadas referenciadas.
    cred_ids = {
        inst.credencial_id
        for inst in instrumentos
        if getattr(inst, "credencial_id", None)
    }
    por_credencial: dict[uuid.UUID, dict[str, str]] = {}
    if cred_ids:
        import google_oauth

        for c in sessao.scalars(
            select(Credencial).where(Credencial.id.in_(cred_ids))
        ):
            valores_cred = credenciais_cofre.decifrar(c)
            # Credencial `google` (OAuth): o access_token dura ~1h. Garante um token
            # fresco sob demanda (renova pelo refresh_token e persiste), para o
            # instrumento sempre receber um token válido. Nunca levanta.
            if c.tipo == "google":
                valores_cred["access_token"] = google_oauth.garantir_token(c)
            por_credencial[c.id] = valores_cred

    pool = chaves_atuais()
    for inst in instrumentos:
        proprios = por_instrumento.get(inst.id, {})
        credencial = por_credencial.get(getattr(inst, "credencial_id", None), {})
        # Prioridade: inline próprio > credencial central > pool de serviço.
        valores = {**credencial, **proprios}
        tipo = obter_tipo(inst.tipo)
        compart = getattr(tipo, "chave_compartilhada", None) if tipo else None
        if compart:
            campo, servico = compart
            # Campo ainda vazio (nem inline nem credencial) → reusa a do pool.
            if not (valores.get(campo) or "").strip() and pool.get(servico):
                valores = {**valores, campo: pool[servico]}
        inst.segredos_decifrados = valores


# Serviços de chave compartilhada com queda de legado no `.env` do cérebro
# (espelha `chaves.SERVICOS_COM_LEGADO`): mapeia o serviço à variável de ambiente.
_ENV_LEGADO_SERVICO = {"tavily": "TAVILY_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def servicos_resolviveis(
    sessao: Session, organizacao_id: uuid.UUID | None
) -> set[str]:
    """Serviços de chave compartilhada que a organização CONSEGUE resolver — pelo
    pool (cofre da org → cofre da consultoria) ou pela queda de legado no `.env`.
    Serve para o cálculo de segredos pendentes não acusar como 'faltando' uma chave
    que o instrumento já reusa do pool (ex.: a Tavily da busca, a OpenAI da imagem)."""
    pool, _ = chaves.resolver_chaves_por_organizacao(sessao, organizacao_id)
    resolviveis = set(pool)
    for servico, env in _ENV_LEGADO_SERVICO.items():
        if servico in chaves.SERVICOS_COM_LEGADO and os.environ.get(env):
            resolviveis.add(servico)
    return resolviveis


def pendentes(
    tipo: str,
    *,
    guardados: set[str],
    cobertos_por_credencial: frozenset[str] | set[str] = frozenset(),
    servicos_resolviveis: frozenset[str] | set[str] = frozenset(),
) -> list[str]:
    """Campos secretos de um instrumento que NENHUMA das três fontes de resolução
    cobre — só esses faltam de verdade. As fontes são as mesmas (e na mesma ordem)
    que a borda aplica em `anexar_aos_instrumentos`: (1) segredo inline guardado no
    próprio instrumento; (2) credencial nomeada apontada; (3) chave de serviço
    compartilhada resolvível pelo pool da org/consultoria.

    Antes este cálculo olhava só a fonte (1), o que gerava falso-alerta de 'faltam
    segredos' para instrumentos já cobertos pelo cofre."""
    from instrumentos.base import campos_secretos, obter_tipo

    cobertos = set(guardados) | set(cobertos_por_credencial)
    tipo_obj = obter_tipo(tipo)
    compart = getattr(tipo_obj, "chave_compartilhada", None) if tipo_obj else None
    # (4) segredos OPCIONAIS do tipo: vazio é o estado normal, não pendência (ex.:
    # o certificado mTLS, que só APIs bancárias exigem). Ver TipoInstrumento.
    opcionais = set(getattr(tipo_obj, "campos_secretos_opcionais", ()) or ())
    faltando: list[str] = []
    for campo in campos_secretos(tipo):
        if campo in cobertos or campo in opcionais:
            continue
        if compart and campo == compart[0] and compart[1] in servicos_resolviveis:
            continue
        faltando.append(campo)
    return faltando
