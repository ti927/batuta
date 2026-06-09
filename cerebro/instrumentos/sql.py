"""Instrumento "Banco de dados direto (SQL)" (PRODUTO §13; Fase adicional).

Dá ao agente acesso a um banco SQL de um sistema que não tem API — ler e
escrever. A configuração traz os dados de conexão (host/porta/banco/usuário
públicos); a SENHA é um SEGREDO (cofre da Fase 7-B). A IA passa o comando SQL e,
de preferência, parâmetros nomeados (`:nome`), que evitam injeção.

Política de falha do encaixe (Tarefa 5.1): falha de CONEXÃO (banco fora do ar)
é falha do instrumento (retentável); um erro de SQL (query ruim, violação de
constraint) NÃO é falha do instrumento — volta à IA como dado, para ela corrigir.

Nesta fase só PostgreSQL (driver `psycopg`, já usado pelo cérebro); o campo
`tipo_banco` fica pronto para outros bancos no futuro. Conexão por chamada
(NullPool), sempre encerrada.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

# Teto de linhas devolvidas num SELECT — evita estourar memória/contexto.
MAX_LINHAS = 100
TIMEOUT_S = 10

# tipo_banco → dialeto/driver do SQLAlchemy. Só PostgreSQL por ora.
_DRIVER = {"postgres": "postgresql+psycopg"}

# Para o modo "somente leitura": o comando precisa COMEÇAR com uma palavra de
# leitura E não conter NENHUMA palavra de escrita (pega até CTE do tipo
# `WITH x AS (...) DELETE ...`). Uma instrução só (sem `;` no meio).
_INICIO_LEITURA = {"SELECT", "WITH", "EXPLAIN", "SHOW", "VALUES", "TABLE"}
_PALAVRAS_ESCRITA = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "MERGE", "CALL", "COPY", "REPLACE", "UPSERT", "COMMENT",
}


def _sem_comentarios(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)  # /* ... */
    sql = re.sub(r"--[^\n]*", " ", sql)  # -- até o fim da linha
    return sql


def eh_leitura(sql: str) -> bool:
    """True se o SQL é uma CONSULTA (não muda dados). Conservador: na dúvida, False."""
    limpo = _sem_comentarios(sql).strip().rstrip(";").strip()
    if not limpo or ";" in limpo:  # vazio ou múltiplas instruções
        return False
    tokens = re.findall(r"[A-Za-z_]+", limpo.upper())
    if not tokens or tokens[0] not in _INICIO_LEITURA:
        return False
    return not (_PALAVRAS_ESCRITA & set(tokens))


class ConfigSQL(BaseModel):
    """Dados de conexão. A `senha` é SEGREDO (cofre 7-B); o resto é público."""

    tipo_banco: Literal["postgres"] = Field(
        default="postgres", description="Tipo do banco (por ora, PostgreSQL)."
    )
    host: str = Field(min_length=1, description="Endereço do servidor de banco.")
    porta: int = Field(default=5432, description="Porta do banco.")
    banco: str = Field(min_length=1, description="Nome do banco de dados.")
    usuario: str = Field(min_length=1, description="Usuário do banco.")
    senha: str = Field(default="", description="Senha do banco (segredo).")
    ssl: Literal["require", "prefer", "disable"] = Field(
        default="prefer", description="Modo de SSL da conexão (sslmode)."
    )
    somente_leitura: bool = Field(
        default=False,
        description=(
            "Se verdadeiro, o instrumento SÓ executa consultas (SELECT) e recusa "
            "escrita — e, por ser seguro, não exige portão de aprovação humana."
        ),
    )


class ArgsSQL(BaseModel):
    """O que a IA passa ao acionar: o SQL e (de preferência) seus parâmetros."""

    sql: str = Field(min_length=1, description="Comando SQL. Use :nome para parâmetros.")
    parametros: dict[str, Any] = Field(
        default_factory=dict,
        description="Valores dos parâmetros nomeados do SQL (evita injeção).",
    )


class BancoSQL(TipoInstrumento):
    tipo = "banco_sql"
    nome_exibicao = "Banco de dados direto (SQL)"
    descricao = (
        "Lê e escreve num banco de dados SQL pelo comando que você fornecer. Para "
        "consultas (SELECT) devolve as linhas; para escrita (INSERT/UPDATE/DELETE) "
        "devolve quantas linhas mudaram. Prefira parâmetros nomeados (:nome) a "
        "concatenar valores no texto do SQL."
    )
    Config = ConfigSQL
    Args = ArgsSQL
    campos_secretos = ("senha",)
    # Baseline irreversível (INSERT/UPDATE/DELETE mudam dados). Mas em modo
    # `somente_leitura` o instrumento só consulta — aí não exige portão.
    acao_irreversivel = True

    def irreversivel_para(self, configuracao: dict) -> bool:
        return not bool((configuracao or {}).get("somente_leitura", False))

    def executar(self, config: ConfigSQL, args: ArgsSQL) -> dict:
        # Trava do modo somente-leitura: recusa qualquer escrita (volta como dado).
        if config.somente_leitura and not eh_leitura(args.sql):
            return {
                "ok": False,
                "erro": (
                    "Este instrumento está em modo SOMENTE LEITURA: só consultas "
                    "(SELECT) são permitidas. Reformule como uma consulta."
                ),
            }
        url = URL.create(
            _DRIVER[config.tipo_banco],
            username=config.usuario,
            password=config.senha,
            host=config.host,
            port=config.porta,
            database=config.banco,
        )
        try:
            engine = create_engine(
                url,
                poolclass=NullPool,
                connect_args={"sslmode": config.ssl, "connect_timeout": TIMEOUT_S},
            )
        except Exception as e:  # dialeto/driver indisponível, URL malformada
            raise FalhaInstrumento(
                f"configuração de banco inválida: {e}", retentavel=False
            )
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                try:
                    resultado = conn.execute(text(args.sql), args.parametros or {})
                    if resultado.returns_rows:
                        linhas = [
                            dict(r._mapping) for r in resultado.fetchmany(MAX_LINHAS)
                        ]
                        trans.commit()
                        return {"ok": True, "linhas": linhas, "n": len(linhas)}
                    trans.commit()
                    return {"ok": True, "linhas_afetadas": resultado.rowcount}
                except SQLAlchemyError as e:
                    # Erro de SQL: volta à IA como dado (não é falha do instrumento).
                    trans.rollback()
                    return {"ok": False, "erro": str(getattr(e, "orig", e))[:500]}
        except OperationalError as e:
            raise FalhaInstrumento(
                f"não foi possível conectar ao banco em {config.host}: {e}",
                retentavel=True,
            )
        finally:
            engine.dispose()


registrar(BancoSQL())
