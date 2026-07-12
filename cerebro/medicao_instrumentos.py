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
from chaves import ORIGEM_ORGANIZACAO
from instrumentos.base import obter_tipo
from modelos import AgenteInstrumento, Instrumento, SegredoInstrumento
from orquestracao.modelos_ia import provedor_do_modelo_seguro

# Tipos de instrumento que consomem IA paga (cobrança própria, fora do LLM do
# agente): os de imagem (gerar do zero e montar a partir de fotos, cobrados por
# imagem) e o de VISÃO (`descrever_imagem`, que lê uma imagem com um modelo de chat).
TIPOS_PAGOS = {"gerar_imagem", "montar_imagem", "descrever_imagem"}


def _id8(nome_ferramenta: str) -> str:
    """O sufixo de 8 hex do id do instrumento embutido no nome da ferramenta
    (`{base}_{id8}`). A `base` pode conter `_`, mas o id8 é sempre o último trecho."""
    return nome_ferramenta.rsplit("_", 1)[-1] if "_" in nome_ferramenta else ""


def _custo_imagem(cfg: dict) -> dict:
    """Entrada de uso de UMA imagem gerada, a partir da config do instrumento."""
    modelo = cfg.get("modelo") or "gpt-image-1"
    tamanho = cfg.get("tamanho") or "1024x1024"
    qualidade = cfg.get("qualidade") or "medium"
    return {
        "modelo": modelo,
        "imagens": 1,
        "custo_usd": round(precos.custo_por_imagem(modelo, tamanho, qualidade), 6),
    }


def _custo_descricao(cfg: dict) -> dict:
    """Entrada de uso de UMA imagem LIDA (visão), a partir da config do instrumento."""
    modelo = cfg.get("modelo") or "?"
    return {
        "modelo": modelo,
        "imagens": 1,
        "custo_usd": round(precos.custo_por_descricao(modelo), 6),
    }


def _entrada_e_servico(inst: Instrumento) -> tuple[dict, str | None]:
    """(entrada de uso, serviço p/ a origem) de um instrumento pago acionado. Para a
    visão, o serviço é o PROVEDOR do modelo escolhido (não há chave compartilhada
    fixa); para imagem, é o serviço da chave compartilhada do tipo."""
    cfg = inst.configuracao or {}
    if inst.tipo == "descrever_imagem":
        return _custo_descricao(cfg), provedor_do_modelo_seguro(cfg.get("modelo") or "")
    return _custo_imagem(cfg), _servico_do_tipo(inst.tipo)


def _servico_do_tipo(tipo_str: str) -> str | None:
    """O serviço da chave compartilhada do tipo (ex.: gerar_imagem→'openai'), ou
    None se o tipo não reusa chave do pool."""
    compart = getattr(obter_tipo(tipo_str), "chave_compartilhada", None)
    return compart[1] if compart else None


def uso_de_instrumentos_pagos(
    sessao: Session,
    agente_id,
    instrumentos_acionados,
    *,
    origens: dict | None = None,
) -> list:
    """Entradas de uso (categoria `instrumento`) dos instrumentos pagos que o
    agente acionou neste passo/turno. Lê o cinto do agente para casar cada nome de
    ferramenta acionada (`{base}_{id8}`) ao instrumento e precificar.

    `origens` é o mapa {serviço: origem} já resolvido pela borda. A origem de cada
    imagem segue a chave que de fato foi usada: se o instrumento tem chave PRÓPRIA
    (segredo no cofre), origem = `organizacao`; se reusa o pool da organização,
    origem = `origens[serviço]` (organizacao/consultoria/legado). Assim a imagem
    paga pela chave-mãe aparece também no painel da consultoria. Devolve [] quando
    não há instrumento pago acionado."""
    if not instrumentos_acionados or not agente_id:
        return []
    if isinstance(agente_id, str):
        agente_id = uuid.UUID(agente_id)
    origens = origens or {}

    pagos = sessao.scalars(
        select(Instrumento)
        .join(AgenteInstrumento, AgenteInstrumento.instrumento_id == Instrumento.id)
        .where(AgenteInstrumento.agente_id == agente_id)
        .where(Instrumento.tipo.in_(TIPOS_PAGOS))
    ).all()
    if not pagos:
        return []
    por_id8 = {inst.id.hex[:8]: inst for inst in pagos}

    # Quais instrumentos pagos têm chave PRÓPRIA (segredo no cofre) — para decidir a
    # origem. Os pagos têm um único campo secreto (a própria chave compartilhada),
    # então a presença de qualquer segredo já indica chave própria.
    com_chave_propria = set(
        sessao.scalars(
            select(SegredoInstrumento.instrumento_id).where(
                SegredoInstrumento.instrumento_id.in_([i.id for i in pagos])
            )
        ).all()
    )

    entradas: list = []
    for nome in instrumentos_acionados:
        if not nome:
            continue
        inst = por_id8.get(_id8(nome))
        if inst is None:
            continue
        entrada, servico = _entrada_e_servico(inst)
        if inst.id in com_chave_propria:
            entrada["origem"] = ORIGEM_ORGANIZACAO
        else:
            entrada["origem"] = origens.get(servico) or ORIGEM_ORGANIZACAO
        entrada["categoria"] = "instrumento"
        entradas.append(entrada)
    return entradas
