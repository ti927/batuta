import Link from "next/link";
import { Building2, ListChecks } from "lucide-react";

import { Card } from "@/components/ui/card";
import { StatusCerebro } from "./status-cerebro";

const ATALHOS = [
  {
    href: "/organizacoes",
    titulo: "Organizações",
    descricao: "Seus times, agentes e instrumentos.",
    Icone: Building2,
  },
  {
    href: "/execucoes",
    titulo: "Execuções",
    descricao: "Acompanhe as automações que já rodaram.",
    Icone: ListChecks,
  },
];

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-medium text-foreground">
        Bem-vindo de volta ao Batuta.
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Você guia. A IA executa.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {ATALHOS.map(({ href, titulo, descricao, Icone }) => (
          <Link key={href} href={href} className="group">
            <Card className="flex h-full items-start gap-4 p-6 transition-colors group-hover:border-[#D6D3E8]">
              <span className="rounded-md bg-accent p-2 text-accent-foreground">
                <Icone className="size-5" />
              </span>
              <span>
                <span className="block font-medium text-foreground">
                  {titulo}
                </span>
                <span className="mt-0.5 block text-sm text-muted-foreground">
                  {descricao}
                </span>
              </span>
            </Card>
          </Link>
        ))}
      </div>

      <div className="mt-8">
        <StatusCerebro />
      </div>
    </main>
  );
}
