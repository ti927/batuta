---
titulo: "Membros e convites"
area: "admin"
slug: "membros-e-convites"
tags: ["membro", "convite", "email", "aceitar", "papel", "desativar", "admin"]
revisado_em: "2026-07-17"
fontes: ["cerebro/rotas/membros.py", "reference_email-convite-smtp"]
---

# Membros e convites

## Em uma frase
Um admin **convida** pessoas por e-mail para uma organização, com um **papel**; a pessoa aceita e vira
membro.

## Para que serve / quando usar
Dar acesso a mais gente (da equipe do cliente, ou da consultoria) e definir o que cada um pode fazer.
Ninguém se autoinscreve — o acesso começa sempre por um **convite** de um admin.

## Como usar (na tela)
1. Na área de **Membros** da organização (só admin), envie um **convite** informando o e-mail e o **papel**
   (observador/operador/admin).
2. A pessoa recebe um e-mail, define a senha e **aceita** o convite — aí o membro é criado.
3. Um admin pode **alterar o papel**, **remover** um membro e **desativar/reativar** um usuário.

## Exemplos
- Convidar um cliente como **operador** para ele mexer nos próprios times.

## Limites e cuidados
- O convite **expira em 7 dias**.
- Se o e-mail já tem conta, o e-mail de convite pode não sair — a pessoa vê o convite por um **aviso dentro
  do Batuta** (banner na home) e aceita ali.
- **Não dá para ficar sem admin:** o sistema barra rebaixar/remover o último admin da organização.
- Toda ação sensível (convite, papel, (des)ativação) é **auditada**.

## Para a IA
Convites e papéis são administração — oriente o consultor a usar a área de Membros; você não concede acesso.
Se algo falha por permissão, aponte que é preciso ser **admin** da organização.

## Relacionado
- [[admin/papeis-e-permissoes]]
- [[operacao/auditoria-e-lgpd]]
