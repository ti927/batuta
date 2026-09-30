---
titulo: "Instrumento do time ou da organização"
area: "instrumentos"
slug: "escopo-do-instrumento"
tags: ["escopo", "organização", "organizacao", "compartilhar instrumento", "todos os times", "usado por", "promover", "reutilizar", "bot de avisos", "aprovação compartilhada"]
revisado_em: "2026-09-30"
fontes: ["cerebro/escopo_instrumento.py", "cerebro/rotas/instrumentos.py", "cerebro/mensageria/aprovacao.py", "cerebro/duplicacao_time.py"]
---

# Instrumento do time ou da organização

## Em uma frase
Um instrumento pode ser **só do time** (o padrão) ou **de toda a organização**: aí qualquer time dela
o põe no cinto dos seus agentes, e a identificação (senha, token, login) é feita **uma vez** e serve a
todos.

## Para que serve / quando usar
- **Da organização:** o que é da empresa inteira e vários times usam igual — o WordPress do site, um
  servidor MCP da empresa, um bot de Telegram só para avisos e pedidos de aprovação. Troca de senha num
  lugar só; nenhum time fica com uma cópia esquecida.
- **Do time:** o que é de um fluxo só, ou que tem configuração própria daquele time (um destinatário
  específico, uma categoria de blog, um canal de conversa com clientes).

## Como usar (na tela)
1. Ao criar ou editar o instrumento, em **Quem pode usar**, escolha **Todos os times da organização**.
   Só **administradores** veem essa opção. No Construtor de uma API (conector), ela fica em
   **Identidade**; no do servidor MCP, no fim do formulário.
2. Nos outros times, ele aparece na lista de instrumentos com o selo **da organização** — é só pôr no
   cinto do agente. **Operador pode encaixar**; mudar a configuração ou os segredos é só com admin.
3. A seção **Usado por** mostra quais times, agentes e automações dependem dele.

## Limites e cuidados
- **Mudar a configuração muda para todos os times** que o usam — a tela avisa. Confira o *Usado por*
  antes.
- **Excluir é recusado enquanto algum agente o usa** (vale para todo instrumento): a tela diz quem, e o
  caminho é tirá-lo do cinto primeiro.
- **Voltar para "só este time" é recusado enquanto outro time o usa.**
- **Bot de Telegram da organização não atende conversa.** Ele só envia avisos e pedidos de aprovação e
  recebe as respostas desses pedidos; mensagem solta recebe um aviso curto. Para conversar com clientes,
  use um bot do time.
- **Vários times aprovando pelo mesmo bot funciona**: cada pedido sai com os botões **Aprovar /
  Recusar**, e a resposta volta para a execução certa — ver [[automacoes/pedir-aprovacao]].
- **Duplicar um time** não copia o instrumento da organização: a cópia usa o mesmo, já conectado.
- **Excluir o time onde o instrumento foi criado** não o apaga: ele passa a morar num time que o usa.
- **Custo e rastro** ficam com o time que executou, não com o time onde o instrumento mora.
- **Um serviço, várias contas** (ex.: um serviço de redes sociais com a conta de cada marca): o
  instrumento da organização não fixa a conta — cada agente diz, no texto dele, **em qual conta** age
  (o id da conta no serviço). Assim um time não publica na conta de outro.

## Para a IA
- `configurar_instrumento(..., escopo="organizacao")` cria da organização (exige admin);
  `editar_instrumento(..., escopo=...)` promove ou rebaixa (admin; rebaixar é recusado enquanto outro
  time usa). `listar_instrumentos` de um time já traz os da organização (campo `escopo`), e
  `encaixar_instrumento` aceita encaixá-los em qualquer time dela.
- Antes de mudar a configuração de um instrumento da organização, leia `usado_por` em
  `ver_instrumento` e **avise o consultor** de quem será afetado.
- Sugira **organização** quando o mesmo sistema aparece em vários times com a mesma identificação;
  sugira **time** quando a configuração é própria do fluxo. Canal de conversa: sempre time.

## Relacionado
- [[instrumentos/cinto]]
- [[instrumentos/mcp]]
- [[automacoes/pedir-aprovacao]]
- [[admin/duplicar-time]]
