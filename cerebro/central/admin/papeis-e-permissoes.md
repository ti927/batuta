---
titulo: "Papéis e permissões"
area: "admin"
slug: "papeis-e-permissoes"
tags: ["papel", "permissao", "admin", "operador", "observador", "acesso", "consultoria"]
revisado_em: "2026-07-17"
fontes: ["cerebro/auth.py", "cerebro/rotas/_comum.py", "cerebro/consultoria.py"]
---

# Papéis e permissões

## Em uma frase
Cada pessoa tem um **papel por organização** — **observador**, **operador** ou **admin** —, e o papel maior
contém o menor.

## Para que serve / quando usar
Controlar quem pode ver, operar e administrar cada organização:

- **Observador** — vê o que existe.
- **Operador** — vê e opera (roda, edita o trabalho do dia a dia).
- **Admin** — tudo, incluindo gerir membros, convites e papéis.

Há ainda o **admin da consultoria**, um papel transversal (da Lure) que administra os recursos
compartilhados — por exemplo, a **chave-mãe** de IA que serve de fallback para as organizações.

## Como usar (na tela)
1. O papel é **por organização** — a mesma pessoa pode ser admin numa e observador em outra.
2. Um admin gere os papéis na área de **membros** da organização.
3. A interface mostra a cada um só o que o seu papel permite.

## Exemplos
- Um cliente com papel **operador** roda e ajusta seus times, mas não convida gente nem muda papéis.

## Limites e cuidados
- **A organização precisa de ao menos um admin** — o sistema impede rebaixar/remover o último.
- Quem não é membro de uma organização **não a enxerga** (nem sabe que existe).
- Papel removido ou usuário desativado tem efeito **imediato**.

## Para a IA
Papéis são coisa de administração — você ajuda a montar times, não a conceder acessos. Se uma ação exige um
papel que o consultor não tem, explique que é preciso um **admin** da organização.

## Relacionado
- [[admin/membros-e-convites]]
- [[fundamentos/hierarquia]]
- [[operacao/auditoria-e-lgpd]]
