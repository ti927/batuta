"use client";

import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, Search } from "lucide-react";

import { api, ErroDaApi } from "@/lib/api";
import { Input } from "@/components/ui/input";

export type CapituloResumo = {
  slug: string;
  titulo: string;
  area: string;
  tags: string[];
  revisado_em: string;
};

type CapituloCompleto = CapituloResumo & { fontes: string[]; corpo: string };

// Áreas na ordem do índice, com rótulo amigável (o backend manda o slug da área).
const AREAS: { chave: string; rotulo: string }[] = [
  { chave: "fundamentos", rotulo: "Fundamentos" },
  { chave: "times-agentes", rotulo: "Times e agentes" },
  { chave: "automacoes", rotulo: "Automações e fluxo" },
  { chave: "instrumentos", rotulo: "Instrumentos" },
  { chave: "segredos", rotulo: "Segredos e conexões" },
  { chave: "mensageria", rotulo: "Mensageria" },
  { chave: "operacao", rotulo: "Operação" },
  { chave: "admin", rotulo: "Administração" },
];

// Estilo do markdown por variantes de descendente (sem plugin typography, que atrita
// com Tailwind v4). Tokens da marca; código de bloco não repete o fundo do inline.
const CLASSES_MD =
  "text-sm text-foreground " +
  "[&_h1]:mt-6 [&_h1]:mb-2 [&_h1]:text-xl [&_h1]:font-medium " +
  "[&_h2]:mt-6 [&_h2]:mb-2 [&_h2]:text-base [&_h2]:font-medium " +
  "[&_h3]:mt-4 [&_h3]:mb-1.5 [&_h3]:text-sm [&_h3]:font-medium " +
  "[&_p]:my-2 [&_p]:leading-relaxed " +
  "[&_ul]:my-2 [&_ul]:ml-5 [&_ul]:list-disc [&_ul]:space-y-1 " +
  "[&_ol]:my-2 [&_ol]:ml-5 [&_ol]:list-decimal [&_ol]:space-y-1 " +
  "[&_li]:leading-relaxed " +
  "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 " +
  "[&_strong]:font-medium " +
  "[&_code]:rounded [&_code]:bg-foreground/5 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[13px] " +
  "[&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-foreground/5 [&_pre]:p-3 [&_pre]:text-[13px] " +
  "[&_pre_code]:bg-transparent [&_pre_code]:p-0 " +
  "[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-sm " +
  "[&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-medium " +
  "[&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 " +
  "[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-primary/40 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground";

export function AjudaCliente({ capitulos }: { capitulos: CapituloResumo[] }) {
  const [busca, setBusca] = useState("");
  // O primeiro capítulo já nasce selecionado (e "carregando"): o fetch acontece no
  // efeito abaixo, e todo setState fica em callback assíncrono (nada síncrono no efeito).
  const [slugAtivo, setSlugAtivo] = useState<string | null>(
    capitulos[0]?.slug ?? null,
  );
  const [cap, setCap] = useState<CapituloCompleto | null>(null);
  const [carregando, setCarregando] = useState<boolean>(!!capitulos[0]);
  const [erro, setErro] = useState<string | null>(null);

  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return capitulos;
    return capitulos.filter(
      (c) =>
        c.titulo.toLowerCase().includes(q) ||
        c.area.toLowerCase().includes(q) ||
        c.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [busca, capitulos]);

  // Busca o capítulo ativo. O setState só ocorre nos callbacks da promessa — não no
  // corpo do efeito (evita o "cascading render" e agrada o react-hooks).
  useEffect(() => {
    if (!slugAtivo) return;
    let vivo = true;
    api
      .get<CapituloCompleto>(`/ajuda/${slugAtivo}`)
      .then((d) => {
        if (vivo) {
          setCap(d);
          setErro(null);
        }
      })
      .catch((e) => {
        if (!vivo) return;
        setErro(
          e instanceof ErroDaApi ? e.message : "Não consegui carregar o capítulo.",
        );
        setCap(null);
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });
    return () => {
      vivo = false;
    };
  }, [slugAtivo]);

  // Clique num capítulo (event handler — setState síncrono é permitido aqui).
  function selecionar(slug: string) {
    if (slug === slugAtivo) return;
    setSlugAtivo(slug);
    setCarregando(true);
    setErro(null);
  }

  // O corpo já traz um "# Título" — removemos para não duplicar o cabeçalho.
  const corpoSemTitulo = (cap?.corpo ?? "").replace(/^#\s+.*\n+/, "");

  if (capitulos.length === 0) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        A Central de Conhecimento ainda não tem capítulos publicados.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Navegação: busca + capítulos por área */}
      <aside className="flex w-72 flex-none flex-col border-r border-border">
        <div className="flex items-center gap-2 border-b border-border p-4">
          <BookOpen className="size-5 text-primary" />
          <h1 className="font-medium text-foreground">Central de conhecimento</h1>
        </div>
        <div className="border-b border-border p-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar…"
              className="pl-8"
            />
          </div>
        </div>
        <nav className="min-h-0 flex-1 overflow-y-auto p-2">
          {AREAS.map(({ chave, rotulo }) => {
            const itens = filtrados.filter((c) => c.area === chave);
            if (itens.length === 0) return null;
            return (
              <div key={chave} className="mb-3">
                <p className="px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {rotulo}
                </p>
                {itens.map((c) => (
                  <button
                    key={c.slug}
                    type="button"
                    onClick={() => selecionar(c.slug)}
                    className={
                      "block w-full truncate rounded-md px-2 py-1.5 text-left text-sm " +
                      (c.slug === slugAtivo
                        ? "bg-primary/10 font-medium text-primary"
                        : "text-foreground hover:bg-foreground/5")
                    }
                  >
                    {c.titulo}
                  </button>
                ))}
              </div>
            );
          })}
          {filtrados.length === 0 && (
            <p className="px-2 py-3 text-sm text-muted-foreground">
              Nada encontrado para “{busca}”.
            </p>
          )}
        </nav>
      </aside>

      {/* Conteúdo do capítulo */}
      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl p-8">
          {carregando && (
            <p className="text-sm text-muted-foreground">Carregando…</p>
          )}
          {erro && <p className="text-sm text-destructive">{erro}</p>}
          {cap && !carregando && (
            <article>
              <header className="mb-4 border-b border-border pb-4">
                <h2 className="text-2xl font-medium text-foreground">
                  {cap.titulo}
                </h2>
                {cap.revisado_em && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Revisado em {cap.revisado_em}
                  </p>
                )}
              </header>
              <div className={CLASSES_MD}>
                <Markdown remarkPlugins={[remarkGfm]}>{corpoSemTitulo}</Markdown>
              </div>
            </article>
          )}
        </div>
      </main>
    </div>
  );
}
