// Busca no cérebro a partir do SERVIDOR (Server Components).
// Devolve um `Response` cru — os Server Components dependem de `resp.status`
// (ex.: 404 → notFound) e fazem `resp.json()` eles mesmos. Aqui só anexamos o
// token da sessão (cookies via cliente-servidor do Supabase) e `no-store`.
// `server-only` garante que este módulo nunca vá para o navegador.

import "server-only";

import { type MeuAcesso } from "@/lib/api";
import { criarClienteServidor } from "@/lib/supabase/cliente-servidor";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export async function buscarCerebro(caminho: string): Promise<Response> {
  // O proxy.ts já renovou o cookie antes da página renderizar; o token está
  // fresco. O cérebro é quem valida (JWKS).
  const supabase = await criarClienteServidor();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  return fetch(`${BASE}${caminho}`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

// Quem sou eu e meus papéis por organização (para a UI ciente de papel, I6.6).
export async function buscarMeuAcesso(): Promise<MeuAcesso | null> {
  const resp = await buscarCerebro("/eu");
  if (!resp.ok) return null;
  return resp.json();
}
