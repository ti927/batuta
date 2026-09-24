"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  Home,
  Inbox,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Contagens = {
  agentes: number;
  instrumentos: number;
  automacoes: number;
  execucoes: number;
  conversas: number;
};

type Aba = {
  chave: string;
  rotulo: string;
  Icone: LucideIcon;
  segmento: string; // "" = Início; senão o sufixo da rota
  contador?: number;
  alerta?: boolean;
  etiqueta?: string; // pílula fixa ao lado do rótulo (ex.: "novo")
};

/**
 * Barra de abas da página do time. Cada aba é uma rota real (deep-link + voltar do
 * navegador funcionam); a ativa vem da URL via `usePathname`, não de estado local.
 * Contadores e pontos de alerta chegam prontos do resumo do time (Server Component).
 */
export function BarraAbasTime({
  timeId,
  contagens,
  alertaConversas = false,
  alertaExecucoes = false,
}: {
  timeId: string;
  contagens: Contagens;
  alertaConversas?: boolean;
  alertaExecucoes?: boolean;
}) {
  const pathname = usePathname();
  const base = `/times/${timeId}`;
  const resto = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  // "" → Início; "/agentes/123" → "agentes".
  const ativa = resto === "" || resto === "/" ? "inicio" : resto.split("/")[1];

  const abas: Aba[] = [
    { chave: "inicio", rotulo: "Início", Icone: Home, segmento: "" },
    {
      chave: "agentes",
      rotulo: "Agentes",
      Icone: Bot,
      segmento: "/agentes",
      contador: contagens.agentes,
    },
    {
      chave: "instrumentos",
      rotulo: "Instrumentos",
      Icone: Wrench,
      segmento: "/instrumentos",
      contador: contagens.instrumentos,
    },
    // A aba "Automações" SAIU da barra em 2026-09-22, quando o Estúdio alcançou
    // paridade (ligar/desligar, rodar, criar, duplicar, excluir, agendamentos, testar
    // um passo) e passou a ser a tela melhor: a condição aparece no fio, o cartão
    // lista as saídas e o desenho se confere sozinho.
    //
    // A tela clássica foi APAGADA em 2026-09-24, depois do teste ao vivo do Estúdio
    // (decisão do maestro). A rota `/times/[id]/automacoes` só redireciona ao Estúdio,
    // para links salvos não caírem numa página quebrada.
    {
      chave: "estudio",
      rotulo: "Automações",
      Icone: Workflow,
      segmento: "/estudio",
    },
    {
      chave: "execucoes",
      rotulo: "Execuções",
      Icone: Activity,
      segmento: "/execucoes",
      contador: contagens.execucoes,
      alerta: alertaExecucoes,
    },
    {
      chave: "conversas",
      rotulo: "Conversas",
      Icone: Inbox,
      segmento: "/conversas",
      contador: contagens.conversas,
      alerta: alertaConversas,
    },
  ];

  return (
    <nav
      aria-label="Seções do time"
      className="-mb-px flex gap-1 overflow-x-auto border-b border-border"
    >
      {abas.map((aba) => {
        const ativaAba = ativa === aba.chave;
        return (
          <Link
            key={aba.chave}
            href={base + aba.segmento}
            aria-current={ativaAba ? "page" : undefined}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors",
              ativaAba
                ? "border-primary font-medium text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <aba.Icone className="size-4" />
            {aba.rotulo}
            {aba.contador !== undefined && aba.contador > 0 && (
              <span
                className={cn(
                  "rounded-full px-1.5 py-0.5 text-[0.7rem] leading-none",
                  ativaAba
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {aba.contador}
              </span>
            )}
            {aba.etiqueta && (
              <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[0.65rem] font-medium leading-none text-primary">
                {aba.etiqueta}
              </span>
            )}
            {aba.alerta && (
              <span
                aria-hidden
                className="size-1.5 rounded-full bg-primary"
                title="Há algo pedindo atenção"
              />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
