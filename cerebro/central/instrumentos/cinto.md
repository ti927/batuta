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

## Personalizado ou pronto (nativo)
- **Personalizado** — tudo o que só conversa com um serviço de fora: uma **API** (conector) ou um
  **servidor MCP**. Nasce em **🌟 Criar instrumento** e se edita no **Construtor**, inclusive quando
  foi a IA quem criou.
- **Pronto (nativo)** — o que mexe no interior do Batuta ou precisa de código de verdade (agendar
  automação, pedir aprovação, quadro do Cérebro, gerar e descrever imagem…). Fica em **Instrumento
  pronto** e abre no painel lateral.
- A **chamada de API avulsa** não se cria mais: virou conector. As que já existem seguem valendo.

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
