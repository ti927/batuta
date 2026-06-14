import { notFound } from "next/navigation";

import { type ConversaComMensagens, type PapelAcesso, type Time } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { ConversaCliente } from "./conversa-cliente";

async function carregar(
  timeId: string,
  conversaId: string,
): Promise<{
  time: Time;
  conversa: ConversaComMensagens;
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respConv, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/conversas/${conversaId}`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404 || respConv.status === 404) return null;
  if (!respTime.ok || !respConv.ok) throw new Error("Falha ao carregar a conversa");
  const time: Time = await respTime.json();
  return {
    time,
    conversa: await respConv.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
  };
}

export default async function ConversaPage({
  params,
}: {
  params: Promise<{ id: string; conversaId: string }>;
}) {
  const { id, conversaId } = await params;
  const dados = await carregar(id, conversaId);
  if (!dados) notFound();
  return (
    <ConversaCliente
      time={dados.time}
      conversa={dados.conversa}
      meuPapel={dados.meuPapel}
    />
  );
}
