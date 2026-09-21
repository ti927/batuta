# MCP para os AGENTES — o Batuta como cliente de servidores MCP

> **Documento-fonte** desta frente. Aprovado pelo maestro em 2026-09-21.
> Não confundir com [`MCP-BATUTA.md`](MCP-BATUTA.md), que é o **sentido oposto**: lá o
> Batuta é um **servidor** MCP que o claude.ai do consultor aciona. Aqui o Batuta é
> **cliente**: o agente do time ganha, no cinto, as ferramentas de um servidor MCP de
> terceiro (Zapier, Composio, ou um MCP nativo qualquer).

---

## 1. Por que agora

O gatilho foi concreto. Em 2026-09-21 o Search Console do blog estava em HTTP 401 havia
dois meses; a conta Google tinha parado de renovar. Consertar a conta é um minuto — mas
**publicar o app OAuth do Batuta no Google não é**: os escopos que ele pede (Gmail,
Drive) são *restritos*, e isso significa verificação completa, prazo de semanas e
avaliação de segurança anual. Enquanto o app fica em *Testing*, o token de renovação
morre a cada 7 dias.

A saída que o maestro apontou: **não ser o intermediário**. O Zapier já é um app
verificado pelo Google, já mantém as conexões de milhares de serviços, e publica um
servidor MCP. Se o agente fala com o Zapier, a fila de verificação some — ela é problema
de quem já a resolveu.

**O que isso NÃO é:** bala de prata. A dependência muda de lugar, não desaparece — ver §7.

---

## 2. O que já existe (e por que nunca rodou)

O instrumento `conectar_mcp` existe desde **2026-06-06** (`cerebro/instrumentos/mcp.py`,
127 linhas). Ele conecta por `streamable_http`/`sse`, aceita cabeçalhos e um
`token_bearer` no cofre, e usa `expandir_ferramentas` — o mecanismo do encaixe pelo qual
UM instrumento vira VÁRIAS ferramentas no cinto.

**E tem zero instâncias em produção.** Não foi esquecimento: são quatro buracos, e cada
um sozinho já o inviabiliza.

| # | Buraco | Consequência |
|---|---|---|
| 1 | Traz **todas** as ferramentas do servidor | O Zapier publica dezenas. O cinto entope, o custo por passo sobe e o agente escolhe errado |
| 2 | `acao_irreversivel = True` fixo | **Toda** chamada para e pede aprovação — até uma consulta. Desligar libera tudo, inclusive o que apaga |
| 3 | Lista as ferramentas a cada passo, sem proteção | Servidor lento ou fora do ar **derruba o passo inteiro**, mesmo com os outros instrumentos sãos |
| 4 | A URL do Zapier carrega a chave | URL é campo aberto hoje: a chave apareceria na tela. Proibido (CLAUDE.md §8) |

---

## 3. Decisões travadas (2026-09-21)

1. **As quatro fatias saem juntas.** Sem a 1 e a 2 o Zapier não roda na prática; sem a 3
   ele não é confiável. Decisão do maestro: *"faz tudo junto"*.

2. **O instrumento é do TIME, como todos os outros.** A tabela `instrumentos` tem
   `time_id NOT NULL` e não tem `organizacao_id` — nenhum tipo é org-wide hoje (a
   decisão de 12/08 para o `conector` foi tomada e nunca construída). Fazer só o MCP
   org-wide criaria duas regras para a mesma palavra "Instrumento". Org-wide é frente
   separada, para **todos** os tipos de uma vez, com migração.

3. **O SEGREDO mora na central de credenciais**, não no instrumento. É o que resolve o
   custo do item 2: o instrumento é do time, mas a credencial é da **organização** —
   cinco times apontam para a mesma, e a chave rotaciona num lugar só. O tipo
   "Token de API (Bearer)" já existe e o `conectar_mcp` já o aceita.

4. **A URL é segredo.** Quando o servidor embute a chave no endereço (padrão do Zapier:
   `.../mcp/s/<chave>/mcp`), o endereço **é** a credencial. Entra em `campos_secretos` e
   ganha um tipo de credencial próprio. O preço — não dá para reler a URL depois de
   salva — é o mesmo de qualquer segredo, e o nome do instrumento diz qual servidor é.

5. **Uma ferramenta nasce pedindo aprovação.** O servidor é de terceiro e o Batuta não
   sabe o que cada ferramenta faz. Liberar é ato consciente, por ferramenta, com aviso —
   nunca o padrão.

---

## 4. As quatro fatias

### Fatia 1 — O cinto para de entupir
Ao configurar o instrumento, o Batuta conecta, lê a lista de ferramentas do servidor e a
pessoa **marca quais entram no cinto**. A escolha fica na config.

- `ConfigMCP` ganha `ferramentas: list[FerramentaMCP]` — `{nome, usar, irreversivel}`.
- `expandir_ferramentas` filtra por `usar`.
- **Lista vazia = todas** (compatibilidade com instâncias antigas; hoje não há nenhuma).

### Fatia 2 — A parede por ferramenta
Cada ferramenta escolhida tem seu próprio interruptor: *só lê* ou *pede aprovação*.

- A ferramenta expandida carrega `metadata={"irreversivel": bool}`.
- `agente.py` passa a ler esse `metadata` ao montar `irreversivel_por_ferramenta`, com o
  valor do instrumento como padrão — nada muda para quem não usa `expandir_ferramentas`.
- `ConectarMCP.irreversivel_para(config)` deixa de ser `True` fixo: é **True se alguma**
  ferramenta escolhida for irreversível. Um MCP só de consulta para de exigir portão.

### Fatia 3 — Servidor fora do ar não derruba o passo
- **Cache** da lista de ferramentas (TTL curto, em memória): hoje ela é buscada na rede a
  cada passo.
- **Isolamento**: montar o cinto passa a proteger cada instrumento. Um que falha vira
  aviso no rastro + evento no banco de logs (`instrumento.cinto_falhou`, nível `error`) —
  o passo segue com o resto. É a §12-A: o caminho degradado não pode ser mudo.

### Fatia 4 — A porta de entrada
Tela dedicada no lugar do formulário cru (URL + transporte + JSON de cabeçalhos):
cola-se a URL, o Batuta testa, mostra as ferramentas com o que cada uma faz, e a pessoa
marca as que quer e o nível de cada uma.

---

## 5. Como se prova

- **Offline (pytest):** servidor MCP dublê; filtro de ferramentas; `irreversivel_para`
  derivado; cinto que sobrevive a um instrumento quebrado; segredo que não vaza no
  retorno de "Acionar".
- **Ao vivo:** um MCP real do Zapier num time de teste, com uma ferramenta de leitura e
  uma de escrita — a de leitura roda direto, a de escrita para e pergunta.

---

## 6. O que NÃO entra nesta frente

- **OAuth para servidores MCP** (`BUILD-PLAN` linha 969). O Zapier resolve com chave na
  URL; OAuth fica para quando um servidor o exigir.
- **Instrumentos org-wide** — frente própria, com migração (§3.2).
- **Marketplace / catálogo de MCPs prontos.**

---

## 7. O risco, dito na cara

Trocar o OAuth próprio pelo Zapier **move** a dependência:

- **Conta por pessoa.** Cada conta Zapier tem plano e cota de tarefas próprios.
  Multi-cliente vira uma conta Zapier por cliente — custo recorrente que hoje não existe.
- **A descrição das ferramentas não é nossa.** O agente escolhe a ferramenta lendo texto
  escrito pelo Zapier. Quando ele erra, não há o que corrigir do nosso lado além de
  escrever melhor no markdown do agente.
- **Nem tudo está lá.** Antes de apostar num caso, conferir se o serviço existe no
  Zapier — o Google Search Console, que originou tudo isto, é justamente o que precisa
  ser confirmado.
- **Mais um elo que cai.** Um servidor MCP de terceiro é mais uma saída para fora do
  processo. Por isso a Fatia 3 não é opcional.


---

## 8. O caminho concreto do Zapier (2026-09-21)

O Zapier tem **três** formas de autenticar, e a primeira tentativa foi na errada. O
server que aparece como *"Claude MCP Server"* é amarrado ao cliente Claude e só oferece
OAuth — por isso ele não mostra token nenhum. Para um backend como o Batuta, o caminho
é o **connection token**:

1. `mcp.zapier.com` → **+ Add MCP Server**
2. Em *"Choose your AI agent"* → **See all** → **Other**
3. No server novo, aba **Connect** → **Generate token**

No Batuta, uma credencial `mcp` na central da organização com:

| Campo | Valor |
|---|---|
| Endereço do servidor MCP | `https://mcp.zapier.com/api/v1/connect` |
| Token de autenticação | o connection token |

A URL pronta que o Zapier oferece (`...?token=...`) **também** funciona, e é a pior das
duas: põe o segredo dentro do endereço, e endereço vaza em log com muito mais facilidade
que um campo cifrado. A própria documentação do Zapier prefere o cabeçalho.

**O token aparece uma vez só, e regerar invalida o anterior na hora** — o instrumento
para de funcionar até alguém colar o novo.

**Por que a credencial `mcp` tem DOIS campos:** um instrumento aponta para uma
credencial só. Com só o endereço nela, o token teria de ser colado no instrumento — e
aí cada time voltaria a ter uma cópia do segredo, que é exatamente o que tirá-lo do
instrumento resolveu. Os dois campos são opcionais porque os servidores diferem: o
Zapier usa endereço genérico + token; outros embutem a chave no caminho e não têm token.
