"""O contrato e o registro de tipos de instrumento (o encaixe).

Cada tipo de instrumento é uma subclasse de `TipoInstrumento` que declara:
- `tipo`: identificador estável, usado no banco (coluna `instrumentos.tipo`);
- `nome_exibicao` e `descricao`: para o humano e para a IA;
- `Config`: o formato da configuração fixa (preenchida por quem monta o agente);
- `Args`: o formato dos argumentos que a IA passa ao acionar o instrumento;
- `executar(config, args)`: roda e devolve um resultado serializável.

A configuração é validada contra `Config`; é isso que torna o JSONB flexível
sem virar caos. A `definicao_para_ia()` produz a descrição no formato de
"ferramenta" que a Fase 4 entregará à LLM.
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel

# Política de retentativa de um instrumento (PRODUTO §16, Tarefa 5.1).
# 3 tentativas no total, com intervalo crescente (backoff) entre elas.
TENTATIVAS = 3
BACKOFF_S = [1, 2, 4]  # espera ANTES de cada nova tentativa; com 3 tentativas usa 1s, 2s


class FalhaInstrumento(Exception):
    """Um instrumento não conseguiu operar (o sistema externo caiu, não
    respondeu, a rede oscilou, a chave expirou). Diferente de uma resposta
    legítima de "não" (ex.: 404), que volta ao agente como dado.

    `retentavel` diz se vale tentar de novo: oscilações de rede e erros de
    servidor (5xx/429) são retentáveis; falhas de autenticação (chave expirada)
    não são — tentar de novo não resolve.
    """

    def __init__(self, mensagem: str, *, retentavel: bool = True):
        super().__init__(mensagem)
        self.retentavel = retentavel


def acionar_com_retentativa(
    tipo: "TipoInstrumento",
    config: BaseModel,
    args: BaseModel,
    *,
    dormir: Callable[[float], None] = time.sleep,
) -> dict:
    """Aciona um instrumento, retentando falhas transitórias com backoff.

    Em `FalhaInstrumento` retentável, espera e tenta de novo até `TENTATIVAS`.
    Se esgotar (ou se a falha não for retentável), repropaga a `FalhaInstrumento`
    — quem chama decide o que fazer (na orquestração, vira falha visível).
    `dormir` é injetável para os testes não esperarem de verdade.
    """
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            return tipo.executar(config, args)
        except FalhaInstrumento as e:
            if not e.retentavel or tentativa == TENTATIVAS:
                raise
            dormir(BACKOFF_S[tentativa - 1])


class TipoInstrumento(ABC):
    """Contrato comum a todo tipo de instrumento."""

    tipo: str
    nome_exibicao: str
    descricao: str
    Config: type[BaseModel]
    Args: type[BaseModel]
    # Campos da Config que são SEGREDOS (Fase 7-B): em vez de irem para a
    # `instrumentos.configuracao` (JSONB em claro), são cifrados no cofre de
    # segredos do instrumento e injetados só na execução. Top-level, string.
    campos_secretos: tuple[str, ...] = ()
    # AÇÃO IRREVERSÍVEL: o instrumento age no mundo externo de forma que não dá
    # para desfazer (publicar, enviar, gravar em sistema de terceiros). É a base
    # da parede de ativação: um agente com instrumento irreversível só pode ser
    # ATIVADO se a cadeia tiver portão de aprovação humana (pausa_humano) antes
    # dele. O padrão é False (só lê / só gera artefato local).
    acao_irreversivel: bool = False

    @abstractmethod
    def executar(self, config: BaseModel, args: BaseModel) -> dict:
        """Executa o instrumento já com config e args validados.

        `config` é uma instância de `self.Config`; `args`, de `self.Args`.
        Devolve um dicionário serializável (vira o resultado do passo).
        """

    def definicao_para_ia(self) -> dict:
        """Descrição do instrumento no formato de ferramenta para a LLM.

        O esquema dos argumentos sai do `Args` (JSON Schema). A Fase 4 usa isto
        para oferecer o instrumento ao modelo.
        """
        return {
            "nome": self.tipo,
            "descricao": self.descricao,
            "parametros": self.Args.model_json_schema(),
        }

    def expandir_ferramentas(self, config: BaseModel) -> list | None:
        """Instrumentos MULTI-FERRAMENTA (Fase adicional/MCP): um único
        instrumento que expõe VÁRIAS ferramentas à IA (ex.: todas as ferramentas
        de um servidor MCP). Quando devolve uma lista, a orquestração usa essas
        ferramentas no lugar da ferramenta única derivada de `executar`.

        O padrão é `None`: o instrumento é de ferramenta única (o caso comum),
        e a orquestração segue pelo `executar`."""
        return None


_REGISTRO: dict[str, TipoInstrumento] = {}


def registrar(instancia: TipoInstrumento) -> None:
    """Registra um tipo de instrumento. Chamado pelos módulos de cada tipo."""
    _REGISTRO[instancia.tipo] = instancia


def obter_tipo(tipo: str) -> TipoInstrumento | None:
    return _REGISTRO.get(tipo)


def tipos_disponiveis() -> list[TipoInstrumento]:
    return list(_REGISTRO.values())


def validar_configuracao(tipo: str, configuracao: dict | None) -> dict:
    """Valida a configuração contra o esquema do tipo e devolve a forma limpa.

    Levanta `ValueError` se o tipo é desconhecido ou a configuração é inválida.
    """
    t = obter_tipo(tipo)
    if t is None:
        raise ValueError(f"Tipo de instrumento desconhecido: {tipo!r}")
    return t.Config.model_validate(configuracao or {}).model_dump()


def campos_secretos(tipo: str) -> tuple[str, ...]:
    """Os campos secretos de um tipo (vazio se o tipo não tem segredos)."""
    t = obter_tipo(tipo)
    return tuple(getattr(t, "campos_secretos", ()) or ()) if t else ()


def acao_irreversivel(tipo: str) -> bool:
    """Se um tipo de instrumento faz ação irreversível (tipo desconhecido = False).
    Base da parede de ativação (portão humano antes de agente irreversível)."""
    t = obter_tipo(tipo)
    return bool(getattr(t, "acao_irreversivel", False)) if t else False


def preparar_config(tipo: str, configuracao: dict | None) -> tuple[dict, dict]:
    """Valida a config e SEPARA os segredos (Fase 7-B). Devolve
    `(config_publica, segredos)`:
    - `config_publica`: a configuração validada SEM os campos secretos — é o que
      vai para `instrumentos.configuracao` (JSONB em claro).
    - `segredos`: {campo: valor} só com os campos secretos REALMENTE informados
      (presentes e não-vazios) na entrada — é o que será cifrado no cofre. Campo
      secreto omitido ou vazio não entra (na edição, preserva o valor atual).

    Levanta `ValueError` se o tipo é desconhecido ou a configuração é inválida.
    """
    t = obter_tipo(tipo)
    if t is None:
        raise ValueError(f"Tipo de instrumento desconhecido: {tipo!r}")
    secretos = set(t.campos_secretos)
    bruta = dict(configuracao or {})
    segredos = {
        campo: str(bruta[campo])
        for campo in secretos
        if campo in bruta and str(bruta[campo]).strip()
    }
    # Valida a config inteira (segredos são campos opcionais do Config) para
    # pegar erros de tipo, mas guarda só a parte pública.
    config_publica = t.Config.model_validate(bruta).model_dump()
    for campo in secretos:
        config_publica.pop(campo, None)
    return config_publica, segredos
