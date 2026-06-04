import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { criarClienteServidor } from "@/lib/supabase/cliente-servidor";
import { BarraSessao } from "./barra-sessao";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

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

  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {user?.email && <BarraSessao email={user.email} />}
        {children}
      </body>
    </html>
  );
}
