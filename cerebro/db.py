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

# Blindagem de rede do engine (incidente de 2026-08-27: a rede até o pooler do Supabase
# congelou e, sem NENHUM limite aqui, um turno ficou 31 min pendurado numa consulta que
# não voltava — o app inteiro pareceu morto). Cada parâmetro corta um modo de falha:
# - pool_pre_ping: testa a conexão ao emprestar; a que morreu ociosa é descartada.
# - pool_recycle=300: nenhuma conexão do pool fica velha o bastante para o pooler
#   matá-la em silêncio do outro lado.
# - connect_timeout: abrir conexão nunca pendura o boot/turno.
# - keepalives: detecta em ~1 min o par que sumiu com a conexão ociosa.
# - tcp_user_timeout=30s: corta envio sem confirmação (o modo de falha do incidente —
#   bytes retransmitidos por 15 min para um buraco negro). Sem efeito no Windows local;
#   ativo no Linux (Railway).
# - statement_timeout=60s: nenhuma consulta do app é legitimamente mais longa que isso.
engine = create_engine(
    _url,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "sslmode": SSLMODE,
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "tcp_user_timeout": 30000,
        "options": "-c statement_timeout=60000",
    },
)


def testar_conexao() -> str:
    """Abre uma conexão e devolve a versão do Postgres. Levanta erro se falhar."""
    with engine.connect() as conn:
        return conn.execute(text("select version()")).scalar()


if __name__ == "__main__":
    print("Conectado:", testar_conexao())
