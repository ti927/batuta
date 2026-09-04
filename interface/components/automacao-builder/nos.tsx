// Nós custom do React Flow para o construtor de automações.
// Gatilho · Agente · Roteador · Para cada item · Fim — visual do handoff (SPEC §6),
// flat e marca Batuta.

import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  ArrowRightLeft,
  CheckCircle2,
  Layers,
  Pencil,
  Hourglass,
  Repeat2,
  Shield,
  Sparkles,
  Zap,
} from "lucide-react";

import type { Agente, Instrumento, NoCadeia } from "@/lib/api";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { RobotFace } from "@/components/robot-face";

import { NODE_W, tone } from "./nucleo";

// Quantos instrumentos do cinto cabem no nó antes de virar "+X mais".
const MAX_BADGES = 4;

export type DadosNo = {
  no: NoCadeia;
  agente?: Agente;
  indice?: number;
  // Automações da organização — o nó "Chamar outra automação" guarda só o ID do
  // alvo, e o NOME sai daqui. Guardar o nome no próprio nó faria duas fontes de
  // verdade: renomear a automação deixaria o cartão mentindo para sempre.
  automacoes?: { id: string; nome: string }[];
  // Cinto do agente: vira badges no corpo do nó (um por linha).
  cinto?: Instrumento[];
  // Abre o editor do agente (drawer flutuante) direto do nó, sem trocar de aba.
  onEditarAgente?: (agenteId: string) => void;
  // Abre o editor do instrumento ao clicar no badge.
  onEditarInstrumento?: (instrumentoId: string) => void;
};

// Handles de saída (direita), um por saída, distribuídos na vertical.
function HandlesSaida({ no }: { no: NoCadeia }) {
  const saidas = no.saidas ?? [];
  const n = saidas.length;
  return (
    <>
      {saidas.map((s, i) => {
        const t = tone(s.tone);
        const top = `${((i + 1) / (n + 1)) * 100}%`;
        return (
          <Handle
            key={s.id ?? i}
            type="source"
            position={Position.Right}
            id={s.id}
            title={s.rotulo}
            style={{
              top,
              width: 11,
              height: 11,
              background: "#fff",
              border: `2px solid ${t.dot}`,
            }}
          />
        );
      })}
    </>
  );
}

function HandleEntrada() {
  return (
    <Handle
      type="target"
      position={Position.Left}
      style={{ width: 11, height: 11, background: "#fff", border: "2px solid #C3BFD6" }}
    />
  );
}

const cartao = (selected: boolean, bg: string, bdSel: string, bd: string) =>
  ({
    width: NODE_W,
    background: bg,
    border: `1px solid ${selected ? bdSel : bd}`,
    borderRadius: 12,
    boxShadow: selected
      ? "0 0 0 3px rgba(109,74,255,.14)"
      : "0 1px 2px rgba(26,23,48,.05)",
    transition: "box-shadow .12s, border-color .12s",
  }) as const;

export function GatilhoNode({ data, selected }: NodeProps) {
  const no = (data as DadosNo).no;
  const rotuloGatilho =
    no.gatilho === "agendamento"
      ? "Agendamento"
      : no.gatilho === "webhook"
        ? "Webhook"
        : no.gatilho === "comentario_instagram"
          ? "Comentário do Instagram"
          : "Manual";
  return (
    <div style={{ ...cartao(!!selected, "#fff", "#6D4AFF", "#E8E6F0"), height: 66 }}>
      <div className="flex h-full items-center gap-3 px-3.5">
        <span
          className="grid size-[34px] flex-none place-items-center rounded-[9px]"
          style={{ background: "#6D4AFF" }}
        >
          <Zap size={18} color="#fff" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#A09DB8" }}
          >
            Gatilho
          </div>
          <div className="text-[14.5px] font-medium" style={{ color: "#1A1730" }}>
            {rotuloGatilho}
          </div>
        </div>
      </div>
      <HandlesSaida no={no} />
    </div>
  );
}

export function FimNode({ selected }: NodeProps) {
  return (
    <div
      style={{ ...cartao(!!selected, "#F4FAF6", "#6D4AFF", "#CDE9D5"), height: 56 }}
    >
      <div className="flex h-full items-center gap-2.5 px-4">
        <CheckCircle2 size={20} color="#3DAA5C" />
        <div className="text-[14.5px] font-medium" style={{ color: "#2F7D45" }}>
          Fim · entrega ao usuário
        </div>
      </div>
      <HandleEntrada />
    </div>
  );
}

export function RoteadorNode({ data, selected }: NodeProps) {
  const no = (data as DadosNo).no;
  return (
    <div style={{ ...cartao(!!selected, "#FBFAFF", "#6D4AFF", "#E0DAF6"), height: 74 }}>
      <div className="flex h-full items-center gap-2.5 px-3.5">
        <span
          className="grid size-8 flex-none place-items-center rounded-[9px]"
          style={{ background: "#EFEAFF" }}
        >
          <Layers size={17} color="#6D4AFF" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#9A8CCB" }}
          >
            Roteador
          </div>
          <div
            className="truncate text-[14px] font-medium"
            style={{ color: "#1A1730" }}
          >
            {no.nome || "Decisão"}
          </div>
        </div>
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

/**
 * "Para cada item" — nó estrutural (não roda IA, não conta como passo). Lê uma lista
 * da ficha da execução e repete o trecho seguinte uma vez por item, cada repetição
 * como um ramo próprio do grafo.
 *
 * Visualmente é primo do roteador (mesmo cartão lilás, ícone de repetição), porque a
 * família é a mesma: peças que dirigem o fluxo sem produzir conteúdo.
 */
export function CadaNode({ data, selected }: NodeProps) {
  const no = (data as DadosNo).no;
  const lista = (no.lista ?? "").trim();
  return (
    <div style={{ ...cartao(!!selected, "#FBFAFF", "#6D4AFF", "#E0DAF6"), height: 74 }}>
      <div className="flex h-full items-center gap-2.5 px-3.5">
        <span
          className="grid size-8 flex-none place-items-center rounded-[9px]"
          style={{ background: "#EFEAFF" }}
        >
          <Repeat2 size={17} color="#6D4AFF" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#9A8CCB" }}
          >
            Para cada item
          </div>
          <div
            className="truncate text-[14px] font-medium"
            style={{ color: lista ? "#1A1730" : "#B42318" }}
          >
            {lista ? `de ${lista}` : "escolha a lista"}
          </div>
        </div>
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

/**
 * O nó "Esperar" (Onda 3): segura o fluxo por um tempo e o solta depois, sem perder a
 * ficha nem o ponto do grafo.
 *
 * Mesma família visual do roteador e do "Para cada item" — peças que dirigem o fluxo
 * sem produzir conteúdo. Sem tempo definido, o cartão diz isso em vermelho: um nó que
 * parece configurado e não está seria a pior das telas.
 */
export function EsperarNode({ data, selected }: NodeProps) {
  const no = (data as DadosNo).no;
  const quanto = Number(no.espera?.quanto ?? 0);
  const unidade = no.espera?.unidade ?? "minutos";
  return (
    <div style={{ ...cartao(!!selected, "#FBFAFF", "#6D4AFF", "#E0DAF6"), height: 74 }}>
      <div className="flex h-full items-center gap-2.5 px-3.5">
        <span
          className="grid size-8 flex-none place-items-center rounded-[9px]"
          style={{ background: "#EFEAFF" }}
        >
          <Hourglass size={17} color="#6D4AFF" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#9A8CCB" }}
          >
            Esperar
          </div>
          <div
            className="truncate text-[14px] font-medium"
            style={{ color: quanto > 0 ? "#1A1730" : "#B42318" }}
          >
            {quanto > 0 ? `${quanto} ${unidade}` : "defina o tempo"}
          </div>
        </div>
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

/**
 * O nó "Chamar outra automação" (Onda 3): roda outra automação inteira e ESPERA o
 * resultado dela para seguir.
 *
 * Mesma família visual do "Esperar" e do roteador — peças que dirigem o fluxo sem
 * produzir conteúdo por si. Sem automação escolhida, o cartão diz isso em vermelho:
 * aqui o aviso importa ainda mais que no "Esperar", porque um `chamar` sem alvo não
 * atrasa o fluxo — ele deixa de fazer o trabalho.
 */
export function ChamarNode({ data, selected }: NodeProps) {
  const d = data as DadosNo;
  const no = d.no;
  const alvoId = no.chamar?.automacao_id ?? "";
  const alvo = (d.automacoes ?? []).find((a) => a.id === alvoId);
  // Alvo escolhido mas fora da lista = automação apagada (ou de outra organização).
  // Dizer "escolha a automação" ali seria mentira; o cartão diz o que houve.
  const rotulo = alvo?.nome ?? (alvoId ? "automação não encontrada" : "escolha a automação");
  return (
    <div style={{ ...cartao(!!selected, "#FBFAFF", "#6D4AFF", "#E0DAF6"), height: 74 }}>
      <div className="flex h-full items-center gap-2.5 px-3.5">
        <span
          className="grid size-8 flex-none place-items-center rounded-[9px]"
          style={{ background: "#EFEAFF" }}
        >
          <ArrowRightLeft size={17} color="#6D4AFF" />
        </span>
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium uppercase tracking-wide"
            style={{ color: "#9A8CCB" }}
          >
            Chamar automação
          </div>
          <div
            className="truncate text-[14px] font-medium"
            style={{ color: alvo ? "#1A1730" : "#B42318" }}
          >
            {rotulo}
          </div>
        </div>
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

export function AgenteNode({ data, selected }: NodeProps) {
  const d = data as DadosNo;
  const no = d.no;
  const ag = d.agente;
  const modelo = (ag?.modelo_ia ?? "").replace("claude-", "");
  // Cinto: mostra até MAX_BADGES; o excedente vira "+X mais" (abre o drawer do
  // agente, onde o cinto inteiro é gerido). Se passar de MAX por só 1, ainda
  // mostra todos (não esconde 1 só atrás de um "+1 mais").
  const cinto = d.cinto ?? [];
  const mostrados = cinto.length <= MAX_BADGES ? cinto : cinto.slice(0, MAX_BADGES - 1);
  const resto = cinto.length - mostrados.length;
  return (
    <div
      className="relative"
      style={{ ...cartao(!!selected, "#fff", "#6D4AFF", "#E8E6F0"), minHeight: 90 }}
    >
      {/* Lápis na borda esquerda: abre o editor do agente sem sair do construtor.
          `nodrag` para não arrastar o nó; stopPropagation para não roubar o clique. */}
      {ag && d.onEditarAgente && (
        <button
          type="button"
          className="nodrag absolute -left-2.5 -top-2.5 z-10 grid size-[26px] place-items-center rounded-full border border-[#E8E6F0] bg-white text-[#6D4AFF] shadow-sm transition-colors hover:bg-[#F4F1FE]"
          title={`Editar o agente “${ag.nome}”`}
          aria-label={`Editar o agente ${ag.nome}`}
          onClick={(e) => {
            e.stopPropagation();
            d.onEditarAgente!(ag.id);
          }}
        >
          <Pencil size={13} />
        </button>
      )}
      <div className="flex h-full flex-col gap-1.5 p-[11px_13px]">
        <div className="flex items-center gap-2.5">
          <RobotFace size={28} indice={d.indice ?? 0} lider={ag?.papel === "lider"} />
          <span
            className="flex-1 truncate text-[14px] font-medium"
            style={{ color: "#1A1730" }}
          >
            {ag?.nome ?? "Agente"}
          </span>
          {no.inicial && (
            <span
              className="flex-none rounded-full px-1.5 py-px text-[10px] font-medium"
              style={{ color: "#3D2A99", background: "#EFEAFF" }}
            >
              início
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {modelo && (
            <span
              className="inline-flex items-center gap-1 text-[11px]"
              style={{ color: "#6B6880" }}
            >
              <Sparkles size={11} color="#6D4AFF" /> {modelo}
            </span>
          )}
          {/* Pode esperar uma pessoa: derivado do CINTO (o agente tem o instrumento
              de pedir aprovação), não de um interruptor no desenho — quem decide
              esperar é ele, quando o markdown dele mandar. */}
          {cinto.some((i) => i.tipo === "pedir_aprovacao") && (
            <span
              className="inline-flex items-center gap-1 rounded-full border px-1.5 py-px text-[10.5px] font-medium"
              style={{ color: "#A9681A", background: "#FDF1E3", borderColor: "#F0D9B4" }}
            >
              <Shield size={10} /> pode esperar você
            </span>
          )}
        </div>

        {/* Cinto do agente: um instrumento por linha. Clicar abre o drawer do
            instrumento; "+X mais" abre o drawer do agente (cinto completo). */}
        {cinto.length > 0 && (
          <div className="mt-0.5 flex flex-col gap-1">
            {mostrados.map((inst) => (
              <button
                key={inst.id}
                type="button"
                className="nodrag flex items-center gap-1.5 rounded-md border border-[#ECEAF4] bg-[#FAFAF7] px-1.5 py-1 text-left transition-colors hover:border-[#D9D2F7] hover:bg-[#F4F1FE]"
                title={`Editar o instrumento “${inst.nome}”`}
                onClick={(e) => {
                  e.stopPropagation();
                  d.onEditarInstrumento?.(inst.id);
                }}
              >
                <IconeInstrumento
                  icone={inst.icone}
                  className="size-3 flex-none text-[#6D4AFF]"
                />
                <span className="truncate text-[11px] text-[#4A4860]">
                  {inst.nome}
                </span>
              </button>
            ))}
            {resto > 0 && ag && (
              <button
                type="button"
                className="nodrag rounded-md px-1.5 py-0.5 text-left text-[11px] font-medium text-[#6D4AFF] hover:underline"
                onClick={(e) => {
                  e.stopPropagation();
                  d.onEditarAgente?.(ag.id);
                }}
              >
                +{resto} mais…
              </button>
            )}
          </div>
        )}
      </div>
      <HandleEntrada />
      <HandlesSaida no={no} />
    </div>
  );
}

export const tiposDeNo = {
  gatilho: GatilhoNode,
  agente: AgenteNode,
  roteador: RoteadorNode,
  cada: CadaNode,
  esperar: EsperarNode,
  chamar: ChamarNode,
  fim: FimNode,
};
