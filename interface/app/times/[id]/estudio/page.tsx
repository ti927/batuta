// ESTÚDIO — a tela do fluxo, em desenvolvimento PARALELO.
//
// Não substitui nem toca a aba "Automações", que segue no ar exatamente como estava:
// esta é uma segunda porta para o mesmo dado, onde o desenho mostra as condições nos
// fios, lista as saídas dentro dos cartões e se confere sozinho. Enquanto ela não for
// exaurida em teste, as duas convivem.
//
// Carrega o mesmo que a tela clássica (deliberadamente: se as duas leem o mesmo, não
// há como uma mostrar uma verdade que a outra não vê).

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

import { EstudioCliente } from "./estudio-cliente";

async function jsonOu<T>(resp: Response, padrao: T): Promise<T> {
  return resp.ok ? ((await resp.json()) as T) : padrao;
}

async function carregar(timeId: string) {
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
    throw new Error("Falha ao carregar o estúdio");

  const time: Time = await respTime.json();
  const agentes: Agente[] = await respAg.json();

  const respCred = await buscarCerebro(
    `/organizacoes/${time.organizacao_id}/credenciais`,
  );
  const credenciaisInstagram = (await jsonOu<Credencial[]>(respCred, [])).filter(
    (c) => c.tipo === "instagram",
  );

  // O cinto de cada agente é o que diz se um passo PARA e pergunta a alguém — é
  // daqui que sai metade dos avisos do desenho. Sem ele a tela mentiria por omissão.
  const cintosPares = await Promise.all(
    agentes.map(async (a) => {
      const r = await buscarCerebro(`/agentes/${a.id}/instrumentos`);
      return [a.id, await jsonOu<Instrumento[]>(r, [])] as const;
    }),
  );

  return {
    time,
    automacoes: (await respAuto.json()) as Automacao[],
    agentes,
    cintos: Object.fromEntries(cintosPares) as Record<string, Instrumento[]>,
    instrumentos: (await respInst.json()) as Instrumento[],
    credenciaisInstagram,
    tipos: await jsonOu<TipoInstrumento[]>(respTipos, []),
    meuPapel: (eu?.papeis[time.organizacao_id] ?? null) as PapelAcesso | null,
  };
}

export default async function EstudioPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dados = await carregar(id);
  if (!dados) notFound();

  // Mesma regra da tela clássica: a `key` remonta o editor quando o dado PERSISTIDO
  // muda (a IA criadora editou o time por fora, por exemplo), sem descartar edição
  // manual em andamento.
  // `configuracao` e `configuracao_gatilho` entram na conta: elas passaram a ser
  // editáveis aqui, e uma assinatura que as ignore faz o editor não remontar depois de
  // salvá-las — a tela mostraria o valor antigo como se o salvamento não tivesse
  // acontecido. Os agentes entram com o `atualizado_em` porque a aba "Ritmo e espera"
  // mora no popup deles e o painel do fluxo mostra quem já sobrepõe o padrão.
  const versao =
    JSON.stringify(
      dados.automacoes.map((a) => [
        a.id,
        a.ativa,
        a.cadeia,
        a.configuracao,
        a.configuracao_gatilho,
      ]),
    ) +
    "::" +
    dados.agentes.map((a) => `${a.id}@${a.atualizado_em}`).join(",");

  return (
    <EstudioCliente
      versao={versao}
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
