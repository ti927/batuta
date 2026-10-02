"""Instrumento "Gerar arquivo e analisar dados" — a IA escreve e roda código num
espaço isolado da Anthropic e entrega arquivos prontos (planilha, Word, PowerPoint,
PDF, gráfico), além da análise em texto.

Por capacidade (hoje só a Anthropic: execução de código + as "habilidades" de
arquivo dela — xlsx, docx, pptx, pdf —, que ensinam a IA a montar cada formato do
jeito certo). O agente diz o que quer ("monte uma planilha com o resumo de vendas por
mês e um gráfico") e, se houver, passa arquivos de entrada por link público (CSV,
planilha, PDF): eles sobem para o espaço de execução antes. Os arquivos GERADOS são
baixados da Anthropic e guardados no armazenamento do Batuta — o resultado traz o
link público de cada um, pronto para o próximo passo (mandar no canal, anexar…).

Operação LONGA (dezenas de segundos a minutos): publica sinal de vida com o tempo
decorrido durante a espera (`anthropic_servidor._com_batimento`). Custo: tokens
(a IA lê o manual da habilidade — medido em 02/10/2026: uma planilha simples custou
cerca de US$ 0,14 no Sonnet 5) + tempo do espaço de execução (1.550 h grátis por mês
por organização, depois US$ 0,05 por hora). Os arquivos ficam guardados na Anthropic
por até 30 dias. Só gera arquivos → não é ação irreversível.
"""

import uuid
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse

import anthropic
import httpx
from pydantic import BaseModel, Field, model_validator

import arquivos
from instrumentos import anthropic_servidor as srv
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

# A execução de código (com habilidades) e a API de arquivos ainda vão pela rota beta
# do SDK instalado. FONTE ÚNICA: se a Anthropic trocar a versão, é só aqui.
FERRAMENTA_CODIGO = "code_execution_20250825"
BETAS = ["code-execution-2025-08-25", "skills-2025-10-02", "files-api-2025-04-14"]
HABILIDADES = ("xlsx", "docx", "pptx", "pdf")

# Uma geração de arquivo leva de segundos a minutos; teto de 10 min por chamada.
TIMEOUT_S = 600.0
MAX_ENTRADAS = 10
MAX_BYTES_ENTRADA = 30_000_000  # 30 MB por arquivo de entrada
MAX_SAIDAS = 10
TIMEOUT_DOWNLOAD_S = 60.0

SISTEMA = (
    "Você gera arquivos e analisa dados para outro agente de uma empresa brasileira. "
    "Use o código e as habilidades disponíveis para entregar exatamente o que foi "
    "pedido, em português do Brasil (datas dd/mm/aaaa, moeda R$, vírgula decimal). "
    "Salve cada arquivo final em $OUTPUT_DIR. Termine com um resumo curto do que foi "
    "entregue e dos números principais — sem inventar dado que não esteja na entrada."
)


class ConfigArquivo(BaseModel):
    provedor: Literal["anthropic"] = Field(
        default="anthropic", title="IA que gera o arquivo",
        description="Por enquanto, só a Anthropic.",
    )
    modelo: str = Field(
        default=srv.MODELO_PADRAO, title="Modelo da IA",
        description="O Sonnet 5 monta planilhas e documentos bem e custa menos que o Opus.",
        json_schema_extra={"enum": srv.modelos_disponiveis()},
    )
    formatos: list[Literal["xlsx", "docx", "pptx", "pdf"]] = Field(
        default_factory=lambda: list(HABILIDADES), title="Formatos que a IA sabe montar",
        description="Planilha (xlsx), Word (docx), PowerPoint (pptx) e PDF. Tirar os que "
        "este agente não usa deixa cada pedido um pouco mais barato.",
    )

    @model_validator(mode="after")
    def _valido(self) -> "ConfigArquivo":
        if self.modelo not in srv.modelos_disponiveis():
            raise ValueError(f"Modelo indisponível para gerar arquivos: {self.modelo}.")
        return self


class ArgsArquivo(BaseModel):
    instrucao: str = Field(
        min_length=5,
        description="O que gerar ou analisar, com os detalhes que importam (colunas, "
        "período, formato do arquivo). Ex.: 'monte uma planilha com o total de vendas "
        "por mês e um gráfico de barras'; 'resuma este CSV num relatório em PDF'.",
    )
    arquivos_url: list[str] = Field(
        default_factory=list,
        description="Links PÚBLICOS (https://) dos arquivos de entrada, se houver: "
        "planilha, CSV, PDF, imagem. Até 10.",
    )


def _nome_do_link(url: str) -> str:
    nome = PurePosixPath(urlparse(url).path).name or "entrada"
    return nome[:120]


def _subir_entradas(cliente: anthropic.Anthropic, urls: list[str]) -> list[dict]:
    """Baixa cada arquivo de entrada e sobe para a Anthropic; devolve os blocos
    `container_upload` que o colocam no espaço de execução."""
    blocos = []
    for url in urls:
        if not url.lower().startswith("https://"):
            raise FalhaInstrumento(
                f"o arquivo de entrada precisa de um link público https://: {url}",
                retentavel=False,
            )
        try:
            r = httpx.get(url, timeout=TIMEOUT_DOWNLOAD_S, follow_redirects=True)
        except httpx.HTTPError as e:
            raise FalhaInstrumento(
                f"não consegui baixar o arquivo de entrada ({url}): {e}", retentavel=True
            ) from e
        if r.status_code >= 400:
            raise FalhaInstrumento(
                f"o link do arquivo de entrada respondeu erro {r.status_code}: {url}",
                retentavel=r.status_code >= 500,
            )
        if len(r.content) > MAX_BYTES_ENTRADA:
            raise FalhaInstrumento(
                f"o arquivo de entrada passa de {MAX_BYTES_ENTRADA // 1_000_000} MB: {url}",
                retentavel=False,
            )
        tipo = (r.headers.get("content-type") or "application/octet-stream").split(";")[0]
        try:
            enviado = cliente.beta.files.upload(file=(_nome_do_link(url), r.content, tipo))
        except anthropic.APIError as e:
            raise srv._traduzir_excecao(e, "") from e
        blocos.append({"type": "container_upload", "file_id": enviado.id})
    return blocos


def _ids_gerados(blocos: list[dict]) -> list[str]:
    """Os arquivos que a execução gerou: o `file_id` que aparece dentro dos resultados
    da execução de código (o que foi salvo em $OUTPUT_DIR)."""
    ids: list[str] = []

    def andar(no):
        if isinstance(no, dict):
            if no.get("file_id") and no.get("type", "").endswith("_output"):
                ids.append(no["file_id"])
            for valor in no.values():
                andar(valor)
        elif isinstance(no, list):
            for item in no:
                andar(item)

    for b in blocos:
        if str(b.get("type", "")).endswith("_tool_result"):
            andar(b.get("content"))
    return list(dict.fromkeys(ids))


def _guardar_saidas(cliente: anthropic.Anthropic, ids: list[str]) -> list[dict]:
    """Baixa os arquivos gerados da Anthropic e guarda no armazenamento do Batuta."""
    saida = []
    for file_id in ids[:MAX_SAIDAS]:
        try:
            meta = cliente.beta.files.retrieve_metadata(file_id)
            conteudo = cliente.beta.files.download(file_id).read()
        except anthropic.APIError as e:
            raise srv._traduzir_excecao(e, "") from e
        nome = PurePosixPath(meta.filename or "arquivo").name or "arquivo"
        tipo = meta.mime_type or "application/octet-stream"
        url = arquivos.salvar(f"{uuid.uuid4().hex[:8]}-{nome}", conteudo, tipo)
        saida.append({"nome": nome, "url": url, "tipo": tipo, "bytes": len(conteudo)})
    return saida


class GerarArquivo(TipoInstrumento):
    tipo = "gerar_arquivo"
    provedores_ia = ("anthropic",)
    categoria = "Pesquisa e leitura"
    nome_exibicao = "Gerar arquivo e analisar dados"
    descricao = (
        "A IA monta arquivos prontos — planilha, Word, PowerPoint, PDF, gráfico — e "
        "analisa dados (de um CSV, de uma planilha, do que você passar). Devolve o "
        "link de cada arquivo e um resumo. Pode levar alguns minutos."
    )
    Config = ConfigArquivo
    Args = ArgsArquivo

    def executar(self, config: ConfigArquivo, args: ArgsArquivo) -> dict:
        urls = [u.strip() for u in args.arquivos_url if u and u.strip()]
        if len(urls) > MAX_ENTRADAS:
            raise FalhaInstrumento(
                f"no máximo {MAX_ENTRADAS} arquivos de entrada (recebi {len(urls)}).",
                retentavel=False,
            )
        cliente = srv._cliente(TIMEOUT_S)
        entradas = _subir_entradas(cliente, urls)
        habilidades = [
            {"type": "anthropic", "skill_id": h, "version": "latest"} for h in config.formatos
        ]
        r = srv.chamar(
            modelo=config.modelo, sistema=SISTEMA,
            conteudo=[{"type": "text", "text": args.instrucao}, *entradas],
            ferramentas=[{"type": FERRAMENTA_CODIGO, "name": "code_execution"}],
            betas=BETAS, container={"skills": habilidades} if habilidades else None,
            timeout=TIMEOUT_S, frase_espera="Gerando o arquivo",
        )
        gerados = _guardar_saidas(cliente, _ids_gerados(r["blocos"]))
        resultado = {
            "ok": True,
            "resumo": r["texto"],
            "arquivos": gerados,
            "uso": r["uso"],
        }
        if not gerados:
            # Não é falha (pode ter sido só análise), mas o agente precisa saber —
            # para não narrar "segue o arquivo" sem arquivo nenhum.
            resultado["aviso"] = "Nenhum arquivo foi gerado; só a análise em texto."
        return resultado


registrar(GerarArquivo())
