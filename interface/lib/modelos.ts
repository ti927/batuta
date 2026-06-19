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

// Serviços cuja chave a organização cadastra no pool ("Chaves de serviço"): os
// provedores de modelo + serviços compartilháveis de instrumento (Tavily/busca).
// Separado de PROVEDORES de propósito — Tavily NÃO é provedor de modelo (não entra
// no seletor de modelo do agente). Espelha cerebro/chaves.py SERVICOS.
export const SERVICOS = [
  "anthropic",
  "openai",
  "google",
  "tavily",
  "exa",
  "firecrawl",
] as const;
export type Servico = (typeof SERVICOS)[number];

export const ROTULO_SERVICO: Record<Servico, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI (GPT / imagens)",
  google: "Google (Gemini)",
  tavily: "Tavily (busca e leitura na web)",
  exa: "Exa (busca semântica)",
  firecrawl: "Firecrawl (leitura de sites)",
};

// Em que funções cada serviço é usado — texto de ajuda na tela de chaves.
export const USADA_POR: Record<Servico, string> = {
  anthropic: "modelos dos agentes e IA de conversa",
  openai: "modelos, IA de conversa, transcrição de áudio e geração de imagem",
  google: "modelos dos agentes e IA de conversa",
  tavily: "busca na web e leitura de sites dos agentes",
  exa: "busca na web (semântica) dos agentes",
  firecrawl: "leitura de sites dos agentes",
};

export const MODELOS_POR_PROVEDOR: Record<Provedor, string[]> = {
  anthropic: ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"],
  openai: ["gpt-4.1", "gpt-4o", "gpt-4o-mini"],
  google: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
};

// Disponibilidade de provedor por chave (própria ou da consultoria), vinda do
// cérebro em GET /organizacoes/{id}/modelos-disponiveis. Só booleanos.
export type ProvedoresDisponiveis = Partial<Record<Provedor, boolean>>;

// O provedor de um modelo (espelha o cérebro): lista conhecida + inferência por
// prefixo. Devolve null se não der para determinar.
export function provedorDoModelo(modelo: string): Provedor | null {
  for (const p of PROVEDORES) {
    if (MODELOS_POR_PROVEDOR[p].includes(modelo)) return p;
  }
  const m = modelo.toLowerCase();
  if (m.startsWith("claude")) return "anthropic";
  if (m.startsWith("gpt") || /^o[134]/.test(m)) return "openai";
  if (m.startsWith("gemini")) return "google";
  return null;
}

// Os provedores a oferecer num seletor: os que têm chave. `incluir` garante que o
// provedor de um modelo já escolhido continue visível, mesmo sem chave (não some o
// valor atual). Quando a disponibilidade ainda não carregou (undefined), mostra
// todos — comportamento seguro de fallback.
export function provedoresParaSeletor(
  disp: ProvedoresDisponiveis | undefined,
  incluir?: Provedor | null,
): Provedor[] {
  if (!disp) return [...PROVEDORES];
  return PROVEDORES.filter((p) => disp[p] || p === incluir);
}

// Observação mostrada no seletor de modelo da IA de conversa (decisão do maestro).
export const NOTA_MODELO_CONVERSA =
  "Para a IA de conversa, prefira modelos de raciocínio profundo (ex.: Claude Opus; " +
  "e, quando houver chave, os modelos de topo de OpenAI e Google).";
