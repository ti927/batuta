// Recebe o link do e-mail de convite do Supabase. O link traz um `token_hash`
// (prova de que o convite é legítimo). Aqui trocamos esse token por uma sessão
// real (cookies) via verifyOtp e seguimos para a tela indicada em `next`.
// Padrão oficial do @supabase/ssr para confirmação de e-mail no App Router.

import { type EmailOtpType } from "@supabase/supabase-js";
import { redirect } from "next/navigation";
import { type NextRequest } from "next/server";

import { criarClienteServidor } from "@/lib/supabase/cliente-servidor";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const proximoBruto = searchParams.get("next") ?? "/";
  // Só aceitamos caminho interno (evita redirecionamento para fora).
  const proximo = proximoBruto.startsWith("/") ? proximoBruto : "/";

  if (token_hash && type) {
    const supabase = await criarClienteServidor();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    // redirect() lança NEXT_REDIRECT, então fica fora do if de erro: em
    // sucesso aplica os cookies recém-gravados e vai para `proximo`.
    if (!error) redirect(proximo);
  }

  // Link inválido/expirado: volta ao login.
  redirect("/login");
}
