import Link from "next/link";

import { criarClienteServidor } from "@/lib/supabase/cliente-servidor";
import { ConviteCliente } from "./convite-cliente";

// Tela de aceite de convite. Chega-se aqui pelo link do e-mail (via
// /auth/confirm, que já criou a sessão). Sem sessão, não há o que aceitar —
// orientamos a pessoa a abrir o link do e-mail.
export default async function ConvitePage() {
  const supabase = await criarClienteServidor();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user?.email) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
        <h1 className="text-2xl font-bold">Convite</h1>
        <p className="max-w-sm text-sm text-zinc-600">
          Abra o link do convite que você recebeu por e-mail para continuar. Se
          já tem conta, faça login.
        </p>
        <Link
          href="/login"
          className="text-sm text-blue-600 underline underline-offset-4"
        >
          Ir para o login →
        </Link>
      </main>
    );
  }

  return <ConviteCliente email={user.email} />;
}
