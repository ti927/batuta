"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { type ChaveApiLer, type Organizacao, type PapelAcesso } from "@/lib/api";
import { GestaoChaves } from "@/components/gestao-chaves";
import { Aviso } from "@/components/ui/aviso";

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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/organizacoes/${organizacao.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        {organizacao.nome}
      </Link>
      <h1 className="mb-2 mt-2 text-2xl font-medium text-foreground">
        Chaves de IA
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
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
        <Aviso variant="atencao">
          Somente administradores desta organização podem ver e gerir as chaves de
          IA.
        </Aviso>
      )}
    </main>
  );
}
