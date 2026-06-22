// Carregador SOB DEMANDA da biblioteca completa de ícones (Font Awesome free).
//
// Mantém o bundle principal leve: o registro pesado (`icones-completo`) só é
// baixado quando, de fato, se busca um ícone fora dos curados ou se precisa
// renderizar um já escolhido que não está nos curados. Singleton: uma única
// importação por sessão, compartilhada por todas as chamadas.

import type { IconDefinition } from "@fortawesome/fontawesome-svg-core";

import type { IconeExterno } from "@/lib/icones-completo";

export type { IconeExterno };

let porId: Map<string, IconDefinition> | null = null;
let lista: IconeExterno[] | null = null;
let carregando: Promise<void> | null = null;

function garantir(): Promise<void> {
  if (porId) return Promise.resolve();
  if (!carregando) {
    carregando = import("@/lib/icones-completo").then((m) => {
      porId = m.POR_ID;
      lista = m.LISTA;
    });
  }
  return carregando;
}

/** Lookup síncrono: devolve o ícone se o registro JÁ estiver carregado (senão undefined). */
export function cacheExterno(id: string): IconDefinition | undefined {
  return porId?.get(id);
}

/** Resolve um ícone por id, carregando o registro completo se preciso. */
export async function resolverExterno(
  id: string,
): Promise<IconDefinition | undefined> {
  const ja = porId?.get(id);
  if (ja) return ja;
  await garantir();
  return porId?.get(id);
}

/**
 * Busca na biblioteca completa por nome (iconName). Carrega o registro na 1ª
 * chamada. Devolve no máximo `limite` resultados (a busca pode casar centenas).
 */
export async function buscarExterno(
  termo: string,
  limite = 60,
): Promise<IconeExterno[]> {
  const t = termo.trim().toLowerCase();
  if (!t) return [];
  await garantir();
  const achados: IconeExterno[] = [];
  for (const item of lista ?? []) {
    if (item.id.includes(t) || item.nome.includes(t)) {
      achados.push(item);
      if (achados.length >= limite) break;
    }
  }
  return achados;
}
