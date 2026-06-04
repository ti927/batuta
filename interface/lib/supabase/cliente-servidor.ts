// Cliente Supabase para o SERVIDOR (Server Components, Server Actions, rotas).
// A sessão vive nos cookies; no Next 16 o `cookies()` é assíncrono, por isso
// esta função é `async`. Em Server Component puro a gravação de cookie pode
// falhar — o `try/catch` no setAll absorve isso (o proxy.ts renova a sessão).

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function criarClienteServidor() {
  const armazemCookies = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return armazemCookies.getAll();
        },
        setAll(cookiesParaGravar) {
          try {
            cookiesParaGravar.forEach(({ name, value, options }) =>
              armazemCookies.set(name, value, options),
            );
          } catch {
            // Chamado de um Server Component sem resposta mutável: ignora.
            // A renovação de sessão acontece no proxy.ts.
          }
        },
      },
    },
  );
}
