# Batuta — Decisão arquitetural da Biblioteca

**Documento de decisão.** Após análise do `ARQUITETURA.md`, aqui está a arquitetura proposta da Biblioteca, com justificativas e plano de implementação. Cada item foi decidido — não é mais uma rodada de perguntas.

---

## TL;DR

- **Busca:** RAG (pgvector + OpenAI `text-embedding-3-small`)
- **OCR:** fora da v1
- **Escrita pelo agente:** fora da v1 (só humano cura)
- **Escopo:** organização inteira, com tags livres pra filtrar
- **Ingestão:** assíncrona via fila existente
- **Consulta pelo agente:** novo tipo de instrumento `consultar_biblioteca`, sem alterar o motor

---

## Resolvendo a "tensão do precedente"

O `ARQUITETURA.md` aponta que a `memorias_projeto` foi feita destilada, sem vetor, e que RAG na Biblioteca contradiz isso. **Não contradiz.** Os casos são tecnicamente diferentes:

|  | `memorias_projeto` | Biblioteca |
|---|---|---|
| Volume | dezenas de itens curtos por projeto | centenas/milhares de pedaços por org |
| Cabe no contexto do modelo? | sim | não, nem de longe |
| Item típico | fato/decisão pontual | pedaço de documento longo |
| Busca útil | recência, categoria | similaridade semântica |

Quando cabe no contexto, vetor é overhead inútil. Quando não cabe, vetor é o jeito matemático de selecionar o que cabe. **A decisão original e esta atual seguem o mesmo princípio aplicado a casos diferentes.**

---

## As 6 decisões, com justificativa

### 1. Busca: RAG com pgvector + embeddings OpenAI

**Razão:** documentos reais de uma consultoria financeira (contratos, planos de conta, planilhas, contábil) têm sinonímia forte e morfologia complexa em português. Full-text iria ignorar "lucratividade" quando o agente perguntar "margem", "EBITDA" quando perguntar "lucro operacional", e assim por diante. RAG resolve.

**Custo (calculado, não estimado):** OpenAI `text-embedding-3-small` custa US$ 0,02 por milhão de tokens. Um PDF de 50 páginas tem ~25 mil tokens — custa meio centavo pra indexar. Cenário de 100 documentos × 30 clientes = 3.000 documentos ≈ **US$ 1,50 uma única vez** (embeddings só refazem se o documento mudar). Na consulta, a busca por similaridade é matemática (custo zero); o custo de IA da consulta é só a chamada do agente, que ia existir de qualquer jeito.

**Infraestrutura:** pgvector já disponível no Postgres do Supabase. Cofre já suporta chave OpenAI. Sem peça nova de infra.

**Alternativas descartadas:**
- *Full-text Postgres:* qualidade insuficiente pro domínio. Manter como possível complemento futuro pra busca por nomes/códigos exatos (híbrido), mas não na v1.
- *Voyage AI ou Cohere:* especializados, possivelmente melhores, mas marginais pro caso de uso e adicionam vendor novo. OpenAI é o padrão de mercado, já no cofre.

### 2. OCR: fora da v1

**Razão:** documentos típicos da consultoria são digitais (PDF nativo, .docx, planilhas exportadas, relatórios). OCR introduz dependência de provedor adicional, custo variável e qualidade inconsistente. Não vale atrasar a v1 pra cobrir o caso minoritário.

**Tipos aceitos na v1:** `.pdf` (texto extraível), `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`.

**Quando reabrir:** quando aparecer um caso concreto em que um cliente importante só tem documentos escaneados. Aí avalia provedor (Tesseract local, Google Document AI, AWS Textract). Não antes.

### 3. Escrita pelo agente: fora da v1 (só humano cura)

**Razão:** "como o agente escreve na Biblioteca" é projeto inteiro à parte — exige política de revisão, mecanismo de aprovação, risco de degradação. A Biblioteca v1 entrega valor enorme só de leitura. Não atrasar pra resolver problema secundário.

**Quando reabrir:** v2, com decisões próprias de revisão e aprovação.

### 4. Escopo: organização + tags livres

**Confirmado:** org-wide (todos os times da organização compartilham a Biblioteca).

**Adicional — tags livres:** cada documento pode ter zero ou mais tags em texto livre (ex.: "controladoria", "contratos", "cliente_X"). O agente pode filtrar a consulta por uma ou mais tags **ou** consultar a base inteira. Tags servem pra organização e refino de busca, não dividem a base.

**Razão:** dá flexibilidade total ao consultor sem inventar novo conceito ("biblioteca-por-time" criaria mais peça arquitetural sem necessidade real).

### 5. Custo e provedor: OpenAI `text-embedding-3-small`

**Razão:** padrão da indústria, ótimo em português, US$ 0,02/milhão de tokens (o mais barato dos modelos OpenAI de qualidade alta), o cofre já comporta o provedor. Não vale experimentar nicho na v1.

**Dimensão do vetor:** 1.536 (default do modelo). Suporta `dimensions: 256` se quiser reduzir tamanho de índice — não recomendado na v1 (perda mínima de qualidade não compensa otimização prematura).

### 6. Ingestão: assíncrona via fila existente

**Razão:** a fila do projeto (`fila.py`, `SELECT ... FOR UPDATE SKIP LOCKED`) já é o mecanismo certo. Síncrona travaria upload de PDFs grandes desnecessariamente.

**Fluxo:** upload retorna imediatamente; trabalhador processa em segundo plano (extrai texto → fatia em pedaços → gera embeddings → salva no pgvector); UI mostra o estado do documento (pendente / processando / pronto / falhou).

**Re-indexação:** quando um documento é substituído ou tem tags editadas (no caso de tags, só re-faz os pedaços se a fatia mudar — tag em si não exige re-embed). Detalhe de implementação.

---

## A arquitetura proposta

### Tabelas novas

**`biblioteca_documentos`**
- `id` (UUID), `organizacao_id` (FK obrigatório — isolamento)
- `nome` (texto), `tipo_arquivo` (`pdf` | `docx` | `txt` | `md` | `csv` | `xlsx`)
- `tamanho_bytes` (int), `storage_path` (texto — onde está no Supabase Storage)
- `tags` (text[])
- `estado_ingestao` (`pendente` | `processando` | `pronto` | `falhou`)
- `mensagem_erro` (texto, nullable)
- `criado_em`, `atualizado_em`, `criado_por` (FK `usuarios`)

**`biblioteca_pedacos`**
- `id` (UUID), `documento_id` (FK), `organizacao_id` (desnormalizado pra isolamento e índice)
- `ordem` (int — ordem do pedaço no documento)
- `texto` (texto — o conteúdo do pedaço)
- `embedding` (vector(1536))
- `tokens` (int)
- `metadados` (JSONB — ex.: `{"pagina": 12}` quando aplicável)
- `criado_em`

Índices essenciais: `(documento_id, ordem)`, `(organizacao_id)`, e o índice IVFFlat ou HNSW no `embedding` (pgvector).

### Storage

Supabase Storage com bucket `biblioteca`, com path `{organizacao_id}/{documento_id}/{nome_arquivo}`. Acesso só pelo cérebro com service role; nunca exposto direto ao navegador.

### Instrumento novo: `consultar_biblioteca`

Encaixa no sistema de instrumentos sem tocar no motor.

- **Config (não-secreta):** `tags_padrao` (text[], opcional) — se o consultor quiser que esse instrumento sempre filtre por certas tags por padrão.
- **Args (o que o agente passa em runtime):** `pergunta` (texto), `tags` (text[], opcional — sobrescreve `tags_padrao`), `max_resultados` (int, default 5)
- **Retorno:** lista de pedaços relevantes com `texto`, `documento_nome`, `pagina` (quando aplicável), e um score de similaridade.
- **`acao_irreversivel`:** false (só lê).
- **Implementação:** gera embedding da pergunta, faz `ORDER BY embedding <=> :pergunta_embedding LIMIT :max_resultados` no pgvector (filtrando por `organizacao_id` e tags), retorna os trechos.

### Tela `/biblioteca`

Substitui o placeholder "em breve". Server Component + ilha cliente, no padrão do resto do app.

- **Listagem** de documentos com nome, tipo, tags, estado (badge colorido), data
- **Upload** drag-and-drop (múltiplos arquivos)
- **Edição** de tags (chips), botão "re-indexar"
- **Exclusão** com confirmação
- **Filtro** por tag e por estado
- **Detalhe** opcional (ver pedaços extraídos — útil pra debug)

### Restrições respeitadas

- ✅ **Não altera o motor** — biblioteca é estendida via novo instrumento, padrão já validado
- ✅ **Isolamento por organização** — `organizacao_id` obrigatório em todas as tabelas, no path do Storage, no filtro de toda query
- ✅ **Segredos só no cérebro** — chave OpenAI no cofre
- ✅ **Interface só fala com o cérebro** — Storage acessado via cérebro
- ✅ **1 réplica do cérebro** — ingestão pesada vai pra fila

---

## Plano de implementação (ordem sugerida)

Cada passo termina com commit + push e nada empilha sobre passo anterior quebrado, no padrão já estabelecido.

1. **Schema** — migration Alembic com as duas tabelas, habilitar extensão `vector` no Postgres se ainda não estiver, criar índice vetorial. Bucket `biblioteca` no Supabase Storage.
2. **Endpoints de gestão** — `POST /biblioteca/documentos` (upload), `GET /biblioteca/documentos` (listar), `PATCH /biblioteca/documentos/{id}` (editar tags), `DELETE /biblioteca/documentos/{id}`. Sem ingestão ainda — só persiste o arquivo e cria o registro em estado `pendente`.
3. **Tela `/biblioteca`** — upload + listagem + tags, mostrando documentos em estado `pendente` (sem trabalhador ainda; visualmente confirma o pipeline de gestão).
4. **Extração de texto** — função pura `extrair_texto(arquivo, tipo) -> str` cobrindo `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`. Testes unitários com amostras pequenas.
5. **Fatiamento** — função `fatiar(texto) -> list[Pedaco]`, com ~500-800 tokens por pedaço e overlap de ~10-15%. Heurística simples; refinar depois se precisar.
6. **Embeddings** — função `gerar_embeddings(textos) -> list[vector]` chamando OpenAI; uso registrado em `precos.py` para aparecer no painel de uso da consultoria.
7. **Trabalhador de ingestão** — picks documento em estado `pendente`, executa extrair → fatiar → embeddar → salvar, atualiza estado. Falhas vão pra `falhou` com `mensagem_erro` legível.
8. **Instrumento `consultar_biblioteca`** — config, args, busca no pgvector, retorno formatado. Auto-registra no catálogo de tipos.
9. **Teste ponta a ponta** — upload de 2-3 documentos reais, criação de agente com instrumento `consultar_biblioteca` no cinto, automação simples ("responda essa pergunta sobre X consultando a Biblioteca"), confirmar respostas com citação dos documentos.
10. **Refino e auditoria** — registrar consultas na `auditoria` (opcional), badge de "consultou Biblioteca" nas execuções, mensagens de erro amigáveis na UI.

---

## O que **não** entra na v1, deliberadamente

Pra ficar explícito e o Claude Code não tentar antecipar:

- OCR (PDFs escaneados / imagens)
- Escrita pelo agente na Biblioteca
- Versionamento de documentos (manter histórico de versões)
- Permissões por documento (todo membro da organização vê toda a Biblioteca)
- Citação automática inline ("conforme o documento X, página Y") — o instrumento devolve a fonte; quem cita é o agente, na resposta dele

Cada um desses é uma decisão própria, futura, sem urgência.

---

## Como o Claude Code deve receber este documento

Sugiro entregar com a instrução:

> Adicionei `BIBLIOTECA-DECISAO.md` na raiz. Lê o documento inteiro junto com `ARQUITETURA.md` e me apresenta um plano detalhado de implementação no padrão dos planos das fases anteriores (investigar/implementar/verificar com Definition of Done por etapa). Segue a ordem dos 10 passos do documento. **Não comece a implementar ainda** — só me apresente o plano para eu aprovar passo por passo.

Isso te dá uma camada de revisão antes do código.
