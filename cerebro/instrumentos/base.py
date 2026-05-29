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

from abc import ABC, abstractmethod

from pydantic import BaseModel


class TipoInstrumento(ABC):
    """Contrato comum a todo tipo de instrumento."""

    tipo: str
    nome_exibicao: str
    descricao: str
    Config: type[BaseModel]
    Args: type[BaseModel]

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
