"""Central de Conhecimento — leitor dos capítulos em `cerebro/central/`.

FONTE ÚNICA das duas pontas: as rotas de `/ajuda` (leitura humana) e a ferramenta
`consultar_conhecimento` da IA criadora. Lê markdowns com um frontmatter simples
(sem PyYAML — parser mínimo), sem banco. Os arquivos são versionados no repo, dentro
de `cerebro/`, então vão para o container do backend (Root Directory = cerebro/).

O `slug` canônico de um capítulo é o CAMINHO relativo (sem `.md`), ex.:
`instrumentos/publicar-instagram` — é o que as rotas e os links `[[...]]` usam.
Arquivos-meta (`_GABARITO.md`, `INDICE.md`) não entram no índice navegável.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent / "central"
# Slugs (nome do arquivo, minúsculo) que são meta e não viram capítulo navegável.
_META = {"_gabarito", "indice"}


@dataclass(frozen=True)
class Capitulo:
    slug: str  # caminho relativo sem .md (ex.: "instrumentos/publicar-instagram")
    titulo: str
    area: str
    tags: tuple[str, ...]
    revisado_em: str
    fontes: tuple[str, ...]
    corpo: str  # markdown SEM o frontmatter

    def resumo(self) -> dict:
        """Metadados leves (para o índice — sem o corpo)."""
        return {
            "slug": self.slug,
            "titulo": self.titulo,
            "area": self.area,
            "tags": list(self.tags),
            "revisado_em": self.revisado_em,
        }


def _norm(s: str) -> str:
    """Minúsculas + sem acentos, para busca tolerante."""
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _valor(bruto: str):
    """Converte um valor do frontmatter: lista JSON (`["a","b"]`/`[]`) ou string."""
    v = (bruto or "").strip()
    if v.startswith("["):
        try:
            return [str(x) for x in json.loads(v)]
        except (ValueError, TypeError):
            return []
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _dividir_frontmatter(texto: str) -> tuple[dict, str]:
    """Separa o frontmatter (entre a 1ª e a 2ª linha `---`) do corpo. Sem frontmatter,
    devolve ({}, texto inteiro)."""
    linhas = texto.splitlines()
    if not linhas or linhas[0].strip() != "---":
        return {}, texto
    meta: dict = {}
    fim = None
    for i in range(1, len(linhas)):
        if linhas[i].strip() == "---":
            fim = i
            break
        chave, sep, resto = linhas[i].partition(":")
        if sep:
            meta[chave.strip()] = _valor(resto)
    if fim is None:
        return {}, texto
    corpo = "\n".join(linhas[fim + 1 :]).strip()
    return meta, corpo


@lru_cache(maxsize=1)
def _carregar() -> dict[str, Capitulo]:
    """Lê todos os capítulos de `cerebro/central/` uma vez (cache). `recarregar()`
    limpa o cache — útil em teste/dev; em produção o conteúdo é estático por deploy."""
    capitulos: dict[str, Capitulo] = {}
    if not RAIZ.is_dir():
        return capitulos
    for caminho in sorted(RAIZ.rglob("*.md")):
        leaf = caminho.stem.lower()
        if leaf in _META:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, corpo = _dividir_frontmatter(texto)
        slug = caminho.relative_to(RAIZ).with_suffix("").as_posix()
        tags = meta.get("tags") or []
        fontes = meta.get("fontes") or []
        capitulos[slug] = Capitulo(
            slug=slug,
            titulo=str(meta.get("titulo") or slug),
            area=str(meta.get("area") or ""),
            tags=tuple(tags if isinstance(tags, list) else []),
            revisado_em=str(meta.get("revisado_em") or ""),
            fontes=tuple(fontes if isinstance(fontes, list) else []),
            corpo=corpo,
        )
    return capitulos


def recarregar() -> None:
    """Esquece o cache (relê do disco na próxima chamada)."""
    _carregar.cache_clear()


def indice() -> list[dict]:
    """Todos os capítulos (resumo, sem corpo), ordenados por área e título."""
    caps = _carregar().values()
    return [c.resumo() for c in sorted(caps, key=lambda c: (c.area, _norm(c.titulo)))]


def indice_titulos() -> list[dict]:
    """Só título/slug/área — o mapa enxuto injetado no prompt da IA (para ela saber o
    que existe para consultar)."""
    return [
        {"titulo": c["titulo"], "slug": c["slug"], "area": c["area"]} for c in indice()
    ]


def obter(slug: str) -> Capitulo | None:
    """Um capítulo pelo slug canônico (caminho relativo sem `.md`)."""
    return _carregar().get((slug or "").strip().strip("/"))


def buscar(consulta: str, limite: int = 5) -> list[Capitulo]:
    """Capítulos mais relevantes à `consulta`, por pontuação simples (sem embeddings —
    acervo pequeno e curado): título e tags pesam mais que o corpo. Devolve [] quando
    nada casa (nunca levanta erro)."""
    termos = [t for t in _norm(consulta or "").split() if len(t) > 1]
    if not termos:
        return []
    pontuados: list[tuple[int, Capitulo]] = []
    for cap in _carregar().values():
        titulo = _norm(cap.titulo)
        tags = _norm(" ".join(cap.tags))
        corpo = _norm(cap.corpo)
        pontos = 0
        for t in termos:
            if t in titulo:
                pontos += 5
            if t in tags:
                pontos += 4
            pontos += corpo.count(t)
        if pontos > 0:
            pontuados.append((pontos, cap))
    pontuados.sort(key=lambda p: (-p[0], p[1].slug))
    return [cap for _, cap in pontuados[: max(1, limite)]]
