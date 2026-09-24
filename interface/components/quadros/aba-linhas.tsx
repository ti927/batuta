"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, ListFilter, Plus, Search, Undo2, X } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro } from "@/lib/api";
import {
  baixarCsv,
  type ColunaQuadro,
  type Filtro,
  type LinhaQuadro,
  mostrarValor,
  operadoresPara,
  type QuadroDetalhe,
  type Resposta,
  type ResultadoConsulta,
  rotaQuadros,
  rotuloOperador,
  quandoRelativo,
} from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { GravadoPor, PainelLateral } from "@/components/quadros/pecas";
import { PainelLinha } from "@/components/quadros/painel-linha";

const POR_PAGINA = 50;

export function AbaLinhas({
  organizacaoId,
  detalhe,
  opera,
  versao,
  aoMudar,
  irParaLinhas,
}: {
  organizacaoId: string;
  detalhe: QuadroDetalhe;
  opera: boolean;
  versao: number;
  aoMudar: () => void;
  irParaLinhas: () => void;
}) {
  const q = detalhe.quadro;
  const base = rotaQuadros(organizacaoId, q.id);
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [filtros, setFiltros] = useState<Filtro[]>([]);
  const [maisRecenteDe, setMaisRecenteDe] = useState<string | null>(null);
  const [res, setRes] = useState<ResultadoConsulta | null>(null);
  const [linhas, setLinhas] = useState<LinhaQuadro[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [filtrando, setFiltrando] = useState(false);
  const [aberta, setAberta] = useState<LinhaQuadro | "nova" | null>(null);
  const [desfazendo, setDesfazendo] = useState<string | null>(null);
  const tipoDe = useMemo(() => Object.fromEntries(q.colunas.map((c) => [c.nome, c.tipo])), [q.colunas]);

  // Busca com uma pausa curta: não consulta a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  // Uma consulta é identificada pelo que a define; "carregando" = a chave pedida ainda
  // não é a que está na tela (calculado, sem ligar estado de dentro de um efeito).
  const chave = JSON.stringify([filtros, buscaAplicada, maisRecenteDe, versao]);
  const [chaveNaTela, setChaveNaTela] = useState<string | null>(null);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const carregando = chave !== chaveNaTela || carregandoMais;

  const buscar = useCallback(
    (deslocamento: number) =>
      api.post<Resposta<ResultadoConsulta>>(`${base}/consulta`, {
        filtros,
        busca: buscaAplicada || null,
        so_o_mais_recente_de: maisRecenteDe,
        limite: POR_PAGINA,
        deslocamento,
      }),
    [base, filtros, buscaAplicada, maisRecenteDe],
  );

  const aplicar = useCallback(
    (r: Resposta<ResultadoConsulta>, deslocamento: number) => {
      if (!r.ok) {
        setErro(r.erro);
        return;
      }
      setErro(null);
      setRes(r);
      setLinhas((atuais) => (deslocamento === 0 ? r.linhas : [...atuais, ...r.linhas]));
    },
    [],
  );

  useEffect(() => {
    let vivo = true;
    buscar(0)
      .then((r) => vivo && aplicar(r, 0))
      .catch((e) => vivo && setErro(mensagemDeErro(e, "Não consegui carregar as linhas. Tente de novo.")))
      .finally(() => vivo && setChaveNaTela(chave));
    return () => {
      vivo = false;
    };
  }, [buscar, aplicar, chave]);

  async function mostrarMais(deslocamento: number) {
    setCarregandoMais(true);
    try {
      aplicar(await buscar(deslocamento), deslocamento);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não consegui carregar mais linhas. Tente de novo."));
    } finally {
      setCarregandoMais(false);
    }
  }

  // Os botões do cabeçalho (nova linha, exportar) falam com esta aba por evento.
  useEffect(() => {
    const nova = () => {
      irParaLinhas();
      setAberta("nova");
    };
    const exportar = async () => {
      try {
        const r = await baixarCsv(organizacaoId, q.id, filtros, buscaAplicada);
        if (!r.ok) toast.error(r.erro);
        else if (r.total > r.exportadas)
          toast.info(`Exportei as ${r.exportadas} primeiras de ${r.total} linhas. Use filtros para exportar em partes.`);
      } catch (e) {
        toast.error(mensagemDeErro(e));
      }
    };
    document.addEventListener("quadro:nova-linha", nova);
    document.addEventListener("quadro:exportar", exportar);
    return () => {
      document.removeEventListener("quadro:nova-linha", nova);
      document.removeEventListener("quadro:exportar", exportar);
    };
  }, [organizacaoId, q.id, irParaLinhas, filtros, buscaAplicada]);

  const ultimaExecucao = detalhe.execucoes_recentes[0];
  const temFiltro = filtros.length > 0 || !!maisRecenteDe || !!buscaAplicada;

  return (
    <div className="flex flex-col gap-3">
      {opera && ultimaExecucao && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[#F0D9B8] bg-warning/10 px-4 py-3 text-sm">
          <Undo2 className="size-4 shrink-0 text-warning" />
          <p className="min-w-[220px] flex-1 text-foreground">
            A última execução que gravou aqui foi de <span className="font-medium">{ultimaExecucao.automacao ?? "uma automação"}</span>,{" "}
            {quandoRelativo(ultimaExecucao.quando)}: {ultimaExecucao.linhas}{" "}
            {ultimaExecucao.linhas === 1 ? "linha" : "linhas"}. Se foi um teste, dá para apagar só o que ela gravou.
          </p>
          <Button variant="outline" size="sm" onClick={() => setDesfazendo(ultimaExecucao.execucao_id)}>
            Apagar o que ela gravou
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-9 min-w-0 flex-[0_1_280px] items-center gap-2 rounded-md border border-input bg-card px-3 text-muted-foreground focus-within:border-ring">
          <Search className="size-4 shrink-0" />
          <input
            id="busca-linhas"
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar nas linhas"
            aria-label="Buscar nas linhas"
            className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </label>
        {filtros.map((f, i) => (
          <span key={i} className="inline-flex h-8 items-center gap-1.5 rounded-full border border-[#CFC2FB] bg-[#F7F4FF] pr-1 pl-3 text-sm text-accent-foreground">
            {f.coluna} {rotuloOperador(f.operador)}
            {f.valor !== undefined && f.valor !== "" ? ` ${mostrarValor(f.valor, tipoDe[f.coluna])}` : ""}
            <button
              type="button"
              className="grid size-6 place-items-center rounded-full hover:bg-accent"
              aria-label="Tirar este filtro"
              onClick={() => setFiltros(filtros.filter((_, j) => j !== i))}
            >
              <X className="size-3.5" />
            </button>
          </span>
        ))}
        {maisRecenteDe && (
          <span className="inline-flex h-8 items-center gap-1.5 rounded-full border border-[#CFC2FB] bg-[#F7F4FF] pr-1 pl-3 text-sm text-accent-foreground">
            Só a mais recente de {maisRecenteDe}
            <button type="button" className="grid size-6 place-items-center rounded-full hover:bg-accent" aria-label="Tirar este filtro" onClick={() => setMaisRecenteDe(null)}>
              <X className="size-3.5" />
            </button>
          </span>
        )}
        <Button variant="outline" size="sm" className="rounded-full" onClick={() => setFiltrando((v) => !v)} aria-expanded={filtrando}>
          <ListFilter /> Filtrar
        </Button>
        <span className="text-sm tabular-nums text-muted-foreground sm:ml-auto">
          {res
            ? temFiltro
              ? `Mostrando ${linhas.length} de ${res.total.toLocaleString("pt-BR")} que batem (${(q.total_linhas ?? 0).toLocaleString("pt-BR")} no quadro)`
              : `Mostrando ${linhas.length} de ${res.total.toLocaleString("pt-BR")} linhas`
            : ""}
        </span>
      </div>

      {filtrando && (
        <FormularioFiltro
          colunas={q.colunas}
          onAplicar={(f) => {
            setFiltros([...filtros, f]);
            setFiltrando(false);
          }}
          onMaisRecente={(c) => {
            setMaisRecenteDe(c);
            setFiltrando(false);
          }}
          onCancelar={() => setFiltrando(false)}
        />
      )}

      {erro && <Aviso>{erro}</Aviso>}

      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full border-collapse text-sm tabular-nums">
          <thead>
            <tr className="bg-[#FCFBFE]">
              {q.colunas.map((c) => (
                <th key={c.id} className="whitespace-nowrap border-b border-border px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                  {c.faz_parte_da_chave && <KeyRound className="mr-1 inline size-3.5 text-primary" aria-label="identifica a linha" />}
                  {c.nome}
                </th>
              ))}
              <th className="whitespace-nowrap border-b border-border px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                Gravado por
              </th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((ln) => (
              <tr
                key={ln.id}
                tabIndex={0}
                onClick={() => setAberta(ln)}
                onKeyDown={(e) => e.key === "Enter" && setAberta(ln)}
                className="cursor-pointer border-b border-[#F1F0F5] last:border-0 hover:bg-[#FBFAFE] focus-visible:bg-[#F5F2FF] focus-visible:outline-none"
              >
                {q.colunas.map((c) => (
                  <td key={c.id} className="max-w-[280px] px-3 py-2.5 align-top text-foreground">
                    <CelulaValor coluna={c} valor={ln.valores[c.nome]} />
                  </td>
                ))}
                <td className="min-w-[200px] px-3 py-2.5 align-top">
                  <GravadoPor carimbo={ln.carimbo} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!carregando && linhas.length === 0 && (
          <div className="px-6 py-10 text-center text-sm text-muted-foreground">
            {temFiltro ? (
              <>
                Nenhuma linha com essa busca ou filtro.{" "}
                <button
                  type="button"
                  className="text-primary underline-offset-4 hover:underline"
                  onClick={() => {
                    setBusca("");
                    setFiltros([]);
                    setMaisRecenteDe(null);
                  }}
                >
                  Limpar
                </button>
              </>
            ) : (
              <>
                Nenhuma linha ainda. Os agentes que gravam neste quadro vão preenchê-lo
                {opera ? "; você também pode acrescentar ou importar uma planilha." : "."}
              </>
            )}
          </div>
        )}
        {carregando && linhas.length === 0 && (
          <div className="px-6 py-10 text-center text-sm text-muted-foreground">Carregando as linhas…</div>
        )}
      </div>

      {res?.proximo != null && (
        <Button variant="outline" className="self-center" disabled={carregando} onClick={() => mostrarMais(res.proximo ?? 0)}>
          {carregando ? "Carregando…" : `Mostrar mais ${Math.min(POR_PAGINA, res.total - linhas.length)}`}
        </Button>
      )}

      {aberta && (
        <PainelLinha
          organizacaoId={organizacaoId}
          quadro={q}
          linha={aberta === "nova" ? null : aberta}
          opera={opera}
          onFechar={() => setAberta(null)}
          aoMudar={aoMudar}
        />
      )}
      {desfazendo && (
        <PainelDesfazer
          base={base}
          execucaoId={desfazendo}
          automacao={ultimaExecucao?.automacao ?? null}
          onFechar={() => setDesfazendo(null)}
          aoApagar={aoMudar}
        />
      )}
    </div>
  );
}

function CelulaValor({ coluna, valor }: { coluna: ColunaQuadro; valor: LinhaQuadro["valores"][string] }) {
  const texto = mostrarValor(valor, coluna.tipo);
  if (!texto) return <span className="text-muted-foreground/60">vazio</span>;
  if (coluna.tipo === "texto_longo") return <span className="line-clamp-2 text-muted-foreground">{texto}</span>;
  return <span className="block truncate">{texto}</span>;
}

function FormularioFiltro({
  colunas,
  onAplicar,
  onMaisRecente,
  onCancelar,
}: {
  colunas: ColunaQuadro[];
  onAplicar: (f: Filtro) => void;
  onMaisRecente: (coluna: string) => void;
  onCancelar: () => void;
}) {
  const [modo, setModo] = useState<"comparar" | "recente">("comparar");
  const [coluna, setColuna] = useState(colunas[0]?.nome ?? "");
  const col = colunas.find((c) => c.nome === coluna);
  const ops = col ? operadoresPara(col.tipo) : [];
  const [operador, setOperador] = useState(ops[0]?.valor ?? "=");
  const [valor, setValor] = useState("");
  const opAtual = ops.find((o) => o.valor === operador) ?? ops[0];
  const ordenaveis = colunas.filter((c) => ["data", "data_hora", "numero", "dinheiro"].includes(c.tipo));

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input type="radio" name="modo-filtro" checked={modo === "comparar"} onChange={() => setModo("comparar")} />
          Filtrar por uma coluna
        </label>
        {ordenaveis.length > 0 && (
          <label className="flex items-center gap-2">
            <input type="radio" name="modo-filtro" checked={modo === "recente"} onChange={() => setModo("recente")} />
            Só a mais recente
          </label>
        )}
      </div>
      {modo === "comparar" ? (
        <div className="flex flex-wrap items-center gap-2">
          <Select
            id="filtro-coluna"
            aria-label="Coluna"
            className="h-9 w-auto"
            value={coluna}
            onChange={(e) => {
              setColuna(e.target.value);
              const nova = colunas.find((c) => c.nome === e.target.value);
              setOperador(nova ? operadoresPara(nova.tipo)[0].valor : "=");
              setValor("");
            }}
          >
            {colunas.map((c) => (
              <option key={c.id}>{c.nome}</option>
            ))}
          </Select>
          <Select id="filtro-operador" aria-label="Condição" className="h-9 w-auto" value={operador} onChange={(e) => setOperador(e.target.value)}>
            {ops.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </Select>
          {!opAtual?.semValor &&
            (col?.tipo === "opcao" || col?.tipo === "sim_nao" ? (
              <Select id="filtro-valor" aria-label="Valor" className="h-9 w-auto" value={valor} onChange={(e) => setValor(e.target.value)}>
                <option value="">(escolha)</option>
                {(col.tipo === "sim_nao" ? ["sim", "não"] : col.opcoes ?? []).map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </Select>
            ) : (
              <Input
                id="filtro-valor"
                aria-label="Valor"
                className="h-9 w-48"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
                placeholder={col?.tipo === "data" ? "DD/MM/AAAA" : col?.tipo === "data_hora" ? "DD/MM/AAAA HH:MM" : ""}
              />
            ))}
          <Button
            size="sm"
            disabled={!opAtual?.semValor && !valor.trim()}
            onClick={() => onAplicar({ coluna, operador, ...(opAtual?.semValor ? {} : { valor: valor.trim() }) })}
          >
            <Plus /> Aplicar
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancelar}>
            Cancelar
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          Mostrar só as linhas com o valor mais recente de
          <Select id="filtro-recente" aria-label="Coluna" className="h-9 w-auto" defaultValue={ordenaveis[0]?.nome} onChange={(e) => setColuna(e.target.value)}>
            {ordenaveis.map((c) => (
              <option key={c.id}>{c.nome}</option>
            ))}
          </Select>
          <Button size="sm" onClick={() => onMaisRecente(ordenaveis.some((c) => c.nome === coluna) ? coluna : ordenaveis[0].nome)}>
            Aplicar
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancelar}>
            Cancelar
          </Button>
        </div>
      )}
    </div>
  );
}

function PainelDesfazer({
  base,
  execucaoId,
  automacao,
  onFechar,
  aoApagar,
}: {
  base: string;
  execucaoId: string;
  automacao: string | null;
  onFechar: () => void;
  aoApagar: () => void;
}) {
  const [previa, setPrevia] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    let vivo = true;
    api
      .post<Resposta<{ apagadas: number }>>(`${base}/linhas/apagar`, { execucao_id: execucaoId, simular: true })
      .then((r) => {
        if (!vivo) return;
        if (r.ok) setPrevia(r.apagadas);
        else setErro(r.erro);
      })
      .catch((e) => vivo && setErro(mensagemDeErro(e)));
    return () => {
      vivo = false;
    };
  }, [base, execucaoId]);

  async function apagar() {
    setOcupado(true);
    try {
      const r = await api.post<Resposta<{ apagadas: number }>>(`${base}/linhas/apagar`, { execucao_id: execucaoId });
      if (!r.ok) return setErro(r.erro);
      toast.success(`${r.apagadas} ${r.apagadas === 1 ? "linha apagada" : "linhas apagadas"}`);
      aoApagar();
      onFechar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <PainelLateral
      titulo="Apagar o que esta execução gravou?"
      subtitulo={automacao ?? undefined}
      onFechar={onFechar}
      rodape={
        <>
          <Button variant="outline" onClick={onFechar}>Cancelar</Button>
          <Button variant="destructive" disabled={ocupado || !previa} onClick={apagar}>
            {ocupado ? "Apagando…" : previa ? `Apagar ${previa} ${previa === 1 ? "linha" : "linhas"}` : "Apagar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        {erro && <Aviso>{erro}</Aviso>}
        {previa === null && !erro && <p className="text-muted-foreground">Contando as linhas…</p>}
        {previa !== null && (
          <>
            <Aviso variant="atencao">
              Saem {previa} {previa === 1 ? "linha" : "linhas"} deste quadro. As outras ficam como estão.
            </Aviso>
            <p className="text-muted-foreground">
              O histórico guarda o que foi apagado e quem apagou. Isso não pode ser desfeito pela tela.
            </p>
          </>
        )}
      </div>
    </PainelLateral>
  );
}
