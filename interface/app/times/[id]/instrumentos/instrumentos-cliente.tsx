"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { Button } from "@/components/ui/button";

// Tenta interpretar um texto como objeto JSON. Devolve [valor, null] ou
// [null, mensagemDeErro]. Vazio vira objeto vazio.
function lerJson(texto: string): [Record<string, unknown> | null, string | null] {
  const t = texto.trim();
  if (!t) return [{}, null];
  try {
    const v = JSON.parse(t);
    if (typeof v !== "object" || v === null || Array.isArray(v))
      return [null, "A configuração precisa ser um objeto JSON { ... }"];
    return [v as Record<string, unknown>, null];
  } catch {
    return [null, "JSON inválido."];
  }
}

// Nomes dos campos esperados na configuração, lidos do JSON Schema do tipo.
function camposDoEsquema(tipo: TipoInstrumento | undefined): string[] {
  if (!tipo) return [];
  const props = tipo.esquema_config?.properties as
    | Record<string, unknown>
    | undefined;
  return props ? Object.keys(props) : [];
}

export function InstrumentosCliente({
  time,
  inicial,
  tipos,
  meuPapel,
}: {
  time: Time;
  inicial: Instrumento[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);

  const [modo, setModo] = useState<null | "novo" | string>(null);
  const [nome, setNome] = useState("");
  const [tipoSel, setTipoSel] = useState(tipos[0]?.tipo ?? "");
  const [configTexto, setConfigTexto] = useState("{}");

  // Estado do "Testar": instrumento sendo testado, argumentos e resultado.
  const [testandoId, setTestandoId] = useState<string | null>(null);
  const [argsTexto, setArgsTexto] = useState("{}");
  const [resultado, setResultado] = useState<string | null>(null);

  const tipoAtual = tipos.find((t) => t.tipo === tipoSel);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function abrirNovo() {
    setNome("");
    setTipoSel(tipos[0]?.tipo ?? "");
    setConfigTexto("{}");
    setErro(null);
    setModo("novo");
  }

  function abrirEdicao(inst: Instrumento) {
    setNome(inst.nome);
    setTipoSel(inst.tipo);
    setConfigTexto(JSON.stringify(inst.configuracao ?? {}, null, 2));
    setErro(null);
    setModo(inst.id);
  }

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    const [config, erroJson] = lerJson(configTexto);
    if (erroJson) {
      setErro(erroJson);
      return;
    }
    try {
      if (modo === "novo") {
        await api.post<Instrumento>(`/times/${time.id}/instrumentos`, {
          nome: nome.trim(),
          tipo: tipoSel,
          configuracao: config,
        });
      } else if (modo) {
        await api.put<Instrumento>(`/instrumentos/${modo}`, {
          nome: nome.trim(),
          configuracao: config,
        });
      }
      setErro(null);
      setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar instrumento");
    }
  }

  async function remover(inst: Instrumento) {
    if (!confirm(`Remover o instrumento "${inst.nome}"?`)) return;
    try {
      await api.delete(`/instrumentos/${inst.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover instrumento");
    }
  }

  function abrirTeste(inst: Instrumento) {
    setTestandoId(inst.id);
    setArgsTexto("{}");
    setResultado(null);
    setErro(null);
  }

  async function acionar(inst: Instrumento) {
    const [args, erroJson] = lerJson(argsTexto);
    if (erroJson) {
      setErro(erroJson);
      return;
    }
    try {
      const r = await api.post<unknown>(`/instrumentos/${inst.id}/acionar`, {
        argumentos: args,
      });
      setResultado(JSON.stringify(r, null, 2));
      setErro(null);
    } catch (e) {
      tratar(e, "Falha ao acionar instrumento");
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
      <p className="mb-6 text-sm text-zinc-500">Instrumentos do time</p>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {modo === null && souOperador && (
        <Button className="mb-6" onClick={abrirNovo} disabled={tipos.length === 0}>
          + Novo instrumento
        </Button>
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-3 rounded border border-zinc-300 bg-zinc-50 p-4">
          <h2 className="font-semibold">
            {modo === "novo" ? "Novo instrumento" : "Editar instrumento"}
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
            Tipo
            <select
              className="rounded border border-zinc-300 px-2 py-1 text-sm disabled:opacity-60"
              value={tipoSel}
              onChange={(e) => setTipoSel(e.target.value)}
              disabled={modo !== "novo"}
            >
              {tipos.map((t) => (
                <option key={t.tipo} value={t.tipo}>
                  {t.nome_exibicao}
                </option>
              ))}
            </select>
          </label>
          {tipoAtual && (
            <p className="text-xs text-zinc-500">
              {tipoAtual.descricao}
              {camposDoEsquema(tipoAtual).length > 0 && (
                <>
                  {" "}
                  Campos da configuração:{" "}
                  <span className="font-mono">
                    {camposDoEsquema(tipoAtual).join(", ")}
                  </span>
                  .
                </>
              )}
            </p>
          )}
          <label className="flex flex-col gap-1 text-xs text-zinc-600">
            Configuração (JSON)
            <textarea
              className="min-h-32 rounded border border-zinc-300 px-2 py-1 font-mono text-sm"
              value={configTexto}
              onChange={(e) => setConfigTexto(e.target.value)}
            />
          </label>
          <div className="flex gap-2">
            <Button onClick={salvar}>Salvar</Button>
            <Button variant="ghost" onClick={() => setModo(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {inicial.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhum instrumento ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {inicial.map((inst) => (
            <li key={inst.id} className="flex flex-col gap-2 p-3">
              <div className="flex items-center gap-2">
                <span className="flex-1 text-sm">
                  {inst.nome}
                  <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-600">
                    {inst.tipo}
                  </span>
                </span>
                {souOperador && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => abrirTeste(inst)}
                  >
                    Testar
                  </Button>
                )}
                {souOperador && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => abrirEdicao(inst)}
                  >
                    Editar
                  </Button>
                )}
                {souAdmin && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => remover(inst)}
                  >
                    Remover
                  </Button>
                )}
              </div>

              {testandoId === inst.id && (
                <div className="flex flex-col gap-2 rounded border border-zinc-200 bg-white p-3">
                  <label className="flex flex-col gap-1 text-xs text-zinc-600">
                    Argumentos (JSON)
                    <textarea
                      className="min-h-20 rounded border border-zinc-300 px-2 py-1 font-mono text-sm"
                      value={argsTexto}
                      onChange={(e) => setArgsTexto(e.target.value)}
                    />
                  </label>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => acionar(inst)}>
                      Acionar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setTestandoId(null)}
                    >
                      Fechar
                    </Button>
                  </div>
                  {resultado && (
                    <pre className="max-h-72 overflow-auto rounded bg-zinc-900 p-3 text-xs text-zinc-100">
                      {resultado}
                    </pre>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
