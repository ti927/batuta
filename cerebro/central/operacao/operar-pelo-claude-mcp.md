---
titulo: "Operar o Batuta pelo Claude (conector MCP)"
area: "operacao"
slug: "operar-pelo-claude-mcp"
tags: ["mcp", "claude", "conector", "consultor", "custo", "integração"]
revisado_em: "2026-08-26"
fontes: ["docs/MCP-BATUTA.md", "cerebro/mcp_servidor.py", "cerebro/mcp_login.py", "cerebro/mcp_ferramentas.py", "cerebro/mcp_ferramentas_escrita.py"]
---

# Operar o Batuta pelo Claude (conector MCP)

## Em uma frase

O Batuta é também um **conector MCP** que o consultor liga no **próprio claude.ai** para
criar, ajustar e diagnosticar times conversando — a IA rodando na **assinatura dele**,
não na conta do Batuta.

## Para que serve / quando usar

A montagem de um time é trabalho de consultor. Fazê-la pelo claude.ai do consultor tira
esse custo de IA da conta do Batuta e o põe na assinatura (custo fixo) de quem monta —
de forma permitida pela Anthropic (o app do usuário é que aciona a ferramenta). É um
**caminho a mais**, ao lado da IA criadora dentro do app: a criadora continua igual.

## Como usar (na tela)

1. No claude.ai (Pro/Max): **Configurações → Conectores → Adicionar conector
   personalizado** e cole a URL do MCP do Batuta terminando em **`/mcp`**.
2. Clique em **Vincular**: aparece a **telinha de login do Batuta** — entre com seu
   e-mail e senha (os mesmos do app).
3. Ative o conector na conversa e peça em linguagem natural: *"liste meus times"*,
   *"crie um agente…"*, *"o que deu errado na última execução?"*.

## Exemplos

- *"Monte um conector para esta API: \<cola a documentação\>"* → o Claude cria o
  instrumento conector e testa as operações.
- *"Duplica o time Post Blog com o nome Post Blog 2"* → clona o time inteiro.

## Limites e cuidados

- **Login real e escopo por papel:** você só enxerga e mexe nas suas organizações/times,
  conforme seu papel (observador lê; operador cria/edita; admin cria organização/time e
  exclui).
- **A IA nunca pluga segredo:** ao criar credenciais ou conectores, o segredo (senha,
  chave de API) fica **pendente** — você o cola no **cofre do Batuta pela tela**, nunca
  no chat. Segredo não passa pelo claude.ai.
- **Ativar não tem mais trava:** o Batuta não recusa mais uma automação com ação
  irreversível. Quem segura uma ação que precisa de gente é o agente, pelo instrumento
  [[automacoes/pedir-aprovacao]].
- **Exclusões são irreversíveis.** O Claude confirma com você antes. Excluir uma **organização** só é
  possível quando ela está **vazia** (sem nenhum time): o Batuta recusa e explica o que precisa sair antes,
  em vez de apagar times, execuções e credenciais em cascata.
- **Depois de uma atualização do Batuta, reconecte o conector** (remova e adicione de novo). O claude.ai
  guarda a lista de ferramentas; sem reconectar, ferramentas novas não aparecem e nomes antigos continuam
  visíveis mesmo já tendo mudado.
- **Se uma ferramenta falhar**, a resposta traz um **código** — cite-o ao pedir ajuda: ele aponta o registro
  exato do erro no servidor (veja [[operacao/sinais-e-diagnostico]]).

## Para a IA

- Este capítulo descreve o **canal** (conector MCP), não uma ferramenta de instrumento.
- As regras de negócio (papéis, "a IA nunca pluga o token", aprovação pelo agente)
  são as MESMAS da criação dentro do app — não há exceção pelo fato de vir do MCP.
- Ordem de trabalho pelo MCP: **ler antes de escrever** (retrato do time, agentes,
  execuções); consultar a Central quando não souber COMO um recurso funciona; deixar
  segredos pendentes para o humano; dar ao agente o instrumento de pedir aprovação
quando a ação for irreversível e alguém precisar confirmar.
- **Instrumento se lê, não se adivinha.** O cinto de um agente vem como uma lista de ids;
  para saber o que cada um é (nome, tipo, configuração, segredos que faltam), use as
  ferramentas de listar/ver instrumento — inclusive para conferir o que foi criado pela
  tela. Nunca deduza a configuração de um instrumento pelo nome dele.
- **Ligar/desligar é da AUTOMAÇÃO, não do time.** As ferramentas de ativar e desativar
  recebem o id de uma automação e não mexem no time nem nos agentes. Ao confirmar com o
  consultor, diga o nome da automação — dizer "vou desligar o time" descreve outra coisa.
- **Gatilho e cadeia convivem:** definir o gatilho e montar a cadeia podem ser feitos em
  qualquer ordem; o Batuta mantém os dois coerentes sozinho.

## Relacionado

- [[uso-e-custos]]
- [[cinto]]
