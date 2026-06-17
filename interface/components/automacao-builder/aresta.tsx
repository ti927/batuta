// Aresta condicional (CondEdge) do construtor: linha colorida por `tone` + pílula
// com o rótulo (clicável para editar a saída no inspector). Loops desenham uma
// curva de volta (lane acima/abaixo), como no handoff.

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  type EdgeProps,
} from "@xyflow/react";

import type { ToneSaida } from "@/lib/api";
import { tone } from "./nucleo";

export type DadosAresta = {
  rotulo: string;
  tone?: ToneSaida;
  lane?: "above" | "below";
  gate?: boolean;
  ativo?: boolean;
  onPick?: (sourceId: string) => void;
};

function bezierPonto(
  t: number,
  p0: [number, number],
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
): [number, number] {
  const mt = 1 - t;
  const a = mt * mt * mt;
  const b = 3 * mt * mt * t;
  const c = 3 * mt * t * t;
  const d = t * t * t;
  return [
    a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
  ];
}

export function CondEdge({
  id,
  source,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
}: EdgeProps) {
  const d = (data ?? {}) as DadosAresta;
  const tn = tone(d.tone);
  const stroke = d.ativo ? "#6D4AFF" : tn.stroke;

  let path: string;
  let labelX: number;
  let labelY: number;

  const backward = targetX < sourceX + 24;
  if (backward) {
    const above = d.lane === "above";
    const laneY = above
      ? Math.min(sourceY, targetY) - 124
      : Math.max(sourceY, targetY) + 122;
    const c1: [number, number] = [sourceX + 84, laneY];
    const c2: [number, number] = [targetX - 84, laneY];
    path = `M ${sourceX} ${sourceY} C ${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${targetX} ${targetY}`;
    [labelX, labelY] = bezierPonto(
      0.5,
      [sourceX, sourceY],
      c1,
      c2,
      [targetX, targetY],
    );
  } else {
    const [p, lx, ly] = getBezierPath({
      sourceX,
      sourceY,
      sourcePosition: sourcePosition ?? Position.Right,
      targetX,
      targetY,
      targetPosition: targetPosition ?? Position.Left,
    });
    path = p;
    labelX = lx;
    labelY = ly;
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{ stroke, strokeWidth: d.ativo ? 2.4 : 1.8 }}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          title="Editar esta saída"
          onClick={(ev) => {
            ev.stopPropagation();
            d.onPick?.(source);
          }}
          style={{
            position: "absolute",
            transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: "all",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            whiteSpace: "nowrap",
            background: tn.pillBg,
            color: tn.pillFg,
            border: `1px solid ${d.ativo ? "#6D4AFF" : tn.pillBd}`,
            borderRadius: 999,
            padding: "3px 10px",
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            boxShadow: d.ativo
              ? "0 0 0 3px rgba(109,74,255,.12)"
              : "0 1px 2px rgba(26,23,48,.05)",
          }}
        >
          {d.tone === "loop" && <span style={{ fontSize: 13, lineHeight: 1 }}>↺</span>}
          {d.rotulo || "(sem rótulo)"}
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

export const tiposDeAresta = { cond: CondEdge };
