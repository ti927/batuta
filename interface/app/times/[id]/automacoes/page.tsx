import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type Instrumento,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AutomacoesCliente } from "./automacoes-cliente";

async function carregar(timeId: string): Promise<{
  time: Time;
  automacoes: Automacao[];
  agentes: Agente[];
  instrumentos: Instrumento[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respAuto, respAg, respInst, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}/instrumentos`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAuto.ok || !respAg.ok || !respInst.ok)
    throw new Error("Falha ao carregar automações");
  const time: Time = await respTime.json();
  return {
    time,
    automacoes: await respAuto.json(),
    agentes: await respAg.json(),
    instrumentos: await respInst.json(),
    meuPapel: eu?.papeis[time.organizacao_id] ?? null,
  };
}

export default async function AutomacoesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();
  // Versão dos dados: muda quando a cadeia/ativa ou a lista de agentes mudam (ex.:
  // a IA edita o time pelo painel lateral). Como `key`, força o editor (que guarda a
  // cadeia em estado local) a remontar com os dados frescos após o router.refresh —
  // some o "nó órfão fantasma" de uma view desatualizada. Só remonta quando o dado
  // PERSISTIDO muda, então não descarta uma edição manual em andamento.
  const versao =
    JSON.stringify(dados.automacoes.map((a) => [a.id, a.ativa, a.cadeia])) +
    "::" +
    dados.agentes.map((a) => a.id).join(",");
  return (
    <AutomacoesCliente
      key={versao}
      time={dados.time}
      inicial={dados.automacoes}
      agentes={dados.agentes}
      instrumentos={dados.instrumentos}
      meuPapel={dados.meuPapel}
    />
  );
}
