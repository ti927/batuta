"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, ListChecks, Zap } from "lucide-react";

import {
  api,
  URL_CEREBRO,
  ErroDaApi,
  type Agente,
  type Automacao,
  type Execucao,
  type ExecucaoComPassos,
  type PapelAcesso,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import {
  ESTADO,
  formatarData,
  InspecaoExecucao,
} from "@/components/inspecao-execucao";
import { Rise } from "@/components/rise";
import { UrlCopiavel } from "@/components/url-copiavel";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const ROTULO_GATILHO: Record<string, string> = {
  manual: "Manual",
  agendamento: "Por horário",
  webhook: "Por webhook",
};

export function AutomacaoDetalheCliente({
  automacao,
  execucoes,
  agentes,
  meuPapel,
}: {
  automacao: Automacao;
  execucoes: Execucao[];
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const souOperador = podeOperar(meuPapel);
  const [erro, setErro] = useState<string | null>(null);
  const [entrada, setEntrada] = useState("");
  const [disparando, setDisparando] = useState(false);
  // Execução aberta no inspetor (por id; o InspecaoExecucao busca e acompanha).
  const [selId, setSelId] = useState<string | null>(null);

  const nomeAgente = (id: string | null) =>
    id === null
      ? "(agente removido)"
      : (agentes.find((a) => a.id === id)?.nome ?? id);

  async function disparar() {
    if (!entrada.trim()) return;
    setDisparando(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/automacoes/${automacao.id}/disparar`,
        { entrada: entrada.trim() },
      );
      setEntrada("");
      setSelId(r.id);
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao disparar");
    } finally {
      setDisparando(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-[820px] px-4 py-8 sm:px-6">
      <Rise>
        <Link
          href={`/times/${automacao.time_id}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          Voltar ao time
        </Link>
        <h1 className="mt-2 font-heading text-2xl font-medium text-foreground">
          {automacao.nome}
        </h1>
        <p className="mb-4 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Zap className="size-3.5" />
            {ROTULO_GATILHO[automacao.tipo_gatilho] ?? automacao.tipo_gatilho}
          </span>
          <span className="inline-flex items-center gap-1">
            início: {nomeAgente(automacao.cadeia?.inicio ?? null)}
          </span>
        </p>

        {automacao.tipo_gatilho === "webhook" && (
          <div className="mb-6">
            <p className="mb-1.5 text-sm font-medium text-foreground">URL do webhook</p>
            <UrlCopiavel
              url={`${URL_CEREBRO}/webhooks/automacoes/${automacao.id}`}
              aviso={
                automacao.ativa
                  ? "Dispare um POST nessa URL para acionar o fluxo."
                  : "A URL só aceita chamadas com o time ativo."
              }
            />
          </div>
        )}

        {erro && <Aviso className="mb-4">{erro}</Aviso>}

        {souOperador && (
          <div className="mb-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-5">
            <Label>Disparar (teste manual)</Label>
            <Textarea
              className="min-h-20"
              placeholder="Mensagem/tarefa de entrada"
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
            />
            <Button className="self-start" onClick={disparar} disabled={disparando}>
              {disparando ? "Executando…" : "Disparar"}
            </Button>
          </div>
        )}

        {selId && (
          <div className="mb-6">
            <InspecaoExecucao
              key={selId}
              execucaoId={selId}
              automacao={automacao}
              agentes={agentes}
              meuPapel={meuPapel}
              onTerminal={() => router.refresh()}
            />
          </div>
        )}

        <h2 className="mb-2 text-sm font-medium text-foreground">
          Execuções anteriores
        </h2>
        {execucoes.length === 0 ? (
          <EstadoVazio icone={ListChecks} titulo="Nenhuma execução ainda.">
            Dispare a automação acima para ver o passo a passo aqui.
          </EstadoVazio>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            {execucoes.map((e) => (
              <li key={e.id} className="flex items-center gap-3 p-3 text-sm">
                <Badge variant={ESTADO[e.estado]?.variante ?? "neutral"}>
                  {ESTADO[e.estado]?.label ?? e.estado}
                </Badge>
                <span className="min-w-0 flex-1 truncate text-muted-foreground">
                  {e.entrada?.texto}
                </span>
                <span className="hidden whitespace-nowrap text-xs text-muted-foreground sm:block">
                  {formatarData(e.criado_em)}
                </span>
                <Button size="sm" variant="outline" onClick={() => setSelId(e.id)}>
                  Ver passos
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Rise>
    </main>
  );
}
