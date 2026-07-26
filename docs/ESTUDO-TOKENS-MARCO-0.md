# Estudo de Tokens — Marco 0 do Programa de Unificação de Estado

> **Status:** ✅ **ESTUDO EXECUTADO (medição real).** Este é o **Marco 0** do
> [`UNIFICACAO-ESTADO.md`](UNIFICACAO-ESTADO.md) — o insumo obrigatório para a **decisão adiada**
> ("um só programa × dois trilhos", §7 do âncora). Não escreve motor: é **planejamento com
> evidência**. A **decisão** continua sendo do maestro; este documento entrega o número na mão e uma
> **recomendação**.
>
> **Fonte dos números:** medição **somente-leitura** no banco que o `.env` local aponta — o
> **snapshot de São Paulo congelado em 2026-07-20** (o banco antigo, pré-migração, mantido para
> rollback). Dados reais de produção até essa data. Scripts em `scratchpad` (não versionados);
> reprodutíveis com as funções de `cerebro/precos.py`.

---

## 1. Método e ressalvas (honestidade primeiro)

- **O que foi medido:** o consumo real de tokens já gravado no banco — cada turno guarda
  `{modelo, tokens_entrada, tokens_saida, categoria}` (em `passos_execucao.saida['uso']`,
  `conversas_criacao.mensagens[].uso` e `mensagens_conversa.uso`). Reusei os agregadores de
  `precos.py` (as mesmas funções da tela `/uso`).
- **Preços:** mostro dois custos — o **do app** (`precos.py`, informativo) e o **REAL** a preços de
  jan/2026. Achei de passagem que `precos.py` tem **Opus a $15/$75** (o preço real do Opus 4.8 é
  **$5/$25**) → **o app superestima o custo em ~2,3×.** Os *tokens* são reais; só o *dólar* do app
  está inflado. (Correção colateral recomendada, §8.)
- **O que este snapshot NÃO cobre:** as conversas mais recentes e mais caras — em especial o time de
  **Reembolsos (Bubble)**, que motivou a remodelagem — vivem no **banco novo de produção** (US East,
  pós-2026-07-20), não neste snapshot. Logo, os números da **mensageria** aqui mostram o *padrão*, mas
  **não** a cauda extrema (o turno de ~90k tokens documentado ao vivo). Isso **reforça**, não enfraquece,
  a conclusão principal (a mensageria é barata; o custo está na criadora) — mas está dito com todas as
  letras. Se o maestro quiser a cauda de produção quantificada, é só apontar o banco novo e eu remeço.

---

## 2. ACHADO Nº 1 — onde o dinheiro está: a **IA criadora** (≈70% de tudo)

Consumo total do snapshot, por **função** em que a IA foi gasta:

| Categoria | Tokens entrada | Tokens saída | Custo app | **Custo REAL** | Fatia (real) |
|---|---:|---:|---:|---:|---:|
| **`conversa`** (IA criadora) | **14.053.237** | 242.414 | $172,02 | **$64,78** | **≈ 69%** |
| `execucao` (agentes/disparo) | 4.611.205 | 852.669 | $38,85 | $27,66 | ≈ 29% |
| `mensageria` (atendimento) | 626.291 | 15.497 | $2,11 | $2,11 | **< 3%** |
| *(`instrumento`: imagem/vídeo — por unidade, não por token)* | — | — | $17,95 | *(fora do escopo-token)* | — |
| **Total (tokens)** | **19.290.733** | 1.110.580 | $230,94 | **≈ $94,55** | 100% |

**Leitura:** a **conversa da IA criadora sozinha é ~69% do custo de token** (e 73% dos tokens de
entrada). A **mensageria** — o "segundo motor" que assustou pela complexidade — custa **< 3%**. **O
problema de custo do Batuta não é o runtime; é a IA criadora.**

---

## 3. ACHADO Nº 2 — a doença da Frente B, **medida** (a conversa inteira reenviada todo turno)

A IA criadora tem **263 turnos** medidos em 23 conversas. O custo por turno **cresce com a idade da
conversa**, exatamente como o diagnóstico previa:

- **Piso fixo medido:** toda conversa nova começa em **~19.718 tokens** de entrada (o prompt de
  sistema: base + catálogo de instrumentos + fotografia do time + memória). Esse é o **prefixo
  estável** — decisivo para o Eixo 3 (cache).
- **A conversa mais longa (32 turnos, 4,26 milhões de tokens de entrada):** sobe de ~20k para
  **300–380k tokens por turno**. Média dos **3 primeiros turnos = 54k**; dos **3 últimos = 340k** →
  **6,3× mais caro por turno** só por a conversa ter envelhecido.

```
Curva real (tokens_entrada por turno, conversa de 32 turnos):
19k 20k 122k 62k 59k 40k 86k 14k 90k 80k 18k 19k 79k 21k 21k 90k 23k 23k 23k
147k 148k 231k 164k 333k 303k 172k 355k 277k 188k 381k 336k 300k
        └─────────── a partir daqui, CADA turno reenvia 150–380k ───────────┘
```

Isso é a Parte A da Frente B (`ECONOMIA-TOKENS-IA-CRIADORA.md`) provada com número: **`loop.py`
reenvia `conversa.mensagens` inteiro todo turno**, então o custo é quadrático na duração da conversa.

---

## 4. ACHADO Nº 3 — a Frente A **não** é problema de custo; é problema de **rastro**

A mensageria (o runtime de conversa) no snapshot:

| | tokens_entrada por turno |
|---|---:|
| turnos medidos | 71 |
| média | 8.821 |
| mediana | 7.627 |
| p90 | 20.224 |
| p99 | 25.084 |
| **máximo** | **25.202** |
| turnos ≥ 40k | **0** |

A mensageria é **barata e limitada** — o histórico é cortado em 20 mensagens de texto
(`LIMITE_HISTORICO`), então não incha como a criadora. O **turno de ~90k** que motivou a remodelagem
**não é conversa longa**: é o **laço react dentro de UM turno** re-chamando um instrumento que devolve
payload gigante (o Bubble com centenas de constraints) e **acumulando cada resultado no contexto**
([agente.py:427](../cerebro/orquestracao/agente.py#L427) soma os tokens de todas as chamadas internas).
É um **evento de cauda** de produção, não o grosso do custo.

**Conclusão:** o valor da Frente A (runtime) **não é economia** — é **depurabilidade** (poder
inspecionar o agente lançador do Bubble, hoje sem rastro) e **unificar o HITL** (o portão). São ganhos
**estruturais**, não de fatura. Isso muda o peso da decisão adiada (§7).

---

## 5. EIXO 2 — modelo por agente (right-size)

Modelos configurados hoje:

- **Agentes:** 17 em `sonnet-4-6`, 14 em `sonnet-5`, 5 em `haiku-4-5`, 5 em `gpt-4.1`, 4 em `opus-4-8`,
  1 em `gpt-4o-mini`. A maioria já está em **Sonnet** (meio-termo) — não há frota inteira em Opus.
- **IA criadora:** ambas as organizações em **`sonnet-5`** (o padrão atual).

**Achado:** o grande gasto histórico de **Opus** (10,3M tokens de entrada no snapshot) veio da **IA
criadora quando o padrão dela ERA Opus** (antes de 2026-06-30, quando virou Sonnet 5). Ou seja, **o
right-size mais impactante — tirar a criadora do Opus — já foi feito.** O que resta de Eixo 2 é fino:
revisar caso a caso agentes superdimensionados (ressalva: qualidade; a criadora quer modelo forte). É a
alavanca **mais barata** (só troca o campo `modelo_ia`, zero código de motor), mas o ganho grande dela
já foi colhido.

---

## 6. EIXO 3 — cache por provedor (dinheiro na mesa **hoje**, na Anthropic)

O prefixo fixo medido (**~19,7k tokens**) repete-se a cada turno da mesma conversa. Ligando o cache da
Anthropic (`cache_control`, a **Parte D** da Frente B — **hoje NÃO ligada**):

- **240 turnos-seguintes × 19,7k × 90% de desconto ≈ 4,26 milhões de tokens de entrada evitáveis** —
  só no prefixo fixo, sem mexer em mais nada. Na prática o prefixo cacheável é **maior** que o piso
  (nos turnos tardios, a maior parte dos 300k é histórico estável, também cacheável).
- **A assimetria (já registrada no benchmark):** os três provedores dão ~90% de desconto em cache de
  entrada, mas a **Anthropic exige marcar `cache_control`** (o Batuta não marca → **paga cheio**),
  enquanto **OpenAI e Gemini auto-cacheiam de graça**. Como o Batuta roda **na Anthropic**, é
  exatamente onde estamos **deixando o desconto na mesa**.
- **Limite honesto:** cache só vale dentro do TTL da sessão (5 min / 1h). **Abrir um time frio** depois
  de horas não pega cache — quem resolve isso é o **resumo rolante** (Parte A). Cache e compactação são
  **complementares**, não concorrentes.

---

## 7. PROJEÇÃO DE ECONOMIA (Frente B, sobre os dados reais)

**Janela + resumo (Parte A)** — limitando o que se envia por turno (aproximado como "cap por turno",
já que a janela troca o histórico inteiro por resumo + últimos N turnos):

| Teto por turno | Tokens da criadora | Redução | Economiza |
|---|---:|---:|---:|
| hoje (sem teto) | 14.053.237 | — | — |
| ~70k | 9.368.447 | **−33%** | 4,68M |
| ~55k | 8.291.320 | **−41%** | 5,76M |
| ~40k | 6.919.724 | **−51%** | 7,13M |

**Cache (Parte D)** empilha por cima: ~4,26M de tokens a mais evitados no prefixo estável (que
**sobrevive** à janela). **Combinado, a maior categoria de custo do Batuta (a criadora, ~70% da
fatura) cai plausivelmente 50–70%** — a maior parte **sem tocar o motor** (tudo vive na borda
`criacao/`).

Para dar escala: a **conversa de 32 turnos** que hoje custa 4,26M tokens (≈ $13 em Sonnet a preço
real, muito mais quando rodava em Opus) cairia para a faixa de **1,3–1,7M** com janela, e menos ainda
com cache.

---

## 8. A TENSÃO (persistir × compactar), resolvida com dado

O âncora (§4) apontou uma tensão: a Frente A quer **persistir o fio inteiro**; a Frente B quer **enviar
pouco**. Os números mostram que **elas nem competem pelos mesmos turnos**:

- Os turnos **caros e crescentes** são os da **criadora** (Frente B) — e a cura é **compactação pura**
  (resumo + janela + cache), que **não precisa tocar o motor**.
- Os turnos da **Frente A** (mensageria) são **baratos e limitados**; o problema lá é **rastro/HITL**,
  não volume. Persistir estado ali serve para **depurar e unificar o portão**, não para cortar fatura.

A reconciliação do âncora continua válida (**guardar o fio completo como iceberg durável, alimentar o
modelo só com janela + resumo**), mas o dado revela algo importante para a **forma**: **o ganho de
custo urgente está inteiro na Frente B, e a Frente B é auto-contida na borda** (a própria
`ECONOMIA-TOKENS-IA-CRIADORA.md` diz: "núcleo de orquestração não é tocado"). A Frente A é um trabalho
**separado** (arquitetura/rastro) que só precisa da suspensão do congelamento **na Fatia 4**.

---

## 9. RECOMENDAÇÃO para a decisão adiada (§7 do âncora) — o maestro decide

> **Recomendação: DOIS TRILHOS COORDENADOS, com a Frente B primeiro.** Não um programa monolítico.

Motivos, com número:
1. **O dinheiro está na Frente B** (~70% do custo) e ela **corta 50–70% sem tocar o motor** e **sem
   depender da governança** (nada de descongelar). É o ganho rápido, barato e de baixo risco.
2. **A Frente A não tem urgência de custo** (mensageria < 3%); seu valor é **rastro + HITL**, um
   trabalho estrutural que **precisa** da suspensão dirigida do congelamento (só na Fatia 4). Acoplá-la
   à Frente B **atrasaria o ganho de custo** e casaria o barato-urgente com o delicado-arriscado.
3. Elas **compartilham o conceito** (memória entre turnos / não reconstruir do texto) e devem se
   **coordenar** (a Fatia 1 de A e a Parte C de B são a mesma ideia — guardar o completo, enviar o
   enxuto), mas **não precisam do mesmo cronograma nem da mesma fundação de código para começar**.

**Sequência sugerida (se o maestro aprovar a forma "dois trilhos"):**
- **Já, barato, sem governança:** Frente B — **Parte D (cache)** primeiro (alívio imediato, baixo
  risco) + **Parte A (resumo/janela)** (o maior corte). Em paralelo, a correção de `precos.py` (§10).
- **Depois, estrutural, com governança:** Frente A — **Fatia 1 (rastro sombra)** resolve já a dor do
  Bubble sem tocar o portão; o resto (Fatias 3–5) segue com a suspensão dirigida quando o maestro quiser.

**A decisão é do maestro.** Enquanto ele não a tomar, o âncora (§7) permanece "adiada"; este estudo só
entrega a evidência e a recomendação.

---

## 10. Correções colaterais achadas (fora do runtime)

- **`cerebro/precos.py` desatualizado:** Opus em `(15.0, 75.0)`; o real do Opus 4.8 é `(5.0, 25.0)`. A
  tela `/uso` **superestima ~2,3×**. É informativo (não cobrança), mas engana a leitura de custo.
  **Correção de 1 linha, aditiva, sem risco** — vale fazer para as próximas medições baterem com a
  realidade. (Não feito nesta rodada; aguarda sinal, como todo código.)
- **Medição cache-aware:** quando a Parte D entrar, `precos.py` deve ler `cache_read_input_tokens` do
  `usage_metadata` para o custo refletir o desconto (hoje contaria o token cacheado como entrada cheia).

---

## 11. Documentos relacionados
- Âncora do programa e a decisão adiada: [`UNIFICACAO-ESTADO.md`](UNIFICACAO-ESTADO.md) (este estudo é o **Marco 0**).
- Frente B (as partes A–E): [`ECONOMIA-TOKENS-IA-CRIADORA.md`](ECONOMIA-TOKENS-IA-CRIADORA.md).
- Frente A (as fatias do runtime): [`REMODELAGEM-MOTOR.md`](REMODELAGEM-MOTOR.md).
- Economia por provedor (cache/preço-base): [`BENCHMARK-MENSAGERIA-MOTORES.md`](BENCHMARK-MENSAGERIA-MOTORES.md) § "Economia por PROVEDOR".
