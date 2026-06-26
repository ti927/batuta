import Image from "next/image";
import Link from "next/link";

import { ATUALIZADO_EM, CONTROLADOR, ROTAS_LEGAIS } from "@/lib/legal";

// Casco compartilhado das páginas legais públicas (/privacidade, /termos,
// /exclusao-de-dados). Server Component estático — sem estado, sem cliente.

// Uma seção com título — as páginas compõem o texto com <Secao> + tags cruas
// (<p>, <ul><li>, <strong>, <a>), estilizadas uma vez no <article> abaixo.
export function Secao({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-medium text-foreground">{titulo}</h2>
      {children}
    </section>
  );
}

export function PaginaLegal({
  titulo,
  atualizadoEm = ATUALIZADO_EM,
  children,
}: {
  titulo: string;
  atualizadoEm?: string;
  children: React.ReactNode;
}) {
  return (
    // O <body> deslogado é `h-dvh overflow-hidden` e injeta `children` direto
    // (app/layout.tsx) — por isso a própria página tem de ser o container de
    // rolagem, senão o texto longo fica cortado.
    <main className="h-dvh w-full overflow-y-auto bg-background">
      <div className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:px-6">
        <header className="flex items-center justify-between gap-4 border-b border-border pb-6">
          <Link href="/" aria-label="Batuta — página inicial">
            <Image
              src="/logo-lockup.png"
              alt="Batuta"
              width={280}
              height={300}
              className="h-auto w-28"
              priority
            />
          </Link>
          <span className="text-xs text-muted-foreground">
            Atualizado em {atualizadoEm}
          </span>
        </header>

        <h1 className="text-2xl font-medium text-foreground sm:text-3xl">
          {titulo}
        </h1>

        {/* Conteúdo legal: estiliza as tags cruas (p/ul/li/a/strong) uma vez só */}
        <article
          className="space-y-9 text-sm leading-relaxed
            [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2
            [&_p]:text-foreground/90
            [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5 [&_ul]:text-foreground/90
            [&_strong]:font-medium [&_strong]:text-foreground"
        >
          {children}
        </article>

        <footer className="space-y-3 border-t border-border pt-6 text-xs text-muted-foreground">
          <nav className="flex flex-wrap gap-x-4 gap-y-1">
            {ROTAS_LEGAIS.map((r) => (
              <Link
                key={r.href}
                href={r.href}
                className="text-primary underline underline-offset-2"
              >
                {r.rotulo}
              </Link>
            ))}
          </nav>
          <p>
            {CONTROLADOR.razaoSocial} — CNPJ {CONTROLADOR.cnpj}.
          </p>
        </footer>
      </div>
    </main>
  );
}
