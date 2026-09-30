---
titulo: "O cinto e os instrumentos"
area: "instrumentos"
slug: "cinto"
tags: ["instrumento", "cinto", "encaixe", "config", "args", "secreto", "credencial", "acao-irreversivel"]
revisado_em: "2026-09-29"
fontes: ["PRODUTO.md §13", "cerebro/instrumentos/base.py"]
---

# O cinto e os instrumentos

## Em uma frase
Instrumentos são as **capacidades** que um agente pode usar (publicar, buscar, gerar imagem, enviar
mensagem…); cada agente tem seu **cinto** com os instrumentos que precisa.

## Para que serve / quando usar
Um instrumento é uma peça plugável, sempre com o mesmo encaixe. Duas coisas importantes de entender:

- **Configuração (o que VOCÊ preenche na tela)** — conexão, conta, ajustes fixos. Vale como está: o
  agente **não** troca esses valores pelo texto dele.
- **Argumentos (o que o AGENTE passa ao usar)** — o conteúdo do momento (a mensagem, o prompt, a
  consulta). Não aparecem no formulário; a IA os preenche na hora.

## Como usar (na tela)
1. No time, crie o instrumento (escolha o tipo, preencha a configuração).
2. **Pendure** o instrumento no cinto do agente que vai usá-lo.
3. Se ele tem **segredo** (token/senha), aponte para uma **credencial** ou preencha o segredo (cofre).
4. Explique no `tools.md` do agente **quando** e **como** usar.

## Os dois tipos: personalizado e pronto do Batuta
Todo instrumento é de UM destes dois tipos. "Nativo" e "pronto" são a MESMA coisa; na tela o nome é
**Prontos do Batuta**.

| | **Personalizado** | **Pronto do Batuta** ("nativo") |
|---|---|---|
| O que é | Ligação com um **serviço de fora**, sem código: uma **API** (conector, com uma ou várias operações) ou um **servidor MCP** | Capacidade que **vem com o Batuta**: mexe no interior dele ou precisa de código de verdade |
| Exemplos | Zernio (Instagram), WordPress por MCP, Search Console, "Data de hoje" | Agendar automação, Pedir aprovação, Quadro do Cérebro, Gerar imagem/vídeo, Descrever imagem, Telegram, Busca na web, Banco SQL, Gerar PDF |
| Nasce em | **🌟 Criar instrumento** → "Uma API" ou "Um servidor MCP" | **Instrumento pronto** |
| Edita em | **Construtor** (também quando foi a IA quem criou) | Painel lateral |
| Identificação | Dentro do próprio instrumento (chave, senha, login, certificado) | Idem; busca e imagem podem usar a chave da organização |

- A **chamada de API avulsa** não se cria mais: virou conector. As que já existem seguem valendo.
- A aba **Instrumentos** mostra as duas listas separadas (**Personalizados** e **Prontos do Batuta**,
  com os quadros do Cérebro num grupo à parte), com busca, filtros (tipo, alcance, situação,
  categoria, agente) e selos no cartão: **precisa de atenção** (falta a chave, a conta caiu ou a
  última conexão falhou), **sem agente**, **do time** / **da organização**, **API** / **MCP**,
  **altera algo** / **só lê** e **pago**. Personalizado sem ícone escolhido ganha o ícone do serviço
  (o que o servidor MCP anuncia, ou o do site da API), buscado pelo Batuta.

## Exemplos
- "Gerar imagem" no cinto do redator; "Publicar no Instagram" no cinto do publicador.
- Um mesmo instrumento de envio pode estar em vários agentes (para só **enviar**).

## Limites e cuidados
- **Ação irreversível** (publicar/enviar/gravar) pede **aprovação antes** — o Batuta cobra
  isso na ativação.
- O instrumento é **genérico**; quem dá o contexto ("a foto da pessoa vai primeiro") é o **markdown do
  agente**, não o instrumento.

## Para a IA
Integração com serviço de fora = instrumento personalizado: API → `montar_conector` (uma ou
várias operações); servidor MCP → `configurar_instrumento` tipo `conectar_mcp`. Nunca a chamada de
API avulsa (é recusada).
Os parâmetros exatos de cada tipo estão no **catálogo** (`catalogo_de_instrumentos`) — a fonte da
verdade; não os repita de memória. `acao_irreversivel` resolve se a ação é irreversível. Config = fixo do
humano (prevalece); Args = conteúdo do agente. Só proponha instrumentos que existem no catálogo.

## Relacionado
- [[times-agentes/agente]]
- [[automacoes/pedir-aprovacao]]
- [[segredos/segredos-de-instrumento]]
