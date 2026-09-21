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
//
// O traçado é ORTOGONAL com cantos arredondados (trechos retos e curvas de 90°), e não
// uma curva livre: é assim que se lê um fluxo, e é o que deixa acompanhar um fio
// específico no meio de vários.

import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
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
  /** Onde o fio faz a curva, de 0 (na saída) a 1 (na chegada). Um valor por saída
   *  afasta os trechos verticais de fios irmãos, que senão ficam um em cima do outro. */
  curva?: number;
  onPick?: (noId: string, saidaId: string) => void;
  noId?: string;
  saidaId?: string;
};

const MAX_TEXTO = 34;

/** Raio dos cantos. O mesmo do traçado do React Flow, para os dois casarem. */
const RAIO = 14;
/** Quanto o fio anda reto ao sair da porta e antes de entrar no destino. */
const STUB = 28;
/** Distância da "pista" por onde um laço volta, acima ou abaixo dos cartões. */
const PISTA = 116;

type Ponto = [number, number];

/**
 * Transforma uma linha quebrada (só segmentos retos) num traçado com cantos
 * arredondados: em cada vértice, recua um pouco nos dois lados e liga com uma
 * curva quadrática. O raio encolhe sozinho quando o segmento é curto demais — sem
 * isso, dois cantos perto um do outro se comem e o fio dá um nó.
 */
function caminhoArredondado(pts: Ponto[], raio = RAIO): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i += 1) {
    const [px, py] = pts[i - 1];
    const [cx, cy] = pts[i];
    const [nx, ny] = pts[i + 1];
    const antes = Math.hypot(cx - px, cy - py);
    const depois = Math.hypot(nx - cx, ny - cy);
    const r = Math.min(raio, antes / 2, depois / 2);
    if (!(r > 0.5)) {
      d += ` L ${cx} ${cy}`;
      continue;
    }
    const ax = cx + ((px - cx) / antes) * r;
    const ay = cy + ((py - cy) / antes) * r;
    const bx = cx + ((nx - cx) / depois) * r;
    const by = cy + ((ny - cy) / depois) * r;
    d += ` L ${ax} ${ay} Q ${cx} ${cy} ${bx} ${by}`;
  }
  const fim = pts[pts.length - 1];
  return `${d} L ${fim[0]} ${fim[1]}`;
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
  // em vez de cortar o desenho no meio. Desenhado à mão porque o traçado automático
  // volta pelo meio e passa por cima dos passos.
  const volta = targetX < sourceX + 24;
  if (volta) {
    const pistaY =
      d.lane === "above"
        ? Math.min(sourceY, targetY) - PISTA
        : Math.max(sourceY, targetY) + PISTA;
    const saida = sourceX + STUB;
    const entrada = targetX - STUB;
    path = caminhoArredondado([
      [sourceX, sourceY],
      [saida, sourceY],
      [saida, pistaY],
      [entrada, pistaY],
      [entrada, targetY],
      [targetX, targetY],
    ]);
    labelX = (saida + entrada) / 2;
    labelY = pistaY;
  } else {
    // Ortogonal com cantos arredondados: é como um fluxo se lê — trechos retos e
    // curvas de 90°, não uma curva livre que passa perto de tudo.
    const [p, lx, ly] = getSmoothStepPath({
      sourceX,
      sourceY,
      sourcePosition: sourcePosition ?? Position.Right,
      targetX,
      targetY,
      targetPosition: targetPosition ?? Position.Left,
      borderRadius: RAIO,
      offset: STUB,
      stepPosition: d.curva ?? 0.5,
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
