// As cores dos fios do estúdio.
//
// Mesma paleta do construtor clássico (`automacao-builder/nucleo.ts`), copiada de
// propósito em vez de importada: esta tela é paralela e vai ser mexida à vontade nos
// testes, e não pode arrastar a tela que já está no ar junto.
//
// A regra que importa: a cor sai do PAPEL da saída, não de um gosto. Uma saída de
// erro é vermelha mesmo que alguém tenha escolhido verde — o desenho não pode mentir
// sobre o que o motor vai fazer.

import type { SaidaCadeia, ToneSaida } from "@/lib/api";

export type Cor = {
  /** Cor do fio. */
  linha: string;
  /** Pílula da condição: fundo, texto, borda. */
  pilulaBg: string;
  pilulaFg: string;
  pilulaBd: string;
  /** Porta (o pontinho na borda do cartão) e o marcador da linha da saída. */
  dot: string;
  /** Como esse tipo de fio se chama na legenda. */
  legenda: string;
};

export const CORES: Record<ToneSaida, Cor> = {
  normal: {
    linha: "#C3BFD6",
    pilulaBg: "#FFFFFF",
    pilulaFg: "#4A4860",
    pilulaBd: "#E3E0EE",
    dot: "#A09DB8",
    legenda: "segue adiante",
  },
  ok: {
    linha: "#79C295",
    pilulaBg: "#E6F4EA",
    pilulaFg: "#2F7D45",
    pilulaBd: "#BEE3CB",
    dot: "#3DAA5C",
    legenda: "deu certo / aprovaram",
  },
  loop: {
    linha: "#E3BB7C",
    pilulaBg: "#FDF1E3",
    pilulaFg: "#A9681A",
    pilulaBd: "#F0D9B4",
    dot: "#E89638",
    legenda: "volta atrás",
  },
  erro: {
    linha: "#E5484D",
    pilulaBg: "#FDECEC",
    pilulaFg: "#B42318",
    pilulaBd: "#F5C2C0",
    dot: "#E5484D",
    legenda: "quando falhar",
  },
};

/** O tom escolhido à mão (cosmético), com o padrão do motor. */
export function cor(t: ToneSaida | undefined): Cor {
  return CORES[t ?? "normal"] ?? CORES.normal;
}

/**
 * A cor DE FATO de uma saída: o papel manda. `erro` é sempre vermelho; "se nenhuma" é
 * sempre o cinza neutro (é rede de segurança, não um caminho escolhido); o resto usa
 * o tom que a pessoa escolheu.
 */
export function corDaSaida(sa: SaidaCadeia): Cor {
  if (sa.tipo === "erro") return CORES.erro;
  if (sa.tipo === "senao") return CORES.normal;
  return cor(sa.tone);
}

/** O fio é tracejado? Volta atrás e falha são tracejados — leem-se como desvio. */
export function tracejado(sa: SaidaCadeia): boolean {
  return sa.tipo === "erro" || sa.tone === "loop";
}
