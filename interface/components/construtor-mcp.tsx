"use client";

// O CONSTRUTOR DE UM SERVIDOR MCP — instrumento PERSONALIZADO (decisão do maestro,
// 2026-09-29): servidor MCP se cria em "Criar instrumento", como o conector, e não na
// lista de tipos prontos. Por dentro é o mesmo formulário (identificação, lista de
// ferramentas, quem pode usar), com o tipo fixo e a moldura do Construtor.

import { ArrowLeft, Check, ChevronRight } from "lucide-react";

import { type Instrumento, type TipoInstrumento, type Time } from "@/lib/api";
import { FormularioInstrumento } from "@/components/formulario-instrumento";
import { UsadoPor } from "@/components/uso-instrumento";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";

export function ConstrutorMCP({
  time,
  instrumento,
  tipos,
  souAdmin,
  onFechar,
  onSalvou,
}: {
  time: Time;
  instrumento: Instrumento | null;
  tipos: TipoInstrumento[];
  souAdmin: boolean;
  onFechar: () => void;
  onSalvou: (salvo: Instrumento) => void;
}) {
  const tipoMcp = tipos.find((t) => t.tipo === "conectar_mcp");
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
        <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Voltar">
          <ArrowLeft className="size-4" />
        </Button>
        <div className="hidden items-center gap-1.5 text-sm text-muted-foreground sm:flex">
          <span>Instrumentos</span>
          <ChevronRight className="size-3.5" />
          <span className="text-foreground">Construtor</span>
        </div>
        <span className="ml-1 min-w-0 truncate font-medium text-foreground">
          {instrumento?.nome || "Novo servidor MCP"}
        </span>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          {instrumento ? (
            <>
              <Check className="size-3.5 text-success" /> salvo
            </>
          ) : (
            "rascunho"
          )}
        </span>
      </header>
      <main className="min-w-0 flex-1 overflow-y-auto px-5 py-6 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-1 text-lg font-semibold text-foreground">Servidor MCP</h1>
          <p className="mb-5 text-sm text-muted-foreground">
            Conecta os agentes a um serviço que publica ferramentas prontas (Zernio, Zapier,
            WordPress…). Salve com o endereço e a identificação, depois escolha quais
            ferramentas entram no cinto.
          </p>
          {tipoMcp ? (
            <FormularioInstrumento
              time={time}
              instrumento={instrumento}
              tipos={tipos}
              tipoFixo="conectar_mcp"
              souAdmin={souAdmin}
              onSalvo={onSalvou}
              onCancelar={onFechar}
            />
          ) : (
            <Aviso>Não consegui carregar este tipo de instrumento. Recarregue a página.</Aviso>
          )}
          {instrumento && <UsadoPor instrumentoId={instrumento.id} />}
        </div>
      </main>
    </div>
  );
}
