"use client";

import { useEffect, useState } from "react";
import { AlertCircle, KeyRound, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro } from "@/lib/api";
import {
  type Alteracao,
  type ColunaQuadro,
  type LinhaQuadro,
  mostrarValor,
  type QuadroDescrito,
  type Resposta,
  rotaQuadros,
  valorParaCampo,
} from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { GravadoPor, PainelLateral, QuemFezAlteracao } from "@/components/quadros/pecas";

export function PainelLinha({
  organizacaoId,
  quadro,
  linha,
  opera,
  onFechar,
  aoMudar,
}: {
  organizacaoId: string;
  quadro: QuadroDescrito;
  linha: LinhaQuadro | null;
  opera: boolean;
  onFechar: () => void;
  aoMudar: () => void;
}) {
  const base = rotaQuadros(organizacaoId, quadro.id);
  const inicial = Object.fromEntries(
    quadro.colunas.map((c) => [c.nome, valorParaCampo(linha?.valores[c.nome] ?? null, c.tipo)]),
  );
  const [valores, setValores] = useState<Record<string, string>>(inicial);
  const [errosCampo, setErrosCampo] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [confirmarApagar, setConfirmarApagar] = useState(false);
  const [historico, setHistorico] = useState<Alteracao[] | null>(null);

  useEffect(() => {
    if (!linha) return;
    let vivo = true;
    api
      .get<{ alteracoes: Alteracao[] }>(`${base}/linhas/${linha.id}/historico`)
      .then((r) => vivo && setHistorico(r.alteracoes.slice().reverse()))
      .catch(() => vivo && setHistorico([]));
    return () => {
      vivo = false;
    };
  }, [base, linha]);

  function tratarRecusa(r: { erro: string; detalhes?: { coluna: string | null; motivo: string }[] }) {
    const porCampo: Record<string, string> = {};
    for (const d of r.detalhes ?? []) if (d.coluna) porCampo[d.coluna] = d.motivo;
    setErrosCampo(porCampo);
    setErro(Object.keys(porCampo).length ? "Corrija os campos marcados. Nada foi salvo." : r.erro);
  }

  async function salvar() {
    setOcupado(true);
    setErro(null);
    setErrosCampo({});
    try {
      if (!linha) {
        const nova = Object.fromEntries(Object.entries(valores).filter(([, v]) => v.trim() !== ""));
        const r = await api.post<Resposta<{ criadas: number }>>(`${base}/linhas`, { linhas: [nova] });
        if (!r.ok) return tratarRecusa(r);
        toast.success("Linha criada");
      } else {
        const mudadas = Object.fromEntries(Object.entries(valores).filter(([k, v]) => v !== inicial[k]));
        if (!Object.keys(mudadas).length) return onFechar();
        const r = await api.patch<Resposta<{ mudadas: number }>>(`${base}/linhas/${linha.id}`, { campos: mudadas });
        if (!r.ok) return tratarRecusa(r);
        toast.success("Linha salva");
      }
      aoMudar();
      onFechar();
    } catch (e) {
      setErro(mensagemDeErro(e, "Não consegui salvar. Seus valores continuam aqui; tente de novo."));
    } finally {
      setOcupado(false);
    }
  }

  async function apagar() {
    if (!linha) return;
    setOcupado(true);
    try {
      const r = await api.post<Resposta<{ apagadas: number }>>(`${base}/linhas/apagar`, { ids: [linha.id] });
      if (!r.ok) return setErro(r.erro);
      toast.success("Linha apagada");
      aoMudar();
      onFechar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  const titulo = linha
    ? quadro.chave.length
      ? quadro.chave.map((n) => mostrarValor(linha.valores[n], quadro.colunas.find((c) => c.nome === n)?.tipo)).join(" · ")
      : "Linha do quadro"
    : "Nova linha";

  return (
    <PainelLateral
      titulo={titulo}
      subtitulo={quadro.nome}
      onFechar={onFechar}
      rodape={
        opera ? (
          confirmarApagar ? (
            <>
              <span className="mr-auto text-sm text-destructive">Apagar esta linha? O histórico guarda o que ela tinha.</span>
              <Button variant="outline" onClick={() => setConfirmarApagar(false)}>Não</Button>
              <Button variant="destructive" onClick={apagar} disabled={ocupado}>Sim, apagar</Button>
            </>
          ) : (
            <>
              {linha && (
                <Button variant="destructive" className="mr-auto" onClick={() => setConfirmarApagar(true)}>
                  <Trash2 /> Apagar linha
                </Button>
              )}
              <Button variant="outline" onClick={onFechar}>Cancelar</Button>
              <Button onClick={salvar} disabled={ocupado}>{ocupado ? "Salvando…" : linha ? "Salvar" : "Criar linha"}</Button>
            </>
          )
        ) : undefined
      }
    >
      <div className="flex flex-col gap-4">
        {erro && <Aviso>{erro}</Aviso>}
        {quadro.colunas.map((c) => (
          <Campo
            key={c.id}
            coluna={c}
            valor={valores[c.nome] ?? ""}
            erro={errosCampo[c.nome]}
            somenteLeitura={!opera}
            onChange={(v) => setValores((atual) => ({ ...atual, [c.nome]: v }))}
          />
        ))}

        {linha && (
          <div className="mt-2 flex flex-col gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Gravado por último</span>
            <GravadoPor carimbo={linha.carimbo} />
            <span className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Histórico desta linha</span>
            {historico === null ? (
              <span className="text-sm text-muted-foreground">Carregando…</span>
            ) : (
              <ol className="flex flex-col gap-3">
                {historico.map((a, i) => (
                  <li key={i} className="border-l-2 border-[#EDEBF4] pl-3 text-sm">
                    <span className="text-xs text-muted-foreground">
                      <QuemFezAlteracao a={a} />
                    </span>
                    <MudancasDaAlteracao a={a} colunas={quadro.colunas} />
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </PainelLateral>
  );
}

function Campo({
  coluna,
  valor,
  erro,
  somenteLeitura,
  onChange,
}: {
  coluna: ColunaQuadro;
  valor: string;
  erro?: string;
  somenteLeitura: boolean;
  onChange: (v: string) => void;
}) {
  const id = `campo-${coluna.id}`;
  const classeErro = erro ? "border-destructive" : "";
  let entrada;
  if (coluna.tipo === "opcao" || coluna.tipo === "sim_nao") {
    const opcoes = coluna.tipo === "sim_nao" ? ["sim", "não"] : coluna.opcoes ?? [];
    entrada = (
      <Select id={id} value={valor} disabled={somenteLeitura} onChange={(e) => onChange(e.target.value)} className={classeErro}>
        <option value="">(vazio)</option>
        {opcoes.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </Select>
    );
  } else if (coluna.tipo === "texto_longo") {
    entrada = <Textarea id={id} rows={4} value={valor} readOnly={somenteLeitura} onChange={(e) => onChange(e.target.value)} className={classeErro} />;
  } else {
    const dica: Record<string, string> = {
      data: "DD/MM/AAAA",
      data_hora: "DD/MM/AAAA HH:MM",
      numero: "ex.: 12 ou 12,5",
      dinheiro: "ex.: 1234,56",
    };
    entrada = (
      <Input
        id={id}
        value={valor}
        readOnly={somenteLeitura}
        placeholder={dica[coluna.tipo] ?? ""}
        inputMode={coluna.tipo === "numero" || coluna.tipo === "dinheiro" ? "decimal" : undefined}
        onChange={(e) => onChange(e.target.value)}
        className={classeErro}
      />
    );
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="flex items-center gap-1.5 text-sm font-medium text-foreground">
        {coluna.faz_parte_da_chave && <KeyRound className="size-3.5 text-primary" />}
        {coluna.nome}
        {coluna.obrigatoria && <span className="text-xs font-normal text-muted-foreground">obrigatória</span>}
      </label>
      {entrada}
      {coluna.descricao && !erro && <span className="text-xs text-muted-foreground">{coluna.descricao}</span>}
      {erro && (
        <span className="flex items-start gap-1 text-xs text-destructive">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" /> {erro}
        </span>
      )}
    </div>
  );
}

function MudancasDaAlteracao({ a, colunas }: { a: Alteracao; colunas: ColunaQuadro[] }) {
  const tipo = (n: string) => colunas.find((c) => c.nome === n)?.tipo;
  if (a.acao === "criou") {
    const n = Object.keys(a.depois ?? {}).length;
    return <p className="mt-0.5 text-muted-foreground">Criou a linha com {n} {n === 1 ? "coluna preenchida" : "colunas preenchidas"}.</p>;
  }
  if (a.acao === "apagou") return <p className="mt-0.5 text-muted-foreground">Apagou a linha.</p>;
  const antes = a.antes ?? {};
  const depois = a.depois ?? {};
  const nomes = [...new Set([...Object.keys(antes), ...Object.keys(depois)])].filter(
    (n) => JSON.stringify(antes[n]) !== JSON.stringify(depois[n]),
  );
  return (
    <ul className="mt-0.5">
      {nomes.map((n) => (
        <li key={n}>
          {n}: <span className="text-muted-foreground line-through">{mostrarValor(antes[n], tipo(n)) || "vazio"}</span>{" "}
          → <span className="text-foreground">{mostrarValor(depois[n], tipo(n)) || "vazio"}</span>
        </li>
      ))}
    </ul>
  );
}
