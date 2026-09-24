import { redirect } from "next/navigation";

// A tela clássica de Automações saiu em 2026-09-24 (o Estúdio assumiu a aba em 22/09). O
// endereço continua respondendo para quem tiver um link salvo: leva ao Estúdio.
export default async function AutomacoesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/times/${id}/estudio`);
}
