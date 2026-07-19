"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  mensagemDeErro,
} from "@/lib/api";
import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";
import { SimboloBatuta } from "@/components/logo";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
        mensagemDeErro(e, "Falha ao aceitar o convite."),
      );
      setEnviando(false);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-1 flex-col items-center justify-center gap-6 p-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <SimboloBatuta className="size-8" />
        <h1 className="text-xl font-medium text-foreground">
          Bem-vindo ao Batuta
        </h1>
        <p className="text-sm text-muted-foreground">
          Defina uma senha para concluir seu acesso.
        </p>
        <p className="text-xs text-muted-foreground/70">{email}</p>
      </div>

      <div className="w-full max-w-sm">
        {erro && <Aviso className="mb-4">{erro}</Aviso>}
        <div className="flex flex-col gap-3">
          <Input
            type="password"
            placeholder="Nova senha"
            value={senha}
            autoComplete="new-password"
            onChange={(e) => setSenha(e.target.value)}
          />
          <Input
            type="password"
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
