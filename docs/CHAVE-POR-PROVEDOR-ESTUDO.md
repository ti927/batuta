# Estudo — unificar a chave de IA: uma chave por provedor (sem papel)

> Pedido do maestro (2026-06-15): hoje a chave de IA tem **duas dimensões**
> (papel `executora` × `criadora`/conversa) além de provedor. Isso gera cadastro
> em dobro e a "pegadinha da imagem" (gerar_imagem/Whisper/busca leem só o balde
> `executora`). Proposta: **a chave é só por provedor** ("este provedor tem
> credencial?"); a escolha de IA já acontece no **modelo** da conversa
> (`Organizacao.modelo_criadora`) e de cada **agente** (`Agente.modelo_ia`).
> Este documento estuda o raio de impacto ANTES de mexer. **Nada implementado.**

## 1. O que muda conceitualmente

- **Antes:** `chaves_api` é única por `(organizacao_id, tipo_ia, provedor)`. A
  resolução recebe `tipo_ia` (default `executora`); a conversa resolve com
  `criadora`. Os consumidores sem papel (imagem/busca/transcrição/agentes) leem o
  balde `executora`.
- **Depois:** `chaves_api` única por `(organizacao_id, provedor)`. A resolução
  ignora papel — devolve "a chave daquele provedor" (org → consultoria → `.env`).
  O papel sai da chave; a escolha de IA continua **só** no modelo (conversa e por
  agente, que já existem). A pegadinha da imagem some de graça.

## 2. Raio de impacto (arquivo por arquivo)

### Cérebro (núcleo de orquestração NÃO é tocado)
- **`modelos.py`** — `ChaveApi`: remover a coluna `tipo_ia`; índice único
  `(organizacao_id, tipo_ia, provedor)` → `(organizacao_id, provedor)`.
- **`chaves.py`** — remover o parâmetro `tipo_ia` de `_buscar`/`_resolver`/
  `resolver_chave`/`resolver_chave_por_time`/`resolver_chave_e_origem_por_time`/
  `resolver_chaves_por_organizacao`/`resolver_chaves_por_time`/
  `provedores_disponiveis`. Resolução vira só por provedor. O fallback de legado
  (`.env`) e a `compartilhavel` da consultoria seguem iguais.
- **`esquemas.py`** — `ChaveApiCriar`/`ChaveApiLer`: remover `tipo_ia`; aposentar
  o `Literal TipoIA`. `modelos-disponiveis` deixa de ser `{executora, criadora}`
  e vira um único mapa por provedor.
- **`rotas/chaves_api.py`** — `_buscar`/`_upsert` sem `tipo_ia`; `modelos-disponiveis`
  passa a devolver um mapa só; auditoria sem `tipo_ia`.
- **`rotas/criacao.py`** — `resolver_chaves_por_organizacao(..., tipo_ia="criadora")`
  → sem papel.
- **`rotas/organizacoes.py`** (`PUT /modelo-criadora`) — a validação "o provedor
  do modelo tem chave?" usa `tipo_ia="criadora"` → passa a usar a disponibilidade
  por provedor.
- **Comentários/docstrings** em `cofre.py`/`criacao/loop.py` (texto, sem lógica).

### Interface
- **`lib/api.ts`** — remover `TipoIA`; `ChaveApiLer.tipo_ia`; `ModelosDisponiveis`
  `{executora, criadora}` → um mapa só (`ProvedoresDisponiveis`).
- **`components/gestao-chaves.tsx`** — remover o seletor de papel (executora/
  conversa) e o `tipo_ia` do PUT; uma chave por serviço.
- **`components/seletor-modelo-conversa.tsx`** e **`components/formulario-agente.tsx`**
  — hoje consomem `disponiveis.criadora` e `disponiveis.executora`; passam a
  consumir o mapa único. Comportamento (só oferecer modelo com chave) é idêntico.
- **`app/organizacoes/[id]/chaves/*`** — ajustar o que passa `disponiveis`.

### Banco (migração)
- Migração que **consolida** as linhas por `(org, provedor)` e troca o índice
  único. **Regra de dedup** (quando houver 2 papéis): manter a `executora` se
  existir, senão a `criadora`; preferir `ativa`; logar o que foi descartado.

## 3. Fluxos verificados (todos continuam funcionando)

| Fluxo | Hoje resolve com | Depois | Quebra? |
|---|---|---|---|
| Execução de agente (cadeia/disparo) | pool `executora` | pool por provedor (modelo do agente decide) | não |
| Conversa (IA criadora) | `criadora` | por provedor (modelo da conversa decide) | não |
| Mensageria (turno do agente) | `executora` | por provedor | não |
| gerar_imagem / busca_web (chave compartilhada) | pool `executora` | por provedor | **conserta a pegadinha** |
| Transcrição de áudio (Whisper) | `executora` | por provedor | **conserta** |
| Seletor de modelo (conversa e agente) | `disponiveis.criadora`/`.executora` | mapa único | não |
| Contabilização (origem org/consultoria/legado) | independe de `tipo_ia` | igual | não |

**Núcleo congelado:** `orquestracao/cadeia.py` e `agente.py` não são tocados (a
mudança é toda na fronteira de resolução de chave).

## 4. O que NÃO muda
- A escolha de **qual IA/modelo** roda (conversa e por agente) — já é onde deve ser.
- O **pool compartilhado** (Tavily, etc.), o reuso `chave_compartilhada`, a
  **Caixa-forte de Credenciais** (credenciais de instrumento são outra coisa).
- O **toggle `compartilhavel`** da consultoria e o fallback `.env`.
- A **contabilização** por origem/categoria.

## 5. Migração — realidade dos dados (produção, 2026-06-15)
Consulta ao banco: **5 linhas, ZERO conflitos**. A Anthropic da consultoria está
em `executora` E `criadora` com a **mesma** chave (`5wAA`); OpenAI consultoria só
`criadora`; Tavily só `executora`; uma org com OpenAI `executora` própria. Ou
seja, **a consolidação aqui é trivial e sem perda** (nenhum (org,provedor) tem
chaves distintas por papel). A regra de dedup existe só para blindar o futuro.
**Reversibilidade:** o downgrade recria a coluna, mas o papel original dos dados
consolidados não volta (informação perdida no merge) — como o dado real não tem
conflito, o risco prático é nulo; ainda assim, fazer a migração com a árvore
limpa e um backup lógico das 5 linhas antes.

## 6. Riscos e mitigações
1. **Dedup na migração** (org+provedor com 2 chaves distintas) — hoje **0 casos**;
   regra determinística (executora>criadora, ativa) + log do descartado.
2. **Banco = produção** (local aponta para o Supabase de prod) — a migração roda
   no banco no ar. Aditiva-reversível só em parte (drop de coluna). Mitigar:
   rodar com aval explícito, fora de horário de uso, com as 5 linhas anotadas.
3. **Selectors de modelo** — trocar `executora`/`criadora` pelo mapa único; teste
   garante que só modelos com chave aparecem.
4. **Testes** — `test_chaves.py::test_tipo_ia_isolado` e partes de
   `test_modelo_conversa_e_uso_consultoria` afirmam o isolamento por papel; serão
   reescritos para o novo contrato (não é regressão, é mudança de contrato).

## 7. Veredito
**Viável e de baixo risco** — a dimensão `tipo_ia` é mecânica (um parâmetro
threaded), o núcleo não é tocado, e o dado real não tem conflito. Some o cadastro
em dobro e a pegadinha da imagem.

## 8. Plano formal — 5 passos (um por vez, com aprovação e verificação concreta)

> Desenho APROVADO pelo maestro (2026-06-15). Fase focada, menor que a Caixa-forte.
> Registrada no `BUILD-PLAN.md` (FILA, item "Chave de IA por provedor").

### Passo 1 — Migração (consolidar + reindexar)
Antes: anotar/backup lógico das linhas atuais de `chaves_api`. Migração: consolida
para uma linha por `(organizacao_id, provedor)` (regra de dedup: mantém a
`executora` se existir, senão a `criadora`; entre ativas, a mais recente; loga o
descartado), troca o índice único `(organizacao_id, tipo_ia, provedor)` →
`(organizacao_id, provedor)` e **dropa a coluna `tipo_ia`**. **Verificar:** SQL
offline (`--sql`) revisado; `upgrade`/estado conferido no banco; as ~5 linhas de
prod viram o esperado (sem perda); `alembic current` no novo head.

### Passo 2 — Resolução sem papel (`chaves.py` + `rotas/chaves_api.py`)
`chaves.py`: remove o parâmetro `tipo_ia` de toda a cadeia de resolução (resolve
só por provedor; legado `.env` e `compartilhavel` intactos). `rotas/chaves_api.py`:
CRUD sem `tipo_ia`; `GET /modelos-disponiveis` passa a devolver **um mapa único**
`{provedor: bool}`. **Verificar:** testes de resolução por provedor (org →
consultoria → legado) + `modelos-disponiveis` mapa único; suíte verde.

### Passo 3 — Conversa e validação de modelo (`rotas/criacao.py` + `rotas/organizacoes.py`)
`criacao.py`: a conversa resolve a chave por provedor (sem `tipo_ia="criadora"`).
`organizacoes.py` (`PUT /modelo-criadora`): a validação "o provedor do modelo tem
chave?" usa a disponibilidade por provedor. **Verificar:** teste de que escolher
um modelo cujo provedor tem chave passa, e sem chave recusa (422); conversa roda.

### Passo 4 — Interface (tira o seletor de papel)
`gestao-chaves.tsx`: remove o seletor executora/conversa; uma chave por serviço
(mantém o toggle `compartilhavel` da consultoria). `lib/api.ts`: remove `TipoIA`/
`tipo_ia`; `ModelosDisponiveis` vira mapa único. `seletor-modelo-conversa.tsx` e
`formulario-agente.tsx`: consomem o mapa único. Telas de chaves ajustam o que
passam. **Verificar:** `tsc`/`eslint` limpos.

### Passo 5 — Limpeza + testes + e2e
Reescrever os testes de "isolamento por papel" para o novo contrato; remover
referências mortas; suíte completa verde; núcleo sem diff. **Verificar (e2e ao
vivo):** com uma chave OpenAI cadastrada uma vez, (a) a conversa num modelo do
provedor funciona, (b) um agente nesse provedor funciona, (c) o gerar_imagem
funciona — provando que uma chave por provedor cobre tudo. Depois: merge + push +
redeploy (com aval do maestro).
