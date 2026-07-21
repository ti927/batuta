"""Instrumento "Guardar imagem recebida" — persiste a foto que o contato enviou na
conversa e devolve a URL pública.

A LEITURA (descrição) da imagem é automática na borda; GUARDAR é sob demanda: o agente
chama este instrumento SÓ quando o markdown mandar (ex.: registrar um comprovante para
lançar noutro sistema) e NÃO chama quando a foto é descartável (ex.: só interessa o
texto que veio junto). É assim que o markdown do agente decide, caso a caso, o destino
de cada imagem — em vez de a borda guardar tudo.

Os bytes vêm do contexto do turno (`midia_recebida`), depositados pela mensageria, que
já baixou a imagem para lê-la. Guarda no MESMO Storage do gerar/montar imagem
(`arquivos.salvar`, bucket público → URL durável). Só escreve no NOSSO bucket → não é
ação irreversível (não exige portão de aprovação).
"""

import uuid

from pydantic import BaseModel

import arquivos
import midia_recebida
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar

# Extensão do arquivo por tipo (só cosmético na URL; o content-type é o que vale).
_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


class ConfigArquivar(BaseModel):
    """Sem configuração — a imagem vem da conversa em curso."""


class ArgsArquivar(BaseModel):
    """Sem argumentos — guarda a(s) imagem(ns) recebida(s) neste turno."""


class ArquivarImagem(TipoInstrumento):
    tipo = "arquivar_imagem"
    categoria = "Conteúdo"
    nome_exibicao = "Guardar imagem recebida (→ URL)"
    descricao = (
        "Guarda a(s) imagem(ns) que o contato enviou NESTA conversa e devolve a URL "
        "pública durável de cada uma. Use quando precisar PRESERVAR a foto — por "
        "exemplo, registrar um comprovante ou anexá-la noutro sistema (Bubble, etc.). "
        "Se a foto for descartável (só interessa o texto), NÃO chame. Ler/descrever a "
        "imagem já é automático; este instrumento é só para GUARDAR. Sem configuração."
    )
    Config = ConfigArquivar
    Args = ArgsArquivar

    def executar(self, config: ConfigArquivar, args: ArgsArquivar) -> dict:
        imagens = midia_recebida.imagens_recebidas_atuais()
        if not imagens:
            raise FalhaInstrumento(
                "não há imagem recebida nesta conversa para guardar (o contato não "
                "enviou foto neste momento, ou ela já não está disponível).",
                retentavel=False,
            )
        urls: list[str] = []
        for im in imagens:
            dados = im.get("bytes")
            if not dados:
                continue
            mime = im.get("mime") or "application/octet-stream"
            ext = _EXT.get(mime, "bin")
            urls.append(arquivos.salvar(f"recebida_{uuid.uuid4().hex}.{ext}", dados, mime))
        if not urls:
            raise FalhaInstrumento(
                "não consegui guardar a imagem agora — tente de novo.", retentavel=True
            )
        return {"ok": True, "urls": urls, "quantidade": len(urls)}


registrar(ArquivarImagem())
