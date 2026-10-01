---
titulo: "Instrumento — Instagram: conta e métricas"
area: "instrumentos"
slug: "instagram-insights"
tags: ["instagram", "insights", "metricas", "conta", "posts", "engajamento", "leitura", "instrumento"]
revisado_em: "2026-10-01"
fontes: ["cerebro/instrumentos/instagram_insights.py"]
---

# Instrumento — Instagram: conta e métricas

> **Não é mais um pronto do Batuta (desde 01/10/2026).** Integração com serviço de fora é
> instrumento **personalizado**: crie em **🌟 Criar instrumento → Uma API** (ou **Um servidor
> MCP**, se o serviço tiver um), com a chave do serviço no próprio instrumento (pela IA:
> `montar_conector` ou `configurar_instrumento` com `conectar_mcp`). Os que já existem seguem
> funcionando e editáveis até serem trocados — este capítulo vale só para eles.
> Ver [[instrumentos/construir-conector]] e [[instrumentos/mcp]].

## Em uma frase
Lê a conta do Instagram e os posts recentes — usuário, total de publicações e, por post, tipo, legenda,
link, data, curtidas e comentários.

## Para que serve / quando usar
Acompanhar o **desempenho** dos posts: um agente que resume o engajamento da semana, ou que decide a
próxima pauta olhando o que teve mais retorno.

## Como usar (na tela)
1. Crie o instrumento **Instagram: conta e métricas**.
2. Em **Credencial da central**, aponte para a credencial `instagram`.
3. Pendure no cinto do agente de relatório/estratégia.

## Exemplos
- Um agente que, toda segunda, lê os 10 últimos posts e monta um resumo de engajamento.

## Limites e cuidados
- **Hashtags e métricas avançadas** (alcance, impressões, visualizações) **ainda não** estão disponíveis
  por este caminho — exigem o setup "API com login do Facebook" (fase futura). Aqui vem o engajamento
  básico: curtidas e comentários.
- Traz de 1 a 25 posts recentes. Só leitura → ninguém precisa aprovar nada.

## Para a IA
Parâmetro no catálogo (`instagram_insights`): `limite`. Não prometa alcance/impressões — este instrumento
entrega conta + posts + curtidas/comentários. Métricas avançadas são fase futura.

## Relacionado
- [[instrumentos/publicar-instagram]]
- [[instrumentos/instagram-ler-post]]
