// Provedores de IA e o catálogo de modelos (que vem do cérebro, ver `InfoModelo`).
// Usado nos seletores de modelo (agente, IA de conversa, instrumentos de IA) e na
// escolha de provedor ao cadastrar uma chave.

export const PROVEDORES = ["anthropic", "openai", "google"] as const;
export type Provedor = (typeof PROVEDORES)[number];

export const ROTULO_PROVEDOR: Record<Provedor, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI (GPT)",
  google: "Google (Gemini)",
};

// Serviços cuja chave a organização cadastra no pool: só os provedores de IA (as
// chaves de serviço de instrumento — Tavily, Exa, Firecrawl, fal.ai — saíram em
// 2026-10-01). Espelha cerebro/chaves.py SERVICOS.
export const SERVICOS = [
  "anthropic",
  "openai",
  "google",
] as const;
export type Servico = (typeof SERVICOS)[number];

export const ROTULO_SERVICO: Record<Servico, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI (GPT / imagens)",
  google: "Google (Gemini)",
};

// Em que funções cada serviço é usado — texto de ajuda na tela de chaves.
export const USADA_POR: Record<Servico, string> = {
  anthropic: "modelos dos agentes e IA de conversa",
  openai: "modelos, IA de conversa e transcrição de áudio",
  google: "modelos dos agentes e IA de conversa",
};

// ── O catálogo de modelos vem do cérebro (GET /modelos) ──────────────────────────
// Fonte única: `cerebro/orquestracao/ciclo_modelos.py`, com a situação e a data de
// saída de cada modelo. Até 2026-10-02 a tela tinha uma cópia própria da lista e da
// tabela de custo — e a cópia ficou velha (oferecia Gemini que o Google já tinha
// desligado). Agora a tela só lê.
export type InfoModelo = {
  id: string;
  provedor: Provedor;
  uso: "texto" | "imagem" | "video" | "transcricao";
  situacao: "ativo" | "descontinuado" | "desligado";
  sai_em: string | null; // AAAA-MM-DD
  substituto: string | null;
  alerta: string | null; // o aviso pronto, em português (null = nada a dizer)
  custo_mtok: [number, number] | null; // [entrada, saída] por 1M tokens (texto)
};

function fmtUSD(v: number): string {
  return v.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtData(iso: string): string {
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

// Os modelos de texto de um provedor que se podem escolher. Um modelo já desligado
// só aparece se for o valor ATUAL — para a pessoa ver o que está configurado e trocar.
export function modelosDoProvedor(
  catalogo: InfoModelo[],
  provedor: Provedor,
  atual?: string | null,
): InfoModelo[] {
  return catalogo.filter(
    (m) =>
      m.uso === "texto" &&
      m.provedor === provedor &&
      (m.situacao !== "desligado" || m.id === atual),
  );
}

// Rótulo no seletor: nome + custo aproximado por 1M tokens + o aviso de saída.
export function rotuloModelo(m: InfoModelo): string {
  const partes = [m.id];
  if (m.custo_mtok) {
    partes.push(
      `(entrada US$ ${fmtUSD(m.custo_mtok[0])} / saída US$ ${fmtUSD(m.custo_mtok[1])} por 1M)`,
    );
  }
  if (m.situacao === "desligado") partes.push("— desligado");
  else if (m.sai_em) partes.push(`— sai em ${fmtData(m.sai_em)}`);
  return partes.join(" ");
}

// Disponibilidade de provedor por chave (própria ou da consultoria), vinda do
// cérebro em GET /organizacoes/{id}/modelos-disponiveis. Só booleanos.
export type ProvedoresDisponiveis = Partial<Record<Provedor, boolean>>;

// O provedor de um modelo, pelo prefixo do nome (o mesmo critério do cérebro para
// modelos que ele não lista). Devolve null se não der para determinar.
export function provedorDoModelo(modelo: string): Provedor | null {
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
  "O padrão é o Claude Sonnet 5 (forte e econômico). Para o raciocínio mais " +
  "exigente, escolha o Claude Opus; e, quando houver chave, os modelos de topo de " +
  "OpenAI e Google.";
