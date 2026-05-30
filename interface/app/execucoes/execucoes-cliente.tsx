"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi, type ExecucaoNaLista } from "@/lib/api";
import { Button } from "@/components/ui/button";

const COR_ESTADO: Record<string, string> = {
  aguardando: "bg-zinc-100 text-zinc-600",
  em_andamento: "bg-amber-100 text-amber-800",
  aguardando_humano: "bg-blue-100 text-blue-800",
  concluida: "bg-green-100 text-green-800",
  falhou: "bg-red-100 text-red-800",
  cancelada: "bg-zinc-200 text-zinc-700",
};

// Estados já encerrados: podem ser apagados, mas não cancelados.
const ENCERRADOS = ["concluida", "falhou", "cancelada"];

const FILTROS: { valor: string; rotulo: string }[] = [
  { valor: "todos", rotulo: "Todas" },
  { valor: "aguardando", rotulo: "Na fila" },
  { valor: "em_andamento", rotulo: "Em andamento" },
  { valor: "aguardando_humano", rotulo: "Aguardando humano" },
  { valor: "concluida", rotulo: "Concluídas" },
  { valor: "falhou", rotulo: "Falhas" },
  { valor: "cancelada", rotulo: "Canceladas" },
];

export function ExecucoesCliente({ inicial }: { inicial: ExecucaoNaLista[] }) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [filtro, setFiltro] = useState("todos");
  const [ocupada, setOcupada] = useState<string | null>(null);

  const lista =
    filtro === "todos" ? inicial : inicial.filter((e) => e.estado === filtro);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function cancelar(id: string) {
    setOcupada(id);
    setErro(null);
    try {
      await api.post(`/execucoes/${id}/cancelar`, {});
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao cancelar");
    } finally {
      setOcupada(null);
    }
  }

  async function apagar(id: string) {
    if (!confirm("Apagar esta execução e seu histórico de passos?")) return;
    setOcupada(id);
    setErro(null);
    try {
      await api.delete(`/execucoes/${id}`);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao apagar");
    } finally {
      setOcupada(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-4xl p-8">
      <Link
        href="/"
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Início
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">Execuções</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Todas as execuções, de todas as automações. Cancele as que estão em curso
        ou paradas; apague as já encerradas.
      </p>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTROS.map((f) => {
          const n =
            f.valor === "todos"
              ? inicial.length
              : inicial.filter((e) => e.estado === f.valor).length;
          return (
            <button
              key={f.valor}
              onClick={() => setFiltro(f.valor)}
              className={`rounded border px-2 py-1 text-xs ${
                filtro === f.valor
                  ? "border-zinc-800 bg-zinc-800 text-white"
                  : "border-zinc-300 text-zinc-600 hover:bg-zinc-100"
              }`}
            >
              {f.rotulo} ({n})
            </button>
          );
        })}
      </div>

      {lista.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhuma execução neste filtro.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {lista.map((e) => {
            const encerrada = ENCERRADOS.includes(e.estado);
            return (
              <li key={e.id} className="flex items-center gap-3 p-3 text-sm">
                <span
                  className={`rounded px-1.5 py-0.5 text-xs ${
                    COR_ESTADO[e.estado] ?? "bg-zinc-100 text-zinc-600"
                  }`}
                >
                  {e.estado}
                </span>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/automacoes/${e.automacao_id}`}
                    className="text-blue-600 underline underline-offset-4"
                  >
                    {e.automacao_nome}
                  </Link>
                  <div className="truncate text-xs text-zinc-400">
                    {e.entrada?.texto ?? "—"}
                  </div>
                </div>
                {!encerrada && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={ocupada === e.id}
                    onClick={() => cancelar(e.id)}
                  >
                    Cancelar
                  </Button>
                )}
                {encerrada && (
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={ocupada === e.id}
                    onClick={() => apagar(e.id)}
                  >
                    Apagar
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
