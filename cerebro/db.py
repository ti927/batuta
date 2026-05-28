"""Conexão do cérebro com o banco Postgres do Supabase."""

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

load_dotenv()


def _montar_url() -> URL:
    """Monta a URL de conexão a partir da DATABASE_URL do .env.

    Faz o parsing por componentes (e não via string crua) porque a senha do
    banco pode conter caracteres especiais ($ * ,) que quebram o parser de URL.
    O SQLAlchemy cuida da codificação ao entregar os componentes ao driver.
    """
    bruta = os.environ["DATABASE_URL"]
    sem_esquema = bruta.split("://", 1)[1]
    credenciais, host_banco = sem_esquema.rsplit("@", 1)
    usuario, senha = credenciais.split(":", 1)
    host_porta, banco = host_banco.split("/", 1)
    host, porta = host_porta.split(":")
    banco = banco.split("?", 1)[0]
    return URL.create(
        "postgresql+psycopg",
        username=usuario,
        password=senha,
        host=host,
        port=int(porta),
        database=banco,
    )


engine = create_engine(_montar_url(), connect_args={"sslmode": "require"})


def testar_conexao() -> str:
    """Abre uma conexão e devolve a versão do Postgres. Levanta erro se falhar."""
    with engine.connect() as conn:
        return conn.execute(text("select version()")).scalar()


if __name__ == "__main__":
    print("Conectado:", testar_conexao())
