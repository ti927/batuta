---
titulo: "Instrumento — Google Search Console: consultar"
area: "instrumentos"
slug: "search-console"
tags: ["search-console", "google", "seo", "cliques", "impressoes", "posicao", "blog", "instrumento"]
revisado_em: "2026-07-18"
fontes: ["cerebro/instrumentos/search_console.py"]
---

# Instrumento — Google Search Console: consultar

## Em uma frase
Lê o desempenho do site no Google (cliques, impressões, CTR e posição média), agrupado por consulta de
busca, página, país, dispositivo ou data.

## Para que serve / quando usar
Para um agente **avaliar o SEO do blog**: quais buscas trazem gente, quais páginas rendem, onde a posição
caiu. É só leitura — bom para relatórios e para decidir a próxima pauta.

## Como usar (na tela)
1. **Conecte a conta Google** que tem acesso ao Search Console do site (veja [[segredos/conectar-google]]).
2. Crie o instrumento **Google Search Console: consultar** e, em **Site (propriedade do Search Console)**,
   informe o site **exatamente** como aparece no Search Console: `sc-domain:seublog.com` (domínio inteiro)
   ou `https://seublog.com/` (prefixo de URL).
3. Em **Credencial da central**, aponte para a credencial `google`.
4. Pendure no cinto do agente "Analista de SEO".

## Exemplos
- Um agente que, toda segunda, lê as 20 principais consultas dos últimos 28 dias e resume o que mudou.
- Agrupar por `page` para ver as páginas com mais impressões e baixa posição (candidatas a melhorar).

## Limites e cuidados
- A conta conectada precisa ter **acesso àquela propriedade** no Search Console (senão vem "permissão
  negada" — 403).
- Os dados têm **~2 a 3 dias de atraso**; os dias mais recentes podem vir incompletos.
- Métricas: cliques, impressões, CTR e posição média (não são visitas do Analytics).
- Só leitura → não exige portão.

## Para a IA
Parâmetros no catálogo (`search_console`): `dias` (últimos N dias, padrão 28), `dimensoes`
(`query`/`page`/`country`/`device`/`date`, uma ou mais) e `limite`. O **site** é da configuração do humano,
não seu. Se der 403, oriente checar o acesso à propriedade e reconectar o Google incluindo o Search Console.

## Relacionado
- [[segredos/conectar-google]]
- [[instrumentos/publicar-wordpress]]
- [[operacao/uso-e-custos]]
