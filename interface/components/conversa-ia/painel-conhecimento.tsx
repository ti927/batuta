"use client";

import { Activity, Brain, Layers, Sparkles, type LucideIcon } from "lucide-react";

import { type Execucao, type MemoriaProjeto, type SnapshotTime } from "@/lib/api";
import { RotuloSecao, rotuloGatilho } from "@/components/conversa-ia/comum";

// Painel "O que eu sei deste projeto" (handoff §6.6): estado atual (consultado ao
// vivo), últimas execuções (histórico) e decisões lembradas (memória de longo prazo).

const ROTULO_CATEGORIA: Record<MemoriaProjeto["categoria"], string> = {
  fato: "Fato",
  decisao: "Decisão",
  preferencia: "Preferência",
};

const ESTADO_EXEC: Record<string, string> = {
  aguardando: "na fila",
  em_andamento: "em andamento",
  aguardando_humano: "aguardando você",
  concluida: "concluída",
  falhou: "falhou",
  cancelada: "cancelada",
};

function dataCurta(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  } catch {
    return "";
  }
}

function Bolinha() {
  return (
    <span
      className="mt-1.5 size-1.5 shrink-0 rounded-full"
      style={{ background: "#B19CD9" }}
    />
  );
}

function Camada({
  Icone,
  titulo,
  origem,
  vazio,
  children,
}: {
  Icone: LucideIcon;
  titulo: string;
  origem: string;
  vazio?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-3.5">
      <div className="flex items-center gap-2">
        <Icone className="size-4 text-primary" />
        <span className="text-sm font-medium text-foreground">{titulo}</span>
      </div>
      <p className="mb-2.5 mt-0.5 text-[11px] text-muted-foreground">{origem}</p>
      {vazio ? (
        <p className="text-sm text-muted-foreground/70">{children}</p>
      ) : (
        <ul className="space-y-2">{children}</ul>
      )}
    </div>
  );
}

export function PainelConhecimento({
  time,
  execucoes,
  memoria,
  comTitulo = true,
}: {
  time: SnapshotTime;
  execucoes: Execucao[];
  memoria: MemoriaProjeto[];
  comTitulo?: boolean;
}) {
  const automacao = time.automacao;
  const fatos: string[] = [
    `${time.agentes.length} agente(s)`,
    `${time.instrumentos.length} instrumento(s)`,
  ];
  if (automacao) {
    fatos.push(
      automacao.ativa ? "automação ativa" : "automação em repouso",
      `gatilho: ${rotuloGatilho(automacao.tipo_gatilho)}`,
    );
  } else {
    fatos.push("sem automação ainda");
  }

  return (
    <div className={comTitulo ? "mt-8" : ""}>
      {comTitulo && <RotuloSecao Icone={Brain}>O que eu sei deste projeto</RotuloSecao>}
      <div className="flex flex-col gap-2.5">
        <Camada Icone={Layers} titulo="Estado atual" origem="consultado ao vivo no banco">
          {fatos.map((f) => (
            <li key={f} className="flex items-start gap-2.5 text-sm">
              <Bolinha />
              <span className="min-w-0 text-foreground">{f}</span>
            </li>
          ))}
        </Camada>

        <Camada
          Icone={Activity}
          titulo="Últimas execuções"
          origem="histórico do projeto"
          vazio={execucoes.length === 0}
        >
          {execucoes.length === 0
            ? "Nenhuma execução ainda."
            : execucoes.map((e) => (
                <li key={e.id} className="flex items-start gap-2.5 text-sm">
                  <Bolinha />
                  <span className="min-w-0 flex-1 text-foreground">
                    <span className="text-[#3D2A99]">
                      {ESTADO_EXEC[e.estado] ?? e.estado}
                    </span>
                    {e.entrada?.texto && (
                      <span className="text-muted-foreground"> — {e.entrada.texto}</span>
                    )}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {dataCurta(e.criado_em)}
                  </span>
                </li>
              ))}
        </Camada>

        <Camada
          Icone={Sparkles}
          titulo="Decisões lembradas"
          origem="memória de longo prazo"
          vazio={memoria.length === 0}
        >
          {memoria.length === 0
            ? "Ainda não registrei nada — peça para eu lembrar de algo."
            : memoria.map((m) => (
                <li key={m.id} className="flex items-start gap-2.5 text-sm">
                  <Bolinha />
                  <span className="min-w-0 text-foreground">
                    <span className="mr-1.5 text-xs font-medium text-[#3D2A99]">
                      {ROTULO_CATEGORIA[m.categoria] ?? "Memória"}
                    </span>
                    {m.conteudo}
                  </span>
                </li>
              ))}
        </Camada>
      </div>
    </div>
  );
}
