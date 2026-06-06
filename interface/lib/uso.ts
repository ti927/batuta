// Rótulos amigáveis para a ORIGEM da chave na medição de uso (Fase 7.6).
// O cérebro registra de qual chave saiu o consumo de cada passo; aqui damos
// nome legível à separação consultoria × cliente.

export const ROTULO_ORIGEM: Record<string, string> = {
  organizacao: "Cliente (chave própria)",
  consultoria: "Consultoria (chave-mãe)",
  legado: "Consultoria (.env legado)",
  desconhecida: "Sem origem registrada",
};

export function rotuloOrigem(origem: string): string {
  return ROTULO_ORIGEM[origem] ?? origem;
}
