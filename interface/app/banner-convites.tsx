"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi, type ConvitePendente } from "@/lib/api";
import { Button } from "@/components/ui/button";

// Aviso de convite dentro do Batuta: quem já tem conta e foi (re)convidado não
// recebe e-mail (o Supabase não reenvia). Ao entrar, vê este banner e aceita
// aqui mesmo. Reusa POST /convites/aceitar, que aceita todos os pendentes do
// e-mail de uma vez. Sem useEffect+fetch — o fetch é no Server Component (home).
export function BannerConvites({ convites }: { convites: ConvitePendente[] }) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function aceitar() {
    setEnviando(true);
    setErro(null);
    try {
      await api.post("/convites/aceitar", {});
      // A home re-renderiza (Server Component) e a lista de pendentes esvazia.
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao aceitar o convite.");
      setEnviando(false);
    }
  }

  return (
    <section className="mb-6 w-full max-w-md rounded-lg border border-accent-foreground/20 bg-accent p-4 text-sm text-accent-foreground">
      <p className="mb-2 font-medium">
        Você {convites.length > 1 ? "tem convites pendentes" : "tem um convite pendente"}:
      </p>
      <ul className="mb-3 list-disc pl-5">
        {convites.map((c) => (
          <li key={c.id}>
            {c.organizacao_nome} — {c.papel}
          </li>
        ))}
      </ul>
      {erro && <p className="mb-2 text-destructive">{erro}</p>}
      <Button onClick={aceitar} disabled={enviando}>
        {enviando ? "Aceitando…" : "Aceitar"}
      </Button>
    </section>
  );
}
