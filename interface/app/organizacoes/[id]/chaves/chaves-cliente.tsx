"use client";

import Link from "next/link";

import { type ChaveApiLer, type Organizacao, type PapelAcesso } from "@/lib/api";
import { GestaoChaves } from "@/components/gestao-chaves";

export function ChavesCliente({
  organizacao,
  meuPapel,
  chaves,
}: {
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  chaves: ChaveApiLer[];
}) {
  const souAdmin = meuPapel === "admin";

  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <div className="mb-1 text-sm">
        <Link
          href={`/organizacoes/${organizacao.id}`}
          className="text-blue-600 underline underline-offset-4"
        >
          ← {organizacao.nome}
        </Link>
      </div>
      <h1 className="mb-2 text-2xl font-bold">Chaves de IA</h1>
      <p className="mb-6 text-sm text-zinc-500">
        As chaves de API que esta organização usa. Quando não há chave própria, o
        Batuta usa a chave-mãe da consultoria. O valor nunca é reexibido depois de
        salvo.
      </p>

      {souAdmin ? (
        <GestaoChaves
          basePath={`/organizacoes/${organizacao.id}/chaves`}
          chavesIniciais={chaves}
        />
      ) : (
        <p className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
          Somente administradores desta organização podem ver e gerir as chaves de
          IA.
        </p>
      )}
    </main>
  );
}
