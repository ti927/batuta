// Permissões por papel (espelham a matriz que o cérebro já enforça — I6.6).
// O cérebro é a fonte da verdade (403); isto só decide o que a tela MOSTRA.

import { type PapelAcesso } from "@/lib/api";

// Operador e admin podem operar o dia a dia: criar/editar agentes, instrumentos
// e automações, vincular cinto, disparar, acionar, cancelar execução.
export function podeOperar(papel: PapelAcesso | null | undefined): boolean {
  return papel === "admin" || papel === "operador";
}

// Só admin: deletar (agente/instrumento/automação/time/execução), criar/editar/
// deletar organização e time, gerir acesso, apagar histórico.
export function podeAdmin(papel: PapelAcesso | null | undefined): boolean {
  return papel === "admin";
}
