"""Qual IA faz o trabalho nos instrumentos "por capacidade" (pesquisar na web, ler
página, ler documento, gerar arquivo) — 2026-10-02.

A escolha é o MODELO, no mesmo seletor do agente (agrupado por empresa e só com as
empresas que têm chave na organização). A empresa sai do modelo. Em branco, o
Batuta escolhe: o padrão da Anthropic se a organização tem a chave dela; senão, o da
OpenAI. Assim um instrumento criado numa organização que só tem a chave da OpenAI
funciona sem ninguém mexer no campo.
"""

from typing import Any

from pydantic import Field

from instrumentos import anthropic_servidor as anthropic_srv
from instrumentos import openai_servidor as openai_srv
from orquestracao import ciclo_modelos
from orquestracao.llm import chaves_atuais

PROVEDORES = ("anthropic", "openai")


def modelos() -> list[str]:
    """Todos os modelos que se podem escolher (a lista que o formulário filtra)."""
    return anthropic_srv.modelos_disponiveis() + openai_srv.modelos_disponiveis()


def campo_modelo(descricao: str) -> Any:
    """O campo `modelo` da configuração: em branco = o Batuta escolhe."""
    return Field(
        default="", title="Modelo da IA", description=descricao,
        json_schema_extra={"enum": ["", *modelos()], "ui": "modelo_ia", "provedores": list(PROVEDORES)},
    )


def provedor(modelo: str) -> str:
    registro = ciclo_modelos.obter(modelo)
    return registro.provedor if registro else "anthropic"


def validar(modelo: str, para_que: str) -> None:
    if modelo and modelo not in modelos():
        raise ValueError(f"Modelo indisponível para {para_que}: {modelo}.")


def de_provedor_antigo(dados: Any, padroes: dict[str, str]) -> Any:
    """Configuração com o campo antigo `provedor` (até 2026-10-02) e sem modelo: vale o
    padrão daquela IA. Uma IA externa que ainda mande `provedor: openai` é atendida."""
    if isinstance(dados, dict) and "provedor" in dados:
        dados = dict(dados)
        antigo = dados.pop("provedor")
        if not dados.get("modelo") and antigo in padroes:
            dados["modelo"] = padroes[antigo]
    return dados


def resolver(modelo: str, padroes: dict[str, str]) -> str:
    """O modelo que de fato roda. `padroes` = {provedor: modelo padrão}."""
    if modelo:
        return modelo
    chaves = chaves_atuais()
    for p in PROVEDORES:
        if chaves.get(p):
            return padroes[p]
    # Sem chave no pool: a Anthropic ainda cai na chave do ambiente (a da consultoria);
    # sem ela também, a chamada falha com o recado de "sem chave".
    return padroes["anthropic"]
