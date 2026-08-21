---
titulo: "Operar o Batuta pelo Claude (conector MCP)"
area: "operacao"
slug: "operar-pelo-claude-mcp"
tags: ["mcp", "claude", "conector", "consultor", "custo", "integração"]
revisado_em: "2026-08-21"
fontes: ["docs/MCP-BATUTA.md", "cerebro/mcp_servidor.py", "cerebro/mcp_login.py"]
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
- **A parede de aprovação continua valendo:** ativar uma automação com ação irreversível
  sem portão humano é recusado.
- **Exclusões são irreversíveis.** O Claude confirma com você antes.

## Para a IA

- Este capítulo descreve o **canal** (conector MCP), não uma ferramenta de instrumento.
- As regras de negócio (papéis, parede, "a IA nunca pluga o token", portão de aprovação)
  são as MESMAS da criação dentro do app — não há exceção pelo fato de vir do MCP.
- Ordem de trabalho pelo MCP: **ler antes de escrever** (retrato do time, agentes,
  execuções); consultar a Central quando não souber COMO um recurso funciona; deixar
  segredos pendentes para o humano; pôr portão antes de ação irreversível.

## Relacionado

- [[uso-e-custos]]
- [[cinto]]
