"""As regras do gatilho WEBHOOK de uma automação — peça genérica, sem fornecedor.

Um serviço de fora (um ERP, uma rede social, um gateway de pagamento) avisa o Batuta
chamando `POST /webhooks/automacoes/{id}`. Serviços sérios avisam assim:

- **assinam** o corpo com um segredo combinado (HMAC-SHA256 em hexadecimal, num
  cabeçalho `X-…-Signature`), para ninguém mais conseguir disparar a automação;
- entregam **pelo menos uma vez**: o mesmo aviso pode chegar de novo, com o mesmo id
  (num cabeçalho `X-…-Event-Id` / `X-…-Delivery`, ou no campo `id` do corpo);
- mandam **vários tipos** de aviso para o mesmo endereço (o nome vem no campo
  `event`/`type` do corpo ou num cabeçalho `X-…-Event`);
- avisam também do que **a própria conta** fez (a resposta que o agente publicou
  volta como "comentário novo") — sem filtro, o agente responde a si mesmo em loop.

Este módulo é puro (sem banco): a rota (`rotas/webhooks.py`) aplica as regras na
ordem assinatura → filtros → repetido → teto. Configuração, em `configuracao_gatilho`:

    {"evento": "comment.received",            # só dispara para este tipo de aviso
     "so_quando":  [{"campo": "a.b", "valor": x}],   # todos precisam casar
     "nunca_quando": [{"campo": "a.b", "valor": x}], # qualquer um casando = ignora
     "teto_por_hora": 50,                     # 0/ausente = sem teto
     "cabecalho_assinatura": "X-Foo-Signature"}  # opcional; sem ele, descobre sozinho

O segredo NÃO mora aí (coluna cifrada em `automacoes`, ver `modelos.Automacao`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

# Chaves que, com valor verdadeiro em qualquer ponto do corpo, marcam um aviso sobre
# algo que a PRÓPRIA conta fez (eco). Nomes usados pelos serviços para isso.
_CHAVES_DE_ECO = {"isownaccount", "is_own_account", "is_echo", "isecho", "from_self"}

# Cabeçalhos com o id do aviso, em ordem de preferência (comparação sem maiúsculas).
_SUFIXOS_ID = ("-event-id", "-delivery", "-delivery-id", "-webhook-id")
_CABECALHOS_ID = ("idempotency-key", "webhook-id")


def ler_json(corpo: bytes) -> Any:
    """O corpo como JSON, ou None se não for JSON."""
    try:
        return json.loads(corpo.decode("utf-8", errors="replace") or "null")
    except json.JSONDecodeError:
        return None


# ─────────────────────────────── assinatura ────────────────────────────────


def cabecalho_da_assinatura(cabecalhos: dict[str, str], nome: str | None) -> str | None:
    """O valor da assinatura: o cabeçalho configurado, ou o primeiro `…-signature`
    (ou `…-signature-256`) que vier."""
    minusculos = {k.lower(): v for k, v in cabecalhos.items()}
    if nome:
        return minusculos.get(nome.lower())
    for chave, valor in minusculos.items():
        if chave.endswith("-signature") or chave.endswith("-signature-256"):
            return valor
    return None


def assinatura_confere(corpo: bytes, segredo: str, assinatura: str | None) -> bool:
    """HMAC-SHA256 do corpo CRU com o segredo, em hexadecimal. Aceita o prefixo
    `sha256=` (formato de alguns serviços). Comparação em tempo constante."""
    if not assinatura or not segredo:
        return False
    recebida = assinatura.strip()
    if recebida.lower().startswith("sha256="):
        recebida = recebida[len("sha256="):]
    esperada = hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada.lower(), recebida.lower())


# ───────────────────────────── id e nome do aviso ───────────────────────────


def id_do_evento(cabecalhos: dict[str, str], dados: Any, corpo: bytes) -> str:
    """O id que o serviço deu a este aviso — a chave para reconhecer a reentrega.
    Sem nenhum, o hash do corpo (o mesmo corpo repetido é o mesmo aviso)."""
    minusculos = {k.lower(): v for k, v in cabecalhos.items()}
    for chave, valor in minusculos.items():
        if valor and (chave in _CABECALHOS_ID or chave.endswith(_SUFIXOS_ID)):
            return str(valor)[:200]
    if isinstance(dados, dict) and isinstance(dados.get("id"), (str, int)):
        return str(dados["id"])[:200]
    return "sha256:" + hashlib.sha256(corpo).hexdigest()


def nome_do_evento(cabecalhos: dict[str, str], dados: Any) -> str | None:
    """O tipo do aviso: campo `event`/`type` do corpo, ou cabeçalho `X-…-Event`."""
    if isinstance(dados, dict):
        for chave in ("event", "type", "event_type", "evento"):
            if isinstance(dados.get(chave), str):
                return dados[chave]
    for chave, valor in cabecalhos.items():
        if chave.lower().endswith("-event") and valor:
            return valor
    return None


# ──────────────────────────────── filtros ──────────────────────────────────


def valor_no_caminho(dados: Any, caminho: str) -> tuple[bool, Any]:
    """(achou, valor) de um campo pelo caminho com pontos: `comment.author.id`."""
    atual = dados
    for parte in (caminho or "").split("."):
        if isinstance(atual, dict) and parte in atual:
            atual = atual[parte]
        elif isinstance(atual, list) and parte.isdigit() and int(parte) < len(atual):
            atual = atual[int(parte)]
        else:
            return False, None
    return True, atual


def _igual(achado: Any, esperado: Any) -> bool:
    """Compara sem se prender a tipo: `true` casa com True, `"123"` com 123."""
    def norm(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v).strip().lower()

    return norm(achado) == norm(esperado)


def _casa(dados: Any, regra: dict) -> bool:
    achou, valor = valor_no_caminho(dados, str(regra.get("campo", "")))
    return achou and _igual(valor, regra.get("valor"))


def eh_eco(dados: Any) -> bool:
    """O aviso é sobre algo que a PRÓPRIA conta fez? (anti-loop, sempre ligado)"""
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if chave.lower() in _CHAVES_DE_ECO and valor is True:
                return True
            if eh_eco(valor):
                return True
    elif isinstance(dados, list):
        return any(eh_eco(v) for v in dados)
    return False


def motivo_para_ignorar(
    cfg: dict, cabecalhos: dict[str, str], dados: Any
) -> str | None:
    """Por que este aviso NÃO dispara a automação (None = dispara). O texto volta ao
    serviço na resposta (200) e vai para o banco de logs."""
    esperado = str(cfg.get("evento") or "").strip()
    if esperado:
        recebido = nome_do_evento(cabecalhos, dados)
        if not recebido or recebido.strip().lower() != esperado.lower():
            return f"evento '{recebido or '(sem nome)'}' não é '{esperado}'"
    if eh_eco(dados):
        return "aviso sobre algo que a própria conta fez"
    for regra in cfg.get("so_quando") or []:
        if isinstance(regra, dict) and not _casa(dados, regra):
            return f"'{regra.get('campo')}' não é '{regra.get('valor')}'"
    for regra in cfg.get("nunca_quando") or []:
        if isinstance(regra, dict) and _casa(dados, regra):
            return f"'{regra.get('campo')}' é '{regra.get('valor')}'"
    return None


def teto_por_hora(cfg: dict) -> int | None:
    """O teto de disparos/hora do gatilho; None = sem teto."""
    try:
        v = int(cfg.get("teto_por_hora") or 0)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def separar_segredo(cfg: dict | None) -> tuple[dict, str | None, bool]:
    """Tira da config do gatilho o que NÃO pode ficar nela: o segredo (campo só de
    escrita da tela) e o pedido de apagá-lo. Devolve (config limpa, segredo novo ou
    None = manter o atual, apagar?)."""
    limpa = dict(cfg or {})
    segredo = str(limpa.pop("segredo", "") or "").strip() or None
    apagar = bool(limpa.pop("remover_segredo", False))
    return limpa, segredo, apagar


def extrair_entrada(corpo: bytes, dados: Any) -> str:
    """O texto que vira a entrada do fluxo: o campo `entrada`, se houver; senão, o
    corpo inteiro."""
    if isinstance(dados, dict) and isinstance(dados.get("entrada"), str):
        return dados["entrada"]
    return corpo.decode("utf-8", errors="replace").strip()
