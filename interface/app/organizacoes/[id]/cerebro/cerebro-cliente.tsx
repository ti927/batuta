"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Clock, Library, Plus, Rows3, Search, Table2, Upload } from "lucide-react";

import { type Organizacao, type PapelAcesso } from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { type QuadroResumo, quandoRelativo } from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Select } from "@/components/ui/select";
import { DialogoNovoQuadro } from "@/components/quadros/dialogo-novo-quadro";
import { RoboAgente, SeloAcesso } from "@/components/quadros/pecas";

type Ordem = "gravacao" | "nome" | "linhas";

export function CerebroCliente({
  organizacao,
  quadros,
  meuPapel,
  erroAoCarregar,
}: {
  organizacao: Organizacao;
  quadros: QuadroResumo[];
  meuPapel: PapelAcesso | null;
  erroAoCarregar: boolean;
}) {
  const [busca, setBusca] = useState("");
  const [time, setTime] = useState("");
  const [agente, setAgente] = useState("");
  const [ordem, setOrdem] = useState<Ordem>("gravacao");
  const [novo, setNovo] = useState<null | "vazio" | "planilha">(null);
  const opera = podeOperar(meuPapel);

  const times = useMemo(
    () => [...new Set(quadros.flatMap((q) => q.usado_por.map((u) => u.time)))].sort(),
    [quadros],
  );
  const agentes = useMemo(
    () => [...new Set(quadros.flatMap((q) => q.usado_por.flatMap((u) => u.agentes)))].sort(),
    [quadros],
  );

  const visiveis = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    const lista = quadros.filter((q) => {
      const texto = [q.nome, q.descricao ?? "", ...q.colunas].join(" ").toLowerCase();
      if (termo && !texto.includes(termo)) return false;
      if (time && !q.usado_por.some((u) => u.time === time)) return false;
      if (agente && !q.usado_por.some((u) => u.agentes.includes(agente))) return false;
      return true;
    });
    return lista.sort((a, b) => {
      if (ordem === "nome") return a.nome.localeCompare(b.nome, "pt-BR");
      if (ordem === "linhas") return b.linhas - a.linhas;
      return (b.ultima_gravacao ?? b.criado_em).localeCompare(a.ultima_gravacao ?? a.criado_em);
    });
  }, [quadros, busca, time, agente, ordem]);

  const filtrando = !!(busca || time || agente);

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-medium text-foreground">Cérebro</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            O que os agentes deixam para outros agentes, inclusive de outros times. Cada
            quadro mostra quem grava e quem lê.
          </p>
        </div>
        {opera && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setNovo("planilha")}>
              <Upload /> Importar planilha
            </Button>
            <Button onClick={() => setNovo("vazio")}>
              <Plus /> Novo quadro
            </Button>
          </div>
        )}
      </div>

      <div className="mt-6 mb-5 flex gap-1 border-b border-border">
        <span className="-mb-px flex items-center gap-2 border-b-2 border-primary px-3 py-2 text-sm font-medium text-foreground">
          <Table2 className="size-4" /> Quadros
          <span className="text-xs text-muted-foreground">{quadros.length}</span>
        </span>
        <span
          className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground"
          title="Os documentos da empresa, consultados pelo sentido. Vem depois."
        >
          <Library className="size-4" /> Biblioteca <Badge>em breve</Badge>
        </span>
      </div>

      {erroAoCarregar && (
        <div className="mb-4">
          <Aviso>Não consegui carregar os quadros agora. Recarregue a página em instantes.</Aviso>
        </div>
      )}

      {quadros.length === 0 && !erroAoCarregar ? (
        <EstadoVazio
          icone={Table2}
          titulo="Esta organização ainda não tem quadros."
          acao={
            opera ? (
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="outline" onClick={() => setNovo("planilha")}>
                  <Upload /> Começar de uma planilha
                </Button>
                <Button onClick={() => setNovo("vazio")}>
                  <Plus /> Criar o primeiro quadro
                </Button>
              </div>
            ) : undefined
          }
        >
          Um quadro guarda o que um agente produz para outro usar depois: o resultado de
          cada rodada, a situação de cada cliente, a lista de contas a pagar.
        </EstadoVazio>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label className="flex h-9 min-w-0 flex-[1_1_260px] items-center gap-2 rounded-md border border-input bg-card px-3 text-muted-foreground focus-within:border-ring">
              <Search className="size-4 shrink-0" />
              <input
                id="busca-quadros"
                type="search"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar por nome, descrição ou coluna"
                aria-label="Buscar quadros"
                className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </label>
            {times.length > 0 && (
              <Select
                id="filtro-time"
                aria-label="Filtrar pelo time que usa"
                className="h-9 w-auto"
                value={time}
                onChange={(e) => setTime(e.target.value)}
              >
                <option value="">Todos os times</option>
                {times.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </Select>
            )}
            {agentes.length > 0 && (
              <Select
                id="filtro-agente"
                aria-label="Filtrar pelo agente"
                className="h-9 w-auto"
                value={agente}
                onChange={(e) => setAgente(e.target.value)}
              >
                <option value="">Qualquer agente</option>
                {agentes.map((a) => (
                  <option key={a}>{a}</option>
                ))}
              </Select>
            )}
            <Select
              id="ordem-quadros"
              aria-label="Ordenar"
              className="h-9 w-auto"
              value={ordem}
              onChange={(e) => setOrdem(e.target.value as Ordem)}
            >
              <option value="gravacao">Gravados por último</option>
              <option value="nome">Nome (A a Z)</option>
              <option value="linhas">Mais linhas</option>
            </Select>
            <span className="text-sm tabular-nums text-muted-foreground sm:ml-auto">
              {filtrando ? `${visiveis.length} de ${quadros.length} quadros` : `${quadros.length} ${quadros.length === 1 ? "quadro" : "quadros"}`}
            </span>
          </div>

          {visiveis.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-6 py-10 text-center text-sm text-muted-foreground">
              Nenhum quadro com essa busca ou filtro.{" "}
              <button
                type="button"
                className="text-primary underline-offset-4 hover:underline"
                onClick={() => {
                  setBusca("");
                  setTime("");
                  setAgente("");
                }}
              >
                Limpar e ver todos
              </button>
            </div>
          ) : (
            <ul className="flex flex-col gap-2.5">
              {visiveis.map((q) => (
                <li key={q.id}>
                  <Link
                    href={`/organizacoes/${organizacao.id}/cerebro/${q.id}`}
                    className="grid gap-4 rounded-lg border border-border bg-card px-5 py-4 transition-colors hover:border-[#D6D3E8] md:grid-cols-[minmax(0,1.6fr)_minmax(0,1.2fr)_auto] md:items-center"
                  >
                    <span className="flex min-w-0 flex-col gap-1">
                      <span className="flex items-center gap-2 font-medium text-foreground">
                        <Table2 className="size-4 shrink-0 text-primary" />
                        <span className="truncate">{q.nome}</span>
                      </span>
                      {q.descricao && (
                        <span className="line-clamp-2 text-sm text-muted-foreground">
                          {q.descricao}
                        </span>
                      )}
                      <span className="mt-0.5 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Rows3 className="size-3.5" />
                          {q.linhas.toLocaleString("pt-BR")} {q.linhas === 1 ? "linha" : "linhas"}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="size-3.5" />
                          última gravação {quandoRelativo(q.ultima_gravacao)}
                        </span>
                      </span>
                    </span>
                    <span className="flex flex-col gap-1.5 border-border md:border-l md:pl-4">
                      {q.usado_por.length === 0 ? (
                        <span className="text-xs text-muted-foreground">
                          Nenhum agente usa este quadro ainda.
                        </span>
                      ) : (
                        q.usado_por.slice(0, 3).map((u) => (
                          <span key={u.instrumento_id} className="flex flex-wrap items-center gap-2 text-xs">
                            <RoboAgente escreve={u.acesso === "ler_e_escrever"} />
                            <span className="text-foreground">
                              {u.agentes.length ? u.agentes.join(", ") : u.instrumento}
                            </span>
                            <span className="text-muted-foreground">{u.time}</span>
                            <SeloAcesso acesso={u.acesso} />
                          </span>
                        ))
                      )}
                      {q.usado_por.length > 3 && (
                        <span className="text-xs text-muted-foreground">
                          e mais {q.usado_por.length - 3}
                        </span>
                      )}
                    </span>
                    <ArrowRight className="hidden size-4 text-muted-foreground md:block" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {novo && (
        <DialogoNovoQuadro
          organizacaoId={organizacao.id}
          comecarDePlanilha={novo === "planilha"}
          quadrosExistentes={quadros}
          onFechar={() => setNovo(null)}
        />
      )}
    </main>
  );
}
