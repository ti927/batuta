// Fonte ÚNICA da "organização ativa" do shell.
//
// Antes havia dois estados locais independentes — um na sidebar, outro no /criar —
// ambos começando na primeira organização da lista e sem se falar. Trocar a org na
// sidebar não chegava ao /criar, então "Criar com a IA" montava o time na
// organização errada (a primeira). Ver a lição das múltiplas fontes de verdade.
//
// Agora a org ativa vive num cookie: a sidebar GRAVA ao trocar, e tanto a sidebar
// quanto o /criar LEEM (no servidor) como valor inicial — sobrevive à navegação e
// ao refresh, e as duas pontas concordam.

export const COOKIE_ORG_ATIVA = "batuta_org_ativa";

// Grava a organização ativa (client-side). Escopo raiz, 1 ano, SameSite=Lax.
export function gravarOrgAtiva(id: string): void {
  document.cookie = `${COOKIE_ORG_ATIVA}=${id}; path=/; max-age=31536000; samesite=lax`;
}
