import Image from "next/image";

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
    <main className="grid min-h-screen md:grid-cols-2">
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
