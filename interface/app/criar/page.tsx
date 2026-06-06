import { type Organizacao } from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { podeOperar } from "@/lib/permissoes";

import { IniciarCliente } from "./iniciar-cliente";

// Server Component: lista as organizações em que o usuário pode operar (criar é
// operação de operador+). A IA criadora monta o time dentro de uma organização.
async function carregar(): Promise<Organizacao[]> {
  const [resp, eu] = await Promise.all([
    buscarCerebro("/organizacoes"),
    buscarMeuAcesso(),
  ]);
  const organizacoes: Organizacao[] = resp.ok ? await resp.json() : [];
  const papeis = eu?.papeis ?? {};
  return organizacoes.filter((o) => podeOperar(papeis[o.id]));
}

export default async function CriarPage() {
  const organizacoes = await carregar();
  return <IniciarCliente organizacoes={organizacoes} />;
}
