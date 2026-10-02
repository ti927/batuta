"""Registro de modelos de IA e seus provedores (Fase 7-A).

Fonte da verdade de qual PROVEDOR (anthropic/openai/google) atende cada modelo.
É consumida pelo motor (para construir o cliente certo e pegar a chave do
provedor) e espelhada na interface (lista de modelos por provedor no seletor do
agente). O `modelo_ia` do agente continua sendo uma string livre; aqui só
mapeamos string → provedor, com inferência por prefixo para modelos não listados.
"""

from orquestracao import ciclo_modelos

PROVEDOR_ANTHROPIC = "anthropic"
PROVEDOR_OPENAI = "openai"
PROVEDOR_GOOGLE = "google"

# Provedores suportados pelo motor nesta fase (ordem = ordem de resolução).
PROVEDORES = (PROVEDOR_ANTHROPIC, PROVEDOR_OPENAI, PROVEDOR_GOOGLE)

# Modelos que se podem ESCOLHER, por provedor — saem do registro de ciclo de vida
# (`ciclo_modelos`, fonte única com a data de saída de cada um). Os já desligados
# ficam de fora da escolha, mas continuam resolvendo o provedor (abaixo), para um
# agente antigo falhar com o recado certo, não com "provedor desconhecido".
MODELOS_POR_PROVEDOR: dict[str, list[str]] = {
    p: ciclo_modelos.modelos(ciclo_modelos.TEXTO, p) for p in PROVEDORES
}

_PROVEDOR_POR_MODELO = {
    nome: m.provedor
    for m in ciclo_modelos.REGISTRO
    if m.uso == ciclo_modelos.TEXTO
    for nome in (m.id, *m.apelidos)
}

# Prefixos para inferir o provedor de um modelo não listado explicitamente.
_PREFIXOS = (
    ("claude", PROVEDOR_ANTHROPIC),
    ("gpt", PROVEDOR_OPENAI),
    ("o1", PROVEDOR_OPENAI),
    ("o3", PROVEDOR_OPENAI),
    ("o4", PROVEDOR_OPENAI),
    ("gemini", PROVEDOR_GOOGLE),
)


def provedor_do_modelo(modelo: str) -> str:
    """O provedor de um modelo. Usa a lista conhecida e, para modelos novos,
    infere pelo prefixo. Levanta ValueError se não der para determinar — assim
    um modelo digitado errado falha de forma clara, não vira chamada ao provedor
    errado."""
    if modelo in _PROVEDOR_POR_MODELO:
        return _PROVEDOR_POR_MODELO[modelo]
    m = (modelo or "").lower()
    for prefixo, provedor in _PREFIXOS:
        if m.startswith(prefixo):
            return provedor
    raise ValueError(
        f"Não foi possível determinar o provedor do modelo de IA '{modelo}'."
    )


def provedor_do_modelo_seguro(modelo: str) -> str | None:
    """Como `provedor_do_modelo`, mas devolve None em vez de levantar — para
    quem só quer rotular (ex.: a medição por origem) sem quebrar."""
    try:
        return provedor_do_modelo(modelo)
    except ValueError:
        return None
