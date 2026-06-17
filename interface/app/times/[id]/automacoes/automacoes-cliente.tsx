"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Layers, Plus, Trash2, Zap } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Automacao,
  type Cadeia,
  type Instrumento,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { AutomacaoBuilder } from "@/components/automacao-builder/builder";
import { sanearGatilho } from "@/components/automacao-builder/nucleo";
import type { ConfigGatilho } from "@/components/automacao-builder/inspector";
import { BotaoRodarAgora } from "@/components/botao-rodar-agora";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

// Tipos de instrumento que são canais de mensageria (podem ser canal de aprovação).
const CANAIS_TIPOS = ["enviar_telegram", "enviar_whatsapp"];
const NOVA = "__nova__";

function hhmm(h: unknown, m: unknown): string {
  return `${String(Number(h ?? 8)).padStart(2, "0")}:${String(
    Number(m ?? 0),
  ).padStart(2, "0")}`;
}

function gatilhoDe(a: Automacao | null): ConfigGatilho {
  const tipo = (a?.tipo_gatilho ?? "manual") as ConfigGatilho["tipo"];
  const cfg = (a?.configuracao_gatilho ?? {}) as Record<string, unknown>;
  return {
    tipo: ["agendamento", "webhook"].includes(tipo) ? tipo : "manual",
    frequencia: (cfg.frequencia as ConfigGatilho["frequencia"]) ?? "diaria",
    diaSemana: Number(cfg.dia_semana ?? 0),
    diaMes: Number(cfg.dia_mes ?? 1),
    horario: hhmm(cfg.hora, cfg.minuto),
    entrada: (cfg.entrada as string) ?? "",
  };
}

// Grafo inicial de uma automação nova: só gatilho + fim (o usuário adiciona agentes).
function cadeiaInicial(tipo: ConfigGatilho["tipo"]): Cadeia {
  return {
    inicial: undefined,
    nos: [
      { id: "gatilho", tipo: "gatilho", gatilho: tipo, x: 60, y: 240, saidas: [] },
      { id: "fim", tipo: "fim", x: 760, y: 250, saidas: [] },
    ],
  };
}

// ───────────────────── editor de UMA automação ─────────────────────
// Remontado por `key={selId}` no pai: o estado editável é inicializado dos props,
// sem efeito de sincronização (padrão recomendado pelo React).

function EditorAutomacao({
  time,
  automacao,
  automacoes,
  agentes,
  canais,
  souOperador,
  souAdmin,
  onSelecionar,
  onNova,
  onCriou,
  onAtualizou,
  onRemoveu,
}: {
  time: Time;
  automacao: Automacao | null;
  automacoes: Automacao[];
  agentes: Agente[];
  canais: Instrumento[];
  souOperador: boolean;
  souAdmin: boolean;
  onSelecionar: (id: string) => void;
  onNova: () => void;
  onCriou: (a: Automacao) => void;
  onAtualizou: (a: Automacao) => void;
  onRemoveu: (id: string) => void;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const [nome, setNome] = useState(automacao?.nome ?? "");
  const [gatilho, setGatilhoEstado] = useState<ConfigGatilho>(() =>
    gatilhoDe(automacao),
  );
  const [ativa, setAtiva] = useState(
    automacao ? (automacao.tipo_gatilho === "manual" ? true : automacao.ativa) : true,
  );
  const [cadeia, setCadeia] = useState<Cadeia>(() =>
    sanearGatilho(
      automacao && (automacao.cadeia?.nos?.length ?? 0) > 0
        ? automacao.cadeia!
        : cadeiaInicial(gatilhoDe(automacao).tipo),
    ),
  );

  const setGatilho = (patch: Partial<ConfigGatilho>) =>
    setGatilhoEstado((g) => ({ ...g, ...patch }));

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function montarConfigGatilho(): Record<string, unknown> {
    if (gatilho.tipo !== "agendamento") return {};
    const [h, m] = gatilho.horario.split(":").map(Number);
    const cfg: Record<string, unknown> = {
      frequencia: gatilho.frequencia,
      hora: h,
      minuto: m,
      entrada: gatilho.entrada,
    };
    if (gatilho.frequencia === "semanal") cfg.dia_semana = gatilho.diaSemana;
    if (gatilho.frequencia === "mensal") cfg.dia_mes = gatilho.diaMes;
    return cfg;
  }

  async function salvar() {
    if (!nome.trim()) {
      setErro("Dê um nome à automação.");
      return;
    }
    if (gatilho.tipo === "agendamento" && !gatilho.entrada.trim()) {
      setErro("No agendamento, escreva a mensagem que o gatilho envia ao fluxo.");
      return;
    }
    const corpo = {
      nome: nome.trim(),
      tipo_gatilho: gatilho.tipo,
      configuracao_gatilho: montarConfigGatilho(),
      cadeia,
      ativa: gatilho.tipo === "manual" ? false : ativa,
    };
    setSalvando(true);
    try {
      if (!automacao) {
        const nova = await api.post<Automacao>(`/times/${time.id}/automacoes`, corpo);
        onCriou(nova);
      } else {
        const atual = await api.put<Automacao>(`/automacoes/${automacao.id}`, corpo);
        onAtualizou(atual);
      }
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar a automação");
    } finally {
      setSalvando(false);
    }
  }

  async function remover() {
    if (!automacao) return;
    if (!confirm(`Remover a automação "${automacao.nome}"?`)) return;
    try {
      await api.delete(`/automacoes/${automacao.id}`);
      onRemoveu(automacao.id);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover a automação");
    }
  }

  const webhookSalvo = !!automacao && gatilho.tipo === "webhook";
  const nAgentes = (cadeia.nos ?? []).filter((n) => n.tipo === "agente").length;
  const nBifurca = (cadeia.nos ?? []).filter(
    (n) => (n.saidas?.length ?? 0) > 1,
  ).length;

  return (
    <div className="flex w-full flex-col px-4 py-4 sm:px-6">
      {/* toolbar da automação */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Input
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Nome da automação"
          disabled={!souOperador}
          className="h-9 w-64"
        />
        <Badge variant="neutral" className="gap-1">
          <Layers className="size-3" /> {nAgentes} agentes · {nBifurca} bifurcações
        </Badge>
        {gatilho.tipo !== "manual" && souOperador && (
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="accent-primary"
              checked={ativa}
              onChange={(e) => setAtiva(e.target.checked)}
            />
            gatilho ativo
          </label>
        )}
        <div className="flex-1" />
        {automacoes.length > 1 && automacao && (
          <Select
            value={automacao.id}
            onChange={(e) => onSelecionar(e.target.value)}
            className="h-9 w-auto"
          >
            {automacoes.map((a) => (
              <option key={a.id} value={a.id}>
                {a.nome}
              </option>
            ))}
          </Select>
        )}
        {souOperador && automacao && (
          <BotaoRodarAgora
            timeId={time.id}
            automacoes={[{ id: automacao.id, nome }]}
            rotulo="Rodar"
            variant="outline"
            size="sm"
          />
        )}
        {souOperador && (
          <Button variant="outline" size="sm" onClick={onNova}>
            <Plus /> Nova
          </Button>
        )}
        {souOperador && (
          <Button size="sm" onClick={salvar} disabled={salvando}>
            {salvando ? "Salvando…" : "Salvar"}
          </Button>
        )}
        {souAdmin && automacao && (
          <Button variant="destructive" size="sm" onClick={remover}>
            <Trash2 />
          </Button>
        )}
      </div>

      {erro && <Aviso className="mb-3">{erro}</Aviso>}

      {/* canvas + inspector */}
      <div className="h-[calc(100vh-17rem)] min-h-[480px] overflow-hidden rounded-xl border border-border bg-card">
        <AutomacaoBuilder
          cadeia={cadeia}
          setCadeia={setCadeia}
          agentes={agentes}
          canais={canais}
          podeEditar={souOperador}
          gatilho={gatilho}
          setGatilho={setGatilho}
          webhookUrl={webhookSalvo ? "salvo" : null}
        />
      </div>
    </div>
  );
}

// ───────────────────── lista + seleção ─────────────────────

export function AutomacoesCliente({
  time,
  inicial,
  agentes,
  instrumentos,
  meuPapel,
}: {
  time: Time;
  inicial: Automacao[];
  agentes: Agente[];
  instrumentos: Instrumento[];
  meuPapel: PapelAcesso | null;
}) {
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);
  const canais = instrumentos.filter((i) => CANAIS_TIPOS.includes(i.tipo));

  // A lista vive em estado local após montar (criar/editar/remover atualizam aqui;
  // o router.refresh sincroniza os contadores do servidor).
  const [automacoes, setAutomacoes] = useState<Automacao[]>(inicial);
  const [selId, setSelId] = useState<string | null>(inicial[0]?.id ?? null);

  if (agentes.length === 0) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
        <EstadoVazio icone={Zap} titulo="Crie agentes antes da automação.">
          A automação encadeia os agentes do time — adicione agentes primeiro.
        </EstadoVazio>
      </main>
    );
  }

  if (selId === null) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
        <EstadoVazio icone={Zap} titulo="Nenhuma automação ainda.">
          {souOperador
            ? "Monte o fluxo do time como um grafo: gatilho, agentes e o fim."
            : "As automações deste time aparecerão aqui."}
        </EstadoVazio>
        {souOperador && (
          <Button className="mt-4" onClick={() => setSelId(NOVA)}>
            <Plus /> Nova automação
          </Button>
        )}
      </main>
    );
  }

  const automacao = selId === NOVA ? null : automacoes.find((a) => a.id === selId) ?? null;

  return (
    <EditorAutomacao
      key={selId}
      time={time}
      automacao={automacao}
      automacoes={automacoes}
      agentes={agentes}
      canais={canais}
      souOperador={souOperador}
      souAdmin={souAdmin}
      onSelecionar={(id) => setSelId(id)}
      onNova={() => setSelId(NOVA)}
      onCriou={(a) => {
        setAutomacoes((lista) => [...lista, a]);
        setSelId(a.id);
      }}
      onAtualizou={(a) =>
        setAutomacoes((lista) => lista.map((x) => (x.id === a.id ? a : x)))
      }
      onRemoveu={(id) => {
        const resto = automacoes.filter((a) => a.id !== id);
        setAutomacoes(resto);
        setSelId(resto[0]?.id ?? null);
      }}
    />
  );
}
