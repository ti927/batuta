import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { type UsoConsultoria } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
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
        própria. Inclui os agentes e a IA de conversa. Valores estimados.
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
          </div>

          {/* Por organização */}
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="p-3 font-medium">Organização</th>
                  <th className="p-3 text-right font-medium">Tokens</th>
                  <th className="p-3 text-right font-medium">Custo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {uso.por_organizacao.map((o) => (
                  <tr key={o.organizacao_id}>
                    <td className="p-3 text-foreground">{o.organizacao_nome}</td>
                    <td className="p-3 text-right text-muted-foreground">
                      {tokens(o.tokens_entrada + o.tokens_saida)}
                    </td>
                    <td className="p-3 text-right text-foreground">
                      {dolar(o.custo_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
