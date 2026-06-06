<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Antes de qualquer trabalho de UI/tela/layout

Leia **`../DESIGN-SYSTEM.md`** (marca, paleta, tokens, tipografia, componentes, voz) **e**
**`../docs/design/README.md`** (handoff hi-fi: as telas desenhadas — criação AI-first, dashboard,
inspeção de execução, IA companheira — e o **shell de navegação em sidebar escura**, a casca
definitiva). São a fonte da verdade visual; não invente telas de memória.

Os `.jsx`/`.html` em `../docs/design/` são **referência de design, não código de produção**: recrie
as telas aqui com Next + Tailwind + **shadcn/ui** + ícones **lucide-react**, seguindo o padrão já
estabelecido (Server Component para busca + ilha cliente para mutação + `router.refresh()`). Os
tokens de marca já estão no `app/globals.css` e os primitivos em `components/ui/`. Assets de marca
(mascote/símbolo/logo) estão em `public/`. Vocabulário nas telas: **Agente/Instrumento/Automação**
(decisão do maestro; ver `DESIGN-SYSTEM.md`).
