---
titulo: "Ler um quadro de fora"
area: "cerebro"
slug: "acesso-de-fora"
tags: ["quadro", "link", "painel", "dashboard", "looker", "google planilhas", "importdata", "power bi", "excel", "csv", "json", "api", "acesso externo", "cerebro"]
revisado_em: "2026-09-24"
fontes: ["cerebro/quadros/links.py", "cerebro/rotas/quadros_publico.py", "docs/CEREBRO-PLANO.md"]
---

# Ler um quadro de fora

## Em uma frase
Um **link de leitura** deixa um painel de fora do Batuta (Google Planilhas, Looker Studio, Power BI, Excel
ou um painel feito sob medida) ler um quadro sem login, e se atualizar sozinho.

## Para que serve / quando usar
Quando um agente alimenta um quadro todo dia e alguém quer ver aquilo num painel: os números da semana, o
funil de vendas, as contas a pagar. O painel lê o quadro direto; ninguém precisa exportar nada.

## Como usar (na tela)
1. **Cérebro** › o quadro › aba **Quem usa** › **Acesso de fora** › **Criar link de leitura** (só
   administradores da organização).
2. Dê um nome ao link (quem vai usar), o limite de leituras por minuto e, se quiser, uma data de validade.
3. **Copie o link na hora.** Depois o Batuta mostra só o final dele. A mesma tela já traz a fórmula pronta
   do Google Planilhas.

**Google Planilhas e Looker Studio:** numa célula da planilha, cole
`=IMPORTDATA("<link>?decimal=virgula")`. A planilha se atualiza sozinha (o Google relê de tempos em
tempos). No Looker Studio, use essa planilha como fonte de dados.

**Power BI e Excel:** “Obter dados” › “Da web” › cole o link.

**Painel próprio:** acrescente `?formato=json` ao link.

## O que dá para pedir no link
Acrescente ao fim do link, com `?` antes do primeiro e `&` entre eles:

| Parâmetro | O que faz | Exemplo |
|---|---|---|
| `formato=json` | devolve JSON em vez de CSV | `?formato=json` |
| `filtro=Coluna\|operador\|valor` | só as linhas que batem; pode repetir | `filtro=Tema\|eq\|COF` |
| datas relativas no filtro | `hoje`, `hoje-90`, `hoje+7` | `filtro=Semana\|gte\|hoje-90` |
| `recente=Coluna` | só a rodada mais recente | `recente=Data` |
| `ordem=Coluna` ou `ordem=-Coluna` | ordena (o `-` é do maior para o menor) | `ordem=-Semana` |
| `colunas=A,B` | só estas colunas | `colunas=Semana,Cliques` |
| `busca=texto` | texto em qualquer coluna | `busca=Goiânia` |
| `limite=N` | até N linhas (máximo 10.000) | `limite=500` |
| `decimal=virgula` | números como 1234,5 (planilha em português) | `decimal=virgula` |

Operadores do filtro: `eq` (igual), `ne` (diferente), `gt`/`gte` (maior / maior ou igual), `lt`/`lte`
(menor / menor ou igual), `contem`, `vazio`, `nao_vazio`.

**Totais já calculados pelo Batuta:** troque o fim do link por `/totais` e diga o que somar:
`<link>/totais?agrupar=Tema&metrica=soma|Cliques&metrica=contar`. Funções: `contar`, `soma`, `media`,
`minimo`, `maximo`; agrupe por até 3 colunas.

## Limites e cuidados
- **O link é uma senha.** Quem tem o link vê o quadro. Não cole em lugar público. Se ele vazar, **Trocar
  o link** gera outro na hora e o antigo para de funcionar.
- Só lê, e só aquele quadro. O link nunca grava nem enxerga outros quadros.
- Cada link tem um limite de leituras por minuto (padrão 60, máximo 600), que você ajusta. Acima dele, o
  painel recebe um aviso para esperar um minuto.
- Até 10.000 linhas por leitura. Para mais, use filtros ou os totais.
- Toda leitura fica contada no link (quantas e a última), e o link aparece em **Quem usa**.
- Não guarde CPF, salário nem dados de saúde num quadro que tem link de fora.

## Para a IA
- Você **não cria nem troca** link de leitura, e **não recebe** o link inteiro: ele é uma senha. Oriente o
  consultor a criar pela tela (quadro › Quem usa › Acesso de fora), como administrador.
- Pelo MCP há `listar_links_quadro` (nome, final, estado, leituras) e `revogar_link_quadro` (pede
  confirmação; o painel para na hora).
- Ajude a montar a URL do painel com os parâmetros acima: por exemplo, para "os últimos 90 dias só do tema
  COF", `?filtro=Semana|gte|hoje-90&filtro=Tema|eq|COF`.
- Para painéis de números, prefira `/totais`: o Batuta soma, o painel só desenha.

## Relacionado
- [[cerebro/quadros]]
- [[cerebro/o-que-e-o-cerebro]]
