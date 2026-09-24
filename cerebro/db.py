"""Conexão do cérebro com o banco Postgres do Supabase."""

import os
import threading

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, event, text

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
#
# ORÇAMENTO DE CONEXÕES (incidente EMAXCONNSESSION, 2026-09-24). O pooler do Supabase em
# modo sessão aceita um número FIXO de clientes (era 15). Com o padrão do SQLAlchemy
# (5 fixas + 10 extras por processo), o cérebro, a memória das conversas e o MCP juntos
# podiam pedir 30+; em repouso já seguravam 11–15, e qualquer pico — um deploy com dois
# cérebros no ar, três execuções na fila — era recusado como erro 500. Agora o orçamento
# é explícito e ajustável sem deploy (variáveis de ambiente), e quem passa do orçamento
# ESPERA uma conexão livre (`pool_timeout`) em vez de abrir uma nova que o pooler recusa.
#   cérebro: DB_POOL_SIZE=5 + DB_MAX_OVERFLOW=7 (até 12) · MCP: 2 + 4 (até 6, fixado em
#   mcp_servidor.py) · memória das conversas: até 4 (memoria_conversa.py).
POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "7"))
POOL_TIMEOUT = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

engine = create_engine(
    _url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
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


# Pooler CHEIO é passageiro (dura segundos: um deploy, um pico). Abrir a conexão de novo
# depois de uma pausa curta resolve — então esperamos e tentamos, em vez de devolver erro
# na primeira recusa. Só para ESTE erro: qualquer outra falha de conexão sobe na hora.
ESPERAS_POOLER_CHEIO = (0.5, 1.0, 2.0, 3.0)  # ~6,5 s no total


def pooler_cheio(erro: BaseException) -> bool:
    texto = str(erro)
    return "EMAXCONNSESSION" in texto or "max clients reached" in texto


def conectar_com_paciencia(conectar, *, dormir=None, avisar=None):
    """Chama `conectar()`; se o pooler estiver cheio, espera e tenta de novo (até
    `ESPERAS_POOLER_CHEIO`). `avisar(tentativas, conseguiu)` é chamado quando houve espera
    — é o que deixa rastro no banco de logs. Devolve a conexão ou levanta o último erro."""
    import time

    dormir = dormir or time.sleep
    for n, espera in enumerate((*ESPERAS_POOLER_CHEIO, None), start=1):
        try:
            conexao = conectar()
        except Exception as e:  # noqa: BLE001 — só o pooler cheio é tratado aqui
            if not pooler_cheio(e) or espera is None:
                if pooler_cheio(e) and avisar:
                    avisar(n, False)
                raise
            dormir(espera)
            continue
        if n > 1 and avisar:
            avisar(n, True)
        return conexao


_avisando = threading.Lock()


def _avisar_pooler_cheio(tentativas: int, conseguiu: bool) -> None:
    """Grava o aviso em SEGUNDO PLANO e no máximo um de cada vez: gravar também pede uma
    conexão, e o aviso não pode esperar o pooler (nem se chamar em cadeia se ele ainda
    estiver cheio). Aviso que chega enquanto outro grava é descartado — o primeiro basta."""
    if not _avisando.acquire(blocking=False):
        return
    threading.Thread(
        target=_gravar_aviso, args=(tentativas, conseguiu), daemon=True
    ).start()


def _gravar_aviso(tentativas: int, conseguiu: bool) -> None:
    # Import tardio: o escritor usa o próprio engine (evita import circular no boot).
    try:
        from observabilidade.escritor import registrar_evento

        registrar_evento(
            categoria="banco",
            acao="banco.pooler_cheio",
            nivel="warning" if conseguiu else "error",
            resultado="ok" if conseguiu else "falha",
            detalhe={
                "tentativas": tentativas,
                "conseguiu": conseguiu,
                "o_que_e": "o pooler do Supabase estava no limite de clientes; "
                + ("a conexão saiu depois de esperar" if conseguiu else "desistimos depois de ~6 s"),
                "orcamento": {"pool_size": POOL_SIZE, "max_overflow": MAX_OVERFLOW},
            },
        )
    except Exception:  # noqa: BLE001 — avisar nunca derruba a conexão
        pass
    finally:
        _avisando.release()


@event.listens_for(engine, "do_connect")
def _conectar_esperando_pooler(dialect, conn_rec, cargs, cparams):
    return conectar_com_paciencia(
        lambda: dialect.connect(*cargs, **cparams), avisar=_avisar_pooler_cheio
    )


def testar_conexao() -> str:
    """Abre uma conexão e devolve a versão do Postgres. Levanta erro se falhar."""
    with engine.connect() as conn:
        return conn.execute(text("select version()")).scalar()


if __name__ == "__main__":
    print("Conectado:", testar_conexao())
