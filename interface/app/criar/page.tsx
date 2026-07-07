import { cookies } from "next/headers";
import Link from "next/link";
import { MessageSquare, Sparkles } from "lucide-react";

import {
  type ConversaCriacaoResumo,
  type Organizacao,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { COOKIE_ORG_ATIVA } from "@/lib/org-ativa";
import { podeOperar } from "@/lib/permissoes";

import { IniciarCliente } from "./iniciar-cliente";

type ConversaComOrg = ConversaCriacaoResumo & { organizacao_nome: string };

// Server Component: lista as organizações em que o usuário pode operar (criar é
// operação de operador+) e as conversas existentes de cada uma, para retomar um
// projeto. A IA criadora monta o time dentro de uma organização.
async function carregar(): Promise<{
  operaveis: Organizacao[];
  conversas: ConversaComOrg[];
}> {
  const [resp, eu] = await Promise.all([
    buscarCerebro("/organizacoes"),
    buscarMeuAcesso(),
  ]);
  const organizacoes: Organizacao[] = resp.ok ? await resp.json() : [];
  const papeis = eu?.papeis ?? {};
  const operaveis = organizacoes.filter((o) => podeOperar(papeis[o.id]));

  const listas = await Promise.all(
    operaveis.map(async (o) => {
      const r = await buscarCerebro(`/organizacoes/${o.id}/conversas-criacao`);
      const cs: ConversaCriacaoResumo[] = r.ok ? await r.json() : [];
      return cs.map((c) => ({ ...c, organizacao_nome: o.nome }));
    }),
  );
  const conversas = listas
    .flat()
    .sort((a, b) => b.atualizado_em.localeCompare(a.atualizado_em));
  return { operaveis, conversas };
}

function formatarData(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
    });
  } catch {
    return "";
  }
}

export default async function CriarPage() {
  const { operaveis, conversas } = await carregar();
  const temConversas = conversas.length > 0;

  // Mesma fonte única da sidebar (cookie): a org ativa vira o padrão do seletor,
  // validada contra as organizações onde este usuário pode operar.
  const orgCookie = (await cookies()).get(COOKIE_ORG_ATIVA)?.value;
  const orgInicial = operaveis.some((o) => o.id === orgCookie)
    ? orgCookie!
    : (operaveis[0]?.id ?? "");

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6">
      <IniciarCliente
        organizacoes={operaveis}
        orgInicial={orgInicial}
        compacto={temConversas}
      />

      {temConversas && (
        <section className="mt-12">
          <h2 className="font-heading text-xl font-semibold text-foreground">
            Continuar um projeto
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Retome uma conversa com a IA — ela lembra de onde vocês pararam.
          </p>
          <ul className="mt-5 space-y-2.5">
            {conversas.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/criar/${c.id}`}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3.5 transition-all hover:border-[#D6D3E8] hover:shadow-sm"
                >
                  <span
                    className="flex size-9 shrink-0 items-center justify-center rounded-md text-white"
                    style={{ background: "linear-gradient(135deg,#6D4AFF,#8A6BFF)" }}
                  >
                    <Sparkles className="size-4.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-foreground">
                      {c.time_nome ?? c.titulo ?? "Time ainda sem nome"}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {operaveis.length > 1 && <>{c.organizacao_nome} · </>}
                      atualizada em {formatarData(c.atualizado_em)}
                    </span>
                  </span>
                  <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
