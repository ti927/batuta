"""Execução de uma cadeia com bifurcação (Tarefa 4.3).

A cadeia é um GRAFO, não uma fila linear (decisão do maestro, alinhada ao
PRODUTO.md §14 "Bifurcação por intenção"). Formato guardado em
`automacoes.cadeia` (JSONB):

    {
      "inicio": "<agente_id>",
      "nos": {
        "<agente_id>": {
          "saidas": [
            {"rotulo": "1", "quando": "descrição de quando seguir por aqui",
             "destino": "<agente_id>"},     # outro agente (pode ser anterior: loop)
            {"rotulo": "2", "quando": "...", "destino": null}   # null = fim (entrega)
          ]
        }
      }
    }

Cada agente roda pelo executor da Tarefa 4.2 (que é LangGraph). Quando o nó tem
mais de uma saída, um passo de roteamento escolhe a saída cujo "quando" melhor
casa com a saída do agente. A saída de um agente vira a entrada do próximo.
Loops são permitidos; um guarda de máximo de passos evita laço infinito.
"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Agente, AgenteInstrumento, Instrumento
from orquestracao.agente import executar_agente
from orquestracao.llm import construir_modelo

# Guarda contra laço infinito: nº máximo de passos (agentes executados).
MAX_PASSOS = 25

# Destinos que encerram a cadeia (entregar ao usuário).
_DESTINOS_FIM = {None, "", "fim", "FIM"}


class _Escolha(BaseModel):
    """Saída estruturada do passo de roteamento."""

    rotulo: str = Field(description="O rótulo EXATO da saída escolhida.")


def _carregar_cinto(sessao: Session, agente_id: uuid.UUID) -> list[Instrumento]:
    return list(
        sessao.scalars(
            select(Instrumento)
            .join(
                AgenteInstrumento,
                AgenteInstrumento.instrumento_id == Instrumento.id,
            )
            .where(AgenteInstrumento.agente_id == agente_id)
        )
    )


def _escolher_saida(saida_texto: str, saidas: list[dict]) -> dict:
    """Escolhe uma saída entre várias, conforme o 'quando' de cada uma e a
    saída produzida pelo agente. Usa a LLM com saída estruturada; em caso de
    rótulo inesperado, cai na primeira saída (determinístico)."""
    opcoes = "\n".join(
        f'- "{s["rotulo"]}": {s.get("quando") or "(sem descrição)"}' for s in saidas
    )
    prompt = (
        "Você é um roteador de fluxo. Dada a SAÍDA de um agente e as OPÇÕES de "
        "caminho, escolha o rótulo da opção que melhor se aplica à saída.\n\n"
        f"SAÍDA DO AGENTE:\n{saida_texto}\n\n"
        f"OPÇÕES:\n{opcoes}\n\n"
        "Responda apenas com o rótulo exato de uma das opções."
    )
    modelo = construir_modelo(None).with_structured_output(_Escolha)
    escolha = modelo.invoke(prompt)
    por_rotulo = {s["rotulo"]: s for s in saidas}
    return por_rotulo.get(escolha.rotulo, saidas[0])


def executar_cadeia(
    sessao: Session,
    cadeia: dict,
    entrada: str,
    max_passos: int = MAX_PASSOS,
) -> dict:
    """Executa a cadeia a partir do nó inicial, seguindo as bifurcações, até
    chegar a um fim. Devolve o resultado final e o rastro de cada passo."""
    inicio = cadeia.get("inicio")
    nos = cadeia.get("nos") or {}
    if not inicio or inicio not in nos:
        raise ValueError("Cadeia inválida: 'inicio' ausente ou fora de 'nos'.")

    no_atual: str | None = inicio
    entrada_atual = entrada
    passos: list[dict] = []
    contagem = 0

    while no_atual is not None:
        contagem += 1
        if contagem > max_passos:
            raise RuntimeError(
                f"Máximo de passos ({max_passos}) excedido — possível laço infinito."
            )

        agente = sessao.get(Agente, uuid.UUID(no_atual))
        if agente is None:
            raise ValueError(f"Agente da cadeia não encontrado: {no_atual}")

        cinto = _carregar_cinto(sessao, agente.id)
        resultado = executar_agente(agente, cinto, entrada_atual)
        saida_texto = resultado["saida"]

        saidas = nos.get(no_atual, {}).get("saidas") or []
        if len(saidas) == 0:
            escolhida = None
        elif len(saidas) == 1:
            escolhida = saidas[0]
        else:
            escolhida = _escolher_saida(saida_texto, saidas)

        passos.append(
            {
                "agente_id": no_atual,
                "agente_nome": agente.nome,
                "entrada": entrada_atual,
                "saida": saida_texto,
                "instrumentos_acionados": resultado["instrumentos_acionados"],
                "saida_escolhida": escolhida["rotulo"] if escolhida else None,
            }
        )

        entrada_atual = saida_texto
        destino = escolhida.get("destino") if escolhida else None
        no_atual = None if destino in _DESTINOS_FIM else destino

    return {"resultado": entrada_atual, "passos": passos}
