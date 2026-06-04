// Cliente Supabase para o NAVEGADOR (ilhas-cliente / "use client").
// Lê a sessão dos cookies do navegador. Só usa as variáveis públicas
// (NEXT_PUBLIC_*) — nenhum segredo do servidor passa por aqui (CLAUDE.md §8).

import { createBrowserClient } from "@supabase/ssr";

export function criarClienteNavegador() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
