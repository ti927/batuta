import { notFound } from "next/navigation";

import {
  type Agente,
  type ConversaCriacaoResumo,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AgentesCliente } from "./agentes-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
  conversaId: string | null;
} | null> {
  const [respTime, respAgentes, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAgentes.ok) throw new Error("Falha ao carregar o time");
  const time: Time = await respTime.json();
  const agentes = await jsonOu<Agente[]>(respAgentes, []);

  // Cinto de cada agente, instrumentos do time, o catálogo de tipos (p/ o editor
  // de instrumento aberto pelo badge) e a conversa (eterna) — para os drawers.
  const [cintosPares, instrumentosResp, tiposResp, conversasResp] = await Promise.all([
    Promise.all(
      agentes.map(async (a) => {
        const r = await buscarCerebro(`/agentes/${a.id}/instrumentos`);
        return [a.id, await jsonOu<Instrumento[]>(r, [])] as const;
      }),
    ),
    buscarCerebro(`/times/${timeId}/instrumentos`),
    buscarCerebro(`/instrumentos/tipos`),
    buscarCerebro(`/organizacoes/${time.organizacao_id}/conversas-criacao`),
  ]);

  const conversas = await jsonOu<ConversaCriacaoResumo[]>(conversasResp, []);
  return {
    time,
    agentes,
    cintos: Object.fromEntries(cintosPares),
    instrumentos: await jsonOu<Instrumento[]>(instrumentosResp, []),
    tipos: await jsonOu<TipoInstrumento[]>(tiposResp, []),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
    conversaId: conversas.find((c) => c.time_id === timeId)?.id ?? null,
  };
}

export default async function AgentesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  // Versão dos dados: muda quando a IA (pelo painel) adiciona/remove/edita um agente
  // ou mexe num cinto. Como `key`, remonta a aba com os dados frescos após o
  // router.refresh (a lista vive em estado local). Ver automacoes/page.tsx.
  const versao =
    JSON.stringify(
      dados.agentes.map((a) => [a.id, a.nome, a.papel, a.modelo_ia]),
    ) +
    "::" +
    Object.entries(dados.cintos)
      .map(([k, v]) => `${k}:${v.map((i) => i.id).join(",")}`)
      .join("|");
  return (
    <AgentesCliente
      key={versao}
      time={dados.time}
      inicial={dados.agentes}
      cintos={dados.cintos}
      instrumentos={dados.instrumentos}
      tipos={dados.tipos}
      meuPapel={dados.meuPapel}
      conversaId={dados.conversaId}
    />
  );
}
