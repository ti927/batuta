// Rascunho local (localStorage) do formulário do agente: rede de segurança contra
// perder o que foi digitado se a aba fechar/recarregar/travar. O formulário salva o
// rascunho enquanto há alterações não salvas e restaura ao reabrir; o drawer o apaga
// quando o usuário confirma descartar. Chave por agente (ou "novo" por time ao criar).

const PREFIXO = "batuta:rascunho:agente:";

export function chaveRascunho(agenteId: string | null, timeId: string): string {
  return PREFIXO + (agenteId ?? `novo:${timeId}`);
}

export function lerRascunho(chave: string): unknown {
  try {
    const t = localStorage.getItem(chave);
    return t ? JSON.parse(t) : null;
  } catch {
    return null;
  }
}

export function salvarRascunho(chave: string, valor: unknown): void {
  try {
    localStorage.setItem(chave, JSON.stringify(valor));
  } catch {
    /* localStorage cheio/indisponível: o rascunho é best-effort */
  }
}

export function limparRascunho(chave: string): void {
  try {
    localStorage.removeItem(chave);
  } catch {
    /* ignore */
  }
}
