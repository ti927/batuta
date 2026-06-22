"use client";

import { Sparkles } from "lucide-react";

import { type Agente, type Instrumento } from "@/lib/api";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { RobotFace } from "@/components/robot-face";
import { Badge } from "@/components/ui/badge";

/**
 * Card de agente (clique abre o editor em drawer). Mostra rosto, nome, badge de
 * líder, resumo (agent.md), modelo e os instrumentos do cinto. Reusado pela aba
 * Agentes e pela aba Início.
 *
 * Se `onEditarInstrumento` for passado, os badges do cinto viram clicáveis e
 * abrem o editor do instrumento (sem trocar de aba) — o clique no badge não
 * dispara a abertura do agente. É um `div` (não `button`) justamente para poder
 * conter os botões dos badges; a acessibilidade de teclado é preservada.
 */
export function CardAgente({
  agente,
  indice,
  cinto,
  onAbrir,
  onEditarInstrumento,
}: {
  agente: Agente;
  indice: number;
  cinto: Instrumento[];
  onAbrir: () => void;
  onEditarInstrumento?: (instrumentoId: string) => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onAbrir}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onAbrir();
        }
      }}
      className="flex w-full cursor-pointer items-start gap-3 rounded-xl border border-border bg-card p-3.5 text-left transition-all hover:border-[#D6D3E8] hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      <RobotFace size={40} indice={indice} lider={agente.papel === "lider"} />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="font-medium text-foreground">{agente.nome}</span>
          {agente.papel === "lider" && (
            <Badge variant="neutral" className="text-[10px]">
              líder
            </Badge>
          )}
        </span>
        {agente.agent_md && (
          <span className="mt-0.5 line-clamp-2 block text-sm text-muted-foreground">
            {agente.agent_md}
          </span>
        )}
        <span className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {agente.modelo_ia && (
            <span className="inline-flex items-center gap-1">
              <Sparkles className="size-3 text-primary" />
              {agente.modelo_ia}
            </span>
          )}
          {cinto.map((i) =>
            onEditarInstrumento ? (
              <button
                key={i.id}
                type="button"
                title={`Editar o instrumento “${i.nome}”`}
                onClick={(e) => {
                  e.stopPropagation();
                  onEditarInstrumento(i.id);
                }}
                className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              >
                <IconeInstrumento icone={i.icone} className="size-3" />
                {i.nome}
              </button>
            ) : (
              <span
                key={i.id}
                className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-foreground"
              >
                <IconeInstrumento icone={i.icone} className="size-3" />
                {i.nome}
              </span>
            ),
          )}
        </span>
      </span>
    </div>
  );
}
