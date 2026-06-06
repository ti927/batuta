"""Gera a CHAVE-MESTRA do cofre (Fase 7) e a grava no .env do cérebro.

Roda uma única vez por ambiente. NÃO imprime o valor (é segredo): apenas o
escreve no .env, em nova linha, se ainda não existir. Idempotente — rodar de
novo não sobrescreve.

    uv run python scripts/gerar_chave_mestra.py

IMPORTANTE: a chave-mestra protege todas as chaves de API cifradas no banco.
Perdê-la torna as chaves cifradas irrecuperáveis. Guarde um backup seguro da
linha COFRE_CHAVE_MESTRA do .env.
"""

import pathlib

from cryptography.fernet import Fernet

ENV = pathlib.Path(__file__).resolve().parent.parent / ".env"
VARIAVEL = "COFRE_CHAVE_MESTRA"


def main() -> None:
    texto = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    if any(linha.startswith(VARIAVEL + "=") for linha in texto.splitlines()):
        print(f"{VARIAVEL} já existe no .env — nada a fazer (idempotente).")
        return

    valor = Fernet.generate_key().decode()
    separador = "" if texto == "" or texto.endswith("\n") else "\n"
    with ENV.open("a", encoding="utf-8") as f:
        f.write(f"{separador}{VARIAVEL}={valor}\n")

    print(f"OK: {VARIAVEL} gerada e gravada no .env (valor NÃO exibido).")
    print("Guarde um backup seguro dessa linha — sem ela, as chaves cifradas no")
    print("banco ficam irrecuperáveis.")


if __name__ == "__main__":
    main()
