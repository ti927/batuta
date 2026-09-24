"""Quadros — a parte de DADOS do Cérebro da organização (`docs/CEREBRO-PLANO.md`).

Um quadro é como uma aba de planilha, só que o Batuta sabe o que tem em cada coluna:
valida o que entra, carimba quem gravou, guarda o histórico e calcula os totais (a IA
não soma — é onde ela erra calada).

A regra desta pasta: **uma camada só**. Agente (instrumento), tela, IA criadora e MCP
chamam o MESMO `servico`; nenhuma porta reimplementa validação, chave ou filtro.

- `tipos`   — os tipos de coluna e a normalização de cada valor;
- `limites` — os limites padrão, todos visíveis e ajustáveis por quadro;
- `filtros` — a linguagem única de filtro/ordem (a mesma para agente, tela e MCP);
- `servico` — criar/alterar quadro, gravar/editar/apagar/consultar/totalizar linhas.
"""
