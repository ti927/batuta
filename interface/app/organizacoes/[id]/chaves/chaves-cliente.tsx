"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import {
  type ChaveApiLer,
  type Credencial,
  type Organizacao,
  type PapelAcesso,
  type TipoCredencial,
} from "@/lib/api";
import { GestaoChaves } from "@/components/gestao-chaves";
import { CofreCredenciais } from "@/components/cofre-credenciais";
import { Aviso } from "@/components/ui/aviso";

export function ChavesCliente({
  organizacao,
  meuPapel,
  chaves,
  credenciais,
  tiposCredencial,
}: {
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  chaves: ChaveApiLer[];
  credenciais: Credencial[];
  tiposCredencial: TipoCredencial[];
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
        Chaves e credenciais
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Tudo num lugar só: as chaves de serviço da organização (usadas pelos
        modelos, pela IA de conversa e pelos instrumentos) e as credenciais de
        cada instrumento. Quando não há chave própria, o Batuta usa a chave-mãe da
        consultoria. Nenhum valor é reexibido depois de salvo.
      </p>

      {!souAdmin ? (
        <Aviso variant="atencao">
          Somente administradores desta organização podem ver e gerir as chaves e
          credenciais.
        </Aviso>
      ) : (
        <div className="flex flex-col gap-10">
          {/* Seção A — chaves de serviço (pool da organização) */}
          <section>
            <h2 className="mb-1 text-lg font-medium text-foreground">
              Chaves de serviço
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Uma chave por serviço, compartilhada por toda a organização. Os
              instrumentos que usam IA ou busca (gerar imagem, busca na web)
              reusam estas chaves automaticamente.
            </p>
            <GestaoChaves
              basePath={`/organizacoes/${organizacao.id}/chaves`}
              chavesIniciais={chaves}
            />
          </section>

          {/* Seção B — caixa-forte de credenciais nomeadas */}
          <section>
            <h2 className="mb-1 text-lg font-medium text-foreground">
              Credenciais
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Senhas e tokens nomeados (WordPress, banco de dados, bot do
              Telegram…) que os instrumentos usam. Crie aqui e aponte o
              instrumento para a credencial — para trocar, muda num lugar só. O
              valor secreto nunca é reexibido.
            </p>
            <CofreCredenciais
              credenciais={credenciais}
              tipos={tiposCredencial}
              organizacaoId={organizacao.id}
            />
          </section>
        </div>
      )}
    </main>
  );
}
