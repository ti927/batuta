# Caixa-forte de Credenciais — plano de implementação

> Desenho **aprovado pelo maestro** (2026-06-15). Substitui a "seção B" (inventário de credenciais
> por-instrumento) por um cofre de **credenciais nomeadas, tipadas e referenciadas**. Resolve a confusão
> que o maestro apontou na validação E deixa o desenho à prova de futuro (MCP, Google Drive/OAuth, Nano
> Banana). Ver o resumo no `BUILD-PLAN.md` (FILA, item "FASE — Caixa-forte de Credenciais") e a memória
> `reference_chaves-unificadas.md`.

## O princípio (a decisão central, à prova de futuro)

Uma credencial é um **saco nomeado, tipado e cifrado de campos** — não uma coluna fixa "senha". O
instrumento **aponta** para uma credencial do tipo certo e soma só a sua config **não-secreta**
(URL, método, nome do banco). Assim:

- Credencial de uma chave só → `{chave: "..."}`.
- WordPress → `{usuario, senha_app}` (o par anda junto, nunca dessincroniza).
- SQL → `{usuario, senha}`. Telegram → `{token}`. REST → `{token}` ou `{usuario, senha}`.
- **OAuth (Google Drive, futuro)** → `{access_token, refresh_token, expira_em, escopos}` — *mesma tabela*,
  só um `tipo` diferente, preenchido por um fluxo de "Conectar" e atualizável pelo sistema.

Instrumento futuro com formato inédito = **novo `tipo` de credencial + campos no JSON, sem mudar o banco.**

## Os três baldes de autenticação (mapa mental)

1. **Chave de provedor (pool, JÁ EXISTE):** uma por serviço, compartilhada, queda org→consultoria→legado.
   OpenAI/Anthropic/Google/Tavily. *Nano Banana cai aqui — reusa a chave `google` via `chave_compartilhada`.*
2. **Credencial nomeada estática (a CAIXA-FORTE, este plano):** o usuário cria, troca num lugar só,
   instrumentos apontam.
3. **Conta OAuth (mesma tabela da caixa-forte, `tipo` diferente):** NÃO construída agora; o desenho não a trava.

## Decisões de desenho fixadas

- **Uma credencial por instrumento** (coluna `instrumentos.credencial_id`, nullable). Cada instrumento é
  uma conexão; se um dia precisar de duas, revisita. Simplificação deliberada do v1.
- **Híbrido / retrocompatível:** o campo de segredo do instrumento pode "usar uma credencial da central"
  **OU** ter valor próprio inline (como hoje). Instrumentos já no ar **não quebram**; **sem migração de dados**.
- **Prioridade na borda:** inline próprio (cofre 7-B do instrumento) > credencial central > pool de serviço.
- **Cifragem:** o saco inteiro vira UM blob JSON cifrado com a mesma `COFRE_CHAVE_MESTRA` (reusa `cofre.py`).
  Exibição: campos secretos mascarados (últimos 4); campos de identidade não-secretos (ex.: `usuario`) podem
  aparecer. Valor pleno nunca volta à interface.
- **Escopo = organização** (compartilhada entre os times da org). Acesso operador+.
- **Dois níveis + toggle "compartilhável" (decisão do maestro 2026-06-15):** um segredo pode pertencer à
  **organização** ou à **consultoria** (`organizacao_id` nulo — mesmo padrão das chaves de IA). Segredos de
  consultoria ganham um toggle **`compartilhavel`**:
  - **Balde 1 (chaves de serviço):** a queda org→consultoria→legado JÁ existe; o toggle passa a **gatekeepear**
    quais chaves da consultoria participam da reserva automática. `compartilhavel=false` → privada da consultoria,
    não serve de fallback. **Retrocompatível:** as chaves de consultoria já existentes nascem `compartilhavel=true`
    (nada que está no ar muda; o maestro desmarca o que quiser tornar privado).
  - **Balde 2 (credenciais nomeadas):** o toggle controla a **visibilidade no seletor** do instrumento. Marcada →
    aparece pros instrumentos de qualquer organização (escolha explícita, nunca fallback automático — evita o
    risco de "alvo errado"). Desmarcada → só a consultoria a vê.
- **Núcleo congelado:** toda a resolução acontece na borda (`anexar_aos_instrumentos`), igual ao reuso de
  chave compartilhada. `cadeia.py`/`agente.py` sem diff.
- **Fora de escopo:** OAuth (balde 3) e credencial por **usuário-final** (cada cliente conectar o próprio
  Drive num atendimento — é da conversa, não da org).

## Os passos (um por vez, cada um com aprovação e verificação concreta)

### Passo 1 — Schema (migração)
Nova tabela `credenciais` (`id, organizacao_id FK nullable [nulo = consultoria], nome, tipo, dados_cifrado
Text, resumo JSONB, compartilhavel Bool, expira_em nullable, timestamps`) + coluna `instrumentos.credencial_id`
(FK nullable, `ON DELETE SET NULL`) + coluna `chaves_api.compartilhavel` (Bool, default `true` nas linhas
existentes — retrocompatível). Modelos no `modelos.py`. **Verificar:** `alembic upgrade head` e `downgrade`
limpos no banco local; teste de criação do modelo.

### Passo 2 — Registro de tipos de credencial (cérebro)
`tipos_credencial.py`: cada tipo declara `tipo`, `nome_exibicao`, `campos = [(nome, rotulo, secreto)]`.
Definir: `wordpress` (usuario, senha_app), `sql` (usuario, senha), `telegram_bot` (token), `rest`
(token | usuario+senha), `webhook` (token), `mcp` (token), `generico` (chave). Cada `TipoInstrumento` ganha
`tipos_credencial_aceitos: tuple[str, ...]` (para filtrar o seletor). **Verificar:** teste listando os tipos e
seus campos.

### Passo 3 — Camada de cofre da credencial (cérebro)
Serviço `credenciais_cofre.py`: `salvar` (cifra o saco), `resumo` (mascarado por campo), `decifrar` (saco em
memória), `usado_por` (conta instrumentos que apontam). **Verificar:** round-trip cifra/decifra + mascaramento
em teste unitário.

### Passo 4 — Resolução na borda (cérebro, núcleo congelado)
Estender `anexar_aos_instrumentos`: se o instrumento tem `credencial_id`, decifra o saco e mescla em
`segredos_decifrados` com a prioridade fixada (pool < credencial < inline próprio). **Balde 1 (toggle):** a
resolução de fallback em `chaves.py` (`_buscar` com `mae=True`) passa a filtrar `compartilhavel=true` — chave
de consultoria privada não entra na reserva automática. **Verificar:** teste de que o instrumento com
`credencial_id` recebe o saco; inline próprio ainda vence; pool segue funcionando; chave de consultoria
`compartilhavel=false` NÃO cai como fallback; `cadeia.py`/`agente.py` sem diff.

### Passo 5 — Rotas (cérebro)
**Substituir** `rotas/credenciais.py` (o inventário antigo) pelo CRUD do cofre: `GET` lista (mascarada +
`usado_por`), `POST` criar, `PUT` atualizar/rotacionar, `DELETE` (bloqueia se em uso). Ligar/desligar o
`credencial_id` do instrumento (na rota de instrumento já existente). Esquemas novos; remover os antigos
(`CredencialInstrumento`/`CredencialCampo`/`RotacionarSegredos`); registrar no `main.py`. **Verificar:** testes
de API (criar, listar mascarado, apagar-em-uso bloqueado).

### Passo 6 — Tela da caixa-forte (interface)
Reescrever a seção B de `chaves-cliente.tsx`: trocar `inventario-credenciais.tsx` por
`cofre-credenciais.tsx` — lista de credenciais nomeadas, modal de criar/editar (campos pelo tipo, secreto
mascarado), "usado por N", trava no apagar. Quando a tela for da **consultoria**, o modal mostra o toggle
**"pode ser compartilhada com as organizações"**. **Balde 1:** a Seção A (`gestao-chaves.tsx`) ganha o mesmo
toggle nas chaves de consultoria. **Verificar:** `tsc`/`eslint` limpos + conferência visual.

### Passo 7 — Seletor no formulário do instrumento (interface)
`formulario-instrumento.tsx`: a área de segredo ganha "usar uma credencial da central" (seletor filtrado pelos
tipos aceitos, mostrando as credenciais **da organização + as da consultoria marcadas como compartilháveis**)
**OU** valor próprio inline (híbrido). Liga ao criar/editar instrumento (`credencial_id`). **Verificar:** build
+ round-trip manual (cria credencial → aponta no instrumento → some o pedido de senha).

### Passo 8 — Limpeza + e2e + docs
Remover o código morto do inventário antigo; suíte inteira verde; conferir núcleo sem diff; atualizar
`BUILD-PLAN.md` + memória. **Verificar (e2e):** criar credencial → referenciar num instrumento → rodar o
instrumento usando a credencial central.

## Esforço honesto
Comparável à Biblioteca: ~8 passos, **uma migração de schema** (sem migração de dados), toca a **borda** e
**duas telas**; núcleo congelado. Maior que a "faxina" que tínhamos planejado, mas é o desenho certo e durável.
