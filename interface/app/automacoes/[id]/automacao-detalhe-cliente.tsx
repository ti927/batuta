"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Automacao,
  type Execucao,
  type ExecucaoComPassos,
} from "@/lib/api";
import { Button } from "@/components/ui/button";

// Estados em que a execução parou de avançar (não há mais o que acompanhar).
const ESTADOS_TERMINAIS = ["concluida", "falhou", "aguardando_humano"];

const COR_ESTADO: Record<string, string> = {
  concluida: "bg-green-100 text-green-800",
  falhou: "bg-red-100 text-red-800",
  em_andamento: "bg-amber-100 text-amber-800",
  aguardando: "bg-zinc-100 text-zinc-600",
  aguardando_humano: "bg-blue-100 text-blue-800",
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
        <p className="rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">
          Erro: {execucao.resultado.erro}
        </p>
      )}
      <ol className="flex flex-col gap-2">
        {execucao.passos.map((p) => (
          <li key={p.id} className="rounded border border-zinc-200 p-2 text-xs">
            <div className="mb-1 font-medium">
              {p.ordem}. {nomeAgente(p.agente_id)}
              {p.saida?.saida_escolhida && (
                <span className="ml-2 rounded bg-violet-100 px-1.5 py-0.5 text-violet-700">
                  saída: {p.saida.saida_escolhida}
                </span>
              )}
              {(p.saida?.instrumentos_acionados ?? []).length > 0 && (
                <span className="ml-2 text-zinc-400">
                  🔧 {p.saida!.instrumentos_acionados!.join(", ")}
                </span>
              )}
            </div>
            <div className="text-zinc-500">entrada: {p.entrada?.texto}</div>
            <div className="whitespace-pre-wrap text-zinc-800">
              saída: {p.saida?.texto}
            </div>
          </li>
        ))}
      </ol>
      {execucao.resultado?.texto && (
        <div className="rounded bg-zinc-900 p-3 text-xs whitespace-pre-wrap text-zinc-100">
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
}: {
  automacao: Automacao;
  execucoes: Execucao[];
  agentes: Agente[];
}) {
  const router = useRouter();
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

  async function responder() {
    if (!aberta || !resposta.trim()) return;
    setRespondendo(true);
    setErro(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/execucoes/${aberta.id}/responder`,
        { resposta: resposta.trim() },
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
    <main className="mx-auto w-full max-w-3xl p-8">
      <Link
        href={`/times/${automacao.time_id}/automacoes`}
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Voltar às automações
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">{automacao.nome}</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Gatilho: {automacao.tipo_gatilho} · início:{" "}
        {nomeAgente(automacao.cadeia?.inicio ?? null)}
      </p>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      <div className="mb-6 flex flex-col gap-2 rounded border border-zinc-300 bg-zinc-50 p-4">
        <label className="text-sm font-medium">Disparar (teste manual)</label>
        <textarea
          className="min-h-20 rounded border border-zinc-300 px-2 py-1 text-sm"
          placeholder="Mensagem/tarefa de entrada"
          value={entrada}
          onChange={(e) => setEntrada(e.target.value)}
        />
        <Button className="self-start" onClick={disparar} disabled={rodando}>
          {rodando ? "Executando..." : "Disparar"}
        </Button>
      </div>

      {aberta && (
        <div className="mb-6 rounded border border-zinc-300 p-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">Execução</span>
            <span
              className={`rounded px-1.5 py-0.5 text-xs ${
                COR_ESTADO[aberta.estado] ?? "bg-zinc-100 text-zinc-600"
              }`}
            >
              {aberta.estado}
            </span>
          </div>
          {aberta.estado === "em_andamento" && (
            <p className="mt-2 flex items-center gap-2 text-sm text-amber-700">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
              Em andamento — {aberta.passos.length} passo(s) concluído(s), rodando o
              próximo…
            </p>
          )}
          <Passos execucao={aberta} nomeAgente={nomeAgente} />

          {aberta.estado === "aguardando_humano" && (
            <div className="mt-3 flex flex-col gap-2 rounded border border-blue-300 bg-blue-50 p-3">
              <span className="text-sm font-medium text-blue-900">
                ⏸ Aguardando sua resposta
              </span>
              <p className="text-sm whitespace-pre-wrap text-blue-900">
                {aberta.passos[aberta.passos.length - 1]?.saida?.texto}
              </p>
              <textarea
                className="min-h-16 rounded border border-zinc-300 px-2 py-1 text-sm"
                placeholder="Sua resposta"
                value={resposta}
                onChange={(e) => setResposta(e.target.value)}
              />
              <Button
                className="self-start"
                onClick={responder}
                disabled={respondendo}
              >
                {respondendo ? "Retomando..." : "Responder e retomar"}
              </Button>
            </div>
          )}
        </div>
      )}

      <h2 className="mb-2 text-sm font-semibold">Execuções anteriores</h2>
      {execucoes.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhuma execução ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {execucoes.map((e) => (
            <li key={e.id} className="flex items-center gap-2 p-3 text-sm">
              <span
                className={`rounded px-1.5 py-0.5 text-xs ${
                  COR_ESTADO[e.estado] ?? "bg-zinc-100 text-zinc-600"
                }`}
              >
                {e.estado}
              </span>
              <span className="flex-1 text-zinc-500">{e.entrada?.texto}</span>
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
