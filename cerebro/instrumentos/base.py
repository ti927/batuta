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
    # CATEGORIA: grupo do instrumento no catálogo (a UI agrupa o dropdown por isto,
    # ex.: "Instagram", "Web (busca e leitura)"). Padrão "Outros".
    categoria: str = "Outros"
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
    # dele. Este é o BASELINE do tipo; a irreversibilidade REAL pode depender da
    # configuração da instância (ver `irreversivel_para`). O padrão é False (só
    # lê / só gera artefato local).
    acao_irreversivel: bool = False
    # CHAVE DE SERVIÇO COMPARTILHADA: alguns instrumentos consomem um serviço cuja
    # chave a organização já cadastra em "Chaves de IA" (ex.: gerar_imagem usa a
    # chave OpenAI; busca_web, a Tavily). Em vez de pedir a chave de novo no cofre
    # do instrumento, ela é REUSADA do pool da organização (queda org→consultoria).
    # Declara `(campo_secreto, servico)`: se o campo próprio estiver vazio, a borda
    # injeta a chave do pool. None = o instrumento não reusa chave compartilhada.
    chave_compartilhada: tuple[str, str] | None = None
    # CAIXA-FORTE DE CREDENCIAIS: tipos de credencial nomeada (ver
    # `tipos_credencial.py`) que esta instância pode REFERENCIAR via
    # `instrumentos.credencial_id`, em vez de guardar o segredo inline. Filtra o
    # seletor "usar uma credencial da central" na UI. Vazio = o instrumento não
    # aceita credencial da central (usa segredo inline próprio / pool, como antes).
    tipos_credencial_aceitos: tuple[str, ...] = ()
    # MENSAGEM APRESENTADA A UM HUMANO: o nome do campo do `Args` cujo valor é o
    # texto que uma pessoa lê quando o agente aciona este instrumento (ex.: um
    # canal de mensageria). Usado pelo portão de aprovação para carregar adiante
    # EXATAMENTE o que foi apresentado ao humano (e não o status que o agente
    # narra depois). None = o instrumento não apresenta mensagem a humano.
    campo_mensagem: str | None = None

    def irreversivel_para(self, configuracao: dict) -> bool:
        """Se ESTA instância (com esta configuração) faz ação irreversível.

        O padrão devolve o baseline do tipo. Tipos cuja config decide leitura vs
        escrita sobrescrevem: REST deriva do `metodo` (GET lê, POST/PUT/DELETE
        escreve); SQL, do `somente_leitura`. É o que evita exigir portão de
        aprovação para uma simples consulta."""
        return self.acao_irreversivel

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

    def dependencias_ui(self) -> dict | None:
        """Campos do formulário cujas OPÇÕES dependem do valor de outro campo
        (dropdown dependente), para a UI nunca oferecer uma combinação que a API
        recusaria. Formato:

            {campo_dependente: {"controlado_por": <campo>,
                                "opcoes": {<valor do controlador>: [opções...]}}}

        O `enum` do campo (no `esquema_config`) continua sendo a UNIÃO de todas as
        opções (validação no backend); este mapa só FILTRA o que a tela mostra
        conforme o controlador. `None` = o tipo não tem campos dependentes (padrão).
        Ex.: `gerar_imagem` filtra tamanho/qualidade pelo modelo escolhido."""
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


def acao_irreversivel(tipo: str, configuracao: dict | None = None) -> bool:
    """Se um instrumento faz ação irreversível, JÁ considerando a configuração
    (tipo desconhecido = False). Sem `configuracao`, cai no baseline do tipo —
    mas o correto é sempre passar a config da instância (REST lê do método, SQL
    do somente_leitura). Base da parede de ativação."""
    t = obter_tipo(tipo)
    if t is None:
        return False
    return bool(t.irreversivel_para(configuracao or {}))


def exige_portao(
    tipo: str, configuracao: dict | None, exige_aprovacao: bool | None
) -> bool:
    """Resolução FINAL: este instrumento exige portão de aprovação humana antes?

    O interruptor da instância manda: `True` força portão, `False` dispensa
    (mesmo numa escrita — guard-rail é o aviso na UI + auditoria). `None` =
    automático: deriva do tipo + config (`acao_irreversivel`)."""
    if exige_aprovacao is not None:
        return bool(exige_aprovacao)
    return acao_irreversivel(tipo, configuracao)


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
