"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ListChecks, Pause } from "lucide-react";

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
import { rotuloOrigem } from "@/lib/uso";
import { UrlCopiavel } from "@/components/url-copiavel";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

// Estados em que a execução parou de avançar (não há mais o que acompanhar).
const ESTADOS_TERMINAIS = ["concluida", "falhou", "aguardando_humano", "cancelada"];

// Cada estado vira uma variante do selo (cor + sentido), DS §9.
type VarianteBadge = "neutral" | "info" | "success" | "warning" | "error";
const VARIANTE_ESTADO: Record<string, VarianteBadge> = {
  concluida: "success",
  falhou: "error",
  em_andamento: "warning",
  aguardando: "neutral",
  aguardando_humano: "info",
  cancelada: "neutral",
};

function Passos({
  execucao,
  nomeAgente,
}: {
  execucao: ExecucaoComPassos;
  nomeAgente: (id: string | null) => string;
}) {
  return (
    <div className="mt-2 flex flex-col gap-2">
      {execucao.resultado?.erro && (
        <Aviso className="text-xs">Erro: {execucao.resultado.erro}</Aviso>
      )}
      <ol className="flex flex-col gap-2">
        {execucao.passos.map((p) => (
          <li
            key={p.id}
            className="rounded-md border border-border bg-card p-2 text-xs"
          >
            <div className="mb-1 flex flex-wrap items-center gap-2 font-medium text-foreground">
              {p.ordem}. {nomeAgente(p.agente_id)}
              {p.saida?.saida_escolhida && (
                <Badge variant="info">saída: {p.saida.saida_escolhida}</Badge>
              )}
              {(p.saida?.instrumentos_acionados ?? []).length > 0 && (
                <span className="font-normal text-muted-foreground">
                  🔧 {p.saida!.instrumentos_acionados!.join(", ")}
                </span>
              )}
            </div>
            <div className="text-muted-foreground">entrada: {p.entrada?.texto}</div>
            <div className="whitespace-pre-wrap text-foreground">
              saída: {p.saida?.texto}
            </div>
            {(p.saida?.uso ?? []).length > 0 && (
              <div className="mt-1 text-muted-foreground">
                🪙{" "}
                {(p.saida?.uso ?? [])
                  .reduce((s, u) => s + u.tokens_entrada, 0)
                  .toLocaleString("pt-BR")}{" "}
                entrada +{" "}
                {(p.saida?.uso ?? [])
                  .reduce((s, u) => s + u.tokens_saida, 0)
                  .toLocaleString("pt-BR")}{" "}
                saída tokens
              </div>
            )}
          </li>
        ))}
      </ol>
      {execucao.resultado?.texto && (
        <div className="rounded-md bg-foreground p-3 text-xs whitespace-pre-wrap text-background">
          {execucao.resultado.texto}
        </div>
      )}
    </div>
  );
}

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
  const [rodando, setRodando] = useState(false);

  // Execução atualmente aberta (recém-disparada ou carregada da lista).
  const [aberta, setAberta] = useState<ExecucaoComPassos | null>(null);

  // Resposta do humano a uma execução pausada.
  const [resposta, setResposta] = useState("");
  const [respondendo, setRespondendo] = useState(false);

  // Acompanhamento ao vivo: enquanto a execução está em andamento, consultamos
  // a cada 1,5s e redesenhamos os passos conforme terminam (Tarefa 5.2).
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  // Limpa o acompanhamento ao sair da tela.
  useEffect(() => pararPoll, []);

  function acompanhar(id: string) {
    pollRef.current = setTimeout(async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
        setAberta(r);
        if (ESTADOS_TERMINAIS.includes(r.estado)) {
          pararPoll();
          setRodando(false);
          router.refresh();
          return;
        }
      } catch {
        // erro transitório ao consultar — tenta de novo no próximo ciclo
      }
      acompanhar(id);
    }, 1500);
  }

  const nomeAgente = (id: string | null) =>
    id === null ? "(agente removido)" : agentes.find((a) => a.id === id)?.nome ?? id;

  async function disparar() {
    if (!entrada.trim()) return;
    pararPoll();
    setRodando(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/automacoes/${automacao.id}/disparar`,
        { entrada: entrada.trim() },
      );
      setAberta(r);
      setEntrada("");
      if (ESTADOS_TERMINAIS.includes(r.estado)) {
        setRodando(false);
        router.refresh();
      } else {
        acompanhar(r.id); // em andamento: acompanha até terminar
      }
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao disparar");
      setRodando(false);
    }
  }

  async function abrir(id: string) {
    setErro(null);
    pararPoll();
    try {
      const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
      setAberta(r);
      if (!ESTADOS_TERMINAIS.includes(r.estado)) {
        setRodando(true);
        acompanhar(id); // aberta uma execução ainda em andamento: acompanha
      }
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao abrir execução");
    }
  }

  // `decisao` é o rótulo de uma saída (portão de aprovação). Se houver feedback
  // digitado, ele acompanha a decisão (ex.: "reprovado: mude o título").
  async function responder(decisao?: string) {
    const fb = resposta.trim();
    const texto = decisao ? (fb ? `${decisao}: ${fb}` : decisao) : fb;
    if (!aberta || !texto) return;
    setRespondendo(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/execucoes/${aberta.id}/responder`,
        { resposta: texto },
      );
      setAberta(r);
      setResposta("");
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao responder");
    } finally {
      setRespondendo(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/times/${automacao.time_id}/automacoes`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar às automações
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">
        {automacao.nome}
      </h1>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">
        Gatilho: {automacao.tipo_gatilho} · início:{" "}
        {nomeAgente(automacao.cadeia?.inicio ?? null)}
      </p>

      {automacao.tipo_gatilho === "webhook" && (
        <div className="mb-6">
          <p className="mb-1.5 text-sm font-medium text-foreground">
            URL do webhook
          </p>
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
        <div className="mb-6 flex flex-col gap-2 rounded-lg border border-border bg-card p-6">
          <Label>Disparar (teste manual)</Label>
          <Textarea
            className="min-h-20"
            placeholder="Mensagem/tarefa de entrada"
            value={entrada}
            onChange={(e) => setEntrada(e.target.value)}
          />
          <Button className="self-start" onClick={disparar} disabled={rodando}>
            {rodando ? "Executando..." : "Disparar"}
          </Button>
        </div>
      )}

      {aberta && (
        <div className="mb-6 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground">Execução</span>
            <Badge variant={VARIANTE_ESTADO[aberta.estado] ?? "neutral"}>
              {aberta.estado}
            </Badge>
          </div>
          {aberta.estado === "aguardando" && (
            <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-muted-foreground" />
              Na fila, aguardando um trabalhador…
            </p>
          )}
          {aberta.estado === "em_andamento" && (
            <p className="mt-2 flex items-center gap-2 text-sm text-warning">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-warning" />
              Em andamento — {aberta.passos.length} passo(s) concluído(s), rodando o
              próximo…
            </p>
          )}
          <Passos execucao={aberta} nomeAgente={nomeAgente} />

          {aberta.uso &&
            aberta.uso.tokens_entrada + aberta.uso.tokens_saida > 0 && (
              <div className="mt-3 rounded-md border border-border bg-background p-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Uso (estimado):</span>{" "}
                {aberta.uso.tokens_entrada.toLocaleString("pt-BR")} entrada +{" "}
                {aberta.uso.tokens_saida.toLocaleString("pt-BR")} saída tokens · ~US${" "}
                {aberta.uso.custo_usd.toFixed(4)}
                {Object.entries(aberta.uso.por_modelo).map(([modelo, u]) => (
                  <div key={modelo} className="text-muted-foreground/70">
                    {modelo}: {u.tokens_entrada.toLocaleString("pt-BR")}+
                    {u.tokens_saida.toLocaleString("pt-BR")} tok · ~US$
                    {u.custo_usd.toFixed(4)}
                  </div>
                ))}
                {Object.keys(aberta.uso.por_origem ?? {}).length > 0 && (
                  <div className="mt-1">
                    <span className="font-medium text-foreground">
                      Por origem da chave:
                    </span>
                    {Object.entries(aberta.uso.por_origem).map(([origem, u]) => (
                      <div key={origem} className="text-muted-foreground/70">
                        {rotuloOrigem(origem)}:{" "}
                        {u.tokens_entrada.toLocaleString("pt-BR")}+
                        {u.tokens_saida.toLocaleString("pt-BR")} tok · ~US$
                        {u.custo_usd.toFixed(4)}
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-1 text-muted-foreground/70">
                  Custo aproximado, apenas informativo — não é cobrança.
                </div>
              </div>
            )}

          {aberta.estado === "aguardando_humano" &&
            (() => {
              const ultimo = aberta.passos[aberta.passos.length - 1];
              const saidasPausa = ultimo?.agente_id
                ? automacao.cadeia?.nos?.[ultimo.agente_id]?.saidas ?? []
                : [];
              return (
                <div className="mt-3 flex flex-col gap-2 rounded-md border border-accent-foreground/20 bg-accent p-3">
                  <span className="flex items-center gap-1.5 text-sm font-medium text-accent-foreground">
                    <Pause className="size-4" />
                    Aguardando sua decisão
                  </span>
                  <p className="text-sm whitespace-pre-wrap text-accent-foreground">
                    {ultimo?.saida?.texto}
                  </p>
                  <Textarea
                    className="min-h-16"
                    placeholder={
                      saidasPausa.length > 0
                        ? "Feedback (opcional) — acompanha a decisão que você escolher abaixo"
                        : "Sua resposta"
                    }
                    value={resposta}
                    onChange={(e) => setResposta(e.target.value)}
                  />
                  {saidasPausa.length > 0 ? (
                    <div className="flex flex-col gap-1.5">
                      <span className="text-xs text-accent-foreground">
                        Sua decisão:
                      </span>
                      {saidasPausa.map((s) => (
                        <div key={s.rotulo} className="flex items-center gap-2">
                          <Button
                            size="sm"
                            disabled={respondendo}
                            onClick={() => responder(s.rotulo)}
                          >
                            {s.rotulo}
                          </Button>
                          <span className="text-xs text-muted-foreground">
                            {s.quando}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Button
                      className="self-start"
                      onClick={() => responder()}
                      disabled={respondendo}
                    >
                      {respondendo ? "Retomando..." : "Responder e retomar"}
                    </Button>
                  )}
                </div>
              );
            })()}
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
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {execucoes.map((e) => (
            <li key={e.id} className="flex items-center gap-2 p-3 text-sm">
              <Badge variant={VARIANTE_ESTADO[e.estado] ?? "neutral"}>
                {e.estado}
              </Badge>
              <span className="flex-1 truncate text-muted-foreground">
                {e.entrada?.texto}
              </span>
              <Button size="sm" variant="outline" onClick={() => abrir(e.id)}>
                Ver passos
              </Button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
