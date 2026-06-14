"""Medição de instrumentos com IA paga (borda) — contabilização da categoria
`instrumento`.

Alguns instrumentos consomem IA paga por fora das chamadas de LLM do agente — hoje
o `gerar_imagem` (OpenAI, cobrado POR IMAGEM). Esse custo nasce DENTRO do
`executar_agente` (núcleo congelado), cujo contrato `executar(config, args)->dict`
não reporta uso. Em vez de tocar o núcleo, a contabilização é feita aqui, na borda:
o motor já devolve `instrumentos_acionados` (a lista de NOMES de ferramenta
acionadas), e cada nome embute o id do instrumento (`{nome}_{id8}`, ver
`orquestracao.agente._nome_de_ferramenta`). Casamos esses nomes com o cinto do
agente, e para cada instrumento pago acionado geramos uma entrada de `uso`
(categoria `instrumento`) que entra nos mesmos painéis de uso (`precos.resumir_uso`).

Sem tabela nova, sem migração, sem carimbar nada na config, sem tocar o núcleo.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import precos
from modelos import AgenteInstrumento, Instrumento

# Tipos de instrumento que consomem IA paga (cobrança própria, fora do LLM do
# agente). Por ora só geração de imagem.
TIPOS_PAGOS = {"gerar_imagem"}


def _id8(nome_ferramenta: str) -> str:
    """O sufixo de 8 hex do id do instrumento embutido no nome da ferramenta
    (`{base}_{id8}`). A `base` pode conter `_`, mas o id8 é sempre o último trecho."""
    return nome_ferramenta.rsplit("_", 1)[-1] if "_" in nome_ferramenta else ""


def _custo_imagem(cfg: dict) -> dict:
    """Entrada de uso de UMA imagem gerada, a partir da config do instrumento."""
    modelo = cfg.get("modelo") or "dall-e-3"
    tamanho = cfg.get("tamanho") or "1024x1024"
    return {
        "modelo": modelo,
        "imagens": 1,
        "custo_usd": round(precos.custo_por_imagem(modelo, tamanho), 6),
    }


def uso_de_instrumentos_pagos(
    sessao: Session,
    agente_id,
    instrumentos_acionados,
    *,
    origem: str = "organizacao",
) -> list:
    """Entradas de uso (categoria `instrumento`) dos instrumentos pagos que o
    agente acionou neste passo/turno. Lê o cinto do agente para casar cada nome de
    ferramenta acionada (`{base}_{id8}`) ao instrumento e precificar.

    `origem` é da chave que o instrumento usa — por padrão `organizacao` (a chave
    do próprio instrumento, no cofre 7-B, é da organização; o `gerar_imagem` não
    cai na chave-mãe da consultoria). Devolve [] quando não há instrumento pago
    acionado."""
    if not instrumentos_acionados or not agente_id:
        return []
    if isinstance(agente_id, str):
        agente_id = uuid.UUID(agente_id)

    pagos = sessao.scalars(
        select(Instrumento)
        .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
        .where(AgenteInstrumento.agente_id == agente_id)
        .where(Instrumento.tipo.in_(TIPOS_PAGOS))
    ).all()
    if not pagos:
        return []
    por_id8 = {inst.id.hex[:8]: inst for inst in pagos}

    entradas: list = []
    for nome in instrumentos_acionados:
        if not nome:
            continue
        inst = por_id8.get(_id8(nome))
        if inst is None:
            continue
        # Hoje só gerar_imagem é pago; o roteamento por tipo já vive em TIPOS_PAGOS.
        entrada = _custo_imagem(inst.configuracao or {})
        entrada["origem"] = origem
        entrada["categoria"] = "instrumento"
        entradas.append(entrada)
    return entradas
