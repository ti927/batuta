"use client";

import { usePathname } from "next/navigation";
import { CircleHelp } from "lucide-react";

// Header da área de conteúdo (handoff §5): 56px, branco, borda inferior. Mostra um
// rótulo da rota atual (breadcrumb v1: o nome amigável da seção, derivado do
// caminho — sem exigir o nome da entidade ainda) + "Como funciona" à direita.

function tituloDaRota(pathname: string): string {
  const p = pathname.replace(/\/+$/, "") || "/";
  const regras: [RegExp, string][] = [
    [/^\/$/, "Início"],
    [/^\/criar/, "Criar com a IA"],
    [/^\/execucoes/, "Execuções"],
    [/^\/biblioteca/, "Biblioteca"],
    [/^\/uso/, "Uso e custos"],
    [/^\/chaves-consultoria/, "Chaves da consultoria"],
    [/^\/configuracoes/, "Configurações"],
    [/^\/organizacoes\/[^/]+\/acesso/, "Acesso e papéis"],
    [/^\/organizacoes\/[^/]+\/chaves/, "Chaves de IA"],
    [/^\/organizacoes\/[^/]+$/, "Organização"],
    [/^\/organizacoes/, "Organizações"],
    [/^\/times\/[^/]+\/automacoes/, "Automações"],
    [/^\/times\/[^/]+\/instrumentos/, "Instrumentos"],
    [/^\/times/, "Time"],
    [/^\/automacoes/, "Execução"],
    [/^\/agentes/, "Agente"],
  ];
  for (const [re, rotulo] of regras) if (re.test(p)) return rotulo;
  return "Batuta";
}

export function CabecalhoConteudo() {
  const pathname = usePathname();
  return (
    <header className="hidden h-14 shrink-0 items-center justify-between border-b border-border bg-card px-5 md:flex">
      <span className="text-sm font-medium text-foreground">
        {tituloDaRota(pathname)}
      </span>
      <span
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground"
        title="Em breve"
      >
        <CircleHelp className="size-4" />
        <span className="hidden sm:inline">Como funciona</span>
      </span>
    </header>
  );
}
