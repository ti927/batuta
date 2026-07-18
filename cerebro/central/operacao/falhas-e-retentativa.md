---
titulo: "Falhas e retentativa"
area: "operacao"
slug: "falhas-e-retentativa"
tags: ["falha", "erro", "retentavel", "idempotencia", "retentativa", "sweeper"]
revisado_em: "2026-07-17"
fontes: ["cerebro/instrumentos/base.py", "PRODUTO.md §16"]
---

# Falhas e retentativa

## Em uma frase
Quando um passo falha, o Batuta decide se **vale tentar de novo** (erro passageiro) ou se **para**
(erro definitivo) — e nunca refaz uma ação já feita.

## Para que serve / quando usar
Entender por que um fluxo às vezes se recupera sozinho e às vezes para na sua frente:

- **Retentável** — erro passageiro (rede, serviço fora do ar, "muitas requisições"/429, 5xx). O motor
  **tenta de novo**.
- **Não-retentável** — erro definitivo (chave recusada, parâmetro inválido, conteúdo bloqueado). O fluxo
  **para** com um recado claro; insistir não adianta.

## Como usar (na tela)
1. Na inspeção da execução, um passo que falhou mostra o **motivo em português** e se foi retentado.
2. Um erro definitivo pede uma **ação sua** (corrigir a chave, o parâmetro, o conteúdo) — não vai se
   resolver sozinho.

## Exemplos
- O provedor respondeu "muitas requisições" → retenta e segue.
- A chave da API foi recusada → para, para você corrigir a chave.

## Limites e cuidados
- **Idempotência:** depois que uma ação que age no mundo (publicar, gerar vídeo, responder comentário) já
  aconteceu, qualquer falha vira **não-retentável** — para nunca publicar/cobrar em dobro.
- Geração de vídeo/imagem pesada tem **teto de tempo**: se estourar, falha limpo numa vez só (não fica
  reprocessando e multiplicando custo).

## Para a IA
Traduza o erro para o consultor: se é retentável, o Batuta cuida; se é definitivo, diga **o que ele precisa
ajustar**. Nunca proponha "rodar de novo" quando o erro é de chave/parâmetro/conteúdo — corrija a causa.

## Relacionado
- [[automacoes/execucoes-e-inspecao]]
- [[operacao/uso-e-custos]]
