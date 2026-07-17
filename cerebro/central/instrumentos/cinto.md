---
titulo: "O cinto e os instrumentos"
area: "instrumentos"
slug: "cinto"
tags: ["instrumento", "cinto", "encaixe", "config", "args", "secreto", "credencial", "acao-irreversivel"]
revisado_em: "2026-07-17"
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

## Exemplos
- "Gerar imagem" no cinto do redator; "Publicar no Instagram" no cinto do publicador.
- Um mesmo instrumento de envio pode estar em vários agentes (para só **enviar**).

## Limites e cuidados
- **Ação irreversível** (publicar/enviar/gravar) exige **portão de aprovação antes** — o Batuta cobra
  isso na ativação.
- O instrumento é **genérico**; quem dá o contexto ("a foto da pessoa vai primeiro") é o **markdown do
  agente**, não o instrumento.

## Para a IA
Os parâmetros exatos de cada tipo estão no **catálogo** (`catalogo_de_instrumentos`) — a fonte da
verdade; não os repita de memória. `acao_irreversivel` resolve se precisa de portão. Config = fixo do
humano (prevalece); Args = conteúdo do agente. Só proponha instrumentos que existem no catálogo.

## Relacionado
- [[times-agentes/agente]]
- [[automacoes/portao-de-aprovacao]]
- [[segredos/segredos-de-instrumento]]
