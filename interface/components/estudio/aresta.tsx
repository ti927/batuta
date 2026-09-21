// O FIO DO ESTÚDIO — e a mudança que motivou esta tela inteira.
//
// No construtor clássico o fio mostra `rotulo`: o NOME interno do caminho
// (“aprovado1”). Nome não responde à pergunta que a pessoa faz ao olhar o desenho —
// “por que o fluxo iria por aqui?”. Aqui o fio mostra a CONDIÇÃO (`quando`): “quando
// você aprovar”. O nome continua existindo, miúdo, porque é a palavra que o agente
// declara — mas ele deixou de ser a legenda principal.
//
// Mais: fio de volta e fio de falha são TRACEJADOS (leem-se como desvio), o fio com
// problema fica vermelho e pontilhado grosso, e quando um passo está selecionado os
// fios que não o tocam desbotam — o foco é o que deixa um grafo grande legível.

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  type EdgeProps,
} from "@xyflow/react";

import type { Cor } from "./cores";

export type DadosArestaEstudio = {
  /** O que a pílula mostra: a condição, ou a frase do papel (erro / se nenhuma). */
  condicao: string;
  /** O nome interno do caminho — legenda miúda, para quem precisa casar com o texto. */
  rotulo: string;
  cor: Cor;
  tracejado?: boolean;
  lane?: "above" | "below";
  /** O fio sai de um passo selecionado (ou chega nele). */
  ativo?: boolean;
  /** Há outro passo selecionado e este fio não o toca — desbota. */
  apagado?: boolean;
  /** Este fio tem um problema que barra o salvamento. */
  comErro?: boolean;
  /** Quem decide é o motor (regra exata), não a IA. */
  comRegra?: boolean;
  onPick?: (noId: string, saidaId: string) => void;
  noId?: string;
  saidaId?: string;
};

const MAX_TEXTO = 34;

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

export function ArestaEstudio({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
}: EdgeProps) {
  const d = (data ?? {}) as DadosArestaEstudio;
  const cor = d.comErro ? "#E5484D" : d.ativo ? "#6D4AFF" : d.cor.linha;

  let path: string;
  let labelX: number;
  let labelY: number;

  // Fio que anda para trás = laço. Sai por uma "pista" acima ou abaixo dos cartões,
  // em vez de cortar o desenho no meio.
  const volta = targetX < sourceX + 24;
  if (volta) {
    const acima = d.lane === "above";
    const pistaY = acima
      ? Math.min(sourceY, targetY) - 116
      : Math.max(sourceY, targetY) + 116;
    const c1: [number, number] = [sourceX + 90, pistaY];
    const c2: [number, number] = [targetX - 90, pistaY];
    path = `M ${sourceX} ${sourceY} C ${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${targetX} ${targetY}`;
    [labelX, labelY] = bezierPonto(0.5, [sourceX, sourceY], c1, c2, [targetX, targetY]);
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

  const texto = d.condicao?.trim() || "";
  const curto = texto.length > MAX_TEXTO ? `${texto.slice(0, MAX_TEXTO - 1)}…` : texto;
  const opacidade = d.apagado ? 0.22 : 1;

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: cor,
          strokeWidth: d.ativo ? 2.4 : d.comErro ? 2.2 : 1.7,
          strokeDasharray: d.comErro ? "2 4" : d.tracejado ? "7 5" : undefined,
          opacity: opacidade,
        }}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          title={
            texto
              ? `${texto}\n(caminho “${d.rotulo}”)`
              : `O caminho “${d.rotulo}” não diz quando seguir por ele.`
          }
          onClick={(ev) => {
            ev.stopPropagation();
            if (d.noId && d.saidaId) d.onPick?.(d.noId, d.saidaId);
          }}
          style={{
            position: "absolute",
            transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: d.apagado ? "none" : "all",
            opacity: opacidade,
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            maxWidth: 230,
            whiteSpace: "nowrap",
            background: d.comErro ? "#FDECEC" : d.cor.pilulaBg,
            color: d.comErro ? "#B42318" : d.cor.pilulaFg,
            border: `1px solid ${
              d.comErro ? "#F5C2C0" : d.ativo ? "#6D4AFF" : d.cor.pilulaBd
            }`,
            borderRadius: 999,
            padding: "3px 9px",
            fontSize: 11.5,
            fontWeight: 500,
            lineHeight: 1.3,
            cursor: "pointer",
            boxShadow: d.ativo
              ? "0 0 0 3px rgba(109,74,255,.12)"
              : "0 1px 2px rgba(26,23,48,.06)",
          }}
        >
          {d.tracejado && d.cor.legenda === "volta atrás" && (
            <span style={{ fontSize: 12, lineHeight: 1 }}>↺</span>
          )}
          {curto || (
            <span style={{ fontStyle: "italic", opacity: 0.85 }}>falta a condição</span>
          )}
          {d.comRegra && (
            <span
              style={{
                fontSize: 9.5,
                fontWeight: 600,
                background: "rgba(109,74,255,.12)",
                color: "#3D2A99",
                borderRadius: 4,
                padding: "0 3px",
              }}
            >
              regra
            </span>
          )}
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

export const tiposDeArestaEstudio = { estudio: ArestaEstudio };
