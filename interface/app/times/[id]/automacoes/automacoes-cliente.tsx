"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Automacao,
  type Cadeia,
  type SaidaCadeia,
  type Time,
} from "@/lib/api";
import { Button } from "@/components/ui/button";

type SaidasPorAgente = Record<string, SaidaCadeia[]>;

function cadeiaParaForm(
  cadeia: Cadeia | null,
  agentes: Agente[],
): { inicio: string; saidas: SaidasPorAgente } {
  const saidas: SaidasPorAgente = {};
  for (const a of agentes) saidas[a.id] = cadeia?.nos?.[a.id]?.saidas ?? [];
  return { inicio: cadeia?.inicio ?? agentes[0]?.id ?? "", saidas };
}

function formParaCadeia(inicio: string, saidas: SaidasPorAgente): Cadeia {
  const nos: Cadeia["nos"] = {};
  for (const [id, lista] of Object.entries(saidas)) nos![id] = { saidas: lista };
  return { inicio, nos };
}

export function AutomacoesCliente({
  time,
  inicial,
  agentes,
}: {
  time: Time;
  inicial: Automacao[];
  agentes: Agente[];
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);

  const [modo, setModo] = useState<null | "novo" | string>(null);
  const [nome, setNome] = useState("");
  const [inicio, setInicio] = useState(agentes[0]?.id ?? "");
  const [saidas, setSaidas] = useState<SaidasPorAgente>({});

  const nomeAgente = (id: string | null) =>
    id === null ? "— fim (entrega ao usuário) —" : agentes.find((a) => a.id === id)?.nome ?? id;

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function abrirNovo() {
    const f = cadeiaParaForm(null, agentes);
    setNome("");
    setInicio(f.inicio);
    setSaidas(f.saidas);
    setErro(null);
    setModo("novo");
  }

  function abrirEdicao(a: Automacao) {
    const f = cadeiaParaForm(a.cadeia, agentes);
    setNome(a.nome);
    setInicio(f.inicio);
    setSaidas(f.saidas);
    setErro(null);
    setModo(a.id);
  }

  function addSaida(agenteId: string) {
    setSaidas((s) => ({
      ...s,
      [agenteId]: [...(s[agenteId] ?? []), { rotulo: "", quando: "", destino: null }],
    }));
  }

  function mudarSaida(agenteId: string, i: number, campo: keyof SaidaCadeia, valor: string | null) {
    setSaidas((s) => {
      const lista = [...(s[agenteId] ?? [])];
      lista[i] = { ...lista[i], [campo]: valor };
      return { ...s, [agenteId]: lista };
    });
  }

  function removerSaida(agenteId: string, i: number) {
    setSaidas((s) => {
      const lista = [...(s[agenteId] ?? [])];
      lista.splice(i, 1);
      return { ...s, [agenteId]: lista };
    });
  }

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    if (!inicio) {
      setErro("Escolha o agente inicial.");
      return;
    }
    const corpo = { nome: nome.trim(), cadeia: formParaCadeia(inicio, saidas) };
    try {
      if (modo === "novo") {
        await api.post<Automacao>(`/times/${time.id}/automacoes`, corpo);
      } else if (modo) {
        await api.put<Automacao>(`/automacoes/${modo}`, corpo);
      }
      setErro(null);
      setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar automação");
    }
  }

  async function remover(a: Automacao) {
    if (!confirm(`Remover a automação "${a.nome}"?`)) return;
    try {
      await api.delete(`/automacoes/${a.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover automação");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <Link
        href={`/times/${time.id}`}
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Voltar ao time
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">{time.nome}</h1>
      <p className="mb-6 text-sm text-zinc-500">Automações do time</p>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {agentes.length === 0 ? (
        <p className="text-sm text-zinc-500">
          Crie agentes no time antes de montar uma automação.
        </p>
      ) : (
        modo === null && (
          <Button className="mb-6" onClick={abrirNovo}>
            + Nova automação
          </Button>
        )
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-4 rounded border border-zinc-300 bg-zinc-50 p-4">
          <h2 className="font-semibold">
            {modo === "novo" ? "Nova automação" : "Editar automação"}
          </h2>
          <label className="flex flex-col gap-1 text-xs text-zinc-600">
            Nome
            <input
              className="rounded border border-zinc-300 px-2 py-1 text-sm"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              autoFocus
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-600">
            Agente inicial (por onde a tarefa entra)
            <select
              className="rounded border border-zinc-300 px-2 py-1 text-sm"
              value={inicio}
              onChange={(e) => setInicio(e.target.value)}
            >
              {agentes.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nome}
                </option>
              ))}
            </select>
          </label>

          <p className="text-xs text-zinc-500">
            Para cada agente, defina suas saídas: o rótulo, quando segui-la, e o
            destino (outro agente — pode ser anterior — ou o fim). Sem saídas = o
            agente encerra a cadeia.
          </p>

          <div className="flex flex-col gap-3">
            {agentes.map((a) => (
              <div key={a.id} className="rounded border border-zinc-200 bg-white p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {a.nome}
                    {a.id === inicio && (
                      <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                        inicial
                      </span>
                    )}
                  </span>
                  <Button size="xs" variant="outline" onClick={() => addSaida(a.id)}>
                    + saída
                  </Button>
                </div>
                {(saidas[a.id] ?? []).length === 0 ? (
                  <p className="text-xs text-zinc-400">Sem saídas (encerra aqui).</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {(saidas[a.id] ?? []).map((s, i) => (
                      <div key={i} className="flex flex-wrap items-center gap-2">
                        <input
                          className="w-20 rounded border border-zinc-300 px-2 py-1 text-xs"
                          placeholder="rótulo"
                          value={s.rotulo}
                          onChange={(e) => mudarSaida(a.id, i, "rotulo", e.target.value)}
                        />
                        <input
                          className="flex-1 rounded border border-zinc-300 px-2 py-1 text-xs"
                          placeholder="quando seguir por aqui"
                          value={s.quando}
                          onChange={(e) => mudarSaida(a.id, i, "quando", e.target.value)}
                        />
                        <select
                          className="rounded border border-zinc-300 px-2 py-1 text-xs"
                          value={s.destino ?? ""}
                          onChange={(e) =>
                            mudarSaida(a.id, i, "destino", e.target.value || null)
                          }
                        >
                          <option value="">→ fim</option>
                          {agentes.map((d) => (
                            <option key={d.id} value={d.id}>
                              → {d.nome}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => removerSaida(a.id, i)}
                        >
                          ✕
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button onClick={salvar}>Salvar</Button>
            <Button variant="ghost" onClick={() => setModo(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {inicial.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhuma automação ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {inicial.map((a) => (
            <li key={a.id} className="flex items-center gap-2 p-3">
              <Link
                href={`/automacoes/${a.id}`}
                className="flex-1 text-sm text-blue-600 underline underline-offset-4"
              >
                {a.nome}
                <span className="ml-2 text-xs text-zinc-400">
                  início: {nomeAgente(a.cadeia?.inicio ?? null)}
                </span>
              </Link>
              <Button size="sm" variant="outline" onClick={() => abrirEdicao(a)}>
                Editar
              </Button>
              <Button size="sm" variant="destructive" onClick={() => remover(a)}>
                Remover
              </Button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
