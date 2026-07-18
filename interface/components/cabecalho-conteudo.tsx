"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CircleHelp } from "lucide-react";

// Header da área de conteúdo (handoff §5): 56px, branco, borda inferior. Mostra um
// rótulo da rota atual (breadcrumb v1: o nome amigável da seção, derivado do
// caminho — sem exigir o nome da entidade ainda) + "Como funciona" à direita, que
// leva à Central de Conhecimento (/ajuda) — o manual do Batuta.

function tituloDaRota(pathname: string): string {
  const p = pathname.replace(/\/+$/, "") || "/";
  const regras: [RegExp, string][] = [
    [/^\/$/, "Início"],
    [/^\/criar/, "Criar com a IA"],
    [/^\/biblioteca/, "Biblioteca"],
    [/^\/uso-consultoria/, "Uso da consultoria"],
    [/^\/uso/, "Uso e custos"],
    [/^\/chaves-consultoria/, "Chaves da consultoria"],
    [/^\/configuracoes-consultoria/, "Configurações da consultoria"],
    [/^\/organizacoes\/[^/]+\/acesso/, "Acesso e papéis"],
    [/^\/organizacoes\/[^/]+\/chaves/, "Chaves e credenciais"],
    [/^\/organizacoes\/[^/]+\/configuracoes/, "Configurações da organização"],
    [/^\/organizacoes\/[^/]+$/, "Gerenciar Times"],
    [/^\/organizacoes/, "Gerenciar Organizações"],
    [/^\/times\/[^/]+\/automacoes/, "Automações"],
    [/^\/times\/[^/]+\/instrumentos/, "Instrumentos"],
    [/^\/times/, "Time"],
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
      <Link
        href="/ajuda"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        title="Central de conhecimento — o manual do Batuta"
      >
        <CircleHelp className="size-4" />
        <span className="hidden sm:inline">Como funciona</span>
      </Link>
    </header>
  );
}
