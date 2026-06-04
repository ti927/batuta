"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Papel,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { Button, buttonVariants } from "@/components/ui/button";

// Modelos de IA conhecidos (Etapa 1). Lista crua; refina-se depois.
const MODELOS = ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"];

type Formulario = {
  nome: string;
  papel: Papel;
  modelo_ia: string;
  agent_md: string;
  skill_md: string;
  tools_md: string;
  soul_md: string;
};

const FORM_VAZIO: Formulario = {
  nome: "",
  papel: "agente",
  modelo_ia: "",
  agent_md: "",
  skill_md: "",
  tools_md: "",
  soul_md: "",
};

function deAgente(a: Agente): Formulario {
  return {
    nome: a.nome,
    papel: a.papel,
    modelo_ia: a.modelo_ia ?? "",
    agent_md: a.agent_md ?? "",
    skill_md: a.skill_md ?? "",
    tools_md: a.tools_md ?? "",
    soul_md: a.soul_md ?? "",
  };
}

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

  // modo: null = nenhum form aberto; "novo" = criando; id = editando aquele agente
  const [modo, setModo] = useState<null | "novo" | string>(null);
  const [form, setForm] = useState<Formulario>(FORM_VAZIO);

  function abrirNovo() {
    setForm(FORM_VAZIO);
    setModo("novo");
  }

  function abrirEdicao(a: Agente) {
    setForm(deAgente(a));
    setModo(a.id);
  }

  function fechar() {
    setModo(null);
    setErro(null);
  }

  function campo<K extends keyof Formulario>(chave: K, valor: Formulario[K]) {
    setForm((f) => ({ ...f, [chave]: valor }));
  }

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function corpo() {
    return {
      nome: form.nome.trim(),
      papel: form.papel,
      modelo_ia: form.modelo_ia || null,
      agent_md: form.agent_md || null,
      skill_md: form.skill_md || null,
      tools_md: form.tools_md || null,
      soul_md: form.soul_md || null,
    };
  }

  async function salvar() {
    if (!form.nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    try {
      if (modo === "novo") {
        await api.post<Agente>(`/times/${time.id}/agentes`, corpo());
      } else if (modo) {
        await api.put<Agente>(`/agentes/${modo}`, corpo());
      }
      setErro(null);
      setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar agente");
    }
  }

  async function remover(a: Agente) {
    if (!confirm(`Remover o agente "${a.nome}"?`)) return;
    try {
      await api.delete(`/agentes/${a.id}`);
      setErro(null);
      if (modo === a.id) setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover agente");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <Link
        href={`/organizacoes/${time.organizacao_id}`}
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Voltar à organização
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">{time.nome}</h1>
      <div className="mb-6 flex items-center gap-3">
        <p className="text-sm text-zinc-500">Agentes do time</p>
        <Link
          href={`/times/${time.id}/instrumentos`}
          className="text-sm text-blue-600 underline underline-offset-4"
        >
          Instrumentos do time →
        </Link>
        <Link
          href={`/times/${time.id}/automacoes`}
          className="text-sm text-blue-600 underline underline-offset-4"
        >
          Automações do time →
        </Link>
      </div>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {modo === null && souOperador && (
        <Button className="mb-6" onClick={abrirNovo}>
          + Novo agente
        </Button>
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-3 rounded border border-zinc-300 bg-zinc-50 p-4">
          <h2 className="font-semibold">
            {modo === "novo" ? "Novo agente" : "Editar agente"}
          </h2>

          <div className="flex flex-wrap gap-3">
            <label className="flex flex-1 flex-col gap-1 text-xs text-zinc-600">
              Nome
              <input
                className="rounded border border-zinc-300 px-2 py-1 text-sm"
                value={form.nome}
                onChange={(e) => campo("nome", e.target.value)}
                autoFocus
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-zinc-600">
              Papel
              <select
                className="rounded border border-zinc-300 px-2 py-1 text-sm"
                value={form.papel}
                onChange={(e) => campo("papel", e.target.value as Papel)}
              >
                <option value="agente">Agente</option>
                <option value="lider">Líder</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-zinc-600">
              Modelo de IA
              <select
                className="rounded border border-zinc-300 px-2 py-1 text-sm"
                value={form.modelo_ia}
                onChange={(e) => campo("modelo_ia", e.target.value)}
              >
                <option value="">(não definido)</option>
                {MODELOS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {(
            [
              ["agent_md", "agent.md — quem o agente é, o que faz"],
              ["skill_md", "skill.md — as habilidades dele"],
              ["tools_md", "tools.md — os instrumentos do cinto"],
              ["soul_md", "soul.md — personalidade, tom, jeito de falar"],
            ] as const
          ).map(([chave, rotulo]) => (
            <label
              key={chave}
              className="flex flex-col gap-1 text-xs text-zinc-600"
            >
              {rotulo}
              <textarea
                className="min-h-24 rounded border border-zinc-300 px-2 py-1 font-mono text-sm"
                value={form[chave]}
                onChange={(e) => campo(chave, e.target.value)}
              />
            </label>
          ))}

          <div className="flex gap-2">
            <Button onClick={salvar}>Salvar</Button>
            <Button variant="ghost" onClick={fechar}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {inicial.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhum agente ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {inicial.map((a) => (
            <li key={a.id} className="flex items-center gap-2 p-3">
              <span className="flex-1 text-sm">
                {a.nome}
                <span
                  className={`ml-2 rounded px-1.5 py-0.5 text-xs ${
                    a.papel === "lider"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-zinc-100 text-zinc-600"
                  }`}
                >
                  {a.papel === "lider" ? "Líder" : "Agente"}
                </span>
                {a.modelo_ia && (
                  <span className="ml-2 text-xs text-zinc-400">{a.modelo_ia}</span>
                )}
              </span>
              <Link
                href={`/agentes/${a.id}`}
                className={buttonVariants({ size: "sm", variant: "outline" })}
              >
                Cinto
              </Link>
              {souOperador && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => abrirEdicao(a)}
                >
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
