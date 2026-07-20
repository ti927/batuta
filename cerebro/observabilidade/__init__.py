"""Observabilidade do Batuta — logging estruturado + banco de logs pesquisável.

Camada de BORDA (o núcleo de orquestração não a conhece). Três peças:

- `contexto`: um ContextVar que carrega o "quem/onde/qual requisição" do momento,
  espelhando o padrão de `orquestracao.llm.usar_chaves` / `orquestracao.atividade.usar_atividade`
  (atravessa o stack e as threads dos workers sem mudar assinatura nenhuma).
- `log`: identidade do servidor (host/pid/commit/ambiente), formatador JSON para o stdout
  e a configuração central de logging.
- `escritor`: `registrar_evento(...)` — emite no stdout JSON e persiste (best-effort, em
  transação própria) na tabela `evento_log`, nunca derrubando o request.

Motivador: um cérebro rodando LOCAL disparava a produção pelo banco compartilhado; sem
carimbo de `host`/`ambiente` em cada evento, isso ficou invisível por horas.
"""
