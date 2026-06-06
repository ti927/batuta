"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";

// Cabeçalho do app (DESIGN-SYSTEM §3): logotipo "Batuta" à esquerda (leva à
// home), e-mail de quem está logado e o botão Sair à direita. O e-mail vem do
// servidor (layout); o signOut é client-side.
export function Cabecalho({ email }: { email: string }) {
  const router = useRouter();
  const [saindo, setSaindo] = useState(false);

  async function sair() {
    setSaindo(true);
    const supabase = criarClienteNavegador();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="Início da Batuta" className="rounded-md">
          <Logo />
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {email}
          </span>
          <Button size="sm" variant="outline" onClick={sair} disabled={saindo}>
            {saindo ? "Saindo…" : "Sair"}
          </Button>
        </div>
      </div>
    </header>
  );
}
