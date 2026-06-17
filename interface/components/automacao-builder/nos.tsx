// Nós custom do React Flow para o construtor de automações.
// Gatilho · Agente · Roteador · Fim — visual do handoff (SPEC §6), flat e marca Batuta.

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { CheckCircle2, Layers, Shield, Sparkles, Zap } from "lucide-react";

import type { Agente, NoCadeia } from "@/lib/api";
import { RobotFace } from "@/components/robot-face";

import { NODE_W, tone } from "./nucleo";

export type DadosNo = {
  no: NoCadeia;
  agente?: Agente;
  indice?: number;
};

// Handles de saída (direita), um por saída, distribuídos na vertical.
function HandlesSaida({ no }: { no: NoCadeia }) {
  const saidas = no.saidas ?? [];
  const n = saidas.length;
  return (
    <>
      {saidas.map((s, i) => {
        const t = tone(s.tone);
        const top = `${((i + 1) / (n + 1)) * 100}%`;
        return (
          <Handle
            key={s.id ?? i}
            type="source"
            position={Position.Right}
            id={s.id}
            title={s.rotulo}
            style={{
              top,
              width: 11,
              height: 11,
              background: "#fff",
              border: `2px solid ${t.dot}`,
            }}
          />
        );
      })}
    </>
  );
}

function HandleEntrada() {
  return (
    <Handle
      type="target"
      position={Position.Left}
      style={{ width: 11, height: 11, background: "#fff", border: "2px solid #C3BFD6" }}
    />
  );
}

const cartao = (selected: boolean, bg: string, bdSel: string, bd: string) =>
  ({
    width: NODE_W,
    background: bg,
    border: `1px solid ${selected ? bdSel : bd}`,
    borderRadius: 12,
    boxShadow: selected
      ? "0 0 0 3px rgba(109,74,255,.14)"
      : "0 1px 2px rgba(26,23,48,.05)",
    transition: "box-shadow .12s, border-color .12s",
  }) as const;

export function GatilhoNode({ data, selected }: NodeProps) {
  const no = (data as DadosNo).no;
  const rotuloGatilho =
    no.gatilho === "agendamento"
      ? "Agendamento"
      : no.gatilho === "webhook"
        ? "Webhook"
        : "Manual";
  return (
    <div style={{ ...cartao(!!selected, "#fff", "#6D4AFF", "#E8E6F0"), height: 66 }}>
      <div className="flex h-full items-center gap-3 px-3.5">
        <span
          className="grid size-[34px] flex-none place-items-center rounded-[9px]"
          style={{ background: "#6D4AFF" }}
        >
          <Zap size={18} color="#fff" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#A09DB8" }}
          >
            Gatilho
          </div>
          <div className="text-[14.5px] font-medium" style={{ color: "#1A1730" }}>
            {rotuloGatilho}
          </div>
        </div>
      </div>
      <HandlesSaida no={no} />
    </div>
  );
}

export function FimNode({ selected }: NodeProps) {
  return (
    <div
      style={{ ...cartao(!!selected, "#F4FAF6", "#6D4AFF", "#CDE9D5"), height: 56 }}
    >
      <div className="flex h-full items-center gap-2.5 px-4">
        <CheckCircle2 size={20} color="#3DAA5C" />
        <div className="text-[14.5px] font-medium" style={{ color: "#2F7D45" }}>
          Fim · entrega ao usuário
        </div>
      </div>
      <HandleEntrada />
    </div>
  );
}

export function RoteadorNode({ data, selected }: NodeProps) {
  const no = (data as DadosNo).no;
  return (
    <div style={{ ...cartao(!!selected, "#FBFAFF", "#6D4AFF", "#E0DAF6"), height: 74 }}>
      <div className="flex h-full items-center gap-2.5 px-3.5">
        <span
          className="grid size-8 flex-none place-items-center rounded-[9px]"
          style={{ background: "#EFEAFF" }}
        >
          <Layers size={17} color="#6D4AFF" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#9A8CCB" }}
          >
            Roteador
          </div>
          <div
            className="truncate text-[14px] font-medium"
            style={{ color: "#1A1730" }}
          >
            {no.nome || "Decisão"}
          </div>
        </div>
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

export function AgenteNode({ data, selected }: NodeProps) {
  const d = data as DadosNo;
  const no = d.no;
  const ag = d.agente;
  const modelo = (ag?.modelo_ia ?? "").replace("claude-", "");
  return (
    <div style={{ ...cartao(!!selected, "#fff", "#6D4AFF", "#E8E6F0"), height: 90 }}>
      <div className="flex h-full flex-col gap-1.5 p-[11px_13px]">
        <div className="flex items-center gap-2.5">
          <RobotFace size={28} indice={d.indice ?? 0} lider={ag?.papel === "lider"} />
          <span
            className="flex-1 truncate text-[14px] font-medium"
            style={{ color: "#1A1730" }}
          >
            {ag?.nome ?? "Agente"}
          </span>
          {no.inicial && (
            <span
              className="flex-none rounded-full px-1.5 py-px text-[10px] font-medium"
              style={{ color: "#3D2A99", background: "#EFEAFF" }}
            >
              início
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {modelo && (
            <span
              className="inline-flex items-center gap-1 text-[11px]"
              style={{ color: "#6B6880" }}
            >
              <Sparkles size={11} color="#6D4AFF" /> {modelo}
            </span>
          )}
          {no.gate && (
            <span
              className="inline-flex items-center gap-1 rounded-full border px-1.5 py-px text-[10.5px] font-medium"
              style={{ color: "#A9681A", background: "#FDF1E3", borderColor: "#F0D9B4" }}
            >
              <Shield size={10} /> espera você
            </span>
          )}
        </div>
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

export const tiposDeNo = {
  gatilho: GatilhoNode,
  agente: AgenteNode,
  roteador: RoteadorNode,
  fim: FimNode,
};
