import { notFound } from "next/navigation";

import {
  type Agente,
  type Automacao,
  type Credencial,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";

import { AutomacoesCliente } from "./automacoes-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string): Promise<{
  time: Time;
  automacoes: Automacao[];
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  credenciaisInstagram: Credencial[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
} | null> {
  const [respTime, respAuto, respAg, respInst, respTipos, eu] = await Promise.all([
    buscarCerebro(`/times/${timeId}`),
    buscarCerebro(`/times/${timeId}/automacoes`),
    buscarCerebro(`/times/${timeId}/agentes`),
    buscarCerebro(`/times/${timeId}/instrumentos`),
    buscarCerebro(`/instrumentos/tipos`),
    buscarMeuAcesso(),
  ]);
  if (respTime.status === 404) return null;
  if (!respTime.ok || !respAuto.ok || !respAg.ok || !respInst.ok)
    throw new Error("Falha ao carregar automações");
  const time: Time = await respTime.json();
  const agentes: Agente[] = await respAg.json();
  // Contas do Instagram conectadas à organização — alimentam o seletor de conta
  // do gatilho "Comentário do Instagram". Só operador+ enxerga (jsonOu → [] se 403).
  const respCred = await buscarCerebro(
    `/organizacoes/${time.organizacao_id}/credenciais`,
  );
  const credenciaisInstagram = (
    await jsonOu<Credencial[]>(respCred, [])
  ).filter((c) => c.tipo === "instagram");
  // Cinto de cada agente — para o editor de agente (drawer) acionado pelo lápis
  // do nó gerir o cinto sem trocar de aba (mesmo padrão da aba Agentes).
  const cintosPares = await Promise.all(
    agentes.map(async (a) => {
      const r = await buscarCerebro(`/agentes/${a.id}/instrumentos`);
      return [a.id, await jsonOu<Instrumento[]>(r, [])] as const;
    }),
  );
  return {
    time,
    automacoes: await respAuto.json(),
    agentes,
    cintos: Object.fromEntries(cintosPares),
    instrumentos: await respInst.json(),
    credenciaisInstagram,
    tipos: await jsonOu<TipoInstrumento[]>(respTipos, []),
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
      cintos={dados.cintos}
      instrumentos={dados.instrumentos}
      credenciaisInstagram={dados.credenciaisInstagram}
      tipos={dados.tipos}
      meuPapel={dados.meuPapel}
    />
  );
}
