import Link from "next/link";

import { StatusCerebro } from "./status-cerebro";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-5xl font-bold tracking-tight">Batuta</h1>
      <p className="text-sm text-zinc-500">Você guia. A IA executa.</p>
      <StatusCerebro />
      <Link
        href="/organizacoes"
        className="mt-4 text-sm text-blue-600 underline underline-offset-4"
      >
        Organizações →
      </Link>
    </main>
  );
}
