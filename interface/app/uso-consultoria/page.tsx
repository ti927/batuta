import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { type UsoAgrupado, type UsoConsultoria } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { rotuloCategoria } from "@/lib/uso";
import { Aviso } from "@/components/ui/aviso";

async function carregar(): Promise<{
  adminConsultoria: boolean;
  uso: UsoConsultoria | null;
}> {
  const eu = await buscarMeuAcesso();
  const adminConsultoria = eu?.admin_consultoria ?? false;
  let uso: UsoConsultoria | null = null;
  if (adminConsultoria) {
    const resp = await buscarCerebro("/uso/consultoria");
    if (resp.ok) uso = await resp.json();
  }
  return { adminConsultoria, uso };
}

function dolar(v: number): string {
  return `~US$ ${v.toFixed(2)}`;
}

function tokens(v: number): string {
  return v.toLocaleString("pt-BR");
}

// Quebra por função (categoria): onde a chave-mãe foi gasta. Ordena da maior para
// a menor; oculta as categorias zeradas.
function PorCategoria({ dados }: { dados: Record<string, UsoAgrupado> }) {
  const linhas = Object.entries(dados ?? {})
    .filter(([, u]) => u.custo_usd > 0)
    .sort((a, b) => b[1].custo_usd - a[1].custo_usd);
  if (linhas.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1">
      {linhas.map(([categoria, u]) => (
        <li
          key={categoria}
          className="flex items-center justify-between gap-2 text-xs"
        >
          <span className="text-muted-foreground">
            {rotuloCategoria(categoria)}
          </span>
          <span className="text-foreground">{dolar(u.custo_usd)}</span>
        </li>
      ))}
    </ul>
  );
}

export default async function UsoConsultoriaPage() {
  const { adminConsultoria, uso } = await carregar();
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href="/organizacoes"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Organizações
      </Link>
      <h1 className="mb-2 mt-2 text-2xl font-medium text-foreground">
        Uso da consultoria
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        O consumo que saiu da <span className="font-medium">chave-mãe</span> da
        consultoria — ou seja, o que a consultoria pagou por organizações sem chave
        própria. Separado por <span className="font-medium">função</span>: execução
        de agentes, IA de conversa, atendimento (mensageria) e transcrição de áudio.
        Valores estimados.
      </p>

      {!adminConsultoria ? (
        <Aviso variant="atencao">
          Esta área é restrita aos administradores da consultoria.
        </Aviso>
      ) : !uso || uso.por_organizacao.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhum consumo na chave-mãe da consultoria até agora.
        </p>
      ) : (
        <>
          {/* Total */}
          <div className="mb-6 rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Total na chave-mãe</p>
            <p className="text-2xl font-medium text-foreground">
              {dolar(uso.total.custo_usd)}
            </p>
            <p className="text-xs text-muted-foreground">
              {tokens(uso.total.tokens_entrada)} tokens de entrada ·{" "}
              {tokens(uso.total.tokens_saida)} de saída
            </p>
            <div className="mt-3 border-t border-border pt-3">
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Por função
              </p>
              <PorCategoria dados={uso.total.por_categoria} />
            </div>
          </div>

          {/* Por organização — cada uma com a quebra por função */}
          <p className="mb-2 text-sm font-medium text-foreground">
            Por organização
          </p>
          <div className="space-y-3">
            {uso.por_organizacao.map((o) => (
              <div
                key={o.organizacao_id}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-foreground">
                    {o.organizacao_nome}
                  </span>
                  <span className="text-foreground">{dolar(o.custo_usd)}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {tokens(o.tokens_entrada + o.tokens_saida)} tokens
                </p>
                <PorCategoria dados={o.por_categoria} />
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
