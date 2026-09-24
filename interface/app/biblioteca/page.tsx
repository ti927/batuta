import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { type Organizacao } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";
import { COOKIE_ORG_ATIVA } from "@/lib/org-ativa";
import { AreaEmBreve } from "@/components/area-em-breve";

// O endereço antigo da Biblioteca: ela virou parte do Cérebro da organização. Leva ao
// cérebro da organização ativa (a mesma do menu).
export default async function BibliotecaPage() {
  const orgCookie = (await cookies()).get(COOKIE_ORG_ATIVA)?.value;
  const resp = await buscarCerebro("/organizacoes");
  const organizacoes: Organizacao[] = resp.ok ? await resp.json() : [];
  const org = organizacoes.find((o) => o.id === orgCookie) ?? organizacoes[0];
  if (org) redirect(`/organizacoes/${org.id}/cerebro`);
  return (
    <AreaEmBreve titulo="Cérebro">
      Você ainda não participa de nenhuma organização. Quando participar, o cérebro dela aparece aqui.
    </AreaEmBreve>
  );
}
