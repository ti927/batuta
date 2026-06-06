import type { Metadata } from "next";
import { Bricolage_Grotesque, Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

import { type ConvitePendente } from "@/lib/api";
import { buscarCerebro } from "@/lib/cerebro-servidor";
import { criarClienteServidor } from "@/lib/supabase/cliente-servidor";
import { BannerConvites } from "./banner-convites";
import { BarraSessao } from "./barra-sessao";

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

  // Convites pendentes para o usuário logado — o aviso aparece em TODA tela
  // autenticada (não só na home), pois é onde quer que ele caia que precisa ver.
  let pendentes: ConvitePendente[] = [];
  if (user?.email) {
    const resp = await buscarCerebro("/convites/pendentes");
    if (resp.ok) pendentes = await resp.json();
  }

  return (
    <html
      lang="pt-BR"
      className={`${inter.variable} ${bricolage.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {user?.email && <BarraSessao email={user.email} />}
        {pendentes.length > 0 && (
          <div className="flex justify-center px-4 pt-4">
            <BannerConvites convites={pendentes} />
          </div>
        )}
        {children}
      </body>
    </html>
  );
}
