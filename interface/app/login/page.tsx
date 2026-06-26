import Image from "next/image";
import Link from "next/link";

import { ROTAS_LEGAIS } from "@/lib/legal";
import { LoginCliente } from "./login-cliente";

// Rota pública (liberada no proxy.ts). Quem já está logado e cai aqui pode
// simplesmente navegar para dentro; a proteção das demais rotas é do proxy.
//
// Layout em duas colunas (DESIGN-SYSTEM / mockup do maestro): à esquerda, a
// logomarca + o formulário de login sobre o off-white Maestro (`bg-background`,
// #fafaf7); à direita, o mascote sobre o branco puro (`bg-card`, #ffffff). No
// mobile empilha: mostra logo + form e oculta o painel do mascote.
export default function LoginPage() {
  return (
    <main className="grid min-h-dvh w-full flex-1 md:grid-cols-2">
      {/* Esquerda — logomarca + login */}
      <div className="flex flex-col items-center justify-center gap-8 bg-background p-8">
        <Image
          src="/logo-lockup.png"
          alt="Batuta"
          width={280}
          height={300}
          priority
          className="h-auto w-44"
        />
        <LoginCliente />

        <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {ROTAS_LEGAIS.map((r) => (
            <Link key={r.href} href={r.href} className="hover:text-foreground">
              {r.rotulo}
            </Link>
          ))}
        </nav>
      </div>

      {/* Direita — mascote */}
      <div className="hidden items-center justify-center bg-card p-8 md:flex">
        <Image
          src="/mascote-completo.png"
          alt="Batuta — Você guia. A IA executa."
          width={680}
          height={620}
          priority
          className="h-auto w-full max-w-md"
        />
      </div>
    </main>
  );
}
