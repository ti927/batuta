"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, Download, Gauge, KeyRound, Pencil, Plus, Rows3, Table2, Trash2, Upload, Users } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro, type PapelAcesso } from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { type QuadroDetalhe, type Resposta, rotaQuadros } from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AbaColunas } from "@/components/quadros/aba-colunas";
import { AcessoDeFora } from "@/components/quadros/acesso-de-fora";
import { AbaLimites } from "@/components/quadros/aba-limites";
import { AbaLinhas } from "@/components/quadros/aba-linhas";
import { DialogoImportar } from "@/components/quadros/dialogo-importar";
import { PainelLateral, RoboAgente, SeloAcesso } from "@/components/quadros/pecas";

type Aba = "linhas" | "colunas" | "quem" | "limites";

export function QuadroCliente({
  organizacaoId,
  detalheInicial,
  meuPapel,
  abrirImportacao,
}: {
  organizacaoId: string;
  detalheInicial: QuadroDetalhe;
  meuPapel: PapelAcesso | null;
  abrirImportacao: boolean;
}) {
  const router = useRouter();
  const [detalhe, setDetalhe] = useState(detalheInicial);
  const [aba, setAba] = useState<Aba>("linhas");
  const [importando, setImportando] = useState(abrirImportacao);
  const [editandoQuadro, setEditandoQuadro] = useState(false);
  const [excluindo, setExcluindo] = useState(false);
  // Muda a cada gravação: a aba de linhas recarrega a consulta quando isto muda.
  const [versao, setVersao] = useState(0);
  const q = detalhe.quadro;
  const opera = podeOperar(meuPapel);
  const base = rotaQuadros(organizacaoId, q.id);

  const recarregar = useCallback(async () => {
    try {
      setDetalhe(await api.get<QuadroDetalhe>(base));
    } catch {
      /* a tela segue com o que tinha; a próxima ação tenta de novo */
    }
    setVersao((v) => v + 1);
  }, [base]);

  const abas: { id: Aba; rotulo: string; Icone: typeof Rows3; cont?: number }[] = [
    { id: "linhas", rotulo: "Linhas", Icone: Rows3, cont: q.total_linhas },
    { id: "colunas", rotulo: "Colunas", Icone: Table2, cont: q.colunas.length },
    { id: "quem", rotulo: "Quem usa", Icone: Users, cont: detalhe.usado_por.length },
    { id: "limites", rotulo: "Limites", Icone: Gauge },
  ];

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <Link
        href={`/organizacoes/${organizacaoId}/cerebro`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" /> Cérebro
      </Link>
      <div className="mt-2 flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-2 text-2xl font-medium text-foreground">
            {q.nome}
            {opera && (
              <Button variant="ghost" size="icon" aria-label="Mudar nome e descrição" onClick={() => setEditandoQuadro(true)}>
                <Pencil className="size-4" />
              </Button>
            )}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            {q.descricao || "Sem descrição. Escreva para que serve: é o que o agente lê."}
            {q.chave.length > 0 && (
              <>
                {" "}
                Cada linha é única por{" "}
                <span className="inline-flex items-center gap-1 text-foreground">
                  <KeyRound className="size-3.5 text-primary" />
                  {q.chave.join(" + ")}
                </span>
                .
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {opera && (
            <Button variant="outline" onClick={() => setImportando(true)}>
              <Upload /> Importar
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() =>
              document.dispatchEvent(new CustomEvent("quadro:exportar"))
            }
          >
            <Download /> Exportar
          </Button>
          {opera && (
            <Button onClick={() => document.dispatchEvent(new CustomEvent("quadro:nova-linha"))}>
              <Plus /> Nova linha
            </Button>
          )}
        </div>
      </div>

      <div className="mt-6 mb-5 flex gap-1 overflow-x-auto border-b border-border" role="tablist">
        {abas.map(({ id, rotulo, Icone, cont }) => (
          <button
            key={id}
            role="tab"
            aria-selected={aba === id}
            onClick={() => setAba(id)}
            className={`-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors ${
              aba === id ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icone className="size-4" /> {rotulo}
            {cont !== undefined && <span className="text-xs tabular-nums text-muted-foreground">{cont.toLocaleString("pt-BR")}</span>}
          </button>
        ))}
      </div>

      {/* A aba de linhas fica montada (escondida) para os botões do cabeçalho — nova
          linha, exportar — funcionarem de qualquer aba. */}
      <div hidden={aba !== "linhas"}>
        <AbaLinhas
          organizacaoId={organizacaoId}
          detalhe={detalhe}
          opera={opera}
          versao={versao}
          aoMudar={recarregar}
          irParaLinhas={() => setAba("linhas")}
        />
      </div>
      {aba === "colunas" && (
        <AbaColunas organizacaoId={organizacaoId} detalhe={detalhe} opera={opera} aoMudar={recarregar} />
      )}
      {aba === "quem" && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Os agentes que têm este quadro no cinto. Para dar ou tirar o acesso, abra o agente no time dele.
          </p>
          {detalhe.usado_por.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-6 py-8 text-center text-sm text-muted-foreground">
              Nenhum agente usa este quadro ainda. No time, crie um instrumento do tipo “Quadro” e
              encaixe no agente.
            </div>
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border bg-card">
              {detalhe.usado_por.map((u) => (
                <li key={u.instrumento_id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <RoboAgente escreve={u.acesso === "ler_e_escrever"} tamanho={24} />
                  <span className="font-medium text-foreground">
                    {u.agentes.length ? u.agentes.join(", ") : "Nenhum agente com este instrumento"}
                  </span>
                  <Link href={`/times/${u.time_id}/instrumentos`} className="text-muted-foreground hover:text-foreground">
                    {u.time} · instrumento “{u.instrumento}”
                  </Link>
                  <span className="ml-auto">
                    <SeloAcesso acesso={u.acesso} />
                  </span>
                </li>
              ))}
            </ul>
          )}
          <AcessoDeFora
            organizacaoId={organizacaoId}
            quadroId={q.id}
            quadroNome={q.nome}
            admin={podeAdmin(meuPapel)}
            colunaExemplo={q.colunas.find((c) => c.tipo === "data" || c.tipo === "data_hora")?.nome ?? null}
          />
        </div>
      )}
      {aba === "limites" && (
        <AbaLimites organizacaoId={organizacaoId} detalhe={detalhe} opera={opera} aoMudar={recarregar} />
      )}

      {podeAdmin(meuPapel) && (
        <div className="mt-12 border-t border-border pt-5">
          <Button variant="destructive" onClick={() => setExcluindo(true)}>
            <Trash2 /> Excluir este quadro
          </Button>
        </div>
      )}

      {importando && (
        <DialogoImportar
          organizacaoId={organizacaoId}
          quadro={q}
          onFechar={() => {
            setImportando(false);
            if (abrirImportacao) router.replace(`/organizacoes/${organizacaoId}/cerebro/${q.id}`);
          }}
          aoImportar={recarregar}
        />
      )}
      {editandoQuadro && (
        <PainelEditarQuadro base={base} nome={q.nome} descricao={q.descricao ?? ""} onFechar={() => setEditandoQuadro(false)} aoSalvar={recarregar} />
      )}
      {excluindo && (
        <PainelExcluirQuadro
          base={base}
          organizacaoId={organizacaoId}
          nome={q.nome}
          onFechar={() => setExcluindo(false)}
        />
      )}
    </main>
  );
}

function PainelEditarQuadro({
  base,
  nome: nomeInicial,
  descricao: descInicial,
  onFechar,
  aoSalvar,
}: {
  base: string;
  nome: string;
  descricao: string;
  onFechar: () => void;
  aoSalvar: () => void;
}) {
  const [nome, setNome] = useState(nomeInicial);
  const [descricao, setDescricao] = useState(descInicial);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function salvar() {
    const operacoes = [];
    if (nome.trim() !== nomeInicial) operacoes.push({ acao: "renomear", nome: nome.trim() });
    if (descricao.trim() !== descInicial) operacoes.push({ acao: "descrever", descricao: descricao.trim() });
    if (!operacoes.length) return onFechar();
    setOcupado(true);
    setErro(null);
    try {
      const r = await api.post<Resposta<object>>(`${base}/estrutura`, { operacoes });
      if (!r.ok) return setErro(r.erro);
      toast.success("Quadro atualizado");
      aoSalvar();
      onFechar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <PainelLateral
      titulo="Nome e descrição"
      onFechar={onFechar}
      rodape={
        <>
          <Button variant="outline" onClick={onFechar}>Cancelar</Button>
          <Button onClick={salvar} disabled={ocupado}>{ocupado ? "Salvando…" : "Salvar"}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {erro && <Aviso>{erro}</Aviso>}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="q-nome">Nome</Label>
          <Input id="q-nome" value={nome} onChange={(e) => setNome(e.target.value)} />
          <span className="text-xs text-muted-foreground">Renomear não afeta os agentes que usam o quadro.</span>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="q-desc">Para que serve</Label>
          <Textarea id="q-desc" rows={5} value={descricao} onChange={(e) => setDescricao(e.target.value)} />
          <span className="text-xs text-muted-foreground">O agente lê esta descrição para saber o que gravar.</span>
        </div>
      </div>
    </PainelLateral>
  );
}

function PainelExcluirQuadro({
  base,
  organizacaoId,
  nome,
  onFechar,
}: {
  base: string;
  organizacaoId: string;
  nome: string;
  onFechar: () => void;
}) {
  const router = useRouter();
  const [previa, setPrevia] = useState<{ linhas_apagadas: number; instrumentos_que_usavam: { instrumento: string; time: string; agentes: string[] }[] } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    let vivo = true;
    api
      .delete<{ linhas_apagadas: number; instrumentos_que_usavam: { instrumento: string; time: string; agentes: string[] }[] }>(
        `${base}?simular=true`,
      )
      .then((r) => vivo && setPrevia(r))
      .catch((e) => vivo && setErro(mensagemDeErro(e)));
    return () => {
      vivo = false;
    };
  }, [base]);

  async function excluir() {
    setOcupado(true);
    try {
      await api.delete(base);
      toast.success(`Quadro “${nome}” excluído`);
      router.push(`/organizacoes/${organizacaoId}/cerebro`);
      router.refresh();
    } catch (e) {
      setErro(mensagemDeErro(e));
      setOcupado(false);
    }
  }

  return (
    <PainelLateral
      titulo={`Excluir “${nome}”?`}
      onFechar={onFechar}
      rodape={
        <>
          <Button variant="outline" onClick={onFechar}>Cancelar</Button>
          <Button variant="destructive" onClick={excluir} disabled={ocupado || !previa}>
            {ocupado ? "Excluindo…" : "Excluir quadro"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        {erro && <Aviso>{erro}</Aviso>}
        {!previa && !erro && <p className="text-muted-foreground">Conferindo o que sai junto…</p>}
        {previa && (
          <>
            <Aviso variant="atencao">
              Saem {previa.linhas_apagadas.toLocaleString("pt-BR")} linhas e todo o histórico. Isso não pode ser desfeito.
            </Aviso>
            {previa.instrumentos_que_usavam.length > 0 && (
              <div>
                <p className="font-medium text-foreground">Estes agentes usam o quadro e vão ficar sem ele:</p>
                <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                  {previa.instrumentos_que_usavam.map((u, i) => (
                    <li key={i}>
                      {u.agentes.join(", ") || u.instrumento} ({u.time})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </PainelLateral>
  );
}
