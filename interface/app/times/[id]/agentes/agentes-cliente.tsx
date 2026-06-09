"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Bot, ChevronLeft, Plus, Settings2, Zap } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { FormularioAgente } from "@/components/formulario-agente";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

export function AgentesCliente({
  time,
  inicial,
  meuPapel,
}: {
  time: Time;
  inicial: Agente[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);

  // modo: null = nenhum form aberto; "novo" = criando; agente = editando aquele
  const [modo, setModo] = useState<null | "novo" | Agente>(null);

  function fechar() {
    setModo(null);
    setErro(null);
  }

  function aoSalvar() {
    setModo(null);
    setErro(null);
    router.refresh();
  }

  async function remover(a: Agente) {
    if (!confirm(`Remover o agente "${a.nome}"?`)) return;
    try {
      await api.delete(`/agentes/${a.id}`);
      setErro(null);
      if (modo !== null && modo !== "novo" && modo.id === a.id) setModo(null);
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao remover agente");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/times/${time.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar ao time
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">{time.nome}</h1>
      <div className="mb-6 mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
        <p className="text-sm text-muted-foreground">Gerenciar agentes</p>
        <Link
          href={`/times/${time.id}/instrumentos`}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <Settings2 className="size-3.5" />
          Instrumentos do time
        </Link>
        <Link
          href={`/times/${time.id}/automacoes`}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <Zap className="size-3.5" />
          Automações do time
        </Link>
      </div>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {modo === null && souOperador && (
        <Button className="mb-6" onClick={() => setModo("novo")}>
          <Plus />
          Novo agente
        </Button>
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium text-foreground">
            {modo === "novo" ? "Novo agente" : "Editar agente"}
          </h2>
          <FormularioAgente
            time={time}
            agente={modo === "novo" ? null : modo}
            onSalvo={aoSalvar}
            onCancelar={fechar}
          />
        </div>
      )}

      {inicial.length === 0 ? (
        <EstadoVazio icone={Bot} titulo="Nenhum agente ainda.">
          {souOperador
            ? "Crie o primeiro agente para montar este time."
            : "Os agentes deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((a) => (
            <li key={a.id} className="flex items-center gap-2 p-3">
              <span className="flex flex-1 flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                {a.nome}
                <Badge variant={a.papel === "lider" ? "info" : "neutral"}>
                  {a.papel === "lider" ? "Líder" : "Agente"}
                </Badge>
                {a.modelo_ia && (
                  <span className="font-normal text-xs text-muted-foreground">
                    {a.modelo_ia}
                  </span>
                )}
              </span>
              <Link
                href={`/agentes/${a.id}`}
                className={buttonVariants({ size: "sm", variant: "outline" })}
              >
                Cinto
              </Link>
              {souOperador && (
                <Button size="sm" variant="outline" onClick={() => setModo(a)}>
                  Editar
                </Button>
              )}
              {souAdmin && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => remover(a)}
                >
                  Remover
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
