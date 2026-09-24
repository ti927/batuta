"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { type Alteracao, type Carimbo, dataHora, iniciais, quemGravou } from "@/lib/quadros";

// Peças pequenas repetidas nas telas dos quadros.

// O robozinho do handoff (§6.1), em miniatura: ciano = quem grava, lilás = quem lê.
export function RoboAgente({ escreve = false, tamanho = 20 }: { escreve?: boolean; tamanho?: number }) {
  return (
    <span
      aria-hidden
      className="relative inline-grid shrink-0 place-items-center"
      style={{
        width: tamanho,
        height: tamanho,
        borderRadius: tamanho * 0.32,
        background: escreve ? "#3DD8C3" : "#B19CD9",
      }}
    >
      <span
        className="flex items-center justify-center gap-[3px]"
        style={{
          width: "62%",
          height: "44%",
          borderRadius: 3,
          background: "rgba(20,16,40,.85)",
        }}
      >
        <span className="size-[3px] rounded-full bg-white" />
        <span className="size-[3px] rounded-full bg-white" />
      </span>
    </span>
  );
}

export function SeloAcesso({ acesso }: { acesso: "ler" | "ler_e_escrever" }) {
  return acesso === "ler_e_escrever" ? (
    <span className="rounded-sm border border-[#CFC2FB] bg-[#F7F4FF] px-1.5 text-[11px] text-accent-foreground">
      lê e grava
    </span>
  ) : (
    <span className="rounded-sm border border-border px-1.5 text-[11px] text-muted-foreground">
      só lê
    </span>
  );
}

// "Gravado por": o agente (robozinho) ou a pessoa (iniciais), e quando.
export function GravadoPor({ carimbo }: { carimbo: Carimbo }) {
  const agente = carimbo.origem === "agente";
  return (
    <span className="flex items-start gap-2 text-xs text-muted-foreground">
      {agente ? (
        <RoboAgente escreve tamanho={22} />
      ) : (
        <span className="grid size-[22px] shrink-0 place-items-center rounded-full bg-accent text-[10px] font-medium text-accent-foreground">
          {iniciais(carimbo.usuario_nome)}
        </span>
      )}
      <span className="min-w-0">
        <span className="block truncate text-foreground">{quemGravou(carimbo)}</span>
        <span className="block">
          {carimbo.automacao_nome ? `${carimbo.automacao_nome} · ` : ""}
          {dataHora(carimbo.atualizado_em)}
        </span>
      </span>
    </span>
  );
}

export function QuemFezAlteracao({ a }: { a: Alteracao }) {
  const verbo = a.acao === "criou" ? "criou" : a.acao === "mudou" ? "mudou" : "apagou";
  return (
    <span>
      {quemGravou(a)} {verbo}
      {a.automacao_nome ? ` · ${a.automacao_nome}` : ""} · {dataHora(a.quando)}
    </span>
  );
}

// Fecha com Esc (padrão dos drawers do app).
function useEsc(onFechar: () => void) {
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [onFechar]);
}

// Painel lateral (mesmo molde do drawer de instrumento: 460px, fundo escurecido).
export function PainelLateral({
  titulo,
  subtitulo,
  onFechar,
  rodape,
  children,
  largura = 460,
}: {
  titulo: React.ReactNode;
  subtitulo?: React.ReactNode;
  onFechar: () => void;
  rodape?: React.ReactNode;
  children: React.ReactNode;
  largura?: number;
}) {
  useEsc(onFechar);
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button className="absolute inset-0 bg-foreground/20" onClick={onFechar} aria-label="Fechar" />
      <aside
        role="dialog"
        aria-modal="true"
        className="relative flex h-full w-full flex-col border-l border-border bg-card shadow-xl"
        style={{ maxWidth: largura }}
      >
        <header className="flex items-start gap-3 border-b border-border p-4">
          <div className="min-w-0 flex-1">
            <h2 className="truncate font-medium text-foreground">{titulo}</h2>
            {subtitulo && <p className="mt-0.5 text-sm text-muted-foreground">{subtitulo}</p>}
          </div>
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
        {rodape && (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-border p-4">{rodape}</footer>
        )}
      </aside>
    </div>
  );
}

// Janela central (formulários mais largos: novo quadro, importar).
export function Janela({
  titulo,
  subtitulo,
  onFechar,
  rodape,
  children,
  largura = 720,
}: {
  titulo: React.ReactNode;
  subtitulo?: React.ReactNode;
  onFechar: () => void;
  rodape?: React.ReactNode;
  children: React.ReactNode;
  largura?: number;
}) {
  useEsc(onFechar);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <button className="absolute inset-0 bg-foreground/25" onClick={onFechar} aria-label="Fechar" />
      <section
        role="dialog"
        aria-modal="true"
        className="relative flex max-h-[calc(100vh-2rem)] w-full flex-col rounded-lg border border-border bg-card shadow-sm"
        style={{ maxWidth: largura }}
      >
        <header className="flex items-start gap-3 border-b border-border p-5">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-medium text-foreground">{titulo}</h2>
            {subtitulo && <p className="mt-0.5 text-sm text-muted-foreground">{subtitulo}</p>}
          </div>
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>
        <div className="overflow-y-auto p-5">{children}</div>
        {rodape && (
          <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border p-4">
            {rodape}
          </footer>
        )}
      </section>
    </div>
  );
}

// Lista das linhas recusadas ("linha 58 · Data: não é uma data").
export function ListaRecusas({ detalhes, prefixo = "linha" }: { detalhes: { linha: number | null; coluna: string | null; motivo: string }[]; prefixo?: string }) {
  if (!detalhes.length) return null;
  return (
    <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm">
      {detalhes.slice(0, 50).map((d, i) => (
        <li key={i}>
          {d.linha ? <span className="tabular-nums">{prefixo} {d.linha} · </span> : null}
          {d.coluna ? <span className="font-medium">{d.coluna}: </span> : null}
          {d.motivo}
        </li>
      ))}
      {detalhes.length > 50 && <li>e mais {detalhes.length - 50}…</li>}
    </ul>
  );
}

// Lê um arquivo de texto (CSV) escolhido pela pessoa.
export function lerArquivo(arquivo: File): Promise<string> {
  return new Promise((ok, falha) => {
    const leitor = new FileReader();
    leitor.onload = () => ok(String(leitor.result ?? ""));
    leitor.onerror = () => falha(new Error("Não consegui ler o arquivo. Tente de novo."));
    leitor.readAsText(arquivo, "utf-8");
  });
}
