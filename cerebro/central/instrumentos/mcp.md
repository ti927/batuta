---
titulo: "Instrumento — Conectar a servidor MCP"
area: "instrumentos"
slug: "mcp"
tags: ["mcp", "model-context-protocol", "integracao", "ferramentas", "servidor", "instrumento", "zapier", "composio", "connection token", "escolher ferramentas"]
revisado_em: "2026-09-22"
fontes: ["cerebro/instrumentos/mcp.py", "cerebro/orquestracao/agente.py", "docs/MCP-AGENTES.md"]
---

# Instrumento — Conectar a servidor MCP

## Em uma frase
Conecta o agente a um **servidor MCP** (Zapier, Composio, um servidor próprio) e põe no cinto dele
**as ferramentas que você escolher** entre as que o servidor publica.

## Para que serve / quando usar
O MCP (Model Context Protocol) é o padrão universal de integração de IA com sistemas. Serve em dois
casos: o sistema que você quer integrar **já expõe** um servidor MCP, ou você quer usar um
**agregador** (o Zapier publica milhares de ações) para não ter de manter a autenticação de cada
serviço dentro do Batuta.

O segundo caso tem um motivo forte: o Google exige verificação completa de app para escopos
restritos (Gmail, Drive), com auditoria anual. Falando com o Zapier — que já é verificado — essa fila
deixa de ser problema do Batuta. O custo é a dependência: conta por pessoa, cota de tarefas, e
descrições de ferramenta escritas por terceiros.

## Como usar (na tela)
1. Guarde a conexão na **central de credenciais** da organização, tipo **"Servidor MCP (endereço e
   token)"** — endereço e token juntos, porque um instrumento aponta para **uma** credencial só. O
   instrumento é do time; a credencial é da organização: a chave rotaciona num lugar só.
2. Crie o instrumento **Conectar a servidor MCP** apontando para essa credencial. Salve.
3. Reabra e use **"Conectar e listar ferramentas"**: o Batuta pergunta ao servidor o que ele publica.
4. **Marque as que entram no cinto** e, em cada uma, escolha **só lê** ou **pede aprovação**.
5. Pendure no cinto do agente.

**Nada vem marcado por padrão** — marcar tudo sozinho seria decidir por você o que essa tela existe
para você decidir.

## Autenticação, por servidor
- **Zapier** (caminho não-interativo): em `mcp.zapier.com` → *Add MCP Server* → em "Choose your AI
  agent" → **See all** → **Other** → aba *Connect* → **Generate token**. No Batuta: endereço
  `https://mcp.zapier.com/api/v1/connect` + o *connection token*. **O token aparece uma vez só**, e
  regerar invalida o anterior na hora.
  O server que aparece como *"Claude MCP Server"* é amarrado ao cliente Claude e só oferece OAuth —
  ele não mostra token nenhum, e não serve aqui.
- **Servidores que embutem a chave no endereço** (`.../mcp/u/<TOKEN>/stateless`, padrão do Make):
  aí a URL **é** a credencial — por isso o endereço é campo secreto no Batuta.

## Limites e cuidados
- Diferente dos outros instrumentos: **um** MCP vira **várias** ferramentas no cinto. Traga só as que
  o agente usa — cada ferramenta ocupa espaço no pedido e custa token em **todo** passo dele.
- **Toda ferramenta nasce pedindo aprovação.** O servidor é de terceiro e o Batuta não tem como saber
  o que cada uma faz. Marcar "só lê" é ato consciente de quem configura, e ninguém confere por você.
- Um MCP em que **nenhuma** ferramenta escolhida é irreversível não exige parede de ativação.
- **Servidor fora do ar não derruba o passo.** O agente roda sem esse instrumento, o rastro registra
  (`origem: "cinto"`), o banco de logs recebe `instrumento.cinto_falhou` e a IA é avisada — para ela
  dizer o que não deu, em vez de narrar sucesso sobre o que não teve.
- A lista de ferramentas fica em **cache por 10 minutos**. Adicionou uma ação no servidor e rodou no
  mesmo minuto? O agente ainda pode estar com a lista anterior. O botão de listar ignora o cache.
- Uma ferramenta escolhida que **sumiu** do servidor é ignorada (não derruba nada), e reaparece como
  "não existe mais no servidor" quando você lista de novo.
- Cada acionamento abre a própria conexão (sem estado entre chamadas).

## Para a IA
- Ao acionar isolado, o instrumento **testa a conexão e lista** as ferramentas — e **não** devolve a
  URL, que é segredo.
- Uma vez no cinto, as ferramentas do MCP aparecem como ferramentas normais do agente; as marcadas
  como irreversíveis param e pedem aprovação, as de leitura correm livres.
- Servidor de terceiro recém-criado costuma publicar **uma só** ferramenta, do tipo
  `get_configuration_url`: isso não é erro de conexão — é o servidor dizendo que ainda não tem ações
  configuradas. Não a ponha no cinto; ela não faz trabalho nenhum.

## Relacionado
- [[instrumentos/construir-conector]]
- [[instrumentos/chamar-rest]]
- [[instrumentos/cinto]]
- [[segredos/segredos-de-instrumento]]
- [[automacoes/pedir-aprovacao]]
