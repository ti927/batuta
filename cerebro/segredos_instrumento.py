"""Cofre de segredos de instrumentos (Fase 7-B, PRODUTO §26).

Guarda cifradas as credenciais de cada instrumento (senha de app do WordPress,
chave da busca web, token de webhook…), separadas da `instrumentos.configuracao`
(JSONB em claro). Reusa a criptografia do cofre (`cofre.py`). Os valores nunca
voltam à interface — só os 4 últimos dígitos (`resumo`).

Na execução, os segredos são DECIFRADOS e injetados na config do instrumento
(via atributo transitório `segredos_decifrados`, que o SQLAlchemy não persiste).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
        for c in sessao.scalars(
            select(Credencial).where(Credencial.id.in_(cred_ids))
        ):
            por_credencial[c.id] = credenciais_cofre.decifrar(c)

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
