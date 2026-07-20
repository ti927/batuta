"use client";

import "@xyflow/react/dist/style.css";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  applyNodeChanges,
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useUpdateNodeInternals,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import { ChevronDown, Layers, Plus } from "lucide-react";

import type {
  Agente,
  Cadeia,
  ConfiguracaoFluxo,
  Credencial,
  Instrumento,
  NoCadeia,
  PapelAcesso,
  SaidaCadeia,
  Time,
  TipoInstrumento,
} from "@/lib/api";
import { DrawerAgente } from "@/components/drawer-agente";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { RobotFace } from "@/components/robot-face";

import { tiposDeAresta } from "./aresta";
import { Inspector, type ConfigGatilho } from "./inspector";
import { indexar, novoIdNo, novoIdSaida, tone } from "./nucleo";
import { tiposDeNo } from "./nos";

// Registro de tipos de nó/aresta como referência estável (fora do componente) —
// exigência do React Flow.
const NODE_TYPES = tiposDeNo;
const EDGE_TYPES = tiposDeAresta;

function primeiroDestino(cadeia: Cadeia, exceto: string): string {
  const alvo = (cadeia.nos ?? []).find(
    (n) => n.tipo !== "gatilho" && n.id !== exceto,
  );
  const fim = (cadeia.nos ?? []).find((n) => n.tipo === "fim");
  return alvo?.id ?? fim?.id ?? "fim";
}

type BuilderProps = {
  cadeia: Cadeia;
  setCadeia: (atualiza: (c: Cadeia) => Cadeia) => void;
  agentes: Agente[];
  canais: Instrumento[];
  podeEditar: boolean;
  gatilho: ConfigGatilho;
  setGatilho: (patch: Partial<ConfigGatilho>) => void;
  webhookUrl?: string | null;
  credenciaisInstagram: Credencial[];
  // Config do fluxo (Tipo de fluxo) — o drawer do portão herda dela e sobrepõe por-nó.
  configFluxo: ConfiguracaoFluxo;
  // Para editar o agente/instrumento de um nó pelo drawer flutuante (sem trocar de aba).
  cintos: Record<string, Instrumento[]>;
  instrumentosTime: Instrumento[];
  tipos: TipoInstrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
};

// `useUpdateNodeInternals` exige estar dentro de um ReactFlowProvider; por isso o
// construtor real vive em BuilderInterno e o export embrulha no provider.
export function AutomacaoBuilder(props: BuilderProps) {
  return (
    <ReactFlowProvider>
      <BuilderInterno {...props} />
    </ReactFlowProvider>
  );
}

function BuilderInterno({
  cadeia,
  setCadeia,
  agentes,
  canais,
  podeEditar,
  gatilho,
  setGatilho,
  webhookUrl,
  credenciaisInstagram,
  configFluxo,
  cintos,
  instrumentosTime,
  tipos,
  time,
  meuPapel,
}: BuilderProps) {
  const [selId, setSelId] = useState<string | null>(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [addAberto, setAddAberto] = useState(false);
  // Agente/instrumento cujo editor (drawer flutuante) está aberto, acionado pelo
  // lápis ou pelos badges do nó.
  const [editAgenteId, setEditAgenteId] = useState<string | null>(null);
  const [editInstrumentoId, setEditInstrumentoId] = useState<string | null>(null);
  const editarAgente = useCallback(
    (agenteId: string) => setEditAgenteId(agenteId),
    [],
  );
  const editarInstrumento = useCallback(
    (instrumentoId: string) => setEditInstrumentoId(instrumentoId),
    [],
  );

  const idx = useMemo(() => indexar(cadeia), [cadeia]);
  const sel = selId ? (idx[selId] ?? null) : null;
  const agenteEdit = editAgenteId
    ? (agentes.find((a) => a.id === editAgenteId) ?? null)
    : null;
  const instrumentoEdit = editInstrumentoId
    ? (instrumentosTime.find((i) => i.id === editInstrumentoId) ?? null)
    : null;

  // ── nós do React Flow ──
  // O React Flow precisa ser DONO do seu próprio array de nós: é nele que
  // `applyNodeChanges` grava `measured` (medição do ResizeObserver) — sem isso
  // o nó nunca "inicializa" e o arrastar quebra (erro #015). A `cadeia` segue
  // sendo a fonte da verdade persistida; `rfNodes` é uma projeção viva.
  const projetarNo = useCallback(
    (no: NoCadeia): Node => {
      const agente =
        no.tipo === "agente" ? agentes.find((a) => a.id === no.ref) : undefined;
      const indice = agente ? agentes.findIndex((a) => a.id === agente.id) : 0;
      const cinto =
        no.tipo === "agente" ? (cintos[no.ref ?? ""] ?? []) : undefined;
      // o gatilho mostra o tipo escolhido no inspector (fonte: estado do gatilho)
      const noView =
        no.tipo === "gatilho" ? { ...no, gatilho: gatilho.tipo } : no;
      return {
        id: no.id,
        type: no.tipo,
        position: { x: no.x ?? 0, y: no.y ?? 0 },
        data: {
          no: noView,
          agente,
          indice,
          cinto,
          onEditarAgente: editarAgente,
          // editar instrumento é só para quem opera (a tela de Instrumentos
          // também só abre o editor para operador).
          onEditarInstrumento: podeEditar ? editarInstrumento : undefined,
        },
        draggable: podeEditar,
        selected: no.id === selId,
      };
    },
    [agentes, cintos, gatilho.tipo, podeEditar, selId, editarAgente, editarInstrumento],
  );

  // Assinatura do que afeta a PROJEÇÃO dos nós. Dispara a reconciliação
  // cadeia→RF. Inclui TUDO que muda o visual do nó (ids, tipo, ref, gate, nome,
  // inicial e o CONTEÚDO das saídas — rótulo/destino/tone/lane afetam handles e
  // rótulos), o tipo do gatilho, o modo de edição e a seleção. NÃO inclui x/y de
  // propósito: a posição é mão única (RF→cadeia via onNodesChange); reprojetar a
  // cada frame de arrasto criaria novos objetos de nó e brigaria com o drag
  // interno do React Flow. A posição persistida na cadeia é relida na próxima
  // reconciliação estrutural.
  const assinatura = useMemo(
    () =>
      JSON.stringify({
        n: (cadeia.nos ?? []).map((n) => ({
          i: n.id,
          t: n.tipo,
          r: n.ref,
          g: n.gate,
          nm: n.nome,
          ini: n.inicial,
          s: (n.saidas ?? []).map((s) => [
            s.id,
            s.rotulo,
            s.destino,
            s.tone,
            s.lane,
          ]),
        })),
        gat: gatilho.tipo,
        e: podeEditar,
        sel: selId,
        // identidade do agente: renomear/trocar modelo pelo drawer refaz o rótulo
        // do nó (a reconciliação preserva posição/medição).
        ag: agentes.map((a) => [a.id, a.nome, a.modelo_ia, a.papel]),
        // cinto de cada agente: pendurar/tirar/renomear instrumento refaz os
        // badges do nó (e a altura, que o React Flow re-mede).
        cin: (cadeia.nos ?? [])
          .filter((n) => n.tipo === "agente")
          .map((n) => [
            n.ref,
            (cintos[n.ref ?? ""] ?? [])
              .map((i) => `${i.id}:${i.nome}:${i.icone ?? ""}`)
              .join(","),
          ]),
      }),
    [cadeia, gatilho.tipo, podeEditar, selId, agentes, cintos],
  );

  const [rfNodes, setRfNodes] = useState<Node[]>(() =>
    (cadeia.nos ?? []).map(projetarNo),
  );
  // Guarda de reconciliação. `setState` no corpo do render (com guarda de
  // igualdade) é o padrão oficial do React para sincronizar com props/estado
  // externo e NÃO é pego pela regra `react-hooks/set-state-in-effect` (que só
  // vale para effects). Roda uma vez por mudança de assinatura (sem loop).
  const [prevSig, setPrevSig] = useState(assinatura);
  if (assinatura !== prevSig) {
    setPrevSig(assinatura);
    setRfNodes((prev) => {
      const anteriores = new Map(prev.map((n) => [n.id, n]));
      return (cadeia.nos ?? []).map((no) => {
        const base = projetarNo(no);
        const old = anteriores.get(no.id);
        // Nó já existente: preserva a medição do RF (senão "des-inicializa" e o
        // #015 volta) e a posição viva do drag. Nó novo: sem `measured` → o
        // ResizeObserver mede e emite `dimensions` via onNodesChange.
        return old
          ? {
              ...base,
              position: old.position,
              measured: old.measured,
              width: old.width,
              height: old.height,
            }
          : base;
      });
    });
  }

  // Recomputa os "handle bounds" do React Flow quando a ESTRUTURA muda (saída
  // adicionada/removida, gatilho religado, nó novo). Como preservamos `measured`
  // p/ o arrastar (#015), o RF não recomputa as âncoras dos handles sozinho — sem
  // isto, arestas para handles novos/alterados não desenham (some o cordão do
  // gatilho e as bifurcações além da 1ª). É a API oficial p/ handles dinâmicos.
  const idsComHandles = useMemo(
    () => (cadeia.nos ?? []).map((n) => n.id),
    // `assinatura` já captura a estrutura (ids/tipos/saídas), excluindo x/y.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [assinatura],
  );
  useEffect(() => {
    for (const id of idsComHandles) updateNodeInternals(id);
  }, [idsComHandles, updateNodeInternals]);

  // ── arestas (uma por saída) ──
  const edges = useMemo<Edge[]>(() => {
    const out: Edge[] = [];
    for (const no of cadeia.nos ?? []) {
      for (const sa of no.saidas ?? []) {
        if (!idx[sa.destino]) continue;
        const ativo = selId === no.id;
        const stroke = ativo ? "#6D4AFF" : tone(sa.tone).stroke;
        out.push({
          id: `${no.id}:${sa.id}`,
          source: no.id,
          sourceHandle: sa.id,
          target: sa.destino,
          type: "cond",
          data: {
            rotulo: sa.rotulo,
            tone: sa.tone,
            lane: sa.lane,
            gate: no.gate,
            ativo,
            onPick: setSelId,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: stroke,
            width: 16,
            height: 16,
          },
        });
      }
    }
    return out;
  }, [cadeia, idx, selId]);

  // ── mutações da cadeia ──
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // 1) Deixa o RF gravar TODAS as changes (incl. `dimensions`/`select`) no
      //    seu próprio array — é o que popula `measured` e mata o #015.
      setRfNodes((nds) => applyNodeChanges(changes, nds));
      // 2) Espelha só a posição de volta na cadeia (persistência). `measured` é
      //    transitório e não se persiste.
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

  const patchNode = useCallback(
    (id: string, patch: Partial<NoCadeia>) =>
      setCadeia((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) => (n.id === id ? { ...n, ...patch } : n)),
      })),
    [setCadeia],
  );

  const patchSaida = useCallback(
    (id: string, sid: string, patch: Partial<SaidaCadeia>) =>
      setCadeia((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) =>
          n.id === id
            ? {
                ...n,
                saidas: (n.saidas ?? []).map((s) =>
                  s.id === sid ? { ...s, ...patch } : s,
                ),
              }
            : n,
        ),
      })),
    [setCadeia],
  );

  const addSaida = useCallback(
    (id: string) =>
      setCadeia((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) =>
          n.id === id
            ? {
                ...n,
                saidas: [
                  ...(n.saidas ?? []),
                  {
                    id: novoIdSaida(),
                    rotulo: "nova condição",
                    destino: primeiroDestino(c, id),
                    tone: "normal" as const,
                  },
                ],
              }
            : n,
        ),
      })),
    [setCadeia],
  );

  const removeSaida = useCallback(
    (id: string, sid: string) =>
      setCadeia((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) =>
          n.id === id
            ? { ...n, saidas: (n.saidas ?? []).filter((s) => s.id !== sid) }
            : n,
        ),
      })),
    [setCadeia],
  );

  // As mutações abaixo mexem SÓ no que é fonte de verdade (estrutura + `cadeia.inicial`).
  // A flag `n.inicial` e a saída do gatilho são derivadas por `normalizarCadeia`, que
  // o pai aplica a TODA escrita (ver automacoes-cliente.tsx). Por isso aqui não as
  // tocamos — assim não há como divergirem.
  const deleteNode = useCallback(
    (id: string) => {
      setCadeia((c) => ({
        ...c,
        // se o removido era o início, zera — normalizarCadeia escolhe o próximo.
        inicial: c.inicial === id ? undefined : c.inicial,
        nos: (c.nos ?? [])
          .filter((n) => n.id !== id)
          .map((n) => ({
            ...n,
            saidas: (n.saidas ?? []).filter((s) => s.destino !== id),
          })),
      }));
      setSelId(null);
    },
    [setCadeia],
  );

  // Escolher o primeiro nó = setar só `cadeia.inicial`; o gatilho e as flags saem
  // corretos pela normalização do pai.
  const definirInicial = useCallback(
    (nodeId: string) => setCadeia((c) => ({ ...c, inicial: nodeId })),
    [setCadeia],
  );

  const addNode = useCallback(
    (kind: "agente" | "roteador", ref?: string) => {
      const id = novoIdNo(kind);
      setCadeia((c) => {
        const fim = (c.nos ?? []).find((n) => n.tipo === "fim");
        const baseX = 360 + ((c.nos?.length ?? 0) % 4) * 40;
        // 1º agente do fluxo: vira o início (só setamos `inicial`; gatilho/flags
        // saem da normalização do pai).
        const ehPrimeiroAgente =
          kind === "agente" &&
          !(c.nos ?? []).some((n) => n.tipo === "agente") &&
          !c.inicial;
        const novo: NoCadeia =
          kind === "roteador"
            ? {
                id,
                tipo: "roteador",
                nome: "Nova decisão",
                x: baseX,
                y: 360,
                saidas: [
                  {
                    id: novoIdSaida(),
                    rotulo: "caso A",
                    destino: fim?.id ?? "fim",
                    tone: "normal",
                  },
                ],
              }
            : {
                id,
                tipo: "agente",
                ref,
                x: baseX,
                y: 360,
                saidas: [
                  {
                    id: novoIdSaida(),
                    rotulo: "resultado",
                    destino: fim?.id ?? "fim",
                    tone: "normal",
                  },
                ],
              };
        return {
          ...c,
          inicial: ehPrimeiroAgente ? id : c.inicial,
          nos: [...(c.nos ?? []), novo],
        };
      });
      setSelId(id);
      setAddAberto(false);
    },
    [setCadeia],
  );

  const onConnect = useCallback(
    (conn: Connection) => {
      if (!podeEditar || !conn.source || !conn.target) return;
      // Conectar A PARTIR do gatilho = escolher o primeiro nó (substitui, não soma).
      if (idx[conn.source]?.tipo === "gatilho") {
        definirInicial(conn.target);
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
                    id: novoIdSaida(),
                    rotulo: "nova condição",
                    destino: conn.target!,
                    tone: "normal" as const,
                  },
                ],
              }
            : n,
        ),
      }));
    },
    [setCadeia, podeEditar, idx, definirInicial],
  );

  return (
    <div className="flex h-full min-h-0">
      {/* canvas */}
      <div className="relative min-w-0 flex-1">
        <ReactFlow
          nodes={rfNodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          onNodesChange={onNodesChange}
          onConnect={onConnect}
          onNodeClick={(_, n) => setSelId(n.id)}
          onPaneClick={() => {
            setSelId(null);
            setAddAberto(false);
          }}
          nodesConnectable={podeEditar}
          nodesDraggable={podeEditar}
          elementsSelectable
          minZoom={0.4}
          maxZoom={1.6}
          defaultViewport={{ x: 40, y: 20, zoom: 0.8 }}
          proOptions={{ hideAttribution: true }}
          style={{ background: "#FAFAF7" }}
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1.1} color="#E0DDF0" />
          <Controls showInteractive={false} />
          {podeEditar && (
            <Panel position="top-right">
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setAddAberto((o) => !o)}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#E8E6F0] bg-white px-3 text-[13px] font-medium text-foreground shadow-sm hover:bg-[#FAFAF7]"
                >
                  <Plus size={15} color="#6D4AFF" /> Adicionar nó
                  <ChevronDown size={14} color="#A09DB8" />
                </button>
                {addAberto && (
                  <div className="absolute right-0 top-11 z-30 w-60 rounded-[10px] border border-[#E8E6F0] bg-white p-1.5 shadow-lg">
                    <div className="px-2 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-[#A09DB8]">
                      Agente do time
                    </div>
                    {agentes.map((a, i) => (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => addNode("agente", a.id)}
                        className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] text-foreground hover:bg-[#F4F1FE]"
                      >
                        <RobotFace size={22} indice={i} lider={a.papel === "lider"} />
                        {a.nome}
                      </button>
                    ))}
                    {agentes.length === 0 && (
                      <div className="px-2 py-1.5 text-[12px] text-muted-foreground">
                        Crie agentes no time primeiro.
                      </div>
                    )}
                    <div className="my-1 h-px bg-[#E8E6F0]" />
                    <button
                      type="button"
                      onClick={() => addNode("roteador")}
                      className="flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-[#F4F1FE]"
                    >
                      <span className="mt-0.5 grid size-[22px] flex-none place-items-center rounded-md bg-[#EFEAFF]">
                        <Layers size={13} color="#6D4AFF" />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[13px] text-foreground">
                          Roteador / condição
                        </span>
                        <span className="block text-[11px] leading-snug text-muted-foreground">
                          Encaminha a tarefa sem rodar agente
                        </span>
                      </span>
                    </button>
                  </div>
                )}
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* inspector */}
      <div className="w-[348px] flex-none overflow-hidden border-l border-[#E8E6F0] bg-white">
        <Inspector
          no={sel}
          cadeia={cadeia}
          agentes={agentes}
          canais={canais}
          podeEditar={podeEditar}
          gatilho={gatilho}
          setGatilho={setGatilho}
          webhookUrl={webhookUrl}
          credenciaisInstagram={credenciaisInstagram}
          configFluxo={configFluxo}
          onDefinirInicial={definirInicial}
          onPatchNode={patchNode}
          onPatchSaida={patchSaida}
          onAddSaida={addSaida}
          onRemoveSaida={removeSaida}
          onDeleteNode={deleteNode}
        />
      </div>

      {/* Editor do agente: drawer flutuante (o mesmo da aba Agentes), aberto pelo
          lápis do nó. Fica sobre o canvas/inspetor — edições de nó são rápidas. */}
      {agenteEdit && (
        <DrawerAgente
          key={agenteEdit.id}
          agente={agenteEdit}
          indice={agentes.findIndex((a) => a.id === agenteEdit.id)}
          cinto={cintos[agenteEdit.id] ?? []}
          instrumentosTime={instrumentosTime}
          time={time}
          meuPapel={meuPapel}
          tipos={tipos}
          conversaId={null}
          onFechar={() => setEditAgenteId(null)}
        />
      )}

      {/* Editor do instrumento: aberto pelos badges do nó. Fica aberto até fechar
          manualmente (não fecha ao salvar/conectar canal). */}
      {instrumentoEdit && (
        <DrawerInstrumento
          key={instrumentoEdit.id}
          instrumento={instrumentoEdit}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
          onFechar={() => setEditInstrumentoId(null)}
          onSalvou={(salvo) => setEditInstrumentoId(salvo.id)}
        />
      )}
    </div>
  );
}
