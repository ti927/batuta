---
titulo: "Credenciais nomeadas (a caixa-forte)"
area: "segredos"
slug: "credenciais-nomeadas"
tags: ["credencial", "cofre", "caixa-forte", "wordpress", "instagram", "telegram", "token", "segredo"]
revisado_em: "2026-07-17"
fontes: ["cerebro/modelos.py (Credencial)", "cerebro/credenciais_cofre.py", "cerebro/tipos_credencial.py"]
---

# Credenciais nomeadas (a caixa-forte)

## Em uma frase
Uma credencial é um conjunto tipado de campos secretos (ex.: WordPress = usuário + senha de app) que
você cadastra **uma vez** e vários instrumentos apontam para ela.

## Para que serve / quando usar
Para reusar um segredo em vários lugares sem recadastrar, e trocá-lo **num lugar só**. Cada credencial
tem um **tipo** conhecido (WordPress, Instagram, Telegram, Bearer, SQL…), que define os campos.

## Como usar (na tela)
1. Em **Chaves e credenciais**, crie a credencial do tipo certo e preencha os campos (vão cifrados).
2. No instrumento, em **Credencial da central**, aponte para ela — os campos fornecidos por ela ficam
   **ocultos** no formulário do instrumento (o valor vem da credencial na hora de usar).
3. Para trocar o segredo, edite a credencial (um lugar só).

## Exemplos
- Uma credencial `instagram` (conta + token) usada pelos instrumentos de publicar/ler/responder.
- Uma credencial WordPress usada por vários times de conteúdo da mesma organização.

## Limites e cuidados
- Segredos **nunca** voltam à tela (só os últimos dígitos).
- Uma credencial pode ser da **organização** ou da **consultoria** (compartilhada). Duplicar time **não**
  copia o segredo — a cópia nasce a reconectar.

## Para a IA
Você **referencia** uma credencial por id — nunca toca no segredo. Ao montar um agente que precisa de um
serviço com segredo (Instagram, WordPress, Telegram), monte tudo e avise que falta o humano ligar/colar a
credencial na tela; não diga que está "pronto/ligado" sem isso.

## Relacionado
- [[segredos/chaves-de-ia]]
- [[segredos/segredos-de-instrumento]]
- [[instrumentos/cinto]]
