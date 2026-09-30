"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Pencil, Plus, ShieldCheck, Wrench } from "lucide-react";

import {
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { ConstrutorInstrumento } from "@/components/construtor-instrumento";
import { ConstrutorMCP } from "@/components/construtor-mcp";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { Button } from "@/components/ui/button";
import { Aviso } from "@/components/ui/aviso";
import { EstadoVazio } from "@/components/ui/estado-vazio";

export function InstrumentosCliente({
  time,
  inicial,
  tipos,
  usadoPor,
  meuPapel,
}: {
  time: Time;
  inicial: Instrumento[];
  tipos: TipoInstrumento[];
  usadoPor: Record<string, string[]>;
  meuPapel: PapelAcesso | null;
}) {
  const souOperador = podeOperar(meuPapel);
  // null = fechado; "novo" = criando; instrumento = editando.
  // Volta do login de um instrumento MCP quando o pop-up foi bloqueado e o login
  // aconteceu na página inteira: avisa e já reabre o instrumento.
  const busca = useSearchParams();
  const voltaLogin = busca.get("mcp_oauth");
  const [aberto, setAberto] = useState<null | "novo" | Instrumento>(() => {
    const id = busca.get("instrumento");
    return (voltaLogin && id && inicial.find((i) => i.id === id)) || null;
  });
  // Construtor de Instrumento (conector): overlay de tela cheia, separado do
  // formulário genérico. "novo" = criar; instrumento = editar um conector.
  const [construtor, setConstrutor] = useState<null | "novo" | Instrumento>(null);
  // Servidor MCP: instrumento personalizado, com o seu próprio Construtor.
  const [construtorMcp, setConstrutorMcp] = useState<null | "novo" | Instrumento>(null);
  // "Criar instrumento": primeiro a pessoa diz o que quer conectar.
  const [escolhendo, setEscolhendo] = useState(false);

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      {voltaLogin === "ok" && (
        <Aviso variant="sucesso" className="mb-4">
          Conta conectada.
        </Aviso>
      )}
      {voltaLogin === "erro" && (
        <Aviso className="mb-4">
          O login não foi concluído. Abra o instrumento e clique em “Conectar” de novo.
        </Aviso>
      )}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-foreground">
            Instrumentos do time
          </h2>
          <p className="text-sm text-muted-foreground">
            As ferramentas que os agentes podem usar.
          </p>
        </div>
        {souOperador && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setEscolhendo(true)}>
              🌟 Criar instrumento
            </Button>
            <Button
              variant="outline"
              onClick={() => setAberto("novo")}
              disabled={tipos.length === 0}
            >
              <Plus className="size-4" /> Instrumento pronto
            </Button>
          </div>
        )}
      </div>

      {inicial.length === 0 ? (
        <EstadoVazio icone={Wrench} titulo="Nenhum instrumento ainda.">
          {souOperador
            ? "Crie instrumentos para os agentes usarem (APIs, banco, web…)."
            : "Os instrumentos deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {inicial.map((inst, i) => {
            const usos = usadoPor[inst.id] ?? [];
            return (
              <button
                key={inst.id}
                onClick={() =>
                  souOperador &&
                  (inst.tipo === "conector"
                    ? setConstrutor(inst)
                    : inst.tipo === "conectar_mcp"
                      ? setConstrutorMcp(inst)
                      : setAberto(inst))
                }
                disabled={!souOperador}
                className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
                  souOperador ? "hover:bg-accent/50" : "cursor-default"
                } ${i > 0 ? "border-t border-border" : ""}`}
              >
                <span className="flex size-8 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <IconeInstrumento icone={inst.icone} className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-foreground">
                      {inst.nome}
                    </span>
                    {inst.escopo === "organizacao" && (
                      <span className="rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground">
                        da organização
                      </span>
                    )}
                    {inst.acao_irreversivel && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[#FDF1E3] px-2 py-0.5 text-xs text-[#A05E16]">
                        <ShieldCheck className="size-3" /> altera algo
                      </span>
                    )}
                  </span>
                  <span className="block truncate font-mono text-xs text-muted-foreground">
                    {inst.tipo}
                    {usos.length > 0 && (
                      <span className="font-sans"> · usado por {usos.join(", ")}</span>
                    )}
                  </span>
                </span>
                {souOperador && (
                  <Pencil className="size-4 shrink-0 text-muted-foreground/60" />
                )}
              </button>
            );
          })}
        </div>
      )}

      {aberto && (
        <DrawerInstrumento
          key={aberto === "novo" ? "novo" : aberto.id}
          instrumento={aberto === "novo" ? null : aberto}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
          onFechar={() => setAberto(null)}
          onSalvou={(salvo) => setAberto(salvo)}
        />
      )}

      {escolhendo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-foreground/20"
            onClick={() => setEscolhendo(false)}
            aria-label="Fechar"
          />
          <div className="relative w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl">
            <h3 className="mb-3 font-medium text-foreground">O que você quer conectar?</h3>
            <div className="flex flex-col gap-2">
              <button
                className="rounded-md border border-border p-3 text-left hover:border-primary hover:bg-accent/40"
                onClick={() => {
                  setEscolhendo(false);
                  setConstrutor("novo");
                }}
              >
                <span className="block text-sm font-medium text-foreground">Uma API</span>
                <span className="text-xs text-muted-foreground">
                  Você descreve as operações (endereço, campos) a partir da documentação.
                </span>
              </button>
              <button
                className="rounded-md border border-border p-3 text-left hover:border-primary hover:bg-accent/40"
                onClick={() => {
                  setEscolhendo(false);
                  setConstrutorMcp("novo");
                }}
              >
                <span className="block text-sm font-medium text-foreground">Um servidor MCP</span>
                <span className="text-xs text-muted-foreground">
                  O serviço já publica as ferramentas (Zernio, Zapier, WordPress…); você escolhe
                  quais entram no cinto.
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {construtorMcp && (
        <ConstrutorMCP
          key={construtorMcp === "novo" ? "novo" : construtorMcp.id}
          time={time}
          instrumento={construtorMcp === "novo" ? null : construtorMcp}
          tipos={tipos}
          souAdmin={podeAdmin(meuPapel)}
          onFechar={() => setConstrutorMcp(null)}
          onSalvou={(salvo) => setConstrutorMcp(salvo)}
        />
      )}

      {construtor && (
        <ConstrutorInstrumento
          key={construtor === "novo" ? "novo" : construtor.id}
          time={time}
          instrumento={construtor === "novo" ? null : construtor}
          onFechar={() => setConstrutor(null)}
          onSalvou={(salvo) => setConstrutor(salvo)}
        />
      )}
    </main>
  );
}
