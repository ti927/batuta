"""Execução de uma cadeia com bifurcação (Tarefa 4.3; grafo visual 2026-06-16).

A cadeia é um GRAFO, não uma fila linear (decisão do maestro, alinhada ao
PRODUTO.md §14 "Bifurcação por intenção"). A forma canônica (lista de nós tipados)
e suas transformações vivem em `orquestracao.grafo`:

    {"inicial": "<id do nó-agente inicial>",
     "nos": [
       {"id","tipo":"gatilho|agente|roteador|fim","ref":<agente_id>,
        "gate":bool, "saidas":[{"rotulo","quando","destino","tone"}]},
       ...
     ]}

O motor NORMALIZA a cadeia na leitura (`grafo.normalizar`, idempotente): assim ele
lê tanto a forma canônica nova quanto o formato antigo (dict-por-agente) sem
migração de dados — cada automação migra de forma preguiçosa ao ser re-salva.

Tipos de nó: `gatilho`/`fim` são estruturais (o motor não os roda — começa no
`inicial`); `agente` roda pelo executor da Tarefa 4.2; `roteador` só classifica a
entrada sobre suas saídas (sem agente). Quando um nó tem mais de uma saída, um
passo de roteamento escolhe a saída cujo "quando"/"rótulo" melhor casa com a saída
produzida. A saída de um nó vira a entrada do próximo. Loops são permitidos; um
guarda de máximo de passos evita laço infinito. `gate` (antes `pausa_humano`) pausa
para um humano: quem escolhe a saída é a RESPOSTA dele (portão de aprovação).
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import segredos_instrumento
from modelos import Agente, AgenteInstrumento, Instrumento
from orquestracao import grafo
from orquestracao.agente import executar_agente
from orquestracao.llm import MODELO_PADRAO, construir_modelo

# Guarda contra laço infinito: nº máximo de passos (agentes executados).
MAX_PASSOS = 25

# Destinos que encerram a cadeia (mantido para retrocompatibilidade de imports).
_DESTINOS_FIM = grafo.DESTINOS_FIM


class _Escolha(BaseModel):
    """Saída estruturada do passo de roteamento."""

    rotulo: str = Field(description="O rótulo EXATO da saída escolhida.")


def validar_cadeia(cadeia: dict, ids_agentes_validos: set[str]) -> None:
    """Valida a estrutura do grafo: tipos de nó, um inicial executável, cada nó
    `agente` apontando para um agente real do time, rótulos de saída únicos por nó
    e destinos que existem (outro nó, inclusive o `fim`). Levanta ValueError com
    mensagem clara. Cadeia vazia é permitida (rascunho). Aceita tanto a forma nova
    quanto a antiga (normaliza antes de validar)."""
    if cadeia is None:
        return
    if not isinstance(cadeia, dict):
        raise ValueError("A cadeia precisa ser um objeto.")
    if grafo.vazia(cadeia):
        return  # rascunho ainda sem cadeia montada

    cadeia = grafo.normalizar(cadeia)
    nos = cadeia.get("nos") or []
    ids_nos = {n["id"] for n in nos}

    # Rascunho permitido: só gatilho/fim, sem nada que rode ainda. Sem nó executável,
    # não há "início" a exigir — o usuário ainda está montando.
    executaveis = [n for n in nos if n.get("tipo") in ("agente", "roteador")]
    if not executaveis:
        return

    inicial = cadeia.get("inicial")
    no_inicial = next((n for n in nos if n["id"] == inicial), None)
    if no_inicial is None or no_inicial.get("tipo") not in ("agente", "roteador"):
        raise ValueError(
            "Esta automação não tem um início que possa rodar. Abra o nó do gatilho "
            "e escolha em 'Começa em' por qual agente o fluxo começa."
        )

    for no in nos:
        tipo = no.get("tipo")
        if tipo not in grafo.TIPOS_VALIDOS:
            raise ValueError(f"Tipo de nó inválido no nó {no['id']}: {tipo}")
        if tipo == "agente":
            ref = no.get("ref")
            if not ref or str(ref) not in ids_agentes_validos:
                raise ValueError(
                    f"O nó {no['id']} aponta para um agente que não é deste time."
                )
        rotulos: set[str] = set()
        for saida in no.get("saidas") or []:
            rotulo = saida.get("rotulo")
            if not rotulo:
                raise ValueError(f"Há uma saída sem 'rotulo' no nó {no['id']}.")
            if rotulo in rotulos:
                raise ValueError(f"Rótulo de saída repetido no nó {no['id']}: {rotulo}")
            rotulos.add(rotulo)
            destino = saida.get("destino")
            if destino not in ids_nos:
                raise ValueError(
                    f"Destino inválido no nó {no['id']} (saída {rotulo}): {destino}"
                )


def _carregar_cinto(sessao: Session, agente_id: uuid.UUID) -> list[Instrumento]:
    cinto = list(
        sessao.scalars(
            select(Instrumento)
            .join(
                AgenteInstrumento,
                AgenteInstrumento.instrumento_id == Instrumento.id,
            )
            .where(AgenteInstrumento.agente_id == agente_id)
        )
    )
    # Fase 7-B: decifra e anexa os segredos de cada instrumento (em memória), para
    # a execução mesclá-los na config sem que eles fiquem em claro no banco.
    segredos_instrumento.anexar_aos_instrumentos(sessao, cinto)
    return cinto


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
    cancelado: Callable[[], bool] | None = None,
) -> dict:
    """Executa a cadeia seguindo as bifurcações, até um fim OU uma pausa para
    humano. Pode começar de `no_inicial` (retomada) em vez do início.

    Devolve um dicionário com `estado`:
    - "concluida": chegou ao fim. `resultado` tem o texto final.
    - "aguardando_humano": parou num nó com `gate`. `pergunta` tem a saída desse
      nó (a proposta/pergunta). O caminho a seguir NÃO é decidido aqui — é a
      resposta do humano que escolhe a saída, no resume (portão, PRODUTO §14).
    `ordem` é o número do último passo; `passos`, o rastro deste trecho.

    `no_inicial` é o ID do NÓ por onde começar (retomada); na partida normal usa o
    `inicial` da cadeia. Se `registrar_passo` for dado, é chamado após cada passo
    com (passo, ordem) — é como a Tarefa 4.4 persiste cada passo."""
    idx = grafo.indexar(grafo.normalizar(cadeia or {}))
    no_atual: str | None = no_inicial or idx.inicial
    if idx.no(no_atual) is None:
        raise ValueError("Cadeia inválida: nó inicial ausente ou fora do grafo.")

    entrada_atual = entrada
    passos: list[dict] = []
    ordem = ordem_inicial
    neste_trecho = 0

    while no_atual is not None:
        # Cancelamento cooperativo (Tarefa 5.5): entre passos, se o operador
        # cancelou, paramos aqui — os passos já feitos ficam registrados.
        if cancelado is not None and cancelado():
            return {"estado": "cancelada", "ordem": ordem, "passos": passos}

        no = idx.no(no_atual)
        if no is None:
            raise ValueError(f"Nó da cadeia não encontrado: {no_atual}")
        tipo = no.get("tipo", "agente")

        # Nós estruturais: o `fim` encerra; o `gatilho` apenas repassa para a sua
        # saída (o motor normalmente parte do `inicial`, não do gatilho, mas
        # tratamos por robustez). Nenhum dos dois conta como passo.
        if tipo == "fim":
            return {
                "estado": "concluida", "resultado": entrada_atual,
                "ordem": ordem, "passos": passos,
            }
        if tipo == "gatilho":
            saidas = no.get("saidas") or []
            destino = saidas[0].get("destino") if saidas else None
            if not destino or idx.eh_fim(destino):
                return {
                    "estado": "concluida", "resultado": entrada_atual,
                    "ordem": ordem, "passos": passos,
                }
            no_atual = destino
            continue

        neste_trecho += 1
        if neste_trecho > max_passos:
            raise RuntimeError(
                f"Máximo de passos ({max_passos}) excedido — possível laço infinito."
            )
        ordem += 1

        iniciado_em = datetime.now(timezone.utc)
        if tipo == "roteador":
            # Roteador: não roda agente nem produz conteúdo — só classifica a
            # entrada sobre as suas saídas e segue. A entrada passa adiante intacta.
            agente_id_str: str | None = None
            agente_nome = no.get("nome") or "roteador"
            saida_texto = entrada_atual
            instrumentos: list = []
            uso_passo: list = []
        else:  # agente
            ref = no.get("ref")
            agente = sessao.get(Agente, uuid.UUID(str(ref))) if ref else None
            if agente is None:
                raise ValueError(
                    f"O nó '{no_atual}' aponta para um agente que não existe mais "
                    f"(ref {ref}). Edite a automação e troque ou remova esse passo."
                )
            cinto = _carregar_cinto(sessao, agente.id)
            resultado = executar_agente(agente, cinto, entrada_atual)
            saida_texto = resultado["saida"]
            instrumentos = resultado["instrumentos_acionados"]
            uso_passo = list(resultado.get("uso") or [])
            agente_id_str = str(agente.id)
            agente_nome = agente.nome
        finalizado_em = datetime.now(timezone.utc)

        saidas = no.get("saidas") or []
        gate = bool(no.get("gate"))

        # Roteamento automático só quando NÃO há gate. Com gate (portão de
        # aprovação, PRODUTO §14), quem escolhe a saída é a RESPOSTA DO HUMANO,
        # decidida no resume — por isso aqui não roteia (e não gasta a chamada).
        escolhida = None
        if not gate:
            if len(saidas) == 1:
                escolhida = saidas[0]
            elif len(saidas) >= 2:
                escolhida, uso_roteamento = _escolher_saida(saida_texto, saidas)
                uso_passo.append(uso_roteamento)

        passo = {
            "no_id": no_atual,
            "agente_id": agente_id_str,
            "agente_nome": agente_nome,
            "entrada": entrada_atual,
            "saida": saida_texto,
            "instrumentos_acionados": instrumentos,
            "saida_escolhida": escolhida["rotulo"] if escolhida else None,
            "uso": uso_passo,
            "iniciado_em": iniciado_em,
            "finalizado_em": finalizado_em,
        }
        passos.append(passo)
        if registrar_passo is not None:
            registrar_passo(passo, ordem)

        # Pausa para humano: o nó terminou (sua saída é a pergunta/proposta).
        # Para aqui; o caminho a seguir é decidido pela resposta do humano.
        if gate:
            return {
                "estado": "aguardando_humano",
                "pergunta": saida_texto,
                "ordem": ordem,
                "passos": passos,
            }

        destino = escolhida.get("destino") if escolhida else None
        if destino is None or idx.eh_fim(destino):
            return {
                "estado": "concluida",
                "resultado": saida_texto,
                "ordem": ordem,
                "passos": passos,
            }

        entrada_atual = saida_texto
        no_atual = destino
