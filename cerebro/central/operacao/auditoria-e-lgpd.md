---
titulo: "Auditoria e LGPD"
area: "operacao"
slug: "auditoria-e-lgpd"
tags: ["auditoria", "lgpd", "registro", "privacidade", "dados", "exclusao", "seguranca"]
revisado_em: "2026-07-17"
fontes: ["cerebro/auditoria.py", "interface/lib/legal.ts", "project_paginas-legais-meta"]
---

# Auditoria e LGPD

## Em uma frase
Ações sensíveis ficam **registradas** (quem fez o quê), os segredos ficam **cifrados**, e há páginas
públicas de privacidade, termos e exclusão de dados.

## Para que serve / quando usar
Rastreabilidade e conformidade: saber quem alterou um papel, criou/revogou um convite, desativou um usuário;
e atender a LGPD. Importa a admins e a quem cuida de dados na organização.

## Como usar (na tela)
1. Ações sensíveis (papéis, convites, (des)ativação de usuário) são **auditadas** automaticamente — o
   registro entra na mesma transação da ação (ou os dois acontecem, ou nenhum).
2. As páginas legais são públicas (sem login): **/privacidade**, **/termos** e **/exclusao-de-dados** em
   batuta.team.

## Exemplos
- Alterar o papel de um membro fica registrado (de qual papel para qual, por quem).

## Limites e cuidados
- **Segredos** (chaves, tokens, senhas) vivem **só no cérebro**, cifrados, e nunca voltam à tela nem
  chegam ao navegador.
- A página de **exclusão de dados** é de **instruções** (como solicitar a exclusão).
- Este capítulo descreve o funcionamento do produto — **não é aconselhamento jurídico**; para textos
  legais definitivos, revise com um advogado.

## Para a IA
Reforce boas práticas: segredo nunca em texto/markdown; dados pessoais tratados com cuidado. Não invente
garantias jurídicas; aponte as páginas legais e a possibilidade de exclusão de dados.

## Relacionado
- [[admin/papeis-e-permissoes]]
- [[admin/membros-e-convites]]
- [[segredos/segredos-de-instrumento]]
