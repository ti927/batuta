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

// Rótulos para a CATEGORIA de uso: em que função a IA paga foi gasta. Deixa claro
// ao usuário onde a chave (própria ou da consultoria) foi consumida.
export const ROTULO_CATEGORIA: Record<string, string> = {
  execucao: "Execução de agentes",
  conversa: "IA de criação/companheira",
  mensageria: "Atendimento (mensageria)",
  transcricao: "Transcrição de áudio",
  instrumento: "Instrumentos com IA (imagens)",
  desconhecida: "Sem categoria registrada",
};

export function rotuloCategoria(categoria: string): string {
  return ROTULO_CATEGORIA[categoria] ?? categoria;
}
