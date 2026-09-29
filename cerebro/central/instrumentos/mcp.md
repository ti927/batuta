---
titulo: "Instrumento — Conectar a servidor MCP"
area: "instrumentos"
slug: "mcp"
tags: ["mcp", "model-context-protocol", "integracao", "ferramentas", "servidor", "instrumento", "zapier", "make", "wordpress", "senha de aplicativo", "basic", "x-api-key", "autenticação", "sse", "composio", "connection token", "escolher ferramentas"]
revisado_em: "2026-09-29"
fontes: ["cerebro/instrumentos/mcp.py", "cerebro/instrumentos/mcp_conexao.py", "cerebro/orquestracao/agente.py", "docs/MCP-AGENTES.md"]
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
1. Crie o instrumento **Conectar a servidor MCP** no time.
2. Em **"Como o Batuta se conecta"**, cole o **endereço** do servidor e escolha **como ele pede
   identificação** (tabela abaixo). Tudo fica **dentro do instrumento** — não é mais preciso criar
   credencial na central.
3. Salve e use **"Conectar e listar ferramentas"**: o Batuta conversa com o servidor, descobre o tipo
   de conexão e mostra o que ele oferece.
4. **Marque as ferramentas que entram no cinto** e, em cada uma, escolha **só lê** ou **pede
   aprovação**. Se o servidor declarar que uma ferramenta só lê ou que altera algo, isso aparece como
   **sugestão** — quem decide é você.
5. Pendure no cinto do agente.

**Nada vem marcado por padrão** — marcar tudo sozinho seria decidir por você o que essa tela existe
para você decidir.

## Como o servidor pede identificação
| Modo | Quando usar | O que o consultor cola |
|---|---|---|
| **A chave já está no endereço** | Make, Zapier e servidores cujo endereço leva a chave (`.../mcp/u/<TOKEN>/...`) | Só o endereço (ele é o segredo) |
| **Token (Bearer)** | O servidor pede `Authorization: Bearer ...` — é o caso do Zapier pelo caminho "Other" | Endereço + token |
| **Usuário e senha** | **WordPress** (plugin MCP Adapter) e sistemas com login simples | Endereço + usuário + senha. No WordPress, uma **senha de aplicativo** (Usuários → Perfil → Senhas de aplicativo), nunca a senha de entrar |
| **Cabeçalho próprio** | A documentação pede um cabeçalho com nome próprio, ex.: `X-API-Key` | Endereço + nome do cabeçalho + valor |
| **Chave no endereço (parâmetro)** | A documentação pede `?api_key=...` no endereço | Endereço + nome do parâmetro + valor |
| **Não pede identificação** | Servidor público ou interno aberto | Só o endereço |

Além do modo, há **cabeçalhos extras** (ex.: `X-Tenant`), cada um podendo ser marcado como protegido.
Em **Avançado**, o tipo de conexão fica em **Automático**: o Batuta tenta o formato atual do MCP e,
se o servidor for antigo (SSE), troca sozinho. Instrumentos criados antes deste ajuste seguem como
estavam (token = Bearer; sem token = sem identificação).

### Exemplos
- **Zapier**: em `mcp.zapier.com` → *Add MCP Server* → em "Choose your AI agent" → **See all** →
  **Other** → aba *Connect* → **Generate token**. No Batuta: endereço
  `https://mcp.zapier.com/api/v1/connect` + modo **Token** com o *connection token*. **O token aparece
  uma vez só**, e regerar invalida o anterior na hora. O server *"Claude MCP Server"* do Zapier só
  oferece login próprio do Claude e não serve aqui.
- **Make**: o endereço já traz a chave → modo **A chave já está no endereço**.
- **WordPress da Lure** (MCP Adapter): endereço `https://<site>/wp-json/mcp/mcp-adapter-default-server`
  + modo **Usuário e senha** com o usuário do WordPress e uma **senha de aplicativo** dele.

### Quando a conexão falha
A tela diz o que houve e o que fazer, com um código para o diagnóstico. Os mais comuns:
`mcp.auth_401` (identificação recusada: confira token/senha/chave), `mcp.auth_403` (a conta não tem
permissão), `mcp.endereco_404` (endereço errado), `mcp.fora_do_ar`, `mcp.tempo_esgotado`,
`mcp.segredo_faltando` (falta preencher um pedaço do modo escolhido). A mensagem **nunca** mostra o
endereço nem o segredo.

## Limites e cuidados
- Diferente dos outros instrumentos: **um** MCP vira **várias** ferramentas no cinto. Traga só as que
  o agente usa — cada ferramenta ocupa espaço no pedido e custa token em **todo** passo dele.
- **Toda ferramenta nasce pedindo aprovação.** O servidor é de terceiro e o Batuta não tem como saber
  o que cada uma faz. Marcar "só lê" é ato consciente de quem configura, e ninguém confere por você.
- Um MCP em que **nenhuma** ferramenta escolhida é irreversível não exige parede de ativação.
- **Servidor fora do ar não derruba o passo.** O agente roda sem esse instrumento, o banco de logs
  recebe `instrumento.cinto_falhou` (com o código da causa), a IA é avisada — para ela dizer o que não
  deu, em vez de narrar sucesso sobre o que não teve — e o **diagnóstico da execução** acusa "o agente
  rodou sem o instrumento", com o que fazer.
- A lista de ferramentas fica em **cache por 10 minutos**. Adicionou uma ação no servidor e rodou no
  mesmo minuto? O agente ainda pode estar com a lista anterior. O botão de listar ignora o cache.
- Uma ferramenta escolhida que **sumiu** do servidor é ignorada (não derruba nada), e reaparece como
  "não existe mais no servidor" quando você lista de novo.
- Cada acionamento abre a própria conexão (sem estado entre chamadas).

## Para a IA
- **Ao criar** (`configurar_instrumento` tipo `conectar_mcp`): a identificação mora **no instrumento**
  — não crie credencial na central. Escolha `auth_modo` pelo que o servidor pede: `url_secreta`
  (Make/Zapier com a chave no endereço), `bearer`, `cabecalho` (+ `auth_nome`), `query` (+
  `auth_nome`), `basic` (+ `auth_usuario`; WordPress) ou `nenhuma`. Deixe `transport` em
  `automatico`. **Você não passa segredo**: o endereço, o token, a senha e o valor da chave são
  colados pelo consultor na tela do instrumento — se vierem na configuração, são ignorados.
- Ao acionar isolado (`testar_instrumento`), o instrumento **testa a conexão e lista** ferramentas,
  recursos e prompts — e **não** devolve a URL, que é segredo. Cada ferramenta traz `sugestao`
  (`so_le`/`altera`/vazio): é o que o **servidor** declara. Use como pista ao decidir `irreversivel`,
  nunca como garantia — na dúvida, pede aprovação.
- Falhou? Leia o `codigo`: `mcp.auth_401` → a identificação está errada (peça ao consultor para
  conferir, não troque de modo às cegas); `mcp.segredo_faltando` → falta o consultor colar algo;
  `mcp.transporte_incompativel` → deixe `transport` em `automatico`.
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
