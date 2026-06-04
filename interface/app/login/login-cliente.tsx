"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";
import { Button } from "@/components/ui/button";

export function LoginCliente() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [entrando, setEntrando] = useState(false);

  async function entrar() {
    if (!email.trim() || !senha) return;
    setEntrando(true);
    setErro(null);
    const supabase = criarClienteNavegador();
    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password: senha,
    });
    if (error) {
      setErro(
        error.message === "Invalid login credentials"
          ? "E-mail ou senha incorretos."
          : error.message,
      );
      setEntrando(false);
      return;
    }
    // Sessão gravada nos cookies; o proxy renova daqui em diante.
    router.push("/");
    router.refresh();
  }

  return (
    <div className="w-full max-w-sm">
      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}
      <div className="flex flex-col gap-3">
        <input
          type="email"
          className="rounded border border-zinc-300 px-3 py-2 text-sm"
          placeholder="E-mail"
          value={email}
          autoComplete="email"
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && entrar()}
        />
        <input
          type="password"
          className="rounded border border-zinc-300 px-3 py-2 text-sm"
          placeholder="Senha"
          value={senha}
          autoComplete="current-password"
          onChange={(e) => setSenha(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && entrar()}
        />
        <Button onClick={entrar} disabled={entrando}>
          {entrando ? "Entrando…" : "Entrar"}
        </Button>
      </div>
    </div>
  );
}
