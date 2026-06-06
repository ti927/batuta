"""A IA criadora (Etapa 2, Fase 9).

Camada conversacional que monta um time inteiro por conversa, em MODO RASCUNHO
(MIGRACAO §6.4): as ferramentas da IA montam um documento (`rascunho.Rascunho`) e
NUNCA tocam as tabelas de negócio; só `materializar`, após a aprovação humana
explícita, grava tudo de uma vez. A separação 'a IA propõe / o consultor confirma'
é, por construção, uma garantia estrutural — não disciplina.
"""
