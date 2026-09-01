"""Instrumento "Pedir aprovação e aguardar" — a espera por uma pessoa, no cinto.

Até 2026-08-31 a espera por um humano era CONFIGURAÇÃO do desenho: um interruptor
("portão") num nó da automação, mais uma trava global da organização ("parede"). Duas
travas, uma delas invisível, e nenhuma delas do agente. O maestro encerrou o assunto:
**toda aprovação é feita pelo agente**. Então a espera virou o que sempre deveria ter
sido — um INSTRUMENTO do cinto, acionado porque o markdown do agente manda.

O agente chama, o instrumento apresenta o pedido à pessoa (por um canal de mensageria,
se houver um configurado) e a execução PAUSA. Quando a pessoa responde, o mesmo agente
continua de onde parou, com a resposta dela em mãos. É o "send and wait for approval"
do n8n, com a diferença de quem manda: aqui é o agente, não o desenho.

Mecânica (quem faz o quê):
- este módulo: valida o canal, envia a mensagem e devolve `aguardando_aprovacao`;
- `orquestracao/agente.py`: vê `pausa_para_humano` no tipo e encerra o turno em espera;
- `orquestracao/cadeia.py`: transforma isso em `aguardando_humano` e grava o passo;
- `mensageria/aprovacao.py`: amarra a conversa de quem vai responder a esta execução;
- `mensageria/retoma.py`: religa o agente com a resposta.

O canal é REFERENCIADO (id de um instrumento de mensageria do time), não reconfigurado
— o token do bot continua morando num lugar só. Sem canal, a aprovação acontece pela
tela da execução, como sempre pôde.
"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

import segredos_instrumento
from instrumentos.base import FalhaInstrumento, TipoInstrumento, registrar
from modelos import Instrumento
from sessao import CriadorDeSessao

# Tipos de instrumento que sabem apresentar um pedido a uma pessoa.
CANAIS_TIPOS = ("enviar_telegram",)


class ConfigPedirAprovacao(BaseModel):
    """Configuração fixa (o humano preenche): POR ONDE o pedido chega à pessoa."""

    canal_instrumento_id: str = Field(
        default="",
        title="Canal do pedido",
        description="O instrumento de mensageria (ex.: um bot do Telegram deste time) "
        "por onde o pedido de aprovação é enviado. Quem responde é o destinatário "
        "configurado nesse canal. Deixe vazio para aprovar só pela tela da execução.",
        json_schema_extra={"ui": "canal_mensageria"},
    )


class ArgsPedirAprovacao(BaseModel):
    """O que a IA passa: exatamente o que a pessoa vai ler e aprovar."""

    mensagem: str = Field(
        min_length=1,
        description="O que a pessoa precisa ver para decidir — o conteúdo pronto (o "
        "texto, o link da imagem, os dados do lançamento) e a pergunta. Escreva a "
        "mensagem inteira: é isto que ela recebe, e é isto que ela aprova.",
    )


class PedirAprovacao(TipoInstrumento):
    tipo = "pedir_aprovacao"
    categoria = "Mensageria"
    nome_exibicao = "Pedir aprovação e aguardar"
    descricao = (
        "Apresenta algo a uma pessoa e PARA o trabalho até ela responder. Use antes de "
        "qualquer ação que não dá para desfazer (publicar, enviar, lançar num sistema) "
        "quando a sua documentação mandar confirmar com alguém. Passe na 'mensagem' "
        "tudo o que a pessoa precisa para decidir. Depois de chamar, NÃO faça mais "
        "nada: você continua quando a resposta dela chegar."
    )
    Config = ConfigPedirAprovacao
    Args = ArgsPedirAprovacao
    # Manda uma mensagem para fora (como o canal). Sinaliza o selo do catálogo e a
    # política de falha: se o pedido não chegou, o agente NÃO pode seguir como se
    # tivesse chegado.
    acao_irreversivel = True
    # O texto que a pessoa lê — é o que o motor carrega adiante como "o apresentado".
    campo_mensagem = "mensagem"
    # A marca que faz a execução PARAR (ver `orquestracao/agente.py`).
    pausa_para_humano = True

    def executar(self, config: ConfigPedirAprovacao, args: ArgsPedirAprovacao) -> dict:
        canal_id = (config.canal_instrumento_id or "").strip()
        if not canal_id:
            # Sem canal: a aprovação acontece pela tela da execução. Nada a enviar.
            return {
                "ok": True,
                "aguardando_aprovacao": True,
                "onde": "tela",
                "mensagem": args.mensagem,
            }
        try:
            cid = uuid.UUID(canal_id)
        except (ValueError, TypeError):
            raise FalhaInstrumento(
                "o canal do pedido de aprovação está mal configurado — escolha, na "
                "configuração do instrumento, por qual canal o pedido é enviado.",
                retentavel=False,
            )

        sessao = CriadorDeSessao()
        try:
            canal = sessao.get(Instrumento, cid)
            if canal is None or canal.tipo not in CANAIS_TIPOS:
                raise FalhaInstrumento(
                    "o canal configurado para o pedido de aprovação não existe mais "
                    "(ou não é um canal de mensageria) — reconfigure o instrumento.",
                    retentavel=False,
                )
            destinatario = (
                (canal.configuracao or {}).get("destinatario_padrao") or ""
            ).strip()
            if not destinatario:
                raise FalhaInstrumento(
                    f"o canal '{canal.nome}' não tem destinatário configurado — sem "
                    "ele não há para quem mandar o pedido nem de quem esperar a "
                    "resposta. Preencha o destinatário na configuração do canal.",
                    retentavel=False,
                )
            segredos = segredos_instrumento.decifrar(sessao, canal.id) or {}
        finally:
            sessao.close()

        # Envia pelo próprio tipo do canal — uma implementação de envio só.
        from instrumentos import obter_tipo

        tipo_canal = obter_tipo(canal.tipo)
        cfg_canal = tipo_canal.Config.model_validate(
            {**(canal.configuracao or {}), **segredos}
        )
        resultado = tipo_canal.executar(
            cfg_canal, tipo_canal.Args.model_validate({"mensagem": args.mensagem})
        )
        if not resultado.get("ok"):
            raise FalhaInstrumento(
                f"o pedido de aprovação não chegou a ninguém pelo canal "
                f"'{canal.nome}': {resultado.get('descricao') or 'envio recusado'}.",
                retentavel=True,
            )
        return {
            "ok": True,
            "aguardando_aprovacao": True,
            "onde": "canal",
            "mensagem": args.mensagem,
            "canal_instrumento_id": str(canal.id),
            "destinatario": destinatario,
        }


registrar(PedirAprovacao())
