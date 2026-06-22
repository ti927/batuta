// Registro COMPLETO do Font Awesome free (solid + brands, ~2.500 ícones).
//
// ATENÇÃO: este módulo embarca a biblioteca INTEIRA — é pesado (centenas de KB).
// Por isso ele NUNCA deve ser importado estaticamente: só via `import()` dinâmico
// (ver `icones-externos.ts`), para o Next colocá-lo num chunk separado, baixado
// SÓ quando alguém busca um ícone fora dos curados ou precisa renderizar um.
// Os ícones curados (uso comum) seguem no bundle principal via `icones-instrumento`.

import { config, type IconDefinition } from "@fortawesome/fontawesome-svg-core";
import { fab } from "@fortawesome/free-brands-svg-icons";
import { fas } from "@fortawesome/free-solid-svg-icons";

config.autoAddCss = false;

export type IconeExterno = { id: string; nome: string; icon: IconDefinition };

// id estável = `prefix:iconName` (ex.: "fab:openai", "fas:dragon") — mesmo formato
// dos curados, então a deduplicação e o lookup batem.
const POR_ID = new Map<string, IconDefinition>();
const LISTA: IconeExterno[] = [];

for (const def of [
  ...Object.values(fas),
  ...Object.values(fab),
] as IconDefinition[]) {
  const id = `${def.prefix}:${def.iconName}`;
  if (POR_ID.has(id)) continue; // pacotes têm aliases p/ a mesma figura
  POR_ID.set(id, def);
  LISTA.push({ id, nome: String(def.iconName).replace(/-/g, " "), icon: def });
}

export { LISTA, POR_ID };
