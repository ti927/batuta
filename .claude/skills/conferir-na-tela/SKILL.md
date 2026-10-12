---
name: conferir-na-tela
description: Use SEMPRE depois de publicar (push + deploy) qualquer mudança que aparece numa tela do Batuta, e sempre que o maestro pedir para testar, conferir, ver funcionando ou "olhar no navegador". Também quando bater a vontade de pedir ao maestro que teste, de subir servidor local para ver a tela, ou de dizer que não dá para testar a interface.
---

# Conferir na tela

Mudança de tela só está pronta depois de **vista funcionando em produção, por você**, no
Chrome do maestro (Claude in Chrome), em https://batuta.team. Não peça ao maestro que
teste. Não suba servidor local para isso. Não diga que não dá: dá, e já foi feito.

## Já autorizado: não peça licença

O maestro autorizou de forma permanente, só dentro de `batuta.team` (permissões em
`.claude/settings.json`):

- abrir a sua própria aba, navegar, rolar, redimensionar, tirar screenshot, ler a
  página e o console;
- clicar para **ler**: abas, categorias, sanfonas, popups, links internos, abrir
  agente/instrumento/execução, **Cancelar**, **X**, Esc;
- consultas **só de leitura** no banco (Supabase `vpedosymamgdghegjmjj`) para achar ids;
  Railway `list-deployments`/`get-logs`; `curl` no `/saude`.

## Precisa do ok do maestro na hora

Qualquer clique que **grava ou dispara algo real**: Salvar, Aplicar, Rodar, Testar este
passo, Ativar/Desativar, Excluir/Remover, Revogar/Trocar link, Enviar, Aprovar,
Conectar/Desconectar, Criar. Também digitar em campo de dado real. Pergunte em uma
linha, dizendo o que vai gravar e onde. Se ele aprovar, use nomes com **TESTES** e diga
no fim o que ficou criado.

## Passo a passo

1. **Antes:** commit e push feitos, suíte verde.
2. **Espere o deploy dos DOIS serviços.** O cérebro sobe antes. Screenshot cedo demais
   mostra a tela VELHA, e aí você diagnostica um defeito que não existe.
   - cérebro, em segundo plano:
     `until curl -s https://api.batuta.team/saude | grep -q <hash7>; do sleep 20; done`
   - interface: Railway `list-deployments` (projeto
     `150f4d27-de0b-4ef6-952b-8f3f5af84e38`, serviço interface
     `7a417c6d-d69a-4374-aa27-13ed3c19d227`) até `SUCCESS` com o seu commit. Leva de 4 a
     5 min. Espere com `sleep 150` em segundo plano, não com consulta repetida.
3. **Ache a tela** (tabela abaixo; ids pelo banco).
4. **Navegue e percorra cada promessa da mudança**: o que o commit diz que mudou, item
   por item, inclusive o caso com dado real (não só o vazio). Mudou layout de celular?
   `resize_window` para 390 px de largura.
5. **Console:** `read_console_messages` com `onlyErrors: true`.
6. **Deixe como achou:** Cancelar/fechar o que abriu e `tabs_close_mcp` na sua aba.
7. **Relate:** cada promessa com ✓ ou ✗ e o que você viu; o que não deu para conferir e
   por quê. Achou defeito? É bug: corrija antes de dar por pronto.

## Onde fica cada tela

| Tela | Endereço |
|---|---|
| Estúdio (automações) | `/times/{time}/estudio` |
| …já com Configurações aberta | `/times/{time}/estudio?automacao={id}&config=` (ou `config=tempo`, `execucao`, `conversa`, `espera`) |
| Agentes · Instrumentos · Conversas | `/times/{time}/agentes` · `/instrumentos` · `/conversas` |
| Execuções · uma execução | `/times/{time}/execucoes` · `/execucoes/{execucao}` |
| Ligações do sistema · Uso | `/status` · `/uso` |

```sql
select id, nome from times order by nome;
select id, nome from automacoes where time_id = '<time>' order by nome;
```

## Quando não dá

| Situação | O que fazer |
|---|---|
| Ferramenta do Chrome falha / aba inválida | `tabs_context_mcp` de novo. Falhou 2 vezes? Diga ao maestro que a extensão do Chrome parece desconectada e o que ficou sem conferir. |
| Caiu na tela de entrar (sessão expirou) | Peça ao maestro que entre. Você nunca digita senha. |
| A tela parece velha | Confira o deploy da interface (passo 2) e recarregue a página. |
| Tentação de subir o cérebro local | Não. O banco local é o de produção, e o agendador local dispara automações reais (já duplicou publicações). |

## Erros que já aconteceram

- Conferir só o `/saude` e tirar screenshot com a interface ainda publicando.
- Pedir ao maestro que teste, ou listar "limitações" em vez de abrir o navegador.
- Clicar em Salvar ou Aplicar "para ver se grava" sem o ok dele.
- Esquecer a aba aberta no navegador do maestro.
