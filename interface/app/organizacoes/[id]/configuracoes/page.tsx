import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import {
  type ModelosDisponiveis,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { SeletorModeloConversa } from "@/components/seletor-modelo-conversa";
import { Aviso } from "@/components/ui/aviso";

import { ParedeSwitch } from "./parede-switch";

async function carregar(organizacaoId: string): Promise<{
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  disponiveis: ModelosDisponiveis | null;
} | null> {
  const [respOrg, eu] = await Promise.all([
    buscarCerebro(`/organizacoes/${organizacaoId}`),
    buscarMeuAcesso(),
  ]);
  if (respOrg.status === 404) return null;
  if (!respOrg.ok) throw new Error("Falha ao carregar a organização");

  const organizacao: Organizacao = await respOrg.json();
  const meuPapel = eu?.papeis[organizacaoId] ?? null;

  let disponiveis: ModelosDisponiveis | null = null;
  if (meuPapel === "admin") {
    const resp = await buscarCerebro(
      `/organizacoes/${organizacaoId}/modelos-disponiveis`,
    );
    if (resp.ok) disponiveis = await resp.json();
  }
  return { organizacao, meuPapel, disponiveis };
}

export default async function ConfiguracoesOrgPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  const souAdmin = dados.meuPapel === "admin";

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/organizacoes/${id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        {dados.organizacao.nome}
      </Link>
      <h1 className="mb-2 mt-2 text-2xl font-medium text-foreground">
        Configurações da organização
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Ajustes que valem para toda a organização.
      </p>

      {!souAdmin ? (
        <Aviso variant="atencao">
          Somente administradores desta organização podem ver e mudar as
          configurações.
        </Aviso>
      ) : (
        <div className="flex flex-col gap-10">
          <ParedeSwitch
            organizacaoId={id}
            ativada={dados.organizacao.parede_ativacao}
          />
          <SeletorModeloConversa
            organizacaoId={id}
            modeloAtual={dados.organizacao.modelo_criadora}
            disponiveis={dados.disponiveis ?? {}}
          />
        </div>
      )}
    </main>
  );
}
