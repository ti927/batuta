// Ilustração da proporção (aspect ratio) de um campo de resolução: desenha um
// retângulo proporcional ao valor ("864x1536" ou "9:16") e um rótulo amigável
// (razão simplificada, orientação e dica de uso para formatos de Instagram).
// Puro/presentacional; se o valor não parsear (ex.: "(padrão)"), não renderiza nada.

const CAIXA = 48; // px — a moldura quadrada onde o retângulo fica centralizado
const MAX = 40; // px — o lado MAIOR do retângulo (o menor é proporcional)

function mdc(a: number, b: number): number {
  return b === 0 ? a : mdc(b, a % b);
}

// Dicas de uso das proporções mais comuns no Instagram (o resto usa só a orientação).
const NOTAS: Record<string, string> = {
  "9:16": "Story / Reels",
  "4:5": "Feed (retrato)",
  "1:1": "Feed (quadrado)",
};

export function IlustracaoProporcao({ valor }: { valor: string }) {
  // Aceita "LxA" (1536x864), "L×A" (com × unicode) ou "L:A" (9:16).
  const partes = (valor || "").split(/[x×:]/i);
  if (partes.length !== 2) return null;
  const l = Number(partes[0].trim());
  const a = Number(partes[1].trim());
  if (!Number.isFinite(l) || !Number.isFinite(a) || l <= 0 || a <= 0) return null;

  const maior = Math.max(l, a);
  const larguraCaixa = Math.max(4, Math.round((MAX * l) / maior));
  const alturaCaixa = Math.max(4, Math.round((MAX * a) / maior));

  const g = mdc(Math.round(l), Math.round(a)) || 1;
  const razao = `${Math.round(l / g)}:${Math.round(a / g)}`;
  const orientacao = l === a ? "quadrado" : l > a ? "paisagem" : "vertical";
  const nota = NOTAS[razao];

  return (
    <div className="flex items-center gap-2.5">
      <div
        className="flex shrink-0 items-center justify-center"
        style={{ width: CAIXA, height: CAIXA }}
        aria-hidden
      >
        <div
          className="rounded-[3px] border-2 border-primary/60 bg-primary/10"
          style={{ width: larguraCaixa, height: alturaCaixa }}
        />
      </div>
      <div className="text-xs leading-tight">
        <div className="font-medium text-foreground">
          {razao} · {orientacao}
        </div>
        {nota && <div className="text-muted-foreground">{nota}</div>}
      </div>
    </div>
  );
}
