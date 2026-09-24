"""Importar planilha (CSV) para um quadro — e sugerir as colunas a partir dela.

É o caminho de migração ("o histórico do Radar está numa planilha"). A importação
passa pelo MESMO `gravar_linhas` (mesma validação, mesmo carimbo), em partes do tamanho
do limite de linhas por gravação, dentro de UM savepoint: tudo ou nada também aqui.
"""

import csv
import io
import uuid

from sqlalchemy.orm import Session

from quadros import limites as limites_mod
from quadros import tipos
from quadros.servico import Autor, ErroQuadro, _em_savepoint, gravar_linhas, obter_quadro
from quadros.filtros import resolver_coluna

MAX_LINHAS_IMPORTACAO = 5000


def ler_csv(texto: str) -> tuple[list[str], list[list[str]]]:
    """(cabeçalho, linhas) de um CSV em texto. Aceita `,` `;` ou tab (detecta)."""
    if not isinstance(texto, str) or not texto.strip():
        raise ErroQuadro("O CSV está vazio.")
    amostra = texto[:5000]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialeto = csv.excel
    leitor = csv.reader(io.StringIO(texto.strip("﻿")), dialeto)
    todas = [ln for ln in leitor if any((c or "").strip() for c in ln)]
    if not todas:
        raise ErroQuadro("O CSV está vazio.")
    cabecalho = [c.strip() for c in todas[0]]
    if any(not c for c in cabecalho):
        raise ErroQuadro("O cabeçalho do CSV tem coluna sem nome.")
    return cabecalho, todas[1:]


def _tipo_provavel(valores: list[str]) -> str:
    cheios = [v for v in valores if (v or "").strip()]
    if not cheios:
        return "texto"
    # Ordem importa: 0/1 é número antes de sim/não; valor com hora é data e hora (a
    # normalização de "data" aceitaria e jogaria a hora fora).
    com_hora = any(":" in v for v in cheios)
    candidatos = ("numero", "data_hora", "sim_nao") if com_hora else ("numero", "data", "sim_nao")
    for tipo in candidatos:
        try:
            for v in cheios:
                tipos.normalizar({"tipo": tipo}, v, tamanho_texto_longo=1)
            return tipo
        except tipos.ValorInvalido:
            continue
    if any(len(v) > tipos.TAMANHO_TEXTO for v in cheios):
        return "texto_longo"
    return "texto"


def sugerir_colunas(texto: str) -> dict:
    """As colunas que um quadro novo teria para receber este CSV, com o tipo provável de
    cada uma (olhando os valores). É SUGESTÃO: quem cria confere e ajusta."""
    cabecalho, linhas = ler_csv(texto)
    colunas = []
    for i, nome in enumerate(cabecalho):
        valores = [ln[i] if i < len(ln) else "" for ln in linhas[:500]]
        colunas.append({"nome": nome, "tipo": _tipo_provavel(valores)})
    return {"colunas": colunas, "linhas_no_csv": len(linhas)}


def importar_csv(
    sessao: Session,
    organizacao_id: uuid.UUID,
    ref,
    texto: str,
    *,
    autor: Autor,
    mapeamento: dict | None = None,
    ignorar_colunas_extras: bool = False,
    modo: str = "acrescentar",
    simular: bool = False,
) -> dict:
    """Importa o CSV para o quadro. O cabeçalho casa com as colunas pelo NOME (sem
    diferenciar maiúscula nem acento) ou pelo `mapeamento` {cabeçalho: coluna}. Tudo ou
    nada: um valor ruim em qualquer linha recusa a importação inteira, com a lista."""

    def trabalho():
        q = obter_quadro(sessao, organizacao_id, ref)
        lim = limites_mod.efetivos(q)
        cabecalho, linhas = ler_csv(texto)
        if not linhas:
            raise ErroQuadro("O CSV só tem o cabeçalho, sem linhas.")
        if len(linhas) > MAX_LINHAS_IMPORTACAO:
            raise ErroQuadro(
                f"O CSV tem {len(linhas)} linhas; a importação aceita até "
                f"{MAX_LINHAS_IMPORTACAO} por vez. Divida o arquivo."
            )
        mapa = {str(k).strip().lower(): v for k, v in (mapeamento or {}).items()}
        destino: list[str | None] = []
        sobrando = []
        for cab in cabecalho:
            alvo = mapa.get(cab.lower(), cab)
            col = resolver_coluna(q, alvo) if alvo else None
            if col is None:
                sobrando.append(cab)
                destino.append(None)
            else:
                destino.append(col["nome"])
        if sobrando and not ignorar_colunas_extras:
            raise ErroQuadro(
                "Estas colunas do CSV não existem no quadro: "
                + ", ".join(f"“{s}”" for s in sobrando)
                + ". Crie as colunas, diga para qual coluna cada uma vai (mapeamento) ou "
                "peça para ignorar as que sobram."
            )
        dicts = []
        for ln in linhas:
            d = {}
            for i, nome in enumerate(destino):
                if nome is not None:
                    d[nome] = ln[i] if i < len(ln) else ""
            dicts.append(d)
        passo = lim["linhas_por_gravacao"]
        total = {"criadas": 0, "atualizadas": 0, "sem_mudanca": 0}
        for inicio in range(0, len(dicts), passo):
            try:
                r = gravar_linhas(
                    sessao, organizacao_id, q.id, dicts[inicio:inicio + passo],
                    autor=autor, modo=modo,
                )
            except ErroQuadro as e:
                # Numera pelas linhas DO CSV (a 1ª linha de dados é a linha 2 do arquivo).
                detalhes = [
                    {**d, "linha": (d["linha"] + inicio + 1) if d.get("linha") else None}
                    for d in e.detalhes
                ]
                raise ErroQuadro(
                    "Nada foi importado: há linhas com problema (a numeração é a do "
                    "arquivo, contando o cabeçalho como linha 1).",
                    detalhes,
                ) from None
            for k in total:
                total[k] += r[k]
        return {
            "quadro": q.nome,
            "linhas_no_csv": len(linhas),
            **total,
            "colunas_ignoradas": sobrando,
        }

    return _em_savepoint(sessao, simular, trabalho)
