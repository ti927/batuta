"""Diagnóstico de SMTP — testa o envio de e-mail isoladamente, fora do Supabase.

Serve para descobrir se as credenciais do Gmail (senha de app) funcionam de
verdade. NÃO faz parte do produto. Lê as credenciais do ambiente ou do
cerebro/.env. Rode a partir da pasta cerebro/:

    uv run python scripts/testar_smtp.py
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
port = int(os.environ.get("SMTP_PORT", "587"))
user = os.environ.get("SMTP_USER")
senha = os.environ.get("SMTP_PASS")
para = os.environ.get("SMTP_TO") or user

if not user or not senha:
    raise SystemExit(
        "Defina SMTP_USER e SMTP_PASS (no cerebro/.env ou no ambiente)."
    )

print(f"Conectando a {host}:{port} como {user} ...")

msg = EmailMessage()
msg["From"] = user
msg["To"] = para
msg["Subject"] = "Teste de SMTP do Batuta"
msg.set_content(
    "Se você recebeu este e-mail, o SMTP do Batuta está funcionando."
)

try:
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        s.login(user, senha)
        s.send_message(msg)
    print(f"OK: e-mail de teste enviado para {para}. Confira a caixa de entrada.")
except smtplib.SMTPAuthenticationError as e:
    print(f"FALHA DE AUTENTICACAO: {e}")
    print(
        "Causa provavel: senha de app errada, criada para OUTRA conta, "
        "ou verificacao em 2 etapas nao ativa na conta do SMTP_USER."
    )
except Exception as e:  # noqa: BLE001 — diagnóstico: queremos ver qualquer erro
    print(f"FALHA: {type(e).__name__}: {e}")
