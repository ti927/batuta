"""Cofre de segredos de um canal de mensageria (espelha `segredos_instrumento`).

Guarda cifrado o token do bot (e futuros segredos do canal), separado da
`canais.config` (JSONB em claro). Reusa a criptografia do cofre (`cofre.py`). Os
valores nunca voltam à interface — só os 4 últimos dígitos (`resumo`). O valor é
DECIFRADO só em runtime, na hora de enviar/receber (Passos 4+).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import cofre
from modelos import SegredoCanal


def salvar_segredos(
    sessao: Session, canal_id: uuid.UUID, segredos: dict[str, str]
) -> list[str]:
    """Cadastra/troca os segredos informados de um canal (upsert, cifrando). Só
    mexe nos campos presentes; campo ausente preserva o valor atual (padrão de
    campo de senha). Devolve a lista de campos alterados."""
    if not segredos:
        return []
    existentes = {
        s.campo: s
        for s in sessao.scalars(
            select(SegredoCanal).where(SegredoCanal.canal_id == canal_id)
        )
    }
    alterados: list[str] = []
    for campo, valor in segredos.items():
        registro = existentes.get(campo)
        if registro is None:
            registro = SegredoCanal(canal_id=canal_id, campo=campo)
            sessao.add(registro)
        registro.valor_cifrado = cofre.cifrar(valor)
        registro.ultimos4 = cofre.ultimos4(valor)
        alterados.append(campo)
    sessao.flush()
    return alterados


def resumo(sessao: Session, canal_id: uuid.UUID) -> dict[str, str]:
    """{campo: ultimos4} dos segredos guardados — para a interface mostrar o que
    está configurado sem nunca reexibir o valor."""
    return {
        s.campo: (s.ultimos4 or "")
        for s in sessao.scalars(
            select(SegredoCanal).where(SegredoCanal.canal_id == canal_id)
        )
    }


def decifrar(sessao: Session, canal_id: uuid.UUID) -> dict[str, str]:
    """{campo: valor decifrado} dos segredos de um canal — usado só em runtime,
    em memória, na hora de falar com o provedor."""
    return {
        s.campo: cofre.decifrar(s.valor_cifrado)
        for s in sessao.scalars(
            select(SegredoCanal).where(SegredoCanal.canal_id == canal_id)
        )
    }
