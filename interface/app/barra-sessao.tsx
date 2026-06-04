"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";
import { Button } from "@/components/ui/button";

// Barra fina no topo: mostra quem está logado e o botão Sair.
// O email vem do servidor (layout); o signOut é client-side.
export function BarraSessao({ email }: { email: string }) {
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
    <div className="flex items-center justify-end gap-3 border-b border-zinc-200 bg-zinc-50 px-4 py-2 text-sm">
      <span className="text-zinc-500">{email}</span>
      <Button size="sm" variant="outline" onClick={sair} disabled={saindo}>
        {saindo ? "Saindo…" : "Sair"}
      </Button>
    </div>
  );
}
