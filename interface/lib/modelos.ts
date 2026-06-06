// Modelos de IA por provedor (Fase 7-A) — espelha o registro do cérebro
// (cerebro/orquestracao/modelos_ia.py). Usado no seletor de modelo do agente
// (agrupado por provedor) e na escolha de provedor ao cadastrar uma chave.
// Lista crua; refina-se com o uso.

export const PROVEDORES = ["anthropic", "openai", "google"] as const;
export type Provedor = (typeof PROVEDORES)[number];

export const ROTULO_PROVEDOR: Record<Provedor, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI (GPT)",
  google: "Google (Gemini)",
};

export const MODELOS_POR_PROVEDOR: Record<Provedor, string[]> = {
  anthropic: ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"],
  openai: ["gpt-4.1", "gpt-4o", "gpt-4o-mini"],
  google: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
};
