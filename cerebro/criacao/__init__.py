"""A IA criadora (Etapa 2) — UMA conversa que nunca termina.

Camada conversacional que monta e MANTÉM um time por conversa. As ferramentas
escrevem no TIME REAL pela porta única e validada de `criacao.servicos`. A proteção
não é mais 'nada é real até aprovar' (rascunho), e sim 'tudo é real mas DORME': a
automação nasce inativa e nada roda até o consultor ATIVAR. A proteção contra ação
irreversível não é uma trava na ativação (a parede foi removida em 2026-08-31) e sim o
instrumento `pedir_aprovacao` no cinto do agente, com a regra escrita no markdown dele.
"""
