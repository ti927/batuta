"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi } from "@/lib/api";
import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";
import { Button } from "@/components/ui/button";

// O convidado já está logado (via link do e-mail). Aqui ele define a senha
// (o convite nasce sem senha — ela é necessária para logar de novo depois) e
// aceita: o cérebro cria o Usuario/Membro a partir dos convites pendentes.
export function ConviteCliente({ email }: { email: string }) {
  const router = useRouter();
  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function finalizar() {
    if (senha.length < 6) {
      setErro("A senha precisa de ao menos 6 caracteres.");
      return;
    }
    if (senha !== confirma) {
      setErro("As senhas não conferem.");
      return;
    }
    setEnviando(true);
    setErro(null);

    // 1) Define a senha na conta do Supabase.
    const supabase = criarClienteNavegador();
    const { error } = await supabase.auth.updateUser({ password: senha });
    if (error) {
      setErro(error.message);
      setEnviando(false);
      return;
    }

    // 2) Aceita o convite no cérebro (lê o e-mail do próprio token).
    try {
      await api.post("/convites/aceitar", {});
    } catch (e) {
      setErro(
        e instanceof ErroDaApi ? e.message : "Falha ao aceitar o convite.",
      );
      setEnviando(false);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Bem-vindo ao Batuta</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Defina uma senha para concluir seu acesso.
        </p>
        <p className="mt-1 text-xs text-zinc-400">{email}</p>
      </div>

      <div className="w-full max-w-sm">
        {erro && (
          <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
            {erro}
          </p>
        )}
        <div className="flex flex-col gap-3">
          <input
            type="password"
            className="rounded border border-zinc-300 px-3 py-2 text-sm"
            placeholder="Nova senha"
            value={senha}
            autoComplete="new-password"
            onChange={(e) => setSenha(e.target.value)}
          />
          <input
            type="password"
            className="rounded border border-zinc-300 px-3 py-2 text-sm"
            placeholder="Confirme a senha"
            value={confirma}
            autoComplete="new-password"
            onChange={(e) => setConfirma(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && finalizar()}
          />
          <Button onClick={finalizar} disabled={enviando}>
            {enviando ? "Concluindo…" : "Concluir acesso"}
          </Button>
        </div>
      </div>
    </main>
  );
}
