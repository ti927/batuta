"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, Wrench } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Instrumento,
  type PapelAcesso,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Select } from "@/components/ui/select";

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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/times/${agente.time_id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar ao time
      </Link>
      <h1 className="mt-2 flex flex-wrap items-center gap-2 text-2xl font-medium text-foreground">
        {agente.nome}
        <Badge variant={agente.papel === "lider" ? "info" : "neutral"}>
          {agente.papel === "lider" ? "Líder" : "Agente"}
        </Badge>
      </h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        Cinto de instrumentos
      </p>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {souOperador && (
        <>
          <div className="mb-2 flex gap-2">
            <Select
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
            </Select>
            <Button onClick={pendurar} disabled={!selecionado}>
              Pendurar no cinto
            </Button>
          </div>

          <p className="mb-6 text-xs text-muted-foreground">
            Para criar instrumentos, vá em{" "}
            <Link
              href={`/times/${agente.time_id}/instrumentos`}
              className="font-medium text-primary hover:underline"
            >
              Instrumentos do time
            </Link>
            .
          </p>
        </>
      )}

      {cinto.length === 0 ? (
        <EstadoVazio icone={Wrench} titulo="O cinto está vazio.">
          {souOperador
            ? "Pendure um instrumento do time acima."
            : "Os instrumentos deste agente aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {cinto.map((inst) => (
            <li key={inst.id} className="flex items-center gap-2 p-3">
              <span className="flex flex-1 flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                {inst.nome}
                <span className="rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-xs font-normal text-muted-foreground">
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
