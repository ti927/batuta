"""Conexão do cérebro com o banco Postgres do Supabase."""

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

load_dotenv()


def _montar_url() -> tuple[URL, str]:
    """Monta a URL de conexão a partir da DATABASE_URL do .env.

    Faz o parsing por componentes (e não via string crua) porque a senha do
    banco pode conter caracteres especiais ($ * ,) que quebram o parser de URL.
    O SQLAlchemy cuida da codificação ao entregar os componentes ao driver.

    Devolve também o `sslmode`. O padrão é **`require`** — a nuvem exige TLS e
    é o que produção sempre usou. Um `?sslmode=` escrito na própria URL manda:
    é assim que o Postgres LOCAL dos testes (que não serve TLS) pede `disable`,
    sem afrouxar a exigência de ninguém mais.
    """
    bruta = os.environ["DATABASE_URL"]
    sem_esquema = bruta.split("://", 1)[1]
    credenciais, host_banco = sem_esquema.rsplit("@", 1)
    usuario, senha = credenciais.split(":", 1)
    host_porta, banco = host_banco.split("/", 1)
    host, porta = host_porta.split(":")
    banco, _, consulta = banco.partition("?")
    sslmode = "require"
    for par in consulta.split("&"):
        chave, _, valor = par.partition("=")
        if chave == "sslmode" and valor:
            sslmode = valor
    return (
        URL.create(
            "postgresql+psycopg",
            username=usuario,
            password=senha,
            host=host,
            port=int(porta),
            database=banco,
        ),
        sslmode,
    )


_url, SSLMODE = _montar_url()
"""Modo TLS efetivo desta conexão (`require` na nuvem, `disable` no banco local
de testes). Público porque é um componente da conexão como host/porta/usuário —
quem reproduz a conexão do cérebro (ex.: o teste do instrumento SQL) precisa
dele para não fixar `require` na mão."""

engine = create_engine(_url, connect_args={"sslmode": SSLMODE})


def testar_conexao() -> str:
    """Abre uma conexão e devolve a versão do Postgres. Levanta erro se falhar."""
    with engine.connect() as conn:
        return conn.execute(text("select version()")).scalar()


if __name__ == "__main__":
    print("Conectado:", testar_conexao())
