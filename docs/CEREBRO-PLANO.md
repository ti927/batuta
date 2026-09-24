# O CÉREBRO da organização — Quadros, Arquivos e Biblioteca

**Plano de construção. Escrito em 2026-09-24.** Substitui a "FASE — Biblioteca" como estava no `BUILD-PLAN.md` e absorve o
`docs/BIBLIOTECA-DECISAO.md`, que vira a **Parte 4** deste plano.

> Estado (2026-09-24): **Entregas 1, 2, 3 e 4 ✅** — a fundação (migração `qdr00quadros001`, `cerebro/quadros/`), o
> instrumento `quadro` (o agente lê e grava), as IAs operando (6 ferramentas na criadora, 13 no MCP, diagnóstico com
> `quadros_gravados`) e a **tela** (menu Cérebro). Suíte 1412; `tsc`/`eslint`/`build` limpos. **Próxima: Entrega 5 —
> Radar e Painel migram da planilha (reescrever markdowns pede aval).**
>
> *Entrega 4, como ficou:* proposta visual aprovada (`claude.ai/artifact/NJi4o3QPvPwWUJJxQsZjYq`) com UMA mudança do
> maestro — **lista em cartões horizontais, um por linha, e sempre com busca/filtro** (virou preferência permanente).
> Menu "Biblioteca" → **"Cérebro"** (`/organizacoes/[id]/cerebro`, a org ativa; `/biblioteca` redireciona). Quadro com
> abas Linhas (busca livre no servidor, filtros removíveis, "só a mais recente de", "gravado por" com nomes, painel da
> linha com histórico, apagar o que uma execução gravou com prévia), Colunas (trocar tipo/remover só depois de "ver o que
> muda"), Quem usa, Limites (ajustáveis). Importar CSV com prévia de TODAS as linhas com problema, mapeamento por coluna,
> pular linhas, substituir pela chave. Instrumento `quadro` voltou à lista da tela com **seletor** (`ui: quadro`) e
> escolha só ler × ler e gravar (`ui: acesso_quadro`). **Importação ficou direta, não em segundo plano:** medida, 5.000
> linhas levavam 8 s; a gravação de linhas novas passou a ser EM LOTE (2 s) — cabe numa chamada com cronômetro. Se um
> caso real passar disso, vira fila. Área "Cérebro" entrou no /ajuda.

---

## 1. Por que o plano mudou

A Biblioteca foi planejada em julho como um lugar onde **uma pessoa sobe documentos e o agente só lê**. Ao revisitar o plano
em 2026-09-24, o maestro trouxe a necessidade real, e ela é outra: **os agentes precisam passar informação uns para os
outros**, inclusive entre times.

Hoje isso é feito com planilha do Google. O caso que mostrou o problema está no ar, no time 📈 COF Post Blog:

- **Radar IA semanal** pergunta às IAs se citam a Lure e grava as abas *Historico* e *Lacunas* de uma planilha.
- **Painel Lure – coleta semanal** (Coletor) lê a planilha para saber que semanas faltam, grava *Semanal*, *WhatsApp* e
  *Buscas*, e lê o *Radar*. O Briefing, logo depois, lê as *Lacunas* e escreve uma linha por tema na aba *Briefing*.
- **Os 5 Analistas dos blogs**, em outros times, leem a linha do seu tema antes de escolher a pauta.

O que isso custa, medido nas execuções:

1. **O agente faz papel de banco de dados.** O markdown dele carrega a tabela de semanas escrita à mão até 2027, regras como
   *"descarte linhas cuja Data não seja data (ex.: 'teste')"*, *"se a pergunta aparecer duas vezes, vale a última"*,
   endereços de célula fixos (`Briefing!A2:D2`), o formato JSON para copiar e *"quebra de linha gera erro 400"*. Cada regra
   é um lugar onde a IA erra calada.
2. **Caro e crescente.** Para saber o que falta, o Coletor lê a aba inteira toda semana. A carga histórica de 24/09 fez
   **64 chamadas** numa execução.
3. **Quebra por fora.** Em 23/09 o Radar falhou duas vezes com *acesso negado (HTTP 403)* ao gravar na planilha.
4. **Cada troca exige montar uma operação de conector** (uma por aba, para ler e para gravar), repetida em cada time que lê.
5. **A memória do agente não serve**: ela é individual. O Radar compara semanas pela própria memória, que o Coletor e os
   Analistas não enxergam.

O `PRODUTO.md §9` sempre descreveu a Biblioteca como **via de mão dupla** (*"os agentes podem alimentar"*). Este plano volta a
essa visão e a amplia: o Batuta é automação **generalizada**, e o mesmo problema aparece em financeiro, estoque, RH, comercial,
atendimento e jurídico (ver §3).

---

## 2. O que é o Cérebro

O cérebro da organização tem **três partes**. Uma quarta, a memória de cada agente, já existe e continua como está.

| Parte | O que guarda | Quem escreve | Quem lê | Parte do plano |
|---|---|---|---|---|
| **Quadros** | Dados com colunas e tipos: registros, fichas, filas de trabalho, tabelas de apoio | Agentes **e** pessoas | Agentes, pessoas, IA criadora, IA externa (MCP) | 1 e 2 |
| **Arquivos** | PDF, Word, planilha anexados a uma linha de quadro (a nota fiscal, o currículo) | Agentes e pessoas | Idem, **com leitura do conteúdo** | 3 |
| **Biblioteca** | Documentos da empresa pesquisáveis **por sentido** | Pessoas (v1) | Agentes | 4 |
| Memória do agente *(já existe)* | O que **um** agente aprendeu | O próprio agente | Só ele | — |

### A regra de fronteira (o que o Cérebro NÃO é)

> **Se a empresa já tem um sistema onde aquilo mora, a fonte da verdade é esse sistema. O Quadro guarda o que é do trabalho
> dos agentes**: o estado da tarefa, o que já foi feito, o que um agente deixou para o outro, o histórico que ninguém mais
> guarda.

Portanto o Cérebro **não é**:

- **O sistema oficial.** Estoque real, contabilidade, folha e o Bubble dos reembolsos continuam onde estão. O Batuta lê e
  escreve neles por instrumento. Estoque "de verdade" alimentado por IA num quadro seria estoque errado.
- **Ferramenta de BI.** Tabela, filtro e totais sim; painel gerencial com gráficos, não. Uma ferramenta de BI pode ler os
  Quadros.
- **Terra de ninguém.** Quadro tem dono e quem o cria é gente (ou a IA criadora a pedido de gente), nunca um agente no
  meio de uma execução.

---

## 3. Para quem serve: os padrões por trás de todos os departamentos

O levantamento com o maestro, em 2026-09-24, cobriu financeiro (contas a pagar, conciliação, cobrança, fechamento, tabelas
de apoio), estoque e compras (ruptura, pedidos em curso, histórico de preço, divergência no recebimento), RH (recrutamento,
admissão, férias, clima/NR-1, desligamentos), comercial (leads, propostas, objeções), atendimento (chamados, respostas que
funcionaram), jurídico (contratos e prazos), operação de consultoria (situação por cliente) e marketing (o Radar e o Painel).

Todos caem em **oito padrões**. É por eles que o Cérebro é desenhado, não pelo caso do marketing:

| # | Padrão | Exemplo | Onde entra |
|---|---|---|---|
| 1 | **Registro que acumula** | Rodadas do Radar, histórico de preços | Parte 1 |
| 2 | **Ficha por chave** (substitui, não duplica) | Briefing por tema, situação do cliente | Parte 1 |
| 3 | **Tabela de apoio** (pessoa cuida, agente lê) | Alçadas, centros de custo, a tabela de semanas | Parte 1 |
| 4 | **"Já processei?"** | Nota já lançada, semana já coletada | Parte 1 |
| 5 | **Totais calculados** | Quanto devo este mês, candidatos por etapa | Parte 1 — **o Batuta calcula, nunca a IA** |
| 6 | **Fila com etapas** (o item passa de mão em mão) | Contas a pagar, recrutamento, compras | Parte 2 — trava para dois agentes não pegarem o mesmo item |
| 7 | **Algo muda, outra automação acorda** | Nota aprovada dispara o pagamento | Parte 2 — gatilho "quando o quadro muda" |
| 8 | **Prazo** | Contrato vencendo, cobrança | Parte 2 — gatilho "quando a data de uma linha chega" |

Com os padrões 6 a 8, os Quadros deixam de ser um lugar de anotação e passam a **mover trabalho entre agentes e times**.

---

## 4. Decisões

### Travadas com o maestro (2026-09-24)

1. **O Cérebro é da ORGANIZAÇÃO**, compartilhado entre times.
2. **Tudo é visível, editável e criável pelo usuário.** O que um agente consegue fazer num quadro, uma pessoa consegue pela
   tela, e tudo fica registrado do mesmo jeito. Criação pela tela, por importação de planilha/CSV, pela IA criadora e pelo MCP.
3. **Papéis:** observador vê; operador cria quadros e edita linhas e colunas; admin exclui quadro.
4. **Não se edita, de propósito:** o carimbo de quem gravou e quando, e o histórico de alterações.
5. **Arquivos ficam fora da primeira versão.** Entram na Parte 3 (coluna "arquivo" com leitura do conteúdo) e na Parte 4
   (Biblioteca), as duas sobre a **mesma** extração de texto, construída uma vez.
6. **Ordem:** Quadros → gatilhos e fila → Arquivos → Biblioteca.
7. **As IAs criadora e externa aprendem junto, em toda entrega** (§8), e o **MCP ganha funções flexíveis** (§7).

### Propostas: valem salvo objeção do maestro

- **P1. O Batuta vira a fonte da verdade** dos dados que hoje estão na planilha do Radar e do Painel. Uma cópia para o Google
  Sheets, só para leitura, pode vir depois. Duas fontes de verdade editáveis divergem (`feedback-bug-recorrente-fonte-de-verdade`).
- **P2. Quem escreve:** qualquer time que tenha o instrumento de **escrita** daquele quadro. A tela mostra, em cada quadro,
  quem lê e quem escreve.
- **P3. Quem cria quadro:** pessoas (tela, importação, IA criadora a pedido, MCP). **Agentes não criam quadro** durante uma
  execução.
- **P4. O gatilho "quando o quadro muda" fica para a Parte 2**, não para a primeira entrega. Ele mexe em como automações
  disparam e merece entrega própria.
- **P5. Agente não apaga linha na v1.** Pessoa apaga pela tela; apagar pelo agente, se vier, será ação irreversível com
  aprovação.
- **P6. Nome e lugar na navegação**: o item "Biblioteca" do menu vira **"Cérebro"**, com abas *Quadros* (e depois *Biblioteca*),
  no nível da organização ativa. **É mudança de tela: vai como proposta visual antes** (`feedback-perguntar-antes-de-mexer-ui`).

---

## 5. Parte 1 — Quadros (o núcleo)

### 5.1 Modelo de dados

Três tabelas novas, todas com `organizacao_id` (isolamento em toda consulta):

- **`quadros`**: `id`, `organizacao_id`, `nome`, `descricao` (para que serve, lido pelas IAs), `colunas` (JSONB: lista de
  `{id, nome, tipo, obrigatoria, opcoes, descricao}`), `chave` (lista de ids de coluna que identificam a linha; vazia =
  registro que só acumula), `criado_por_id`, `criado_em`, `atualizado_em`, `arquivado_em`.
- **`quadro_linhas`**: `id`, `quadro_id`, `organizacao_id`, `valores` (JSONB `{coluna_id: valor}`), `chave_valor` (texto
  normalizado da chave, **único por quadro** quando há chave, e é isso que torna a "gravação pela chave" atômica), `versao`,
  e o **carimbo**: `origem` (`agente` | `pessoa` | `ia_criadora` | `mcp` | `importacao`), `agente_id`, `execucao_id`,
  `usuario_id`, `criado_em`, `atualizado_em`.
- **`quadro_alteracoes`**: o histórico. `linha_id`, `antes`, `depois`, o mesmo carimbo e `quando`. Só se acrescenta; ninguém
  edita.

**Por que JSONB e não uma tabela de verdade por quadro:** criar tabela no banco a cada quadro que o usuário inventa (DDL
dinâmico) é frágil em migração, permissão e backup. JSONB com índice GIN aguenta confortavelmente centenas de milhares de
linhas por organização, e os totais saem por SQL com conversão de tipo. **Se um quadro crescer além disso, é sinal de que o
dado mora num sistema oficial** (regra de fronteira), e não de que precisamos de outra arquitetura.

**Tipos de coluna na v1:** texto curto, texto longo, número, dinheiro (número com 2 casas), data, data e hora, sim/não,
opção (lista fechada, útil para *estado*: pendente/aprovado/pago). Planejados: **arquivo** (Parte 3), **ligação para linha de
outro quadro** (sob demanda).

**Validação é do Batuta, não do agente:** data que não é data, número que não é número, opção fora da lista e obrigatória
vazia são **recusadas por escrito**, dizendo qual linha, qual coluna e o porquê. **A chamada é tudo-ou-nada**: com qualquer
recusa, nada é gravado. Assim o agente nunca precisa adivinhar o que entrou pela metade.

### 5.2 A camada única

Um serviço só (`cerebro/quadros/`) faz tudo: criar, alterar colunas, gravar, consultar, totalizar, histórico. **Agente, tela,
IA criadora e MCP chamam o mesmo serviço.** É a lição de `feedback-bug-recorrente-fonte-de-verdade`: regra espelhada em quatro
portas é regra que diverge.

### 5.3 O instrumento `quadro`

Um tipo novo de instrumento, **um por quadro e por nível de acesso**, e isso é o que torna o compartilhamento **explícito**. O
time do RH só enxerga o quadro de admissões se tiver o instrumento apontando para ele.

- **Configuração:** `quadro_id` (escolhido numa lista dos quadros da organização) e `acesso`: `ler` ou `ler_e_escrever`.
- **Ações** (o instrumento se abre em várias ferramentas, pelo `expandir_ferramentas` que o conector já usa):
  - **consultar**: filtros, ordem, colunas, limite; e o atalho **"só a mais recente de"** (ex.: *as lacunas da rodada mais
    recente*), padrão que apareceu no Radar e no Painel;
  - **totais**: agrupar por coluna e somar, contar, média, mínimo, máximo. **Número calculado pelo banco**, porque IA somando
    é onde ela erra calada;
  - **já existe?**: recebe valores da chave e responde quais já estão gravados. Substitui o *"leia a aba inteira para achar o
    que falta"* do Coletor;
  - **acrescentar linhas**;
  - **gravar pela chave**: cria ou substitui (o briefing do tema COF sobrescreve o da semana passada, sem `A2:D2`);
  - **atualizar campos** de linhas achadas pela chave.
- **A ferramenta se descreve sozinha:** as colunas, os tipos, as opções e a descrição do quadro entram na descrição da
  ferramenta que o modelo vê. **O markdown do agente não precisa ensinar formato de dado**: some a regra de "JSON numa linha
  só" e de "copie o formato".
- **Leitura enxuta:** a consulta devolve em forma de tabela compacta, com teto de linhas e o aviso *"há mais N linhas"*
  (nunca corta calado).
- **Carimbo automático:** quem gravou (agente e execução) vem do contexto de quem está agindo, sem o agente informar nada.
  **Ponto técnico a resolver na Entrega 1:** hoje o instrumento recebe só `(config, args)`, sem organização nem execução
  (o contexto de log só é preenchido no disparo e na criadora, não na mensageria). A solução é um contexto de "quem está
  agindo" preenchido na borda nos **três** caminhos (disparo, conversa por canal, "testar passo"/"acionar"), mais a checagem
  de que a organização do time dono do instrumento é a do quadro.
- **Irreversibilidade:** ler é seguro; escrever não é irreversível (há histórico e dá para desfazer).
- **Custo:** nenhuma chamada de IA. O custo é só o que o agente já pagaria.

### 5.4 Limites, todos visíveis e ajustáveis

Pela lei *"nenhum limite é secreto"* (`PRODUTO.md §21`): linhas por chamada de gravação, linhas devolvidas por consulta,
tamanho de texto longo, número de quadros e de linhas por organização. Todos com valor-padrão, mostrados na tela do quadro
e ajustáveis. Estourar um limite dá recusa com a frase de onde mudar.

### 5.5 A tela (proposta visual ANTES de implementar)

- **Lista de quadros** da organização: nome, descrição, linhas, última gravação, quem lê e quem escreve.
- **O quadro:** a tabela com filtro, ordem e busca; editar célula; acrescentar e apagar linha; ver o **carimbo** de cada
  linha, com clique para a execução que gravou; **histórico** da linha; **apagar tudo o que uma execução gravou** (desfazer
  uma rodada de teste).
- **Colunas:** criar, renomear, trocar tipo (com prévia do que não se converte), apagar (com aviso de quais agentes usam).
- **Importar planilha/CSV:** o Batuta sugere colunas e tipos, a pessoa confere, e a importação roda **em segundo plano com
  progresso** (§9). **Exportar CSV.**
- O texto da tela passa pela skill **`escrever-para-quem-usa`** (`CLAUDE.md §17-A`).

---

## 6. Partes 2, 3 e 4 (depois da primeira)

### Parte 2 — Os Quadros movem trabalho

- **Fila com trava:** ação **"pegar o próximo"** (reivindica a próxima linha num estado, com a mesma trava que a fila de
  execuções usa, `FOR UPDATE SKIP LOCKED`), para dois agentes nunca pegarem o mesmo item; com prazo de devolução se o agente
  morrer no meio, e um vigia para itens presos.
- **Gatilho "quando o quadro muda":** linha nova, ou coluna que passa a ter certo valor (ex.: `estado = aprovado`), dispara
  uma automação e entrega a linha como entrada. **Toca a forma de disparar**: registrar como ampliação no `MIGRACAO.md §6.1`,
  com anti-laço (automação que grava no quadro que a dispara) e tetos.
- **Gatilho "quando a data chega":** coluna de data de uma linha dispara a automação N dias antes ou depois, reaproveitando o
  agendador e o resgate de agendamento que não disparou.

### Parte 3 — Arquivos nas linhas

- Tipo de coluna **arquivo**: guardado em pasta **privada** do Storage, separada por organização (hoje o Storage do Batuta é
  público e sem pasta por organização: precisa de leitura, apagar e link temporário).
- **Extração de texto** de `.pdf` (com texto), `.docx`, `.xlsx`, `.csv`, `.txt`, `.md`, **em segundo plano**, com estado
  visível (na fila / lendo / pronto / não consegui ler + motivo). O agente recebe o arquivo **e** o texto.
- Envio de arquivo pela tela (hoje a API só recebe JSON).
- Fora: PDF escaneado ou foto (sem leitura de imagem), `.doc`/`.xls` antigos, PowerPoint, e-mail, áudio, vídeo.

### Parte 4 — Biblioteca (busca por sentido)

O `docs/BIBLIOTECA-DECISAO.md` continua valendo no essencial (organização inteira, etiquetas, OpenAI `text-embedding-3-small`,
sem leitura de imagem, pessoas curam), com três correções vindas da investigação de 2026-09-24:

- a extração de texto **já existirá** (Parte 3);
- o banco de testes local é `postgres:17` sem pgvector e precisa trocar de imagem (`pgvector/pgvector:pg17`). Em produção a
  extensão `vector` 0.8.2 está disponível e não ligada, e a própria migração a liga;
- o custo de preparar documentos acontece **fora** de execução e conversa, e o painel de uso hoje não tem onde somá-lo. Entra
  como fonte nova de uso, a categoria "Biblioteca" (nenhum custo invisível).

Na Parte 4 vale estender a busca por sentido às **colunas de texto longo dos Quadros** ("já tivemos reclamação parecida?").

### Sob demanda (entra quando aparecer o caso real)

- **Colunas sensíveis por papel** (salário, CPF, saúde), com registro de quem leu (LGPD, `PRODUTO.md §23`). **Condição para o RH usar.**
- **Formulário externo**: pessoa de fora do Batuta acrescenta uma linha (pedido de compra, de férias).
- **Ligação entre quadros** (a linha do pedido aponta para a do fornecedor).
- **Memória compartilhada**: aprendizados em texto que valem para vários agentes, com revisão humana (item 2 dos pontos em aberto do `PRODUTO.md`).
- **Cópia para Google Sheets** só para leitura.

---

## 7. O MCP: funções flexíveis

O MCP é a porta da IA externa (o claude.ai do consultor) e hoje tem 44 ferramentas. Para os Quadros, a flexibilidade vem de
**quatro princípios**, não de muitas funções:

1. **Uma linguagem de filtro só**, igual à dos agentes: lista de `{coluna, operador, valor}` com `=`, `≠`, `>`, `≥`, `<`,
   `≤`, `contém`, `está em`, `vazio`, `não vazio`, mais ordem, limite e "só a mais recente de". Quem aprende uma vez usa em
   consultar, totalizar, editar e apagar.
2. **`simular` em toda escrita**: devolve o que *aconteceria* (quantas linhas, quais recusas, que colunas não se convertem)
   sem gravar. É o que deixa uma IA externa operar com segurança um dado real.
3. **Paginação e contagem sempre**: toda leitura diz quantas linhas há no total e devolve o cursor da próxima página.
4. **Erro que ensina**: toda recusa diz o quê, onde e como corrigir, em português, no padrão das outras ferramentas.

As ferramentas, respeitando o escopo por papel que o MCP já aplica:

| Ferramenta | O que faz | Papel |
|---|---|---|
| `listar_quadros` | Quadros da organização, com linhas, última gravação, quem lê e quem escreve | observador |
| `ver_quadro` | Colunas, tipos, chave, descrição, limites, amostra das últimas linhas, instrumentos que o usam | observador |
| `consultar_quadro` | Filtros, ordem, colunas, limite, cursor | observador |
| `totais_quadro` | Agrupar e somar, contar, média, mínimo, máximo | observador |
| `historico_linha` | Todas as mudanças de uma linha, com o carimbo | observador |
| `exportar_quadro` | CSV (com filtro) | observador |
| `criar_quadro` | Nome, descrição, colunas, chave (`simular` disponível) | operador |
| `alterar_quadro` | Renomear; acrescentar, renomear, trocar tipo e remover colunas; mudar a chave; sempre com prévia via `simular` | operador |
| `gravar_linhas` | Modo `acrescentar` ou `pela_chave`; tudo-ou-nada; `simular` | operador |
| `editar_linhas` | Atualiza campos das linhas achadas por filtro ou por id; `simular` diz quantas mudam | operador |
| `apagar_linhas` | Por id, por filtro ou **por execução** (desfazer uma rodada); `simular` obrigatório antes | operador |
| `importar_csv` | Texto CSV + mapeamento de colunas (ou sugestão automática); `simular` mostra a leitura | operador |
| `excluir_quadro` | Irreversível: confirma com o consultor antes, como os outros `excluir_*` | admin |

E nas ferramentas que já existem:

- **`diagnosticar_execucao`** passa a listar **o que a execução gravou em quadros** (e recusas de validação). *"O agente disse
  que gravou"* nunca mais é prova (`CLAUDE.md §12-A`).
- **`ver_agente` / `listar_instrumentos`** mostram o quadro e o acesso de cada instrumento `quadro`.
- **`listar_tipos_instrumento`** traz o tipo `quadro` sozinho (catálogo automático).

Toda gravação pelo MCP leva o carimbo `origem = mcp` com o usuário.

---

## 8. Ensinar as IAs (em toda entrega, não no fim)

Lições que já custaram caro e que valem como regra desta frente:

- **As IAs leem a docstring, não o capítulo** (`feedback-varrer-o-capitulo-canonico`: em agosto, `basic`/`oauth2` existiam e
  nunca foram oferecidos porque a docstring não os listava).
- **Mudou o mecanismo? Varra os 4 markdowns** (`feedback-varrer-todos-os-markdowns-do-agente`: regra nova num, velha no
  outro, e o agente obedece a velha).

**Toda entrega fecha com este checklist, e não está pronta sem ele:**

1. **Central de Conhecimento**: área nova `cerebro/central/cerebro/` com os capítulos:
   - `o-que-e-o-cerebro`: as partes e a regra de fronteira;
   - `quadros`: colunas, tipos, chave, carimbo, histórico, limites;
   - `instrumento-quadro`: as ações, o filtro, "só a mais recente de", tudo-ou-nada;
   - **`onde-guardar`**, o mais importante para a criadora: a tabela de decisão **quadro × memória do agente × ficha da
     execução (`anotar`) × sistema externo × Biblioteca**, com exemplos de erro comum ("usar memória do agente para passar
     dado a outro agente", "usar quadro como sistema oficial");
   - `receitas`: Radar/Painel, contas a pagar, recrutamento, cobrança, com colunas sugeridas;
   - `sinais-e-diagnostico`: recusa de validação, "há mais N linhas", quadro sem ninguém escrevendo.

   E mais uma linha no `INDICE.md` para cada capítulo.
2. **Docstrings** das ferramentas da criadora e do MCP com os tipos, operadores e modos **listados por extenso**.
3. **Prompt da IA criadora** (`criacao/prompt.py`): o tipo `quadro` na lista de instrumentos de leitura/escrita, e um bloco
   *"QUANDO DOIS AGENTES PRECISAM DA MESMA INFORMAÇÃO"*: criar o quadro, dar o instrumento de escrita a quem produz e o de
   leitura a quem consome, e **não** ensinar formato de dado no markdown (a ferramenta já se descreve).
4. **Ferramentas da criadora** (`criacao/ferramentas.py`): `listar_quadros`, `ver_quadro`, `criar_quadro`, `alterar_quadro`,
   `consultar_quadro`, `importar_csv`. Ela trabalha num time, mas o quadro é da organização: as ferramentas operam na
   organização do time, e a criadora **diz** ao consultor quando o quadro é usado por outros times.
5. **Mensagens de atividade** (`orquestracao/atividade.py`): o que aparece ao vivo enquanto o agente consulta ou grava.
6. **Varredura de vocabulário**: nenhuma tela, docstring ou capítulo pode chamar isso de "tabela JSONB", "upsert" ou "chave
   composta" para quem usa.

---

## 9. Sem travar, sem erro genérico, sem silêncio (`CLAUDE.md §12-A`)

- **Importar planilha grande e (Partes 3/4) ler arquivo** são trabalho de **segundo plano**, com progresso na tela, vigia de
  presos e recuperação de órfãos no boot. Nunca um pedido que fica minutos aberto.
- **Recusa de validação é resposta, não falha muda**: o agente recebe o motivo por linha, e o diagnóstico da execução mostra
  a recusa. Um agente que narra *"gravei"* depois de uma recusa aparece no aviso de `diagnosticar_execucao`.
- **Quadros moram no banco principal:** não criam ligação externa nova. Storage (Parte 3) e o provedor de embeddings
  (Parte 4) nascem com **timeout, sonda e nome na página `/status`**.
- **Dado lido de quadro é dado, não instrução.** Um agente grava, outro lê: texto gravado não pode virar ordem para o
  segundo agente. Vale a mesma proteção anti-injeção dos instrumentos.

---

## 10. As entregas

Cada uma segue o ritual investigar → planejar → implementar → verificar → relatar, termina com a suíte verde, `tsc`,
`eslint` e `build` limpos, e **o checklist do §8**.

**Entrega 1 — A fundação.**
Migração das três tabelas, a camada única de serviço (§5.2), os tipos e a validação, o histórico e os testes (isolamento
entre organizações provado por teste). Sem tela.
*Ensino:* capítulos `o-que-e-o-cerebro` e `quadros`.
*Como ficou (2026-09-24):* o serviço recebe **quem grava explicitamente** (`Autor`: origem, agente, execução, pessoa) em vez
de adivinhar por contexto — quem monta o `Autor` é a porta (ferramenta do agente, rota, MCP). Por isso o **contexto de
quem está agindo** (§5.3) passou para a Entrega 2, onde a ferramenta do agente é quem precisa dele; nesta entrega o motor
ficou intocado. Duas descobertas dos testes viraram regra: "1.000"/"1,000" são **recusados como ambíguos** (mil ou um?)
em vez de chutados, e o histórico ganhou um número sequencial (duas mudanças na mesma transação têm o mesmo horário). A
área `cerebro` da Central ainda **não aparece no /ajuda** (a lista de áreas da tela é fixa): entra junto com a tela, na
Entrega 4 — até lá, só as IAs leem, e os capítulos dizem "em construção".

*Como ficaram as Entregas 2 e 3 (2026-09-24):*
- **Toque mínimo no motor, dito na cara** (evolução dirigida, `MIGRACAO.md §6.1`): (1) o contrato de instrumento ganhou
  `expandir_ferramentas_da_instancia(inst, config)` — padrão delega ao antigo; o `quadro` precisa da instância para
  saber a organização pelo TIME dono do instrumento (a config sozinha não prova nada); (2) `executar_agente` põe o
  `agente_id` no contexto de quem-fez durante o turno (é o carimbo). Nada mais do motor mudou.
- **`resolver_config(sessao, org, config)`**, gancho novo chamado pelas QUATRO portas de criar/editar instrumento
  (tela ×2, `criacao/servicos` ×2 — a criadora e o MCP passam por ali): o `quadro` recebe o nome, **guarda o id**
  (renomear o quadro não quebra o instrumento) e recusa na hora quadro inexistente ou de outra organização.
- **`oculto_na_tela`** (novo, ≠ `oculto_no_catalogo`): o tipo `quadro` fica fora do dropdown da tela até a Entrega 4
  trazer o seletor de quadro, mas segue no catálogo das IAs. O `oculto_no_catalogo` esconderia das IAs também.
- A recusa do quadro volta ao agente como `ok:false` com o motivo por linha e entra nos erros da execução (a borda
  já registrava `ok:false` das ferramentas expandidas). Falha de banco vira resposta honesta + evento `quadro.falhou`.
- A consulta volta ao agente em forma de **tabela compacta** (cabeçalho + linhas como listas) — barata em tokens.
- Importar CSV (`quadros/importacao.py`) sugere colunas pelos valores e importa tudo-ou-nada em partes do limite;
  numera os erros pela linha do ARQUIVO.
- MCP: apagar linhas e excluir quadro **só simulam sem `confirmar=true`**; importar CSV simula por padrão. As
  descrições das ferramentas com `_FILTROS_DOC` usam o marcador `_doc(...)` — string montada no corpo da função
  **não é docstring** em Python, e a ferramenta iria para a IA externa sem descrição (pego antes de subir).
- **Fica para quando houver a tela:** o seletor de quadro no formulário do instrumento; a área "Cérebro" no /ajuda.

**Entrega 2 — O agente usa.**
Instrumento `quadro` com as seis ações, descrição gerada a partir das colunas, carimbo automático, mensagens de atividade e
`diagnosticar_execucao` mostrando o que foi gravado.
*Ensino:* `instrumento-quadro`, `onde-guardar`, o prompt da criadora.
*Prova:* um agente de teste grava, outro agente de **outro time** lê, e um terceiro sem o instrumento não enxerga.

**Entrega 3 — As IAs operam.**
As ferramentas da criadora e do MCP (§7), com `simular`, filtro único, paginação e erro que ensina.
*Ensino:* docstrings, `receitas`, `sinais-e-diagnostico`.
*Prova:* criar, alimentar, consultar e desfazer um quadro inteiro **só pelo MCP**.

**Entrega 4 — A tela.**
*Primeiro* a proposta visual para o maestro aprovar, *depois* a construção: lista, tabela, colunas, carimbo, histórico,
importar CSV em segundo plano e exportar. Menu "Cérebro" (P6).

**Entrega 5 — O caso real: Radar e Painel.**
Criar os quadros (Radar – respostas, Radar – lacunas, Painel – semanas, Painel – WhatsApp, Painel – buscas, Briefing por tema)
e importar o histórico da planilha. Depois, **com aval do maestro**, reescrever os markdowns do Radar, do Coletor, do Briefing
e dos 5 Analistas, varrendo os 4 markdowns de cada um. Rodar ao vivo e só então parar de gravar na planilha.
*Prova:* chamadas e custo **antes × depois**. A referência de hoje: 64 chamadas na carga histórica e a aba inteira lida
toda semana.

**Depois:** Parte 2 (fila e gatilhos) → Parte 3 (arquivos) → Parte 4 (Biblioteca), cada uma com seu próprio plano
detalhado, apresentado antes.

### Definition of Done da Parte 1

O Radar e o Painel rodam sem planilha. Os Analistas dos 5 blogs leem o briefing de um quadro, com instrumento visível no
cinto. O maestro vê, edita, importa e exporta pela tela. A IA criadora monta um quadro novo a pedido e explica onde guardar
cada coisa. O MCP opera um quadro de ponta a ponta com `simular`. O isolamento entre organizações está provado. E **nenhum
markdown de agente ensina formato de dado**.

---

## 11. Riscos, ditos na cara

- **Agente gravando lixo:** mitigado pela validação tudo-ou-nada, pelo carimbo e pelo "desfazer por execução". Não é
  eliminado: um valor válido e errado passa.
- **Quadro virando sistema oficial por acidente:** a regra de fronteira está na Central e no prompt da criadora; o limite de
  linhas avisa quando o uso passa do razoável.
- **Duas escritas na mesma linha ao mesmo tempo** (tela × agente): a gravação pela chave é atômica e o histórico guarda as
  duas; a última vence, e fica visível que houve as duas.
- **Dados pessoais** entram cedo demais (RH antes das colunas sensíveis): a Central e a criadora avisam que quadro sem
  proteção por coluna **não** é lugar para CPF, salário ou saúde até essa peça existir.
- **Custo de leitura** voltando pela porta dos fundos (agente consultando tudo sempre): teto de linhas por consulta, o
  atalho "já existe?" e os totais calculados pelo banco existem justamente para isso.
