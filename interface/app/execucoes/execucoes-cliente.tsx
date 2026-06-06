"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, ListChecks } from "lucide-react";

import {
  api,
  ErroDaApi,
  type ExecucaoNaLista,
  type PapelAcesso,
  type ResumoUso,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { rotuloOrigem } from "@/lib/uso";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

// Cada estado vira uma variante do selo (cor + sentido), DS §9.
type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";
const VARIANTE_ESTADO: Record<string, VarianteBadge> = {
  aguardando: "neutral",
  em_andamento: "warning",
  aguardando_humano: "info",
  concluida: "success",
  falhou: "error",
  cancelada: "neutral",
};

// Estados já encerrados: podem ser apagados, mas não cancelados.
const ENCERRADOS = ["concluida", "falhou", "cancelada"];

const FILTROS: { valor: string; rotulo: string }[] = [
  { valor: "todos", rotulo: "Todas" },
  { valor: "aguardando", rotulo: "Na fila" },
  { valor: "em_andamento", rotulo: "Em andamento" },
  { valor: "aguardando_humano", rotulo: "Aguardando humano" },
  { valor: "concluida", rotulo: "Concluídas" },
  { valor: "falhou", rotulo: "Falhas" },
  { valor: "cancelada", rotulo: "Canceladas" },
];

export function ExecucoesCliente({
  inicial,
  uso,
  papeis,
}: {
  inicial: ExecucaoNaLista[];
  uso: ResumoUso | null;
  papeis: Record<string, PapelAcesso>;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [filtro, setFiltro] = useState("todos");
  const [ocupada, setOcupada] = useState<string | null>(null);

  const lista =
    filtro === "todos" ? inicial : inicial.filter((e) => e.estado === filtro);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function cancelar(id: string) {
    setOcupada(id);
    setErro(null);
    try {
      await api.post(`/execucoes/${id}/cancelar`, {});
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao cancelar");
    } finally {
      setOcupada(null);
    }
  }

  async function apagar(id: string) {
    if (!confirm("Apagar esta execução e seu histórico de passos?")) return;
    setOcupada(id);
    setErro(null);
    try {
      await api.delete(`/execucoes/${id}`);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao apagar");
    } finally {
      setOcupada(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Início
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">Execuções</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        Todas as execuções, de todas as automações. Cancele as que estão em curso
        ou paradas; apague as já encerradas.
      </p>

      {uso && uso.tokens_entrada + uso.tokens_saida > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-card p-4 text-sm">
          <p className="mb-1 font-medium text-foreground">
            Uso por origem da chave{" "}
            <span className="text-xs font-normal text-muted-foreground">
              (estimado, informativo — não é cobrança)
            </span>
          </p>
          <p className="mb-2 text-xs text-muted-foreground">
            Total: {uso.tokens_entrada.toLocaleString("pt-BR")} entrada +{" "}
            {uso.tokens_saida.toLocaleString("pt-BR")} saída tokens · ~US$
            {uso.custo_usd.toFixed(4)}
          </p>
          <ul className="divide-y divide-border rounded-md border border-border bg-background">
            {Object.entries(uso.por_origem).map(([origem, u]) => (
              <li key={origem} className="flex items-center gap-2 p-2 text-xs">
                <span className="flex-1 text-foreground">
                  {rotuloOrigem(origem)}
                </span>
                <span className="text-muted-foreground">
                  {u.tokens_entrada.toLocaleString("pt-BR")}+
                  {u.tokens_saida.toLocaleString("pt-BR")} tok
                </span>
                <span className="font-medium text-foreground">
                  ~US${u.custo_usd.toFixed(4)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTROS.map((f) => {
          const n =
            f.valor === "todos"
              ? inicial.length
              : inicial.filter((e) => e.estado === f.valor).length;
          return (
            <Button
              key={f.valor}
              size="sm"
              variant={filtro === f.valor ? "default" : "outline"}
              onClick={() => setFiltro(f.valor)}
            >
              {f.rotulo} ({n})
            </Button>
          );
        })}
      </div>

      {lista.length === 0 ? (
        <EstadoVazio icone={ListChecks} titulo="Nenhuma execução neste filtro.">
          Troque o filtro acima ou dispare uma automação.
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {lista.map((e) => {
            const encerrada = ENCERRADOS.includes(e.estado);
            const papel = papeis[e.organizacao_id];
            return (
              <li key={e.id} className="flex items-center gap-3 p-3 text-sm">
                <Badge variant={VARIANTE_ESTADO[e.estado] ?? "neutral"}>
                  {e.estado}
                </Badge>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/automacoes/${e.automacao_id}`}
                    className="font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {e.automacao_nome}
                  </Link>
                  <div className="truncate text-xs text-muted-foreground">
                    {e.entrada?.texto ?? "—"}
                  </div>
                </div>
                {!encerrada && podeOperar(papel) && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={ocupada === e.id}
                    onClick={() => cancelar(e.id)}
                  >
                    Cancelar
                  </Button>
                )}
                {encerrada && podeAdmin(papel) && (
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={ocupada === e.id}
                    onClick={() => apagar(e.id)}
                  >
                    Apagar
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
