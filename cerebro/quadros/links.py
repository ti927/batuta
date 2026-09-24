"""Links de leitura de um quadro — para painéis de fora lerem o quadro sem login.

Regras:
- **Só leitura e só daquele quadro.** O link nunca grava nem enxerga outro quadro.
- **O link é uma senha.** Guardamos só o hash (sha256) e os 4 últimos caracteres; o link
  inteiro aparece uma vez (ao criar ou trocar). Não há como "ver de novo" — troca-se.
- **Revogar e expirar cortam na hora.**
- **Limite de leituras por minuto**, por link, visível e ajustável (nenhum limite secreto).
  Contado em memória: o cérebro roda em UMA réplica (ARQUITETURA); se isso mudar, o
  contador precisa ir para o banco.
- **Toda leitura deixa rastro:** `usos` + `ultimo_uso_em` no link e um evento no banco de
  logs (`quadro.link_lido`).
"""

import hashlib
import re
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modelos import QuadroLink
from quadros.servico import ErroQuadro, obter_quadro

PREFIXO = "bq_"
LIMITE_PADRAO = 60
LIMITE_TETO = 600
MAX_NOME = 120
FUSO = ZoneInfo("America/Sao_Paulo")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _novo_token() -> str:
    return PREFIXO + secrets.token_urlsafe(32)


def caminho_publico(token: str) -> str:
    """O caminho do link no cérebro (a tela junta com o endereço público do cérebro)."""
    return f"/publico/quadros/{token}"


def serializar(link: QuadroLink) -> dict:
    agora = datetime.now(timezone.utc)
    if link.revogado_em:
        estado = "revogado"
    elif link.expira_em and link.expira_em <= agora:
        estado = "expirado"
    else:
        estado = "ativo"
    return {
        "id": str(link.id),
        "nome": link.nome,
        "final": link.token_final,
        "estado": estado,
        "limite_por_minuto": link.limite_por_minuto,
        "expira_em": link.expira_em,
        "revogado_em": link.revogado_em,
        "ultimo_uso_em": link.ultimo_uso_em,
        "usos": link.usos,
        "criado_em": link.criado_em,
    }


def _validar(nome: str, limite: int | None, expira_em: datetime | None) -> tuple[str, int]:
    nome = (nome or "").strip()
    if not nome:
        raise ErroQuadro("Dê um nome ao link (ex.: “Painel do Looker”), para saber quem o usa.")
    if len(nome) > MAX_NOME:
        raise ErroQuadro(f"O nome do link aceita até {MAX_NOME} caracteres.")
    limite = LIMITE_PADRAO if limite is None else limite
    if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= LIMITE_TETO:
        raise ErroQuadro(f"O limite de leituras por minuto vai de 1 a {LIMITE_TETO}.")
    if expira_em is not None:
        if expira_em.tzinfo is None:
            expira_em = expira_em.replace(tzinfo=FUSO)
        if expira_em <= datetime.now(timezone.utc):
            raise ErroQuadro("A data de validade precisa estar no futuro.")
    return nome, limite


def criar(
    sessao: Session,
    organizacao_id: uuid.UUID,
    quadro_ref,
    *,
    nome: str,
    limite_por_minuto: int | None = None,
    expira_em: datetime | None = None,
    criado_por_id: uuid.UUID | None = None,
) -> tuple[QuadroLink, str]:
    """Cria o link. Devolve `(link, token)` — o token INTEIRO só existe aqui."""
    q = obter_quadro(sessao, organizacao_id, quadro_ref)
    nome, limite = _validar(nome, limite_por_minuto, expira_em)
    token = _novo_token()
    link = QuadroLink(
        quadro_id=q.id, organizacao_id=organizacao_id, nome=nome,
        token_hash=_hash(token), token_final=token[-4:], limite_por_minuto=limite,
        expira_em=expira_em, criado_por_id=criado_por_id,
    )
    sessao.add(link)
    sessao.flush()
    return link, token


def listar(sessao: Session, organizacao_id: uuid.UUID, quadro_ref) -> list[QuadroLink]:
    q = obter_quadro(sessao, organizacao_id, quadro_ref)
    return list(
        sessao.scalars(
            select(QuadroLink).where(QuadroLink.quadro_id == q.id).order_by(QuadroLink.criado_em.desc())
        ).all()
    )


def _do_quadro(sessao, organizacao_id, quadro_ref, link_id) -> QuadroLink:
    q = obter_quadro(sessao, organizacao_id, quadro_ref)
    try:
        lid = uuid.UUID(str(link_id))
    except (ValueError, TypeError):
        raise ErroQuadro("O id do link não é válido.") from None
    link = sessao.scalar(select(QuadroLink).where(QuadroLink.id == lid, QuadroLink.quadro_id == q.id))
    if link is None:
        raise ErroQuadro("Não achei esse link neste quadro.")
    return link


def revogar(sessao: Session, organizacao_id: uuid.UUID, quadro_ref, link_id) -> QuadroLink:
    link = _do_quadro(sessao, organizacao_id, quadro_ref, link_id)
    if link.revogado_em is None:
        link.revogado_em = datetime.now(timezone.utc)
        sessao.flush()
    return link


def trocar(sessao: Session, organizacao_id: uuid.UUID, quadro_ref, link_id) -> tuple[QuadroLink, str]:
    """Gera um link NOVO no lugar do antigo (o antigo para de funcionar na hora)."""
    link = _do_quadro(sessao, organizacao_id, quadro_ref, link_id)
    if link.revogado_em is not None:
        raise ErroQuadro("Este link foi revogado. Crie um link novo.")
    token = _novo_token()
    link.token_hash = _hash(token)
    link.token_final = token[-4:]
    sessao.flush()
    return link, token


def ajustar(
    sessao: Session, organizacao_id: uuid.UUID, quadro_ref, link_id, *,
    limite_por_minuto: int | None = None, expira_em: datetime | None = None, sem_validade: bool = False,
) -> QuadroLink:
    link = _do_quadro(sessao, organizacao_id, quadro_ref, link_id)
    _nome, limite = _validar(link.nome, limite_por_minuto if limite_por_minuto is not None else link.limite_por_minuto, expira_em)
    link.limite_por_minuto = limite
    if sem_validade:
        link.expira_em = None
    elif expira_em is not None:
        link.expira_em = expira_em
    sessao.flush()
    return link


# ─────────────────────────────── leitura de fora ───────────────────────────────


class LinkRecusado(Exception):
    """O link não vale (inexistente, revogado, expirado) ou passou do limite.
    `status` é o código HTTP; `str(e)` é a frase para quem lê o painel."""

    def __init__(self, mensagem: str, status: int):
        super().__init__(mensagem)
        self.status = status


_janelas: dict[str, deque] = {}
_trava = threading.Lock()


def _dentro_do_limite(link: QuadroLink) -> bool:
    agora = time.monotonic()
    with _trava:
        janela = _janelas.setdefault(link.token_hash, deque())
        while janela and agora - janela[0] > 60:
            janela.popleft()
        if len(janela) >= link.limite_por_minuto:
            return False
        janela.append(agora)
        return True


def abrir(sessao: Session, token: str) -> QuadroLink:
    """O link válido para este token, já contando a leitura. Levanta `LinkRecusado`."""
    link = sessao.scalar(select(QuadroLink).where(QuadroLink.token_hash == _hash(token or "")))
    if link is None:
        raise LinkRecusado("Link não encontrado. Confira se ele foi copiado inteiro.", 404)
    if link.revogado_em is not None:
        raise LinkRecusado("Este link foi revogado. Peça um novo a quem administra o quadro no Batuta.", 410)
    if link.expira_em is not None and link.expira_em <= datetime.now(timezone.utc):
        raise LinkRecusado("Este link passou da validade. Peça um novo a quem administra o quadro no Batuta.", 410)
    if not _dentro_do_limite(link):
        raise LinkRecusado(
            f"Leituras demais em um minuto (o limite deste link é {link.limite_por_minuto}). "
            "Espere um minuto; se o painel precisa de mais, o limite pode ser aumentado no Batuta.",
            429,
        )
    sessao.execute(
        update(QuadroLink)
        .where(QuadroLink.id == link.id)
        .values(usos=QuadroLink.usos + 1, ultimo_uso_em=datetime.now(timezone.utc))
    )
    return link


_HOJE = re.compile(r"^hoje\s*([+-])\s*(\d{1,4})$|^hoje$", re.IGNORECASE)


def data_relativa(valor: str) -> str:
    """"hoje", "hoje-90", "hoje+7" → a data (Brasília) em AAAA-MM-DD. Outro valor passa
    como veio. É o que deixa um painel pedir "os últimos 90 dias" num link fixo."""
    m = _HOJE.match((valor or "").strip())
    if not m:
        return valor
    dia = datetime.now(FUSO).date()
    if m.group(1):
        n = int(m.group(2))
        dia = dia + timedelta(days=n if m.group(1) == "+" else -n)
    return dia.isoformat()


def filtros_da_url(filtros: list[str]) -> list[dict]:
    """`filtro=Coluna|operador|valor` (repetível) → a linguagem única de filtro.
    Operadores sem símbolo para caber numa URL: eq, ne, gt, gte, lt, lte, contem, vazio,
    nao_vazio (os símbolos =, >= etc. também valem)."""
    saida = []
    for f in filtros or []:
        partes = f.split("|", 2)
        if len(partes) < 2:
            raise ErroQuadro(f"Filtro “{f}” incompleto. Use filtro=Coluna|operador|valor (ex.: filtro=Tema|eq|COF).")
        item = {"coluna": partes[0].strip(), "operador": partes[1].strip()}
        if len(partes) == 3:
            item["valor"] = data_relativa(partes[2])
        saida.append(item)
    return saida
