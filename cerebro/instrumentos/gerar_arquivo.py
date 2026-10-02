"""Instrumento "Gerar arquivo e analisar dados" — a IA escreve e roda código num
espaço isolado da Anthropic e entrega arquivos prontos (planilha, Word, PowerPoint,
PDF, gráfico), além da análise em texto.

Por capacidade: o modelo escolhido diz qual IA faz. Na Anthropic, execução de código
+ as "habilidades" de arquivo dela (xlsx, docx, pptx, pdf), que ensinam a IA a montar
cada formato do jeito certo. Na OpenAI, o "code interpreter" (Python num espaço
isolado, com as bibliotecas de planilha, Word e PowerPoint) — medido em 02/10/2026:
uma planilha com fórmula e gráfico em 11 s, cerca de US$ 0,03, contra 65 s e US$ 0,23
na Anthropic. O agente diz o que quer ("monte uma planilha com o resumo de vendas por
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

import mimetypes
import re
import uuid
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse

import anthropic
import httpx
import openai
from pydantic import BaseModel, Field, model_validator

import arquivos
from instrumentos import anthropic_servidor as srv
from instrumentos import escolha_ia
from instrumentos import openai_servidor as oai
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
    "entregue e dos números principais — sem inventar dado que não esteja na entrada e "
    "sem citar pastas ou caminhos de arquivo (quem pediu recebe o link pronto)."
)
# Na OpenAI os arquivos ficam em /mnt/data, e não há habilidades: os formatos
# permitidos vão nas instruções.
SISTEMA_OPENAI = SISTEMA.replace("$OUTPUT_DIR", "/mnt/data") + (
    " Gere só arquivos nestes formatos: {formatos}. Não gere imagens de conferência."
)
# Espaço de execução da OpenAI: 1 GB (US$ 0,03 por sessão de até 20 min).
MEMORIA_OPENAI = "1g"
PADROES = {"anthropic": srv.MODELO_PADRAO, "openai": oai.MODELO_PADRAO_WEB}
# Sem o Google: a execução de código dele não devolve arquivo (só imagem de gráfico).
PROVEDORES = ("anthropic", "openai")


class ConfigArquivo(BaseModel):
    modelo: str = escolha_ia.campo_modelo(
        "Em branco, o Batuta usa o padrão da IA com chave: GPT-5.6 Luna (rápido e "
        "barato, cerca de US$ 0,03 por arquivo) ou Claude Sonnet 5 (cerca de US$ 0,15 a "
        "0,25, mais demorado).",
        PROVEDORES,
    )
    formatos: list[Literal["xlsx", "docx", "pptx", "pdf"]] = Field(
        default_factory=lambda: list(HABILIDADES), title="Formatos que a IA sabe montar",
        description="Planilha (xlsx), Word (docx), PowerPoint (pptx) e PDF. Tirar os que "
        "este agente não usa deixa cada pedido um pouco mais barato.",
    )

    @model_validator(mode="before")
    @classmethod
    def _provedor_antigo(cls, dados):
        return escolha_ia.de_provedor_antigo(dados, PADROES)

    @model_validator(mode="after")
    def _valido(self) -> "ConfigArquivo":
        escolha_ia.validar(self.modelo, "gerar arquivos", PROVEDORES)
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


def _baixar_entradas(urls: list[str]) -> list[tuple[str, bytes, str]]:
    """Baixa cada arquivo de entrada: (nome, conteúdo, tipo)."""
    baixados = []
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
        baixados.append((_nome_do_link(url), r.content, tipo))
    return baixados


def _subir_entradas(cliente: anthropic.Anthropic, urls: list[str]) -> list[dict]:
    """Baixa cada arquivo de entrada e sobe para a Anthropic; devolve os blocos
    `container_upload` que o colocam no espaço de execução."""
    blocos = []
    for arquivo in _baixar_entradas(urls):
        try:
            enviado = cliente.beta.files.upload(file=arquivo)
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


# O tipo de cada formato do Office, sem depender da tabela do sistema (no servidor ela
# não tinha o xlsx: o arquivo saía como "application/octet-stream" — uso real, 02/10).
_TIPOS_OFFICE = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _gerados_openai(cliente: openai.OpenAI, itens: list[dict]) -> list[tuple[str, str, str]]:
    """Os arquivos que o code interpreter entregou: (espaço, arquivo, nome). Vale o que
    a resposta cita como arquivo; sem citação, os arquivos que a IA criou na pasta de
    saída — sem as imagens de conferência que ela gera para si (subpastas, `cfile_…`)."""
    citados = {
        (a["container_id"], a["file_id"]): a.get("filename") or "arquivo"
        for a in oai.anotacoes(itens)
        if a.get("type") == "container_file_citation" and a.get("container_id") and a.get("file_id")
    }
    if citados:
        return [(c, f, n) for (c, f), n in citados.items()]
    espacos = {i["container_id"] for i in itens
               if i.get("type") == "code_interpreter_call" and i.get("container_id")}
    achados = []
    for espaco in espacos:
        try:
            for f in cliente.containers.files.list(container_id=espaco):
                caminho = PurePosixPath(f.path or "")
                if (f.source == "assistant" and str(caminho.parent) == "/mnt/data"
                        and not caminho.name.startswith("cfile_")):
                    achados.append((espaco, f.id, caminho.name))
        except openai.APIError as e:
            raise oai.traduzir_excecao(e, "") from e
    return achados


def _guardar_saidas_openai(cliente: openai.OpenAI, gerados: list[tuple[str, str, str]]) -> list[dict]:
    """Baixa os arquivos gerados da OpenAI e guarda no armazenamento do Batuta."""
    saida = []
    for espaco, file_id, nome in gerados[:MAX_SAIDAS]:
        try:
            conteudo = cliente.containers.files.content.retrieve(file_id, container_id=espaco).read()
        except openai.APIError as e:
            raise oai.traduzir_excecao(e, "") from e
        nome = PurePosixPath(nome).name or "arquivo"
        tipo = _TIPOS_OFFICE.get(PurePosixPath(nome).suffix.lower()) or \
            mimetypes.guess_type(nome)[0] or "application/octet-stream"
        url = arquivos.salvar(f"{uuid.uuid4().hex[:8]}-{nome}", conteudo, tipo)
        saida.append({"nome": nome, "url": url, "tipo": tipo, "bytes": len(conteudo)})
    return saida


# Um caminho do espaço de execução ($OUTPUT_DIR/x.xlsx, /mnt/user-data/outputs/x.pdf,
# /mnt/data/x.docx na OpenAI).
_CAMINHO = r"`?(?:\$OUTPUT_DIR|/mnt/(?:user-data/)?outputs|(?:sandbox:)?/mnt/data)/[^\s`)]*`?"
# O link de download que a OpenAI põe no texto: "[Baixar x.xlsx](sandbox:/mnt/data/x.xlsx)".
_LINK_SANDBOX = re.compile(r"\s*\[[^\]]*\]\(sandbox:[^)]*\)")
# Entre parênteses no meio de uma frase: "a planilha ($OUTPUT_DIR/a.xlsx) tem…".
_CAMINHO_ENTRE_PARENTESES = re.compile(r"\s*\(" + _CAMINHO + r"\)")
_TEM_CAMINHO = re.compile(_CAMINHO)
_FRASES = re.compile(r"(?<=[.!?;])\s+")


def _sem_caminho_interno(texto: str) -> str:
    """Tira do resumo os caminhos do espaço de execução ("salvo em $OUTPUT_DIR/x.xlsx"):
    não interessam a quem pediu, que recebe o link do arquivo. O caminho entre
    parênteses sai sozinho; a frase que ainda cita um caminho sai inteira (é sempre a
    do "salvei em…")."""
    saida = []
    for linha in texto.split("\n"):
        if _LINK_SANDBOX.search(linha):
            # Sem o link, "…e gráfico: [Baixar](sandbox:…)." vira "…e gráfico."
            linha = re.sub(r"\s*:\s*\.?\s*$", ".", _LINK_SANDBOX.sub("", linha))
        linha = _CAMINHO_ENTRE_PARENTESES.sub("", linha)
        frases = [f for f in _FRASES.split(linha) if not _TEM_CAMINHO.search(f)]
        saida.append(" ".join(frases))
    return "\n".join(saida).strip()


class GerarArquivo(TipoInstrumento):
    tipo = "gerar_arquivo"
    provedores_ia = PROVEDORES
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
        modelo = escolha_ia.resolver(config.modelo, PADROES)
        if escolha_ia.provedor(modelo) == "openai":
            return self._pela_openai(config, args, urls, modelo)
        cliente = srv._cliente(TIMEOUT_S)
        entradas = _subir_entradas(cliente, urls)
        habilidades = [
            {"type": "anthropic", "skill_id": h, "version": "latest"} for h in config.formatos
        ]
        r = srv.chamar(
            modelo=modelo, sistema=SISTEMA,
            conteudo=[{"type": "text", "text": args.instrucao}, *entradas],
            ferramentas=[{"type": FERRAMENTA_CODIGO, "name": "code_execution"}],
            betas=BETAS, container={"skills": habilidades} if habilidades else None,
            timeout=TIMEOUT_S, frase_espera="Gerando o arquivo",
        )
        gerados = _guardar_saidas(cliente, _ids_gerados(r["blocos"]))
        return _resultado(r, gerados)

    def _pela_openai(self, config: ConfigArquivo, args: ArgsArquivo, urls: list[str], modelo: str) -> dict:
        cliente = oai.cliente(TIMEOUT_S)
        baixados = _baixar_entradas(urls)
        enviados: list[str] = []
        try:
            for arquivo in baixados:
                try:
                    enviados.append(cliente.files.create(file=arquivo, purpose="user_data").id)
                except openai.APIError as e:
                    raise oai.traduzir_excecao(e, modelo) from e
            r = oai.chamar(
                modelo=modelo,
                sistema=SISTEMA_OPENAI.format(formatos=", ".join(config.formatos) or "os pedidos"),
                conteudo=[{"type": "input_text", "text": args.instrucao}],
                ferramentas=[{"type": "code_interpreter", "container": {
                    "type": "auto", "memory_limit": MEMORIA_OPENAI, "file_ids": enviados,
                }}],
                timeout=TIMEOUT_S, frase_espera="Gerando o arquivo", cliente_pronto=cliente,
            )
            gerados = _guardar_saidas_openai(cliente, _gerados_openai(cliente, r["itens"]))
        finally:
            # As entradas não precisam ficar na OpenAI depois do trabalho.
            for file_id in enviados:
                try:
                    cliente.files.delete(file_id)
                except openai.APIError:
                    pass
        return _resultado(r, gerados)


def _resultado(r: dict, gerados: list[dict]) -> dict:
    resultado = {
        "ok": True,
        "resumo": _sem_caminho_interno(r["texto"]),
        "arquivos": gerados,
        "uso": r["uso"],
    }
    if not gerados:
        # Não é falha (pode ter sido só análise), mas o agente precisa saber —
        # para não narrar "segue o arquivo" sem arquivo nenhum.
        resultado["aviso"] = "Nenhum arquivo foi gerado; só a análise em texto."
    return resultado


registrar(GerarArquivo())
