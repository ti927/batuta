"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import {
  type ChaveApiLer,
  type CredencialInstrumento,
  type ModelosDisponiveis,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { GestaoChaves } from "@/components/gestao-chaves";
import { InventarioCredenciais } from "@/components/inventario-credenciais";
import { SeletorModeloConversa } from "@/components/seletor-modelo-conversa";
import { Aviso } from "@/components/ui/aviso";

export function ChavesCliente({
  organizacao,
  meuPapel,
  chaves,
  disponiveis,
  credenciais,
}: {
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  chaves: ChaveApiLer[];
  disponiveis: ModelosDisponiveis | null;
  credenciais: CredencialInstrumento[];
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
            <SeletorModeloConversa
              organizacaoId={organizacao.id}
              modeloAtual={organizacao.modelo_criadora}
              disponiveis={disponiveis?.criadora ?? {}}
            />
          </section>

          {/* Seção B — credenciais por-instância dos instrumentos */}
          <section>
            <h2 className="mb-1 text-lg font-medium text-foreground">
              Credenciais de instrumentos
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              As senhas e tokens presos a um instrumento específico (WordPress,
              bot do Telegram, banco de dados…). Rotacione qualquer uma aqui se
              vazar — sem precisar abrir o instrumento.
            </p>
            <InventarioCredenciais credenciais={credenciais} />
          </section>
        </div>
      )}
    </main>
  );
}
