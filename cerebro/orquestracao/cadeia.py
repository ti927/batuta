"""Execução de uma cadeia — o motor caminha o GRAFO por ONDAS (fan-out).

A cadeia é um GRAFO dirigido (PRODUTO §14). A forma canônica (lista de nós tipados)
e suas transformações vivem em `orquestracao.grafo`:

    {"inicial": "<id do nó-agente inicial>",
     "nos": [
       {"id","tipo":"gatilho|agente|roteador|fim","ref":<agente_id>,
        "gate":bool, "saidas":[{"rotulo","quando","destino","tipo","tone"}]},
       ...
     ]}

O motor NORMALIZA a cadeia na leitura (`grafo.normalizar`, idempotente): lê tanto a
forma canônica nova quanto o formato antigo (dict-por-agente) sem migração de dados.

## O grafo se comporta como grafo (2026-08-31)

Até aqui o motor tinha um PONTEIRO ÚNICO: um nó com várias saídas seguia UMA delas e
as outras eram descartadas em silêncio — quem desenhava "aprovado → Carrossel" e
"aprovado → Story" via só um dos dois rodar. Agora o motor caminha por **ondas**:

- Cada nó, ao terminar, pode liberar **VÁRIAS** saídas — todas cujas condições foram
  atendidas (o agente as declara pela ferramenta `seguir_para`, que aceita lista).
- Os destinos liberados formam a **próxima onda**. Se dois ramos reencontram o mesmo
  nó na mesma onda, ele roda **UMA vez** com os textos dos dois juntos (junção
  implícita — sem isso, um fluxo em Y publicaria em dobro).
- Cada saída tem um PAPEL (`grafo.TIPOS_SAIDA`): `condicional` (o caso normal),
  `erro` (percorrida quando o nó falha — o passo falho fica gravado e o fluxo segue
  por ela em vez de a execução morrer) e `senao` (rede de segurança, percorrida só
  quando nenhuma condicional foi atendida).
- **Nunca mais escolha silenciosa:** se nada casa e não há `senao`, aquele ramo
  termina com o motivo gravado no rastro. Antes caía calado na primeira saída.
- O teto de passos (`max_passos`) vale por EXECUÇÃO (soma as retomadas), não por
  trecho.

`gate` (portão de aprovação) pausa para um humano: quem escolhe a saída é a RESPOSTA
dele, na retomada. Ao pausar, o motor devolve as **pendências** — os ramos da onda que
ainda não rodaram —, para a retomada continuar de onde parou sem perder trabalho.
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

# Guarda contra laço infinito: nº máximo de passos (agentes executados) POR EXECUÇÃO
# — a contagem soma as retomadas (o `ordem_inicial` carrega o que já rodou).
MAX_PASSOS = 25

# Como os textos de vários ramos que reencontram o mesmo nó são juntados na entrada.
SEPARADOR_JUNCAO = "\n\n---\n\n"

# Destinos que encerram a cadeia (mantido para retrocompatibilidade de imports).
_DESTINOS_FIM = grafo.DESTINOS_FIM


class _Escolha(BaseModel):
    """Saída estruturada do passo de roteamento (fallback, quando o agente não
    declarou o caminho). Devolve TODOS os rótulos cuja condição se aplica."""

    rotulos: list[str] = Field(
        description="Os rótulos EXATOS de TODAS as opções cuja condição foi atendida. "
        "Pode ser mais de uma. Lista vazia se nenhuma se aplica."
    )


def validar_cadeia(
    cadeia: dict, ids_agentes_validos: set[str], *, exigir_condicao: bool = True
) -> None:
    """Valida a estrutura do grafo: tipos de nó, um inicial executável, cada nó
    `agente` apontando para um agente real do time, rótulos de saída únicos por nó,
    destinos que existem e — quando o nó bifurca — a CONDIÇÃO de cada saída
    preenchida. Levanta ValueError com mensagem clara. Cadeia vazia é permitida
    (rascunho). Aceita tanto a forma nova quanto a antiga (normaliza antes).

    `exigir_condicao=False` afrouxa SÓ a exigência da condição — para COPIAR uma
    cadeia que já existia (duplicar time/automação). Automações criadas antes de
    2026-08-31 têm todas as condições vazias; recusar a cópia puniria o usuário por
    um dado legado que ele não escreveu. Ele preenche ao editar."""
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

        # A CONDIÇÃO é obrigatória quando o nó bifurca. Era o buraco que fazia o
        # motor escolher no escuro: o editor só tinha caixa para o `rotulo`, então
        # todo `quando` ficava vazio e o agente recebia nomes sem significado.
        # Nós estruturais (gatilho) e saídas de erro/"senão" não têm condição.
        condicionais, _, _ = grafo.separar_saidas(no.get("saidas"))
        if exigir_condicao and tipo in ("agente", "roteador") and len(condicionais) >= 2:
            sem_condicao = [
                s["rotulo"] for s in condicionais if not (s.get("quando") or "").strip()
            ]
            if sem_condicao:
                nome = no.get("nome") or no["id"]
                raise ValueError(
                    f"O passo '{nome}' bifurca em {len(condicionais)} caminhos, mas "
                    f"{'a saída' if len(sem_condicao) == 1 else 'as saídas'} "
                    + ", ".join(f"'{r}'" for r in sem_condicao)
                    + " não diz quando seguir por ela. Preencha 'Siga por aqui "
                    "quando…' em cada saída — é por essa frase que o agente decide."
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


def _rotear_por_llm(saida_texto: str, saidas: list[dict]) -> tuple[list[dict], dict]:
    """Fallback de roteamento: quando o agente NÃO declarou o caminho (automação
    antiga, modelo que ignorou a ferramenta), uma LLM lê a condição de cada saída e
    devolve TODAS as que se aplicam ao texto produzido.

    Devolve (saídas escolhidas, uso). **Lista vazia é uma resposta legítima** — não
    existe mais "cai na primeira": quando nada casa, quem decide é a saída `senão`,
    e na falta dela o ramo termina com o motivo gravado no rastro."""
    opcoes = "\n".join(
        f'- "{s["rotulo"]}": {s.get("quando") or "(sem condição escrita)"}'
        for s in saidas
    )
    prompt = (
        "Você é um roteador de fluxo. Dada a SAÍDA de um agente e as OPÇÕES de "
        "caminho, devolva os rótulos de TODAS as opções cuja condição foi atendida "
        "(pode ser mais de uma; pode ser nenhuma).\n\n"
        f"SAÍDA DO AGENTE:\n{saida_texto}\n\n"
        f"OPÇÕES:\n{opcoes}\n\n"
        "Responda apenas com os rótulos exatos das opções atendidas."
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
    escolhidas = [
        por_rotulo[r] for r in (getattr(escolha, "rotulos", None) or []) if r in por_rotulo
    ]
    return escolhidas, uso


def _escolher_saida(saida_texto: str, saidas: list[dict]) -> tuple[dict, dict]:
    """Escolhe UMA saída (usado pela retomada mecânica de portão, onde a resposta do
    humano decide um caminho só). Mantido sobre `_rotear_por_llm`."""
    escolhidas, uso = _rotear_por_llm(saida_texto, saidas)
    return (escolhidas[0] if escolhidas else saidas[0]), uso


def _empilhar(proxima: dict[str, list[str]], destino: str, textos: list[str]) -> None:
    """Enfileira textos para um destino na PRÓXIMA onda. Se dois ramos apontam para
    o mesmo nó, os textos se acumulam e o nó roda UMA vez (junção implícita)."""
    proxima.setdefault(destino, []).extend(textos)


def _como_itens(mapa: dict[str, list[str]]) -> list[dict]:
    """A onda como lista de itens serializáveis (é também o formato das pendências
    guardadas quando a execução pausa)."""
    return [{"no": nid, "entradas": list(textos)} for nid, textos in mapa.items()]


def executar_cadeia(
    sessao: Session,
    cadeia: dict,
    entrada: str,
    *,
    no_inicial: str | None = None,
    frente_inicial: list[dict] | None = None,
    ordem_inicial: int = 0,
    max_passos: int = MAX_PASSOS,
    registrar_passo: Callable[[dict, int], None] | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> dict:
    """Caminha o grafo por ondas, até acabarem os ramos OU uma pausa para humano.

    Devolve um dicionário com `estado`:
    - "concluida": todos os ramos terminaram. `resultado` tem o texto final (os
      textos dos ramos que chegaram ao fim, juntos); `avisos` lista os ramos que
      terminaram sem caminho.
    - "aguardando_humano": um nó com `gate` pausou. `pergunta` é a saída desse nó;
      `pendentes` são os ramos da onda que ainda não rodaram (a retomada os leva
      adiante para nenhum trabalho se perder).
    - "cancelada": o operador cancelou entre passos.
    `ordem` é o número do último passo; `passos`, o rastro deste trecho.

    `no_inicial` começa de um nó só (retomada simples); `frente_inicial` começa de
    vários ramos ao mesmo tempo (retomada com pendências), no formato
    `[{"no": <id>, "entradas": [<texto>, ...]}, ...]`."""
    idx = grafo.indexar(grafo.normalizar(cadeia or {}))

    if frente_inicial:
        onda = [
            {"no": i["no"], "entradas": list(i.get("entradas") or [])}
            for i in frente_inicial
            if i.get("no")
        ]
    else:
        onda = [{"no": no_inicial or idx.inicial, "entradas": [entrada]}]
    if not onda or idx.no(onda[0]["no"]) is None:
        raise ValueError("Cadeia inválida: nó inicial ausente ou fora do grafo.")

    passos: list[dict] = []
    avisos: list[str] = []
    resultados: list[str] = []
    ordem = ordem_inicial

    while onda:
        proxima: dict[str, list[str]] = {}
        for pos, item in enumerate(onda):
            # Cancelamento cooperativo (Tarefa 5.5): entre passos, se o operador
            # cancelou, paramos aqui — os passos já feitos ficam registrados.
            if cancelado is not None and cancelado():
                return {"estado": "cancelada", "ordem": ordem, "passos": passos}

            no_atual = item["no"]
            entradas = item["entradas"] or [""]
            no = idx.no(no_atual)
            if no is None:
                raise ValueError(f"Nó da cadeia não encontrado: {no_atual}")
            tipo = no.get("tipo", "agente")

            # Nós estruturais: o `fim` encerra aquele ramo; o `gatilho` apenas
            # repassa para a sua saída. Nenhum dos dois conta como passo.
            if tipo == "fim":
                resultados.extend(entradas)
                continue
            if tipo == "gatilho":
                saidas_g = no.get("saidas") or []
                destino = saidas_g[0].get("destino") if saidas_g else None
                if not destino or idx.eh_fim(destino):
                    resultados.extend(entradas)
                else:
                    _empilhar(proxima, destino, entradas)
                continue

            ordem += 1
            # Teto POR EXECUÇÃO: `ordem_inicial` traz o que já rodou antes da
            # retomada, então um laço que atravessa portões também é contido.
            if ordem > max_passos:
                raise RuntimeError(
                    f"Máximo de passos ({max_passos}) excedido — possível laço infinito."
                )

            entrada_atual = (
                entradas[0] if len(entradas) == 1 else SEPARADOR_JUNCAO.join(entradas)
            )
            saidas = no.get("saidas") or []
            condicionais, saidas_erro, saidas_senao = grafo.separar_saidas(saidas)
            gate = bool(no.get("gate"))
            iniciado_em = datetime.now(timezone.utc)
            # Identidade do nó resolvida ANTES de rodar: se ele falhar, o passo falho
            # precisa dizer QUEM falhou (é o nome que aparece na timeline e no aviso
            # da falha). Sem isto o passo falho saía anônimo, justo quando importa.
            id_agente, nome_do_no = _identidade_do_no(sessao, no, tipo)

            try:
                executado = _rodar_no(
                    sessao, no, no_atual, tipo, entrada_atual,
                    condicionais=condicionais, gate=gate,
                )
            except Exception as e:
                # O nó falhou. O passo falho é GRAVADO (antes a timeline pulava do
                # último passo bom direto para "falhou", sem dizer onde) e, se o nó
                # tem uma saída de ERRO desenhada, o fluxo segue por ela levando a
                # mensagem — a falha vira um caminho, não o fim da execução.
                finalizado_em = datetime.now(timezone.utc)
                passo_falho = _montar_passo(
                    no_atual, tipo, gate, agente_id=id_agente,
                    agente_nome=nome_do_no,
                    entrada=entrada_atual, saida=f"Falhou: {e}",
                    instrumentos=[], erros_instrumentos=[], uso=[],
                    escolhidas=[], motivo=None, iniciado_em=iniciado_em,
                    finalizado_em=finalizado_em, estado="falhou", erro=str(e),
                )
                passos.append(passo_falho)
                if registrar_passo is not None:
                    registrar_passo(passo_falho, ordem)
                if not saidas_erro:
                    raise
                texto_erro = (
                    f"O passo anterior ('{passo_falho['agente_nome']}') falhou.\n"
                    f"Erro: {e}\n\nEntrada que ele recebeu:\n{entrada_atual}"
                )
                for s in saidas_erro:
                    _seguir(idx, proxima, resultados, s, [texto_erro])
                continue

            finalizado_em = datetime.now(timezone.utc)
            saida_texto = executado["saida"]
            uso_passo = executado["uso"]

            # Portão de aprovação: o que segue adiante é o que foi APRESENTADO ao
            # humano — a(s) mensagem(ns) que o agente enviou pelo canal de aprovação
            # do nó (ou, na falta, qualquer canal usado no turno) — e NÃO o status
            # que ele narrou depois ("enviei, aguardando"). Sem isto o conteúdo
            # aprovado se perde. Portão só de tela (sem envio): mantém o texto.
            if gate and executado["mensagens_enviadas"]:
                canal_id = str((no.get("aprovacao") or {}).get("instrumento_id") or "")
                apresentadas = executado["mensagens_enviadas"].get(canal_id) or [
                    t
                    for textos in executado["mensagens_enviadas"].values()
                    for t in textos
                ]
                if apresentadas:
                    saida_texto = "\n\n".join(apresentadas)

            # --- A decisão de caminho -------------------------------------------
            # Com gate, quem escolhe é a pessoa (na retomada) — aqui não se decide.
            escolhidas: list[dict] = []
            motivo = executado["motivo"]
            aviso: str | None = None
            if not gate:
                if len(condicionais) == 1:
                    escolhidas = list(condicionais)
                elif len(condicionais) >= 2:
                    por_rotulo = {s["rotulo"]: s for s in condicionais if s.get("rotulo")}
                    declarados = [r for r in executado["ramos"] if r in por_rotulo]
                    if declarados:
                        escolhidas = [por_rotulo[r] for r in declarados]
                    else:
                        # O agente não declarou (ou declarou rótulo inexistente):
                        # a LLM roteadora lê as condições. Pode devolver várias — e
                        # pode devolver nenhuma, que agora é resposta legítima.
                        escolhidas, uso_rot = _rotear_por_llm(saida_texto, condicionais)
                        uso_passo.append(uso_rot)
                if not escolhidas and saidas_senao:
                    escolhidas = list(saidas_senao)
                    motivo = motivo or "nenhuma condição foi atendida"
                if not escolhidas:
                    # NUNCA mais escolha silenciosa: o ramo termina aqui e o motivo
                    # fica no rastro (antes caía calado na primeira saída).
                    nome_no = no.get("nome") or no_atual
                    aviso = (
                        f"O passo '{nome_no}' terminou sem seguir por nenhum caminho: "
                        + (
                            "ele não tem saída ligada."
                            if not condicionais
                            else "nenhuma das condições das saídas foi atendida e não "
                            "há saída 'se nenhuma das outras'."
                        )
                    )
                    avisos.append(aviso)

            passo = _montar_passo(
                no_atual, tipo, gate,
                agente_id=executado["agente_id"], agente_nome=executado["agente_nome"],
                entrada=entrada_atual, saida=saida_texto,
                instrumentos=executado["instrumentos"],
                erros_instrumentos=executado["erros_instrumentos"],
                uso=uso_passo, escolhidas=escolhidas, motivo=motivo,
                iniciado_em=iniciado_em, finalizado_em=finalizado_em,
                aviso=aviso,
            )
            passos.append(passo)
            if registrar_passo is not None:
                registrar_passo(passo, ordem)

            # Pausa para humano: o nó terminou (sua saída é a pergunta/proposta).
            # Para aqui; o caminho é decidido pela resposta. As PENDÊNCIAS (ramos
            # desta onda que ainda não rodaram + os já liberados) vão junto, para a
            # retomada continuar sem perder trabalho.
            if gate:
                pendentes = [
                    {"no": i["no"], "entradas": list(i["entradas"])}
                    for i in onda[pos + 1 :]
                ] + _como_itens(proxima)
                return {
                    "estado": "aguardando_humano",
                    "pergunta": saida_texto,
                    "no_pausado": no_atual,
                    "pendentes": pendentes,
                    "ordem": ordem,
                    "passos": passos,
                    "avisos": avisos,
                }

            if not escolhidas:
                resultados.append(saida_texto)
                continue
            for s in escolhidas:
                _seguir(idx, proxima, resultados, s, [saida_texto])

        onda = _como_itens(proxima)

    return {
        "estado": "concluida",
        "resultado": SEPARADOR_JUNCAO.join(resultados) if resultados else "",
        "avisos": avisos,
        "ordem": ordem,
        "passos": passos,
    }


def _seguir(idx, proxima: dict, resultados: list[str], saida: dict, textos: list[str]) -> None:
    """Encaminha os textos pela saída: destino que encerra vira resultado; senão,
    entra na próxima onda."""
    destino = saida.get("destino")
    if destino is None or idx.eh_fim(destino):
        resultados.extend(textos)
    else:
        _empilhar(proxima, destino, textos)


def _identidade_do_no(sessao: Session, no: dict, tipo: str) -> tuple[str | None, str]:
    """(id do agente, nome legível) de um nó, resolvidos SEM rodar nada. Um nó de
    agente cujo `ref` não existe mais devolve o id mesmo assim: o passo falho aponta
    para o agente que sumiu, que é exatamente a informação útil."""
    if tipo != "agente":
        return None, (no.get("nome") or "roteador")
    ref = no.get("ref")
    if not ref:
        return None, (no.get("nome") or "passo sem agente")
    agente = sessao.get(Agente, uuid.UUID(str(ref)))
    return str(ref), (agente.nome if agente else "(agente removido)")


def _rodar_no(
    sessao: Session,
    no: dict,
    no_id: str,
    tipo: str,
    entrada_atual: str,
    *,
    condicionais: list[dict],
    gate: bool,
) -> dict:
    """Roda UM nó (agente ou roteador) e devolve o que ele produziu, já num formato
    uniforme. Não decide caminho — isso é do chamador."""
    if tipo == "roteador":
        # Roteador: não roda agente nem produz conteúdo — só classifica a entrada
        # sobre as suas saídas e segue. A entrada passa adiante intacta.
        return {
            "saida": entrada_atual, "agente_id": None,
            "agente_nome": no.get("nome") or "roteador",
            "instrumentos": [], "erros_instrumentos": [], "uso": [],
            "mensagens_enviadas": {}, "ramos": [], "motivo": None,
        }

    ref = no.get("ref")
    agente = sessao.get(Agente, uuid.UUID(str(ref))) if ref else None
    if agente is None:
        raise ValueError(
            f"O nó '{no_id}' aponta para um agente que não existe mais "
            f"(ref {ref}). Edite a automação e troque ou remova esse passo."
        )
    cinto = _carregar_cinto(sessao, agente.id)
    # O agente enxerga as saídas CONDICIONAIS (não as de erro/"senão", que são do
    # motor) e DECLARA por quais o fluxo segue — podendo declarar VÁRIAS. Num
    # portão, as instruções de ABERTURA do nó (o "portao.md") guiam como ele
    # apresenta o pedido — aditivo, com fallback ao texto padrão.
    texto_portao = (no.get("instrucoes") or {}).get("abertura") if gate else None
    resultado = executar_agente(
        agente, cinto, entrada_atual, saidas=condicionais, gate=gate,
        texto_portao=texto_portao,
    )
    return {
        "saida": resultado["saida"],
        "agente_id": str(agente.id),
        "agente_nome": agente.nome,
        "instrumentos": resultado["instrumentos_acionados"],
        "erros_instrumentos": resultado.get("erros_instrumentos") or [],
        "uso": list(resultado.get("uso") or []),
        "mensagens_enviadas": resultado.get("mensagens_enviadas") or {},
        # `ramos_escolhidos` é a lista (fan-out); `ramo_escolhido` (singular) segue
        # aceito para quem ainda devolve um caminho só.
        "ramos": list(resultado.get("ramos_escolhidos") or [])
        or ([resultado["ramo_escolhido"]] if resultado.get("ramo_escolhido") else []),
        "motivo": resultado.get("motivo_ramo"),
    }


def _montar_passo(
    no_id: str, tipo: str, gate: bool, *, agente_id, agente_nome, entrada, saida,
    instrumentos, erros_instrumentos, uso, escolhidas: list[dict], motivo,
    iniciado_em, finalizado_em, estado: str = "concluido", erro: str | None = None,
    aviso: str | None = None,
) -> dict:
    """O registro de um passo, no formato que `disparo._fazer_registrador` grava."""
    return {
        "no_id": no_id,
        # Tipo do passo na timeline (Fatia 4.1): o nó de PORTÃO é uma espera por
        # humano; os demais, agente ou roteador.
        "tipo": "espera_humano" if gate else ("roteador" if tipo == "roteador" else "agente"),
        "agente_id": agente_id,
        "agente_nome": agente_nome,
        "entrada": entrada,
        "saida": saida,
        "instrumentos_acionados": instrumentos,
        "erros_instrumentos": erros_instrumentos,
        # Retrocompat: `saida_escolhida` (singular) segue sendo o primeiro caminho.
        # `saidas_escolhidas` é a verdade nova — o fluxo pode seguir por vários.
        "saida_escolhida": escolhidas[0]["rotulo"] if escolhidas else None,
        "saidas_escolhidas": [s["rotulo"] for s in escolhidas],
        "motivo_ramo": motivo,
        "aviso": aviso,
        "estado": estado,
        "erro": erro,
        "uso": uso,
        "iniciado_em": iniciado_em,
        "finalizado_em": finalizado_em,
    }
