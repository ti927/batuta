"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, Plus, Wrench } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { FormularioInstrumento } from "@/components/formulario-instrumento";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

// Tenta interpretar um texto como objeto JSON. Devolve [valor, null] ou
// [null, mensagemDeErro]. Vazio vira objeto vazio.
function lerJson(texto: string): [Record<string, unknown> | null, string | null] {
  const t = texto.trim();
  if (!t) return [{}, null];
  try {
    const v = JSON.parse(t);
    if (typeof v !== "object" || v === null || Array.isArray(v))
      return [null, "Os argumentos precisam ser um objeto JSON { ... }"];
    return [v as Record<string, unknown>, null];
  } catch {
    return [null, "JSON inválido."];
  }
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

  // modo: null = nenhum form aberto; "novo" = criando; instrumento = editando
  const [modo, setModo] = useState<null | "novo" | Instrumento>(null);

  // Estado do "Testar": instrumento sendo testado, argumentos e resultado.
  const [testandoId, setTestandoId] = useState<string | null>(null);
  const [argsTexto, setArgsTexto] = useState("{}");
  const [resultado, setResultado] = useState<string | null>(null);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function aoSalvar() {
    setModo(null);
    setErro(null);
    router.refresh();
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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/times/${time.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar ao time
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">{time.nome}</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        Instrumentos do time
      </p>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {modo === null && souOperador && (
        <Button
          className="mb-6"
          onClick={() => setModo("novo")}
          disabled={tipos.length === 0}
        >
          <Plus />
          Novo instrumento
        </Button>
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium text-foreground">
            {modo === "novo" ? "Novo instrumento" : "Editar instrumento"}
          </h2>
          <FormularioInstrumento
            time={time}
            instrumento={modo === "novo" ? null : modo}
            tipos={tipos}
            onSalvo={aoSalvar}
            onCancelar={() => setModo(null)}
          />
        </div>
      )}

      {inicial.length === 0 ? (
        <EstadoVazio icone={Wrench} titulo="Nenhum instrumento ainda.">
          {souOperador
            ? "Crie o primeiro instrumento para este time."
            : "Os instrumentos deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((inst) => (
            <li key={inst.id} className="flex flex-col gap-2 p-3">
              <div className="flex items-center gap-2">
                <span className="flex flex-1 flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                  {inst.nome}
                  <span className="rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-xs font-normal text-muted-foreground">
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
                    onClick={() => setModo(inst)}
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
                <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
                  <Label className="flex-col items-start gap-1">
                    Argumentos (JSON)
                    <Textarea
                      className="min-h-20 font-mono"
                      value={argsTexto}
                      onChange={(e) => setArgsTexto(e.target.value)}
                    />
                  </Label>
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
                    <pre className="max-h-72 overflow-auto rounded-md bg-foreground p-3 text-xs text-background">
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
