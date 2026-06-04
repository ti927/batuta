"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Instrumento,
  type PapelAcesso,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { Button } from "@/components/ui/button";

export function CintoCliente({
  agente,
  cinto,
  instrumentosDoTime,
  meuPapel,
}: {
  agente: Agente;
  cinto: Instrumento[];
  instrumentosDoTime: Instrumento[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souOperador = podeOperar(meuPapel);

  // Instrumentos do time que ainda não estão no cinto.
  const noCinto = new Set(cinto.map((i) => i.id));
  const disponiveis = instrumentosDoTime.filter((i) => !noCinto.has(i.id));
  const [selecionado, setSelecionado] = useState("");

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function pendurar() {
    if (!selecionado) return;
    try {
      await api.post<Instrumento>(`/agentes/${agente.id}/instrumentos`, {
        instrumento_id: selecionado,
      });
      setSelecionado("");
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao pendurar instrumento");
    }
  }

  async function tirar(inst: Instrumento) {
    try {
      await api.delete(`/agentes/${agente.id}/instrumentos/${inst.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao tirar instrumento");
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-8">
      <Link
        href={`/times/${agente.time_id}`}
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Voltar ao time
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">
        {agente.nome}
        <span
          className={`ml-2 rounded px-1.5 py-0.5 align-middle text-xs ${
            agente.papel === "lider"
              ? "bg-amber-100 text-amber-800"
              : "bg-zinc-100 text-zinc-600"
          }`}
        >
          {agente.papel === "lider" ? "Líder" : "Agente"}
        </span>
      </h1>
      <p className="mb-6 text-sm text-zinc-500">Cinto de instrumentos</p>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {souOperador && (
        <>
          <div className="mb-6 flex gap-2">
            <select
              className="flex-1 rounded border border-zinc-300 px-2 py-1.5 text-sm"
              value={selecionado}
              onChange={(e) => setSelecionado(e.target.value)}
            >
              <option value="">
                {disponiveis.length === 0
                  ? "Nenhum instrumento disponível neste time"
                  : "Escolha um instrumento do time…"}
              </option>
              {disponiveis.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.nome} ({i.tipo})
                </option>
              ))}
            </select>
            <Button onClick={pendurar} disabled={!selecionado}>
              Pendurar no cinto
            </Button>
          </div>

          <p className="mb-2 text-xs text-zinc-500">
            Para criar instrumentos, vá em{" "}
            <Link
              href={`/times/${agente.time_id}/instrumentos`}
              className="text-blue-600 underline underline-offset-4"
            >
              Instrumentos do time
            </Link>
            .
          </p>
        </>
      )}

      {cinto.length === 0 ? (
        <p className="text-sm text-zinc-500">O cinto está vazio.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {cinto.map((inst) => (
            <li key={inst.id} className="flex items-center gap-2 p-3">
              <span className="flex-1 text-sm">
                {inst.nome}
                <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-600">
                  {inst.tipo}
                </span>
              </span>
              {souOperador && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => tirar(inst)}
                >
                  Tirar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
