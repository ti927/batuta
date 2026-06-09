import type { Metadata } from "next";
import { Bricolage_Grotesque, Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

import {
  type ConvitePendente,
  type MeuAcesso,
  type Organizacao,
  type Time,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { criarClienteServidor } from "@/lib/supabase/cliente-servidor";
import { CabecalhoConteudo } from "@/components/cabecalho-conteudo";
import { Sidebar } from "@/components/sidebar";
import { BannerConvites } from "./banner-convites";

// Inter é a fonte de interface (corpo, títulos internos, formulários). Só os
// pesos 400/500, como manda o DESIGN-SYSTEM (§5).
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500"],
});

// Bricolage Grotesque é a fonte de marca — usada só no logotipo "Batuta"
// (exposta como `font-heading`).
const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  weight: ["500", "600"],
});

// Monoespaçada reservada a trechos de dado cru (ex.: JSON de execuções).
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Batuta",
  description: "Você guia. A IA executa.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Quem está logado? (null na tela de login). Mostra a barra de sessão só
  // quando há usuário — o proxy.ts já garante que rotas protegidas têm sessão.
  const supabase = await criarClienteServidor();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Dados do shell (sidebar): convites pendentes, organizações do usuário, papéis e
  // os times de cada organização. Só quando há sessão (login/convite não têm shell).
  let pendentes: ConvitePendente[] = [];
  let organizacoes: Organizacao[] = [];
  let timesPorOrg: Record<string, Time[]> = {};
  let eu: MeuAcesso | null = null;
  if (user?.email) {
    const [respConv, respOrgs, acesso] = await Promise.all([
      buscarCerebro("/convites/pendentes"),
      buscarCerebro("/organizacoes"),
      buscarMeuAcesso(),
    ]);
    if (respConv.ok) pendentes = await respConv.json();
    organizacoes = respOrgs.ok ? await respOrgs.json() : [];
    eu = acesso;
    const listas = await Promise.all(
      organizacoes.map(async (o) => {
        const r = await buscarCerebro(`/organizacoes/${o.id}/times`);
        return [o.id, r.ok ? ((await r.json()) as Time[]) : []] as const;
      }),
    );
    timesPorOrg = Object.fromEntries(listas);
  }

  const logado = Boolean(user?.email);

  return (
    <html
      lang="pt-BR"
      className={`${inter.variable} ${bricolage.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* Casco travado na altura da tela. Logado: sidebar (esquerda) + coluna de
          conteúdo (header + área que rola por dentro). Sem sessão (login/convite):
          só o conteúdo. Telas de altura cheia (a conversa) preenchem e rolam por
          coluna; nenhuma página estica o documento inteiro. */}
      <body className="flex h-dvh flex-col overflow-hidden bg-background md:flex-row">
        {logado ? (
          <>
            <Sidebar
              email={user!.email!}
              organizacoes={organizacoes}
              timesPorOrg={timesPorOrg}
              papeis={eu?.papeis ?? {}}
              adminConsultoria={eu?.admin_consultoria ?? false}
            />
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
              <CabecalhoConteudo />
              <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
                {pendentes.length > 0 && (
                  <div className="mx-auto flex w-full max-w-6xl justify-center px-4 pt-4 sm:px-6">
                    <BannerConvites convites={pendentes} />
                  </div>
                )}
                {children}
              </div>
            </div>
          </>
        ) : (
          children
        )}
      </body>
    </html>
  );
}
