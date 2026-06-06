import Link from "next/link";

import { type ChaveApiLer } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ConsultoriaCliente } from "./consultoria-cliente";

async function carregar(): Promise<{
  adminConsultoria: boolean;
  chaves: ChaveApiLer[];
}> {
  const eu = await buscarMeuAcesso();
  const adminConsultoria = eu?.admin_consultoria ?? false;
  let chaves: ChaveApiLer[] = [];
  if (adminConsultoria) {
    const resp = await buscarCerebro("/chaves-consultoria");
    if (resp.ok) chaves = await resp.json();
  }
  return { adminConsultoria, chaves };
}

export default async function ChavesConsultoriaPage() {
  const { adminConsultoria, chaves } = await carregar();
  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <div className="mb-1 text-sm">
        <Link
          href="/organizacoes"
          className="text-blue-600 underline underline-offset-4"
        >
          ← Organizações
        </Link>
      </div>
      <h1 className="mb-2 text-2xl font-bold">Chave-mãe da consultoria</h1>
      <p className="mb-6 text-sm text-zinc-500">
        A chave padrão usada quando uma organização não tem chave própria. Vale
        para todas as organizações como fallback.
      </p>

      {adminConsultoria ? (
        <ConsultoriaCliente chaves={chaves} />
      ) : (
        <p className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
          Esta área é restrita aos administradores da consultoria.
        </p>
      )}
    </main>
  );
}
