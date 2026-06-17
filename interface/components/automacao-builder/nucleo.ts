// Tokens visuais e helpers do construtor de automações (grafo).
// Cores do handoff `docs/design_handoff_automacoes_grafo/SPEC.md §6` — flat, marca Batuta.

import type { Cadeia, NoCadeia, ToneSaida } from "@/lib/api";

export const NODE_W = 234;

export type ToneInfo = {
  stroke: string;
  pillBg: string;
  pillFg: string;
  pillBd: string;
  dot: string;
  rotulo: string;
};

export const TONES: Record<ToneSaida, ToneInfo> = {
  ok: {
    stroke: "#79C295",
    pillBg: "#E6F4EA",
    pillFg: "#2F7D45",
    pillBd: "#BEE3CB",
    dot: "#3DAA5C",
    rotulo: "aprova / segue",
  },
  loop: {
    stroke: "#E3BB7C",
    pillBg: "#FDF1E3",
    pillFg: "#A9681A",
    pillBd: "#F0D9B4",
    dot: "#E89638",
    rotulo: "volta atrás",
  },
  normal: {
    stroke: "#C3BFD6",
    pillBg: "#FFFFFF",
    pillFg: "#6B6880",
    pillBd: "#E3E0EE",
    dot: "#A09DB8",
    rotulo: "caminho normal",
  },
};

export function tone(t: ToneSaida | undefined): ToneInfo {
  return TONES[t ?? "normal"] ?? TONES.normal;
}

export const TONE_KEYS: ToneSaida[] = ["normal", "ok", "loop"];

// Gera um id estável de saída para novas saídas criadas na UI.
let _uid = 0;
export function novoIdSaida(): string {
  _uid += 1;
  return `s${_uid}_${Math.random().toString(36).slice(2, 7)}`;
}

export function novoIdNo(prefixo: string): string {
  _uid += 1;
  return `${prefixo}_${Math.random().toString(36).slice(2, 7)}`;
}

// Índice {id: nó} de uma cadeia.
export function indexar(cadeia: Cadeia): Record<string, NoCadeia> {
  const idx: Record<string, NoCadeia> = {};
  for (const n of cadeia.nos ?? []) idx[n.id] = n;
  return idx;
}
