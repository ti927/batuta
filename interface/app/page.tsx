import Link from "next/link";

import { type ConvitePendente } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";

import { BannerConvites } from "./banner-convites";
import { StatusCerebro } from "./status-cerebro";

export default async function Home() {
  // Convites pendentes para quem já tem conta (não recebe e-mail): mostra o
  // banner para aceitar aqui mesmo. Falha graciosa para [] se algo der errado.
  const resp = await buscarCerebro("/convites/pendentes");
  const pendentes: ConvitePendente[] = resp.ok ? await resp.json() : [];

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      {pendentes.length > 0 && <BannerConvites convites={pendentes} />}
      <h1 className="text-5xl font-bold tracking-tight">Batuta</h1>
      <p className="text-sm text-zinc-500">Você guia. A IA executa.</p>
      <StatusCerebro />
      <div className="mt-4 flex gap-4 text-sm">
        <Link
          href="/organizacoes"
          className="text-blue-600 underline underline-offset-4"
        >
          Organizações →
        </Link>
        <Link
          href="/execucoes"
          className="text-blue-600 underline underline-offset-4"
        >
          Execuções →
        </Link>
      </div>
    </main>
  );
}
