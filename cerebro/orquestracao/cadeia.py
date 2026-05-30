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
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Agente, AgenteInstrumento, Instrumento
from orquestracao.agente import executar_agente
from orquestracao.llm import MODELO_PADRAO, construir_modelo

# Guarda contra laço infinito: nº máximo de passos (agentes executados).
MAX_PASSOS = 25

# Destinos que encerram a cadeia (entregar ao usuário).
_DESTINOS_FIM = {None, "", "fim", "FIM"}


class _Escolha(BaseModel):
    """Saída estruturada do passo de roteamento."""

    rotulo: str = Field(description="O rótulo EXATO da saída escolhida.")


def validar_cadeia(cadeia: dict, ids_agentes_validos: set[str]) -> None:
    """Valida a estrutura do grafo e que todo nó/destino é um agente do time.
    Levanta ValueError com mensagem clara. Cadeia vazia é permitida (rascunho)."""
    if not isinstance(cadeia, dict):
        raise ValueError("A cadeia precisa ser um objeto.")
    nos = cadeia.get("nos")
    inicio = cadeia.get("inicio")
    if not nos and not inicio:
        return  # rascunho ainda sem cadeia montada
    if not isinstance(nos, dict) or not nos:
        raise ValueError("A cadeia precisa ter ao menos um nó em 'nos'.")
    if not inicio or inicio not in nos:
        raise ValueError("A cadeia precisa de um 'inicio' que esteja em 'nos'.")
    for no_id, no in nos.items():
        if no_id not in ids_agentes_validos:
            raise ValueError(f"O nó {no_id} não é um agente deste time.")
        rotulos: set[str] = set()
        for saida in (no or {}).get("saidas") or []:
            rotulo = saida.get("rotulo")
            if not rotulo:
                raise ValueError(f"Há uma saída sem 'rotulo' no nó {no_id}.")
            if rotulo in rotulos:
                raise ValueError(f"Rótulo de saída repetido no nó {no_id}: {rotulo}")
            rotulos.add(rotulo)
            destino = saida.get("destino")
            if destino not in _DESTINOS_FIM and destino not in ids_agentes_validos:
                raise ValueError(
                    f"Destino inválido no nó {no_id} (saída {rotulo}): {destino}"
                )


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


def _escolher_saida(saida_texto: str, saidas: list[dict]) -> tuple[dict, dict]:
    """Escolhe uma saída entre várias, conforme o 'quando' de cada uma e a
    saída produzida pelo agente. Usa a LLM com saída estruturada; em caso de
    rótulo inesperado, cai na primeira saída (determinístico).

    Devolve (saída escolhida, uso) — o uso (modelo/tokens) do passo de
    roteamento é contabilizado na medição (Tarefa 5.4)."""
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
    modelo = construir_modelo(None).with_structured_output(_Escolha, include_raw=True)
    resposta = modelo.invoke(prompt)
    escolha = resposta["parsed"]
    u = getattr(resposta["raw"], "usage_metadata", None) or {}
    uso = {
        "modelo": MODELO_PADRAO,  # o roteamento usa sempre o modelo padrão
        "tokens_entrada": u.get("input_tokens", 0),
        "tokens_saida": u.get("output_tokens", 0),
    }
    por_rotulo = {s["rotulo"]: s for s in saidas}
    return por_rotulo.get(escolha.rotulo, saidas[0]), uso


def executar_cadeia(
    sessao: Session,
    cadeia: dict,
    entrada: str,
    *,
    no_inicial: str | None = None,
    ordem_inicial: int = 0,
    max_passos: int = MAX_PASSOS,
    registrar_passo: Callable[[dict, int], None] | None = None,
) -> dict:
    """Executa a cadeia seguindo as bifurcações, até um fim OU uma pausa para
    humano. Pode começar de `no_inicial` (retomada) em vez do início.

    Devolve um dicionário com `estado`:
    - "concluida": chegou ao fim. `resultado` tem o texto final.
    - "aguardando_humano": parou num agente marcado `pausa_humano`. `pergunta`
      tem a saída desse agente (o que perguntar) e `proximo_no` para onde seguir
      quando a resposta chegar.
    `ordem` é o número do último passo; `passos`, o rastro deste trecho.

    Se `registrar_passo` for dado, é chamado após cada passo com (passo, ordem)
    — é como a Tarefa 4.4 persiste cada passo em `passos_execucao`."""
    nos = cadeia.get("nos") or {}
    no_atual: str | None = no_inicial or cadeia.get("inicio")
    if not no_atual or no_atual not in nos:
        raise ValueError("Cadeia inválida: nó inicial ausente ou fora de 'nos'.")

    entrada_atual = entrada
    passos: list[dict] = []
    ordem = ordem_inicial
    neste_trecho = 0

    while no_atual is not None:
        neste_trecho += 1
        if neste_trecho > max_passos:
            raise RuntimeError(
                f"Máximo de passos ({max_passos}) excedido — possível laço infinito."
            )
        ordem += 1

        agente = sessao.get(Agente, uuid.UUID(no_atual))
        if agente is None:
            raise ValueError(f"Agente da cadeia não encontrado: {no_atual}")

        iniciado_em = datetime.now(timezone.utc)
        cinto = _carregar_cinto(sessao, agente.id)
        resultado = executar_agente(agente, cinto, entrada_atual)
        finalizado_em = datetime.now(timezone.utc)
        saida_texto = resultado["saida"]

        uso_passo = list(resultado.get("uso") or [])
        no = nos.get(no_atual, {})
        saidas = no.get("saidas") or []
        if len(saidas) == 0:
            escolhida = None
        elif len(saidas) == 1:
            escolhida = saidas[0]
        else:
            escolhida, uso_roteamento = _escolher_saida(saida_texto, saidas)
            uso_passo.append(uso_roteamento)

        passo = {
            "agente_id": no_atual,
            "agente_nome": agente.nome,
            "entrada": entrada_atual,
            "saida": saida_texto,
            "instrumentos_acionados": resultado["instrumentos_acionados"],
            "saida_escolhida": escolhida["rotulo"] if escolhida else None,
            "uso": uso_passo,
            "iniciado_em": iniciado_em,
            "finalizado_em": finalizado_em,
        }
        passos.append(passo)
        if registrar_passo is not None:
            registrar_passo(passo, ordem)

        destino = escolhida.get("destino") if escolhida else None
        proximo = None if destino in _DESTINOS_FIM else destino

        # Pausa para humano: o agente terminou (sua saída é a pergunta). Para
        # aqui SEMPRE que marcado. Ao responder, a retomada segue para `proximo`
        # (a saída escolhida); se não houver próximo, a resposta encerra o fluxo.
        if no.get("pausa_humano"):
            return {
                "estado": "aguardando_humano",
                "pergunta": saida_texto,
                "proximo_no": proximo,
                "ordem": ordem,
                "passos": passos,
            }

        if proximo is None:
            return {
                "estado": "concluida",
                "resultado": saida_texto,
                "ordem": ordem,
                "passos": passos,
            }

        entrada_atual = saida_texto
        no_atual = proximo
