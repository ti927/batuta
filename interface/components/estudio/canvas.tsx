"use client";

// O CANVAS DO ESTÚDIO.
//
// A fiação com o React Flow segue o mesmo padrão do construtor clássico — que não é
// gosto, é cicatriz: o React Flow precisa ser DONO do próprio array de nós (é ali que
// `applyNodeChanges` grava a medição, sem a qual o arrastar quebra), e handles que
// mudam exigem `updateNodeInternals` na mão. Copiado de propósito: esta tela é
// paralela e não pode arrastar a que está no ar.
//
// O que é novo aqui: o desenho se confere sozinho (painel de problemas), o foco
// desbota o que não interessa, o mapa mostra onde você está num fluxo grande, e
// "organizar" arruma tudo em colunas.

import "@xyflow/react/dist/style.css";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  applyNodeChanges,
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useUpdateNodeInternals,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Hourglass,
  Layers,
  LayoutGrid,
  Plus,
  Repeat2,
  ShieldAlert,
} from "lucide-react";

import type {
  Agente,
  AutomacaoDaOrg,
  Cadeia,
  Instrumento,
  NoCadeia,
  SaidaCadeia,
} from "@/lib/api";
import { RobotFace } from "@/components/robot-face";

import { arrumar } from "./arrumar";
import { corDaSaida, tracejado } from "./cores";
import { tiposDeArestaEstudio } from "./aresta";
import { tiposDeNoEstudio, type DadosNoEstudio } from "./nos";
import { analisar, nomeDoNo, papel, porNo, type Problema } from "./problemas";

const NODE_TYPES = tiposDeNoEstudio;
const EDGE_TYPES = tiposDeArestaEstudio;

// Um id de saída/nó novo. Local ao estúdio para não depender do módulo do clássico.
let _seq = 0;
function novoId(prefixo: string): string {
  _seq += 1;
  return `${prefixo}_${Math.random().toString(36).slice(2, 7)}${_seq}`;
}

export type CanvasProps = {
  cadeia: Cadeia;
  setCadeia: (atualiza: (c: Cadeia) => Cadeia) => void;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  automacoesOrg: AutomacaoDaOrg[];
  podeEditar: boolean;
  gatilhoTipo: NoCadeia["gatilho"];
  selId: string | null;
  setSelId: (id: string | null) => void;
  saidaSel: string | null;
  setSaidaSel: (id: string | null) => void;
  onEditarAgente: (agenteId: string) => void;
  onEditarInstrumento: (instrumentoId: string) => void;
  /** Sobe a análise para o cabeçalho da página (contador de problemas). */
  onProblemas?: (p: Problema[]) => void;
};

export function CanvasEstudio(props: CanvasProps) {
  return (
    <ReactFlowProvider>
      <CanvasInterno {...props} />
    </ReactFlowProvider>
  );
}

function CanvasInterno({
  cadeia,
  setCadeia,
  agentes,
  cintos,
  automacoesOrg,
  podeEditar,
  gatilhoTipo,
  selId,
  setSelId,
  saidaSel,
  setSaidaSel,
  onEditarAgente,
  onEditarInstrumento,
  onProblemas,
}: CanvasProps) {
  const updateNodeInternals = useUpdateNodeInternals();
  const { fitView } = useReactFlow();
  const [addAberto, setAddAberto] = useState(false);
  const [painelProblemas, setPainelProblemas] = useState(true);

  const porIdNo = useMemo(
    () => new Map((cadeia.nos ?? []).map((n) => [n.id, n])),
    [cadeia],
  );

  const problemas = useMemo(
    () => analisar({ cadeia, agentes, cintos, automacoes: automacoesOrg }),
    [cadeia, agentes, cintos, automacoesOrg],
  );
  useEffect(() => {
    onProblemas?.(problemas);
  }, [problemas, onProblemas]);
  const problemasPorNo = useMemo(() => porNo(problemas), [problemas]);
  const saidasComErro = useMemo(
    () => new Set(problemas.filter((p) => p.nivel === "erro" && p.saidaId).map((p) => p.saidaId!)),
    [problemas],
  );

  const nomeDe = useCallback(
    (id: string) => nomeDoNo(porIdNo.get(id), agentes),
    [porIdNo, agentes],
  );
  // "Volta para": o destino está à esquerda (ou na mesma coluna) deste passo.
  const ehVoltaDe = useCallback(
    (origemId: string, destinoId: string) => {
      const o = porIdNo.get(origemId);
      const d = porIdNo.get(destinoId);
      if (!o || !d) return false;
      return (d.x ?? 0) < (o.x ?? 0) + 24;
    },
    [porIdNo],
  );

  const selecionarSaida = useCallback(
    (noId: string, saidaId: string) => {
      setSelId(noId);
      setSaidaSel(saidaId);
    },
    [setSelId, setSaidaSel],
  );

  // ── projeção cadeia → nós do React Flow ──
  const projetar = useCallback(
    (no: NoCadeia): Node => {
      const agente = no.tipo === "agente" ? agentes.find((a) => a.id === no.ref) : undefined;
      const indice = agente ? agentes.findIndex((a) => a.id === agente.id) : 0;
      const dados: DadosNoEstudio = {
        no: no.tipo === "gatilho" ? { ...no, gatilho: gatilhoTipo } : no,
        agente,
        indice,
        cinto: no.tipo === "agente" ? (cintos[no.ref ?? ""] ?? []) : undefined,
        automacoes: automacoesOrg,
        problemas: problemasPorNo.get(no.id) ?? [],
        nomeDe,
        ehVolta: (destino: string) => ehVoltaDe(no.id, destino),
        saidaSelecionada: selId === no.id ? saidaSel : null,
        onSelecionarSaida: selecionarSaida,
        onEditarAgente,
        onEditarInstrumento: podeEditar ? onEditarInstrumento : undefined,
      };
      return {
        id: no.id,
        type: no.tipo,
        position: { x: no.x ?? 0, y: no.y ?? 0 },
        data: dados as unknown as Record<string, unknown>,
        draggable: podeEditar,
        selected: no.id === selId,
      };
    },
    [
      agentes,
      cintos,
      automacoesOrg,
      gatilhoTipo,
      problemasPorNo,
      nomeDe,
      ehVoltaDe,
      selId,
      saidaSel,
      selecionarSaida,
      onEditarAgente,
      onEditarInstrumento,
      podeEditar,
    ],
  );

  // Assinatura do que muda o CARTÃO. Sem x/y de propósito (posição é mão única:
  // React Flow → cadeia), senão o arrastar briga com a reprojeção.
  const assinatura = useMemo(
    () =>
      JSON.stringify({
        n: (cadeia.nos ?? []).map((n) => ({
          i: n.id,
          t: n.tipo,
          r: n.ref,
          nm: n.nome,
          ini: n.inicial,
          s: (n.saidas ?? []).map((s) => [
            s.id,
            s.rotulo,
            s.quando,
            s.tipo,
            s.destino,
            s.tone,
            s.lane,
            s.regra?.campo,
          ]),
          c: [n.espera?.quanto, n.espera?.unidade, n.lista, n.chamar?.automacao_id],
        })),
        gat: gatilhoTipo,
        e: podeEditar,
        sel: selId,
        ssel: saidaSel,
        prob: problemas.map((p) => p.id),
        aut: automacoesOrg.map((a) => [a.id, a.nome]),
        ag: agentes.map((a) => [a.id, a.nome, a.modelo_ia, a.papel]),
        cin: (cadeia.nos ?? [])
          .filter((n) => n.tipo === "agente")
          .map((n) => [
            n.ref,
            (cintos[n.ref ?? ""] ?? []).map((i) => `${i.id}:${i.nome}:${i.tipo}`).join(","),
          ]),
      }),
    [cadeia, gatilhoTipo, podeEditar, selId, saidaSel, problemas, automacoesOrg, agentes, cintos],
  );

  const [rfNodes, setRfNodes] = useState<Node[]>(() => (cadeia.nos ?? []).map(projetar));
  const [prevSig, setPrevSig] = useState(assinatura);
  if (assinatura !== prevSig) {
    setPrevSig(assinatura);
    setRfNodes((prev) => {
      const anteriores = new Map(prev.map((n) => [n.id, n]));
      return (cadeia.nos ?? []).map((no) => {
        const base = projetar(no);
        const velho = anteriores.get(no.id);
        // Nó que já existia: preserva a medição (senão "des-inicializa" e o arrastar
        // quebra) e a posição viva do arrasto.
        return velho
          ? {
              ...base,
              position: velho.position,
              measured: velho.measured,
              width: velho.width,
              height: velho.height,
            }
          : base;
      });
    });
  }

  // Handles mudaram (saída nova/removida, nó novo)? O React Flow precisa ser avisado.
  const idsParaRemedir = useMemo(
    () => (cadeia.nos ?? []).map((n) => n.id),
    // `assinatura` já cobre a estrutura (ids, tipos, saídas).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [assinatura],
  );
  useEffect(() => {
    for (const id of idsParaRemedir) updateNodeInternals(id);
  }, [idsParaRemedir, updateNodeInternals]);

  // ── arestas ──
  const edges = useMemo<Edge[]>(() => {
    const out: Edge[] = [];
    for (const no of cadeia.nos ?? []) {
      for (const sa of no.saidas ?? []) {
        if (!porIdNo.has(sa.destino) || !sa.id) continue;
        const c = corDaSaida(sa);
        const pp = papel(sa);
        const ativo = selId === no.id || selId === sa.destino;
        const comErro = saidasComErro.has(sa.id);
        const linha = comErro ? "#E5484D" : ativo ? "#6D4AFF" : c.linha;
        const apagado = !!selId && !ativo;
        // Mesma regra do cartão: o fio só fica "sem condição" quando a condição é
        // mesmo obrigatória (o passo bifurca). Com um caminho só, ele é sempre tomado.
        const condicionais = (no.saidas ?? []).filter((s) => papel(s) === "condicional");
        const obrigatoria =
          pp === "condicional" &&
          (no.tipo === "agente" || no.tipo === "roteador") &&
          condicionais.length >= 2;
        const escrita = (sa.quando ?? "").trim();
        const condicao =
          pp === "erro"
            ? "se este passo falhar"
            : pp === "senao"
              ? "se nenhuma das outras"
              : no.tipo === "gatilho"
                ? "começa por aqui"
                : escrita || (obrigatoria ? "" : "assim que terminar");
        out.push({
          id: `${no.id}:${sa.id}`,
          source: no.id,
          sourceHandle: sa.id,
          target: sa.destino,
          type: "estudio",
          zIndex: ativo ? 5 : 0,
          data: {
            condicao,
            rotulo: sa.rotulo,
            cor: c,
            tracejado: tracejado(sa),
            lane: sa.lane ?? "below",
            ativo,
            apagado,
            comErro,
            comRegra: !!sa.regra?.campo,
            noId: no.id,
            saidaId: sa.id,
            onPick: selecionarSaida,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: linha,
            width: 15,
            height: 15,
          },
        });
      }
    }
    return out;
  }, [cadeia, porIdNo, selId, saidasComErro, selecionarSaida]);

  // ── mutações ──
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setRfNodes((nds) => applyNodeChanges(changes, nds));
      const moves = changes.filter(
        (c): c is Extract<NodeChange, { type: "position" }> =>
          c.type === "position" && !!c.position,
      );
      if (!moves.length) return;
      setCadeia((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) => {
          const m = moves.find((x) => x.id === n.id);
          return m?.position ? { ...n, x: m.position.x, y: m.position.y } : n;
        }),
      }));
    },
    [setCadeia],
  );

  const onConnect = useCallback(
    (conn: Connection) => {
      if (!podeEditar || !conn.source || !conn.target) return;
      // Puxar o fio DO gatilho = escolher o primeiro passo (substitui, não soma).
      if (porIdNo.get(conn.source)?.tipo === "gatilho") {
        setCadeia((c) => ({ ...c, inicial: conn.target! }));
        return;
      }
      // Arrastar de uma porta EXISTENTE (sourceHandle) = religar aquele fio, não criar
      // outro. Era o jeito mais natural de mexer no desenho e não existia.
      if (conn.sourceHandle) {
        setCadeia((c) => ({
          ...c,
          nos: (c.nos ?? []).map((n) =>
            n.id === conn.source
              ? {
                  ...n,
                  saidas: (n.saidas ?? []).map((s) =>
                    s.id === conn.sourceHandle ? { ...s, destino: conn.target! } : s,
                  ),
                }
              : n,
          ),
        }));
        return;
      }
      setCadeia((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) =>
          n.id === conn.source
            ? {
                ...n,
                saidas: [
                  ...(n.saidas ?? []),
                  {
                    id: novoId("s"),
                    rotulo: "novo caminho",
                    quando: "",
                    tipo: "condicional" as const,
                    destino: conn.target!,
                    tone: "normal" as const,
                  } satisfies SaidaCadeia,
                ],
              }
            : n,
        ),
      }));
    },
    [podeEditar, porIdNo, setCadeia],
  );

  const addNo = useCallback(
    (kind: "agente" | "roteador" | "cada" | "esperar" | "chamar", ref?: string) => {
      const id = novoId(kind);
      setCadeia((c) => {
        const fim = (c.nos ?? []).find((n) => n.tipo === "fim");
        const baseX = 380 + ((c.nos?.length ?? 0) % 4) * 40;
        const ehPrimeiroAgente =
          kind === "agente" && !(c.nos ?? []).some((n) => n.tipo === "agente") && !c.inicial;
        const saidaPadrao = (rotulo: string): SaidaCadeia => ({
          id: novoId("s"),
          rotulo,
          quando: "",
          destino: fim?.id ?? "fim",
          tone: "normal",
        });
        const base = { id, x: baseX, y: 340 };
        const novo: NoCadeia =
          kind === "chamar"
            ? {
                ...base,
                tipo: "chamar",
                nome: "Chamar outra automação",
                chamar: { automacao_id: "" },
                saidas: [saidaPadrao("com o resultado")],
              }
            : kind === "esperar"
              ? {
                  ...base,
                  tipo: "esperar",
                  nome: "Esperar",
                  espera: { quanto: 0, unidade: "minutos" },
                  saidas: [saidaPadrao("depois da espera")],
                }
              : kind === "cada"
                ? { ...base, tipo: "cada", lista: "", saidas: [saidaPadrao("cada item")] }
                : kind === "roteador"
                  ? {
                      ...base,
                      tipo: "roteador",
                      nome: "Nova decisão",
                      saidas: [saidaPadrao("caso A")],
                    }
                  : { ...base, tipo: "agente", ref, saidas: [saidaPadrao("resultado")] };
        return {
          ...c,
          inicial: ehPrimeiroAgente ? id : c.inicial,
          nos: [...(c.nos ?? []), novo],
        };
      });
      setSelId(id);
      setSaidaSel(null);
      setAddAberto(false);
    },
    [setCadeia, setSelId, setSaidaSel],
  );

  const organizar = useCallback(() => {
    const alturas: Record<string, number> = {};
    for (const n of rfNodes) {
      const h = n.measured?.height ?? n.height;
      if (h) alturas[n.id] = h;
    }
    const pos = arrumar(cadeia, alturas);
    setCadeia((c) => ({
      ...c,
      nos: (c.nos ?? []).map((n) => (pos[n.id] ? { ...n, ...pos[n.id] } : n)),
    }));
    setTimeout(() => fitView({ duration: 320, padding: 0.16 }), 60);
  }, [rfNodes, cadeia, setCadeia, fitView]);

  const irPara = useCallback(
    (p: Problema) => {
      if (!p.noId) return;
      setSelId(p.noId);
      setSaidaSel(p.saidaId ?? null);
      fitView({ nodes: [{ id: p.noId }], duration: 380, maxZoom: 1.1, padding: 0.4 });
    },
    [fitView, setSelId, setSaidaSel],
  );

  const erros = problemas.filter((p) => p.nivel === "erro");
  const avisos = problemas.filter((p) => p.nivel === "aviso");

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      edgeTypes={EDGE_TYPES}
      onNodesChange={onNodesChange}
      onConnect={onConnect}
      onNodeClick={(_, n) => {
        setSelId(n.id);
        setSaidaSel(null);
      }}
      onPaneClick={() => {
        setSelId(null);
        setSaidaSel(null);
        setAddAberto(false);
      }}
      nodesConnectable={podeEditar}
      nodesDraggable={podeEditar}
      elementsSelectable
      minZoom={0.25}
      maxZoom={1.8}
      defaultViewport={{ x: 40, y: 20, zoom: 0.78 }}
      proOptions={{ hideAttribution: true }}
      style={{ background: "#FAFAF7" }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1.1} color="#E0DDF0" />
      {/* Cada canto com um dono: zoom em cima à esquerda, ferramentas em cima à
          direita, o mapa embaixo à direita e os problemas embaixo à esquerda. No
          clássico o zoom mora embaixo à esquerda — aqui esse canto é do painel que
          diz o que está errado, que é o que mais importa nesta tela. */}
      <Controls showInteractive={false} position="top-left" />
      <MiniMap
        pannable
        zoomable
        style={{ background: "#fff", border: "1px solid #E8E6F0", borderRadius: 10 }}
        maskColor="rgba(26,23,48,.06)"
        nodeColor={(n) => {
          if (problemasPorNo.get(n.id)?.some((p) => p.nivel === "erro")) return "#E5484D";
          if (n.type === "gatilho") return "#6D4AFF";
          if (n.type === "fim") return "#3DAA5C";
          if (n.type === "agente") return "#C3BFD6";
          return "#E0DAF6";
        }}
        nodeStrokeWidth={0}
      />

      {/* ── barra de ferramentas ── */}
      <Panel position="top-right">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={organizar}
            disabled={!podeEditar}
            title="Arruma os cartões em colunas, seguindo a ordem do fluxo"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#E8E6F0] bg-white px-3 text-[13px] font-medium text-[#1A1730] shadow-sm hover:bg-[#FAFAF7] disabled:opacity-50"
          >
            <LayoutGrid size={15} color="#6D4AFF" /> Organizar
          </button>
          {podeEditar && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setAddAberto((o) => !o)}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#E8E6F0] bg-white px-3 text-[13px] font-medium text-[#1A1730] shadow-sm hover:bg-[#FAFAF7]"
              >
                <Plus size={15} color="#6D4AFF" /> Adicionar passo
                <ChevronDown size={14} color="#A09DB8" />
              </button>
              {addAberto && (
                <div className="absolute right-0 top-11 z-30 w-64 rounded-[10px] border border-[#E8E6F0] bg-white p-1.5 shadow-lg">
                  <div className="px-2 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-[#A09DB8]">
                    Agente do time
                  </div>
                  {agentes.map((a, i) => (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => addNo("agente", a.id)}
                      className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] text-[#1A1730] hover:bg-[#F4F1FE]"
                    >
                      <RobotFace size={22} indice={i} lider={a.papel === "lider"} />
                      {a.nome}
                    </button>
                  ))}
                  {agentes.length === 0 && (
                    <div className="px-2 py-1.5 text-[12px] text-[#6B6880]">
                      Crie agentes no time primeiro.
                    </div>
                  )}
                  <div className="my-1 h-px bg-[#E8E6F0]" />
                  <ItemAdd
                    Icone={Layers}
                    titulo="Decisão"
                    ajuda="Encaminha a tarefa sem rodar agente (e sem gastar IA)"
                    onClick={() => addNo("roteador")}
                  />
                  <ItemAdd
                    Icone={Repeat2}
                    titulo="Para cada item"
                    ajuda="Repete o trecho seguinte uma vez por item de uma lista"
                    onClick={() => addNo("cada")}
                  />
                  <ItemAdd
                    Icone={Hourglass}
                    titulo="Esperar"
                    ajuda="Segura o fluxo por um tempo e continua daqui"
                    onClick={() => addNo("esperar")}
                  />
                  <ItemAdd
                    Icone={ArrowRightLeft}
                    titulo="Chamar outra automação"
                    ajuda="Roda outra automação e espera o resultado dela"
                    onClick={() => addNo("chamar")}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </Panel>

      {/* ── o desenho se confere ── */}
      <Panel position="bottom-left">
        <div className="w-[330px] overflow-hidden rounded-[12px] border border-[#E8E6F0] bg-white shadow-lg">
          <button
            type="button"
            onClick={() => setPainelProblemas((a) => !a)}
            className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-[#FAFAF7]"
          >
            {erros.length ? (
              <ShieldAlert size={15} color="#B42318" />
            ) : avisos.length ? (
              <AlertTriangle size={15} color="#A9681A" />
            ) : (
              <CheckCircle2 size={15} color="#3DAA5C" />
            )}
            <span className="flex-1 text-[12.5px] font-medium text-[#1A1730]">
              {erros.length === 0 && avisos.length === 0
                ? "O desenho está coerente"
                : [
                    erros.length
                      ? `${erros.length} ${erros.length === 1 ? "erro" : "erros"}`
                      : null,
                    avisos.length
                      ? `${avisos.length} ${avisos.length === 1 ? "aviso" : "avisos"}`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
            </span>
            {painelProblemas ? (
              <ChevronDown size={15} color="#A09DB8" />
            ) : (
              <ChevronUp size={15} color="#A09DB8" />
            )}
          </button>
          {painelProblemas && (
            <div className="max-h-[38vh] overflow-y-auto border-t border-[#F0EEF7]">
              {problemas.length === 0 ? (
                <p className="px-3 py-2.5 text-[11.5px] leading-snug text-[#6B6880]">
                  Todo passo tem para onde ir, todo caminho diz quando é seguido, e
                  ninguém ficou solto no desenho.
                </p>
              ) : (
                problemas.map((p) => {
                  const erro = p.nivel === "erro";
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => irPara(p)}
                      className="flex w-full items-start gap-2 border-b border-[#F7F6FB] px-3 py-2 text-left last:border-b-0 hover:bg-[#FAFAF7]"
                    >
                      <span
                        className="mt-[3px] flex-none"
                        style={{ color: erro ? "#B42318" : "#A9681A" }}
                      >
                        {erro ? <ShieldAlert size={13} /> : <AlertTriangle size={13} />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span
                          className="block text-[11.5px] font-medium leading-snug"
                          style={{ color: erro ? "#B42318" : "#1A1730" }}
                        >
                          {p.titulo}
                        </span>
                        <span className="mt-px block text-[11px] leading-snug text-[#6B6880]">
                          {p.comoResolver}
                        </span>
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>
      </Panel>
    </ReactFlow>
  );
}

function ItemAdd({
  Icone,
  titulo,
  ajuda,
  onClick,
}: {
  Icone: typeof Layers;
  titulo: string;
  ajuda: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-[#F4F1FE]"
    >
      <span className="mt-0.5 grid size-[22px] flex-none place-items-center rounded-md bg-[#EFEAFF]">
        <Icone size={13} color="#6D4AFF" />
      </span>
      <span className="min-w-0">
        <span className="block text-[13px] text-[#1A1730]">{titulo}</span>
        <span className="block text-[11px] leading-snug text-[#6B6880]">{ajuda}</span>
      </span>
    </button>
  );
}
