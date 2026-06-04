// proxy.ts — no Next 16 isto substitui o antigo middleware.ts (mesma função,
// nome novo; ver node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md).
// Roda antes de cada requisição: renova a sessão do Supabase e protege as rotas.

import type { NextRequest } from "next/server";
import { renovarSessao } from "@/lib/supabase/proxy-sessao";

export async function proxy(request: NextRequest) {
  return renovarSessao(request);
}

export const config = {
  // Roda em tudo, menos arquivos estáticos e imagens — o padrão oficial do
  // @supabase/ssr. Assim a sessão é renovada em toda navegação de página.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
