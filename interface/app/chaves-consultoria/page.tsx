import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { type ChaveApiLer } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { Aviso } from "@/components/ui/aviso";

import { ConsultoriaCliente } from "./consultoria-cliente";

async function carregar(): Promise<{
  adminConsultoria: boolean;
  chaves: ChaveApiLer[];
}> {
  const eu = await buscarMeuAcesso();
  const adminConsultoria = eu?.admin_consultoria ?? false;
  let chaves: ChaveApiLer[] = [];
  if (adminConsultoria) {
    const respChaves = await buscarCerebro("/chaves-consultoria");
    if (respChaves.ok) chaves = await respChaves.json();
  }
  return { adminConsultoria, chaves };
}

export default async function ChavesConsultoriaPage() {
  const { adminConsultoria, chaves } = await carregar();
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
        Chaves de IA da consultoria
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Uma chave por IA. Marque como compartilhável a que pode servir às
        organizações que não têm chave própria.
      </p>

      {adminConsultoria ? (
        <ConsultoriaCliente chaves={chaves} />
      ) : (
        <Aviso variant="atencao">
          Esta área é restrita aos administradores da consultoria.
        </Aviso>
      )}
    </main>
  );
}
