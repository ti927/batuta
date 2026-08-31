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
  // Seta de ERRO — cor derivada do papel da saída, não escolhida à mão, para o
  // desenho não poder mentir sobre o que o motor vai fazer.
  erro: {
    stroke: "#E5484D",
    pillBg: "#FDECEC",
    pillFg: "#B42318",
    pillBd: "#F5C2C0",
    dot: "#E5484D",
    rotulo: "quando der erro",
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

// Normalização canônica da cadeia NO FRONT. É a FONTE ÚNICA de verdade do "início":
// `cadeia.inicial`. A flag `n.inicial` de cada nó e a saída do nó gatilho são
// DERIVADAS dele — nunca editadas à mão. Esta função ESPELHA `grafo._completar` do
// cérebro (cerebro/orquestracao/grafo.py): mesma regra para inicial, mesma religação
// do gatilho, mesmos defaults de saída. Assim TELA == BANCO == MOTOR, sem divergir.
//
// Pura e idempotente. NUNCA toca x/y (preserva o arrasto) e NÃO inventa nós nem
// posições (o motor segue dono do layout). Se mudar a regra aqui, mude lá também.
export function normalizarCadeia(cadeia: Cadeia): Cadeia {
  const nos = cadeia.nos ?? [];
  const ids = new Set(nos.map((n) => n.id));

  // 1) inicial: explícito-válido > 1º nó marcado `inicial` > 1º agente > undefined
  //    (mesma ordem de grafo._completar passo 2).
  let inicial =
    cadeia.inicial && ids.has(cadeia.inicial) ? cadeia.inicial : undefined;
  if (!inicial) {
    inicial =
      nos.find((n) => n.inicial)?.id ??
      nos.find((n) => n.tipo === "agente")?.id ??
      undefined;
  }

  return {
    ...cadeia,
    inicial,
    nos: nos.map((n) => {
      if (n.tipo === "gatilho") {
        // 2) saída do gatilho DERIVADA do inicial (preserva id/rotulo existentes).
        return {
          ...n,
          saidas: inicial
            ? [
                {
                  id: n.saidas?.[0]?.id ?? novoIdSaida(),
                  rotulo: n.saidas?.[0]?.rotulo ?? "inicia o fluxo",
                  destino: inicial,
                  tone: "normal" as const,
                },
              ]
            : [],
        };
      }
      // 3) saídas: garante id + tone (cosméticos); 4) flag inicial DERIVADA.
      return {
        ...n,
        inicial: n.id === inicial,
        saidas: (n.saidas ?? []).map((s, j) => ({
          ...s,
          id: s.id ?? `${n.id}-${j}`,
          tone: s.tone ?? ("normal" as const),
        })),
      };
    }),
  };
}
