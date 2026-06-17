// Inspector do construtor: edita o nó selecionado (gatilho/agente/roteador/fim).
// É onde nascem as bifurcações (saídas com rótulo + destino + tom) e o portão de
// aprovação — incluindo o canal de aprovação por mensageria (decisão do maestro).

import {
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Clock,
  Layers,
  Play,
  Plus,
  Shield,
  X,
  Zap,
} from "lucide-react";

import type {
  Agente,
  Cadeia,
  Instrumento,
  NoCadeia,
  SaidaCadeia,
  ToneSaida,
} from "@/lib/api";
import { RobotFace } from "@/components/robot-face";

import { TONE_KEYS, tone } from "./nucleo";

// índice 0 = segunda, alinhado ao agendador do cérebro (agendador.py)
const DIAS_SEMANA = [
  "Segunda",
  "Terça",
  "Quarta",
  "Quinta",
  "Sexta",
  "Sábado",
  "Domingo",
];

export type ConfigGatilho = {
  tipo: "manual" | "agendamento" | "webhook";
  frequencia: "diaria" | "semanal" | "mensal";
  diaSemana: number;
  diaMes: number;
  horario: string;
  entrada: string;
};

function nomeNo(no: NoCadeia, agentes: Agente[]): string {
  if (no.tipo === "agente")
    return agentes.find((a) => a.id === no.ref)?.nome ?? "Agente";
  if (no.tipo === "roteador") return no.nome || "Roteador";
  if (no.tipo === "fim") return "Fim · entrega ao usuário";
  return "Gatilho";
}

const inputCls =
  "w-full rounded-md border border-[#E8E6F0] bg-white px-2.5 py-1.5 text-[13px] text-[#1A1730] outline-none focus:border-primary";

function LinhaSaida({
  no,
  sa,
  idx,
  cadeia,
  agentes,
  podeEditar,
  onChange,
  onRemove,
}: {
  no: NoCadeia;
  sa: SaidaCadeia;
  idx: number;
  cadeia: Cadeia;
  agentes: Agente[];
  podeEditar: boolean;
  onChange: (patch: Partial<SaidaCadeia>) => void;
  onRemove: () => void;
}) {
  const tn = tone(sa.tone);
  const destinos = (cadeia.nos ?? []).filter((n) => n.tipo !== "gatilho");
  return (
    <div className="flex flex-col gap-2.5 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-2.5">
      <div className="flex items-center gap-2">
        <span
          className="size-2.5 flex-none rounded-full"
          style={{ background: tn.dot }}
        />
        <span className="text-[11.5px] font-medium" style={{ color: "#A09DB8" }}>
          Saída {idx + 1}
        </span>
        <div className="flex-1" />
        {podeEditar && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remover saída"
            className="p-0.5 text-[#A09DB8] hover:text-foreground"
          >
            <X size={15} />
          </button>
        )}
      </div>
      <div>
        <label className="mb-1 block text-[11px]" style={{ color: "#6B6880" }}>
          {no.gate
            ? "Decisão (o que você responde)"
            : no.tipo === "roteador"
              ? "Quando a tarefa que chega for…"
              : "Quando o resultado for…"}
        </label>
        <input
          className={inputCls}
          value={sa.rotulo}
          disabled={!podeEditar}
          onChange={(e) => onChange({ rotulo: e.target.value })}
        />
      </div>
      <div>
        <label
          className="mb-1 flex items-center gap-1.5 text-[11px]"
          style={{ color: "#6B6880" }}
        >
          <ArrowRight size={12} color="#A09DB8" /> vai para
        </label>
        <select
          className={`${inputCls} cursor-pointer`}
          value={sa.destino}
          disabled={!podeEditar}
          onChange={(e) => onChange({ destino: e.target.value })}
        >
          {destinos.map((d) => (
            <option key={d.id} value={d.id}>
              {nomeNo(d, agentes)}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-1.5">
        {TONE_KEYS.map((tk) => {
          const t = tone(tk);
          const on = (sa.tone ?? "normal") === tk;
          return (
            <button
              key={tk}
              type="button"
              disabled={!podeEditar}
              onClick={() => onChange({ tone: tk as ToneSaida })}
              title={t.rotulo}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-md border px-1 py-1.5 text-[11px]"
              style={{
                borderColor: on ? t.dot : "#E8E6F0",
                background: on ? t.pillBg : "#fff",
                color: on ? t.pillFg : "#A09DB8",
                fontWeight: on ? 500 : 400,
              }}
            >
              <span className="size-[7px] rounded-full" style={{ background: t.dot }} />
              {t.rotulo.split(" ")[0]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Inspector({
  no,
  cadeia,
  agentes,
  canais,
  podeEditar,
  gatilho,
  setGatilho,
  webhookUrl,
  onDefinirInicial,
  onPatchNode,
  onPatchSaida,
  onAddSaida,
  onRemoveSaida,
  onDeleteNode,
}: {
  no: NoCadeia | null;
  cadeia: Cadeia;
  agentes: Agente[];
  canais: Instrumento[];
  podeEditar: boolean;
  gatilho: ConfigGatilho;
  setGatilho: (patch: Partial<ConfigGatilho>) => void;
  webhookUrl?: string | null;
  onDefinirInicial: (nodeId: string) => void;
  onPatchNode: (id: string, patch: Partial<NoCadeia>) => void;
  onPatchSaida: (id: string, sid: string, patch: Partial<SaidaCadeia>) => void;
  onAddSaida: (id: string) => void;
  onRemoveSaida: (id: string, sid: string) => void;
  onDeleteNode: (id: string) => void;
}) {
  if (!no) {
    return (
      <div className="p-7 text-[#6B6880]">
        <div className="mb-3 grid size-[42px] place-items-center rounded-[11px] bg-[#EFEAFF]">
          <Layers size={22} color="#6D4AFF" />
        </div>
        <div className="mb-1.5 text-[14.5px] font-medium text-[#1A1730]">
          Selecione um nó
        </div>
        <p className="text-[13px] leading-relaxed">
          Clique em qualquer nó do grafo para editar suas saídas. É aqui que você
          cria as condicionais: cada saída tem um rótulo (&ldquo;quando o resultado
          for X&rdquo;) e um destino.
        </p>
      </div>
    );
  }

  const ag = no.tipo === "agente" ? agentes.find((a) => a.id === no.ref) : undefined;
  const indice = ag ? agentes.findIndex((a) => a.id === ag.id) : 0;
  // Candidatos a "primeiro nó": só o que o motor sabe executar (agente/roteador).
  const inicios = (cadeia.nos ?? []).filter(
    (n) => n.tipo === "agente" || n.tipo === "roteador",
  );

  return (
    <div className="flex h-full flex-col">
      {/* cabeçalho */}
      <div className="flex items-start gap-3 border-b border-[#E8E6F0] p-4">
        {no.tipo === "agente" ? (
          <RobotFace size={38} indice={indice} lider={ag?.papel === "lider"} />
        ) : (
          <span
            className="grid size-[38px] flex-none place-items-center rounded-[10px]"
            style={{ background: no.tipo === "fim" ? "#E6F4EA" : "#EFEAFF" }}
          >
            {no.tipo === "gatilho" ? (
              <Zap size={19} color="#6D4AFF" />
            ) : no.tipo === "fim" ? (
              <CheckCircle2 size={19} color="#3DAA5C" />
            ) : (
              <Layers size={19} color="#6D4AFF" />
            )}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="text-[16px] font-medium text-[#1A1730]">
            {nomeNo(no, agentes)}
          </div>
          <div className="mt-0.5 text-[12.5px] text-[#6B6880]">
            {no.tipo === "agente"
              ? "Trabalhador do fluxo"
              : no.tipo === "gatilho"
                ? "O que inicia este fluxo"
                : no.tipo === "fim"
                  ? "Entrega o resultado a quem pediu"
                  : "Decide o caminho da tarefa"}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 pb-8">
        {/* gatilho */}
        {no.tipo === "gatilho" && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2">
              {(
                [
                  ["manual", Play, "Dispara pelo botão de teste."],
                  ["agendamento", Clock, "Roda sozinho num horário fixo."],
                  ["webhook", Zap, "Um sistema externo dispara via URL."],
                ] as const
              ).map(([k, Ic, hint]) => {
                const on = gatilho.tipo === k;
                return (
                  <button
                    key={k}
                    type="button"
                    disabled={!podeEditar}
                    onClick={() => setGatilho({ tipo: k })}
                    className="flex items-start gap-2.5 rounded-[9px] border p-2.5 text-left"
                    style={{
                      borderColor: on ? "#6D4AFF" : "#E8E6F0",
                      background: on ? "#F4F1FE" : "#fff",
                    }}
                  >
                    <span
                      className="grid size-[30px] flex-none place-items-center rounded-lg"
                      style={{ background: on ? "#6D4AFF" : "#EFEAFF" }}
                    >
                      <Ic size={15} color={on ? "#fff" : "#6D4AFF"} />
                    </span>
                    <div>
                      <div className="text-[13.5px] font-medium capitalize text-[#1A1730]">
                        {k}
                      </div>
                      <div className="mt-px text-[11.5px] leading-snug text-[#6B6880]">
                        {hint}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Começa em: o primeiro nó que o gatilho aciona (= cadeia.inicial). */}
            <div className="flex flex-col gap-1.5 rounded-[9px] border border-[#E8E6F0] p-3">
              <span
                className="flex items-center gap-1.5 text-[12px] font-medium"
                style={{ color: "#1A1730" }}
              >
                <Play size={12} color="#6D4AFF" /> Começa em
              </span>
              {inicios.length > 0 ? (
                <select
                  className={`${inputCls} cursor-pointer`}
                  value={cadeia.inicial ?? ""}
                  disabled={!podeEditar}
                  onChange={(e) => onDefinirInicial(e.target.value)}
                >
                  {!cadeia.inicial && (
                    <option value="" disabled>
                      Escolha o primeiro agente…
                    </option>
                  )}
                  {inicios.map((n) => (
                    <option key={n.id} value={n.id}>
                      {nomeNo(n, agentes)}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-[11.5px]" style={{ color: "#A09DB8" }}>
                  Adicione um agente ao fluxo para escolher por onde ele começa.
                </span>
              )}
              <span
                className="text-[11px] leading-snug"
                style={{ color: "#A09DB8" }}
              >
                O primeiro agente que o gatilho aciona quando o fluxo dispara.
              </span>
            </div>

            {gatilho.tipo === "agendamento" && (
              <div className="flex flex-col gap-2 rounded-[9px] border border-[#E8E6F0] p-3">
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Frequência
                  <select
                    className={`${inputCls} mt-1`}
                    value={gatilho.frequencia}
                    disabled={!podeEditar}
                    onChange={(e) =>
                      setGatilho({
                        frequencia: e.target.value as ConfigGatilho["frequencia"],
                      })
                    }
                  >
                    <option value="diaria">Todo dia</option>
                    <option value="semanal">Toda semana</option>
                    <option value="mensal">Todo mês</option>
                  </select>
                </label>
                {gatilho.frequencia === "semanal" && (
                  <label className="text-[11px]" style={{ color: "#6B6880" }}>
                    Dia da semana
                    <select
                      className={`${inputCls} mt-1`}
                      value={gatilho.diaSemana}
                      disabled={!podeEditar}
                      onChange={(e) =>
                        setGatilho({ diaSemana: Number(e.target.value) })
                      }
                    >
                      {DIAS_SEMANA.map((d, i) => (
                        <option key={i} value={i}>
                          {d}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {gatilho.frequencia === "mensal" && (
                  <label className="text-[11px]" style={{ color: "#6B6880" }}>
                    Dia do mês
                    <input
                      type="number"
                      min={1}
                      max={31}
                      className={`${inputCls} mt-1`}
                      value={gatilho.diaMes}
                      disabled={!podeEditar}
                      onChange={(e) => setGatilho({ diaMes: Number(e.target.value) })}
                    />
                  </label>
                )}
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Horário (fuso de Brasília)
                  <input
                    type="time"
                    className={`${inputCls} mt-1`}
                    value={gatilho.horario}
                    disabled={!podeEditar}
                    onChange={(e) => setGatilho({ horario: e.target.value })}
                  />
                </label>
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Mensagem que o gatilho envia ao fluxo
                  <textarea
                    className={`${inputCls} mt-1 min-h-16`}
                    placeholder="Ex.: Gere o lembrete mensal de fechamento."
                    value={gatilho.entrada}
                    disabled={!podeEditar}
                    onChange={(e) => setGatilho({ entrada: e.target.value })}
                  />
                </label>
              </div>
            )}

            {gatilho.tipo === "webhook" && (
              <p className="text-[12px] leading-relaxed text-[#6B6880]">
                {webhookUrl
                  ? "Um sistema externo dispara este fluxo por uma URL (POST). O corpo enviado vira a entrada."
                  : "Salve a automação para gerar a URL do webhook."}
              </p>
            )}
          </div>
        )}

        {/* agente: portão (+ aprovação por canal) */}
        {no.tipo === "agente" && (
          <div className="mb-4 flex flex-col gap-2.5">
            <div className="flex items-start gap-3 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3">
              <Shield
                size={17}
                color={no.gate ? "#E89638" : "#A09DB8"}
                className="mt-0.5"
              />
              <div className="flex-1">
                <div className="text-[13.5px] font-medium text-[#1A1730]">
                  Portão de aprovação
                </div>
                <div className="mt-0.5 text-[11.5px] leading-snug text-[#6B6880]">
                  O fluxo pausa aqui e espera você decidir. Sua resposta escolhe a
                  saída.
                </div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={!!no.gate}
                disabled={!podeEditar}
                onClick={() => onPatchNode(no.id, { gate: !no.gate })}
                className="relative h-[23px] w-10 flex-none rounded-full transition-colors"
                style={{ background: no.gate ? "#6D4AFF" : "#D6D3E8" }}
              >
                <span
                  className="absolute top-[3px] size-[17px] rounded-full bg-white transition-all"
                  style={{ left: no.gate ? 20 : 3 }}
                />
              </button>
            </div>

            {/* Aprovação por canal (só faz sentido com o portão ligado) */}
            {no.gate && (
              <div className="flex flex-col gap-2 rounded-[10px] border border-[#E8E6F0] p-3">
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Pedir aprovação por
                  <select
                    className={`${inputCls} mt-1 cursor-pointer`}
                    value={no.aprovacao?.instrumento_id ?? ""}
                    disabled={!podeEditar || canais.length === 0}
                    onChange={(e) =>
                      onPatchNode(no.id, {
                        aprovacao: e.target.value
                          ? {
                              instrumento_id: e.target.value,
                              destinatario: no.aprovacao?.destinatario ?? "",
                            }
                          : null,
                      })
                    }
                  >
                    <option value="">Só pela tela</option>
                    {canais.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                  </select>
                </label>
                {no.aprovacao?.instrumento_id && (
                  <label className="text-[11px]" style={{ color: "#6B6880" }}>
                    Destinatário (quem aprova neste canal)
                    <input
                      className={`${inputCls} mt-1`}
                      placeholder="ex.: id do chat do Telegram"
                      value={no.aprovacao?.destinatario ?? ""}
                      disabled={!podeEditar}
                      onChange={(e) =>
                        onPatchNode(no.id, {
                          aprovacao: {
                            instrumento_id: no.aprovacao?.instrumento_id ?? null,
                            destinatario: e.target.value,
                          },
                        })
                      }
                    />
                  </label>
                )}
                {no.aprovacao?.instrumento_id &&
                  !(no.aprovacao?.destinatario ?? "").trim() && (
                    <span className="text-[11px] text-warning">
                      ⚠ Sem destinatário, a aprovação por canal não funciona — vale só
                      a tela.
                    </span>
                  )}
                {canais.length === 0 && (
                  <span className="text-[11px]" style={{ color: "#A09DB8" }}>
                    Sem canais no time. Crie um instrumento de canal (Telegram) para
                    aprovar por mensagem.
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {/* roteador: o que é + nome */}
        {no.tipo === "roteador" && (
          <div className="mb-4 flex flex-col gap-3">
            <p className="flex gap-2 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3 text-[11.5px] leading-relaxed text-[#6B6880]">
              <Layers size={14} color="#6D4AFF" className="mt-px flex-none" />
              <span>
                O roteador não tem agente: ele <b>lê a tarefa que chega</b> e a
                encaminha por um dos caminhos abaixo, conforme a condição de cada
                saída — sem produzir trabalho. Ligue um nó até ele (arraste da
                bolinha da esquerda) para que algo chegue aqui.
              </span>
            </p>
            <label
              className="block text-[12px] font-medium"
              style={{ color: "#6B6880" }}
            >
              Nome da decisão
              <input
                className={`${inputCls} mt-1.5`}
                value={no.nome ?? ""}
                placeholder="ex.: É sobre agenda ou exame?"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { nome: e.target.value })}
              />
            </label>
          </div>
        )}

        {/* saídas (todos menos fim) */}
        {no.tipo !== "fim" && no.tipo !== "gatilho" && (
          <div>
            <div className="mb-2.5 inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[#1A1730]">
              <Zap size={14} color="#6D4AFF" /> Saídas
              {(no.saidas ?? []).length > 1
                ? ` · bifurca em ${no.saidas.length}`
                : ""}
            </div>
            <div className="flex flex-col gap-2.5">
              {(no.saidas ?? []).map((sa, i) => (
                <LinhaSaida
                  key={sa.id ?? i}
                  no={no}
                  sa={sa}
                  idx={i}
                  cadeia={cadeia}
                  agentes={agentes}
                  podeEditar={podeEditar}
                  onChange={(patch) => onPatchSaida(no.id, sa.id ?? "", patch)}
                  onRemove={() => onRemoveSaida(no.id, sa.id ?? "")}
                />
              ))}
            </div>
            {podeEditar && (
              <button
                type="button"
                onClick={() => onAddSaida(no.id)}
                className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-[9px] border border-dashed border-[#C9B8FF] bg-[#F4F1FE] p-2.5 text-[13px] font-medium text-primary"
              >
                <Plus size={15} /> Adicionar saída (bifurcar)
              </button>
            )}
            {(no.saidas ?? []).length > 1 && (
              <p className="mt-2 flex gap-1.5 text-[11.5px] leading-normal text-[#6B6880]">
                <CircleHelp size={13} color="#A09DB8" className="mt-px flex-none" />
                {no.gate
                  ? "Sua resposta no portão escolhe por qual saída o fluxo segue."
                  : no.tipo === "roteador"
                    ? "O roteador lê a tarefa que chega e segue pela saída cuja condição casar."
                    : "O agente classifica o resultado e segue por uma das saídas."}
              </p>
            )}
          </div>
        )}

        {no.tipo === "fim" && (
          <p className="text-[13px] leading-relaxed text-[#6B6880]">
            Quando a tarefa chega aqui, o resultado final é entregue a quem disparou o
            fluxo.
          </p>
        )}
      </div>

      {/* rodapé: remover (só agente/roteador) */}
      {podeEditar && (no.tipo === "agente" || no.tipo === "roteador") && (
        <div className="border-t border-[#E8E6F0] p-3.5">
          <button
            type="button"
            onClick={() => onDeleteNode(no.id)}
            className="inline-flex items-center gap-1.5 text-[13px] text-destructive"
          >
            <X size={15} /> Remover nó do fluxo
          </button>
        </div>
      )}
    </div>
  );
}
