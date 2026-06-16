import Link from "next/link";
import { notFound } from "next/navigation";
import { Sparkles } from "lucide-react";

import {
  type ConversaCriacaoResumo,
  type PapelAcesso,
  type Time,
  type TimeResumo,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { podeOperar } from "@/lib/permissoes";
import { BarraAbasTime } from "@/components/barra-abas-time";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  resumo: TimeResumo | null;
  meuPapel: PapelAcesso | null;
  conversaId: string | null;
} | null> {
  const [respTime, respResumo, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/resumo`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok) throw new Error("Falha ao carregar o time");

  const time: Time = await respTime.json();
  const resumo: TimeResumo | null = respResumo.ok ? await respResumo.json() : null;
  const meuPapel = eu?.papeis[time.organizacao_id] ?? null;

  // A conversa (eterna) da IA criadora que mantém este time, para o botão
  // "Conversar sobre o projeto" cair na conversa certa (ou abrir uma nova).
  const respConversas = await buscarCerebro(
    `/organizacoes/${time.organizacao_id}/conversas-criacao`,
  );
  const conversas = await jsonOu<ConversaCriacaoResumo[]>(respConversas, []);
  const conversaId = conversas.find((c) => c.time_id === timeId)?.id ?? null;

  return { time, resumo, meuPapel, conversaId };
}

export default async function TimeLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  const { time, resumo, meuPapel, conversaId } = dados;
  const souOperador = podeOperar(meuPapel);
  const ativo = resumo?.ativo ?? false;

  return (
    <>
      {/* Cabeçalho persistente + barra de abas: ficam fixos no topo enquanto o
          conteúdo da aba rola por baixo. O usuário nunca "sai" do time. */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto w-full max-w-[1000px] px-5 pt-6 sm:px-8">
          <div className="flex flex-wrap items-start gap-4">
            <div className="min-w-60 flex-1">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="font-heading text-[23px] font-medium leading-tight text-foreground">
                  {time.nome}
                </h1>
                <Badge variant={ativo ? "success" : "neutral"}>
                  {ativo ? "ativo" : "em repouso"}
                </Badge>
              </div>
              {time.descricao && (
                <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">
                  {time.descricao}
                </p>
              )}
            </div>
            {souOperador && (
              <Link
                href={conversaId ? `/criar/${conversaId}` : "/criar"}
                className={buttonVariants({ variant: "outline" })}
              >
                <Sparkles className="size-4 text-primary" />
                Conversar sobre o projeto
              </Link>
            )}
          </div>

          <div className="mt-4">
            <BarraAbasTime
              timeId={time.id}
              contagens={{
                agentes: resumo?.agentes ?? 0,
                instrumentos: resumo?.instrumentos ?? 0,
                automacoes: resumo?.automacoes ?? 0,
                execucoes: resumo?.execucoes ?? 0,
                conversas: resumo?.conversas ?? 0,
              }}
              alertaConversas={(resumo?.conversas_em_andamento ?? 0) > 0}
              alertaExecucoes={(resumo?.pendencias ?? 0) > 0}
            />
          </div>
        </div>
      </div>

      {children}
    </>
  );
}
