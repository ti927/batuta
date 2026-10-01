"use client";

// O CONSTRUTOR DE UM SERVIDOR MCP OU DE UM BANCO DE DADOS — instrumentos PERSONALIZADOS
// (decisão do maestro, 2026-09-29; o banco entrou em 2026-10-01): nascem em "Criar
// instrumento", como o conector, e não na lista de tipos prontos. Por dentro é o mesmo
// formulário (identificação, campos, quem pode usar), com o tipo fixo e a moldura do
// Construtor.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, ChevronRight, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
  type Instrumento,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { FormularioInstrumento } from "@/components/formulario-instrumento";
import { UsadoPor } from "@/components/uso-instrumento";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";

// O que muda de um tipo para o outro: só os textos da moldura.
const TEXTOS: Record<TipoConstrutor, { novo: string; titulo: string; ajuda: string }> = {
  conectar_mcp: {
    novo: "Novo servidor MCP",
    titulo: "Servidor MCP",
    ajuda:
      "Conecta os agentes a um serviço que publica ferramentas prontas (Zernio, Zapier, " +
      "WordPress…). Salve com o endereço e a identificação, depois escolha quais " +
      "ferramentas entram no cinto.",
  },
  banco_sql: {
    novo: "Novo banco de dados",
    titulo: "Banco de dados",
    ajuda:
      "Os agentes consultam (e, se você permitir, alteram) um banco PostgreSQL. Marque " +
      "“Somente leitura” quando eles só precisam consultar.",
  },
};

export type TipoConstrutor = "conectar_mcp" | "banco_sql";

export function ConstrutorMCP({
  tipo = "conectar_mcp",
  time,
  instrumento,
  tipos,
  souAdmin,
  onFechar,
  onSalvou,
}: {
  tipo?: TipoConstrutor;
  time: Time;
  instrumento: Instrumento | null;
  tipos: TipoInstrumento[];
  souAdmin: boolean;
  onFechar: () => void;
  onSalvou: (salvo: Instrumento) => void;
}) {
  const tipoDef = tipos.find((t) => t.tipo === tipo);
  const textos = TEXTOS[tipo];
  const router = useRouter();
  // Abre sempre com o instrumento como está AGORA no Batuta. A cópia que chega de
  // uma lista pode ser de antes da chave ser colada — e aí o formulário acha que o
  // endereço e o token não existem e barra o salvar.
  const [atual, setAtual] = useState<Instrumento | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const instrumentoId = instrumento?.id ?? null;
  useEffect(() => {
    if (!instrumentoId) return;
    let vivo = true;
    api
      .get<Instrumento>(`/instrumentos/${instrumentoId}`)
      .then((i) => {
        if (vivo) setAtual(i);
      })
      .catch((e) => {
        if (vivo) setErroCarga(mensagemDeErro(e, "Não consegui abrir este instrumento"));
      });
    return () => {
      vivo = false;
    };
  }, [instrumentoId, tentativa]);

  function salvou(salvo: Instrumento) {
    toast.success(instrumento ? "Instrumento salvo" : "Instrumento criado");
    setAtual(salvo);
    router.refresh();
    onSalvou(salvo);
  }

  const carregando = instrumentoId !== null && atual?.id !== instrumentoId;
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
          {instrumento?.nome || textos.novo}
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
          <h1 className="mb-1 text-lg font-semibold text-foreground">{textos.titulo}</h1>
          <p className="mb-5 text-sm text-muted-foreground">{textos.ajuda}</p>
          {!tipoDef ? (
            <Aviso>Não consegui carregar este tipo de instrumento. Recarregue a página.</Aviso>
          ) : erroCarga && carregando ? (
            <Aviso>
              {erroCarga}{" "}
              <button
                type="button"
                className="underline"
                onClick={() => {
                  setErroCarga(null);
                  setTentativa((n) => n + 1);
                }}
              >
                Tentar de novo
              </button>
            </Aviso>
          ) : carregando ? (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <RefreshCw className="size-3.5 animate-spin" /> Abrindo o instrumento…
            </p>
          ) : (
            <FormularioInstrumento
              time={time}
              instrumento={atual}
              tipos={tipos}
              tipoFixo={tipo}
              souAdmin={souAdmin}
              onSalvo={salvou}
              onCancelar={onFechar}
            />
          )}
          {instrumento && <UsadoPor instrumentoId={instrumento.id} />}
        </div>
      </main>
    </div>
  );
}
