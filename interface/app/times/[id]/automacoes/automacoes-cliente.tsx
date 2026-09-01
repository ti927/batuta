"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, Copy, Layers, Plus, Sliders, Trash2, X, Zap } from "lucide-react";
import { toast } from "sonner";

import {
  URL_CEREBRO,
  api,
  mensagemDeErro,
  type Agente,
  type Automacao,
  type Cadeia,
  type ConfiguracaoFluxo,
  type Credencial,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { AgendamentosAutomacao } from "@/components/agendamentos-automacao";
import { AutomacaoBuilder } from "@/components/automacao-builder/builder";
import { DialogoConfigFluxo } from "@/components/automacao-builder/config-fluxo";
import { normalizarCadeia } from "@/components/automacao-builder/nucleo";
import type { ConfigGatilho } from "@/components/automacao-builder/inspector";
import { BotaoRodarAgora } from "@/components/botao-rodar-agora";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

const NOVA = "__nova__";

function hhmm(h: unknown, m: unknown): string {
  return `${String(Number(h ?? 8)).padStart(2, "0")}:${String(
    Number(m ?? 0),
  ).padStart(2, "0")}`;
}

function gatilhoDe(a: Automacao | null): ConfigGatilho {
  const tipo = (a?.tipo_gatilho ?? "manual") as ConfigGatilho["tipo"];
  const cfg = (a?.configuracao_gatilho ?? {}) as Record<string, unknown>;
  const midias = cfg.midias;
  return {
    tipo: ["agendamento", "webhook", "comentario_instagram"].includes(tipo)
      ? tipo
      : "manual",
    frequencia: (cfg.frequencia as ConfigGatilho["frequencia"]) ?? "diaria",
    diaSemana: Number(cfg.dia_semana ?? 0),
    diaMes: Number(cfg.dia_mes ?? 1),
    horario: hhmm(cfg.hora, cfg.minuto),
    entrada: (cfg.entrada as string) ?? "",
    credencialId: (cfg.credencial_id as string) ?? "",
    midiasModo: Array.isArray(midias) ? "especificas" : "todas",
    midiasIds: Array.isArray(midias) ? (midias as string[]).join(", ") : "",
    palavraChave: (cfg.palavra_chave as string) ?? "",
    tetoPorHora: Number(cfg.teto_por_hora ?? 50),
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
  cintos,
  instrumentos,
  credenciaisInstagram,
  tipos,
  meuPapel,
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
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  credenciaisInstagram: Credencial[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
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
  // Estado real da automação (inclui as MANUAIS): antes, manual era forçada a inativa e
  // não dava para ligar pela tela — mas o agendamento SÓ dispara automação ativa, então
  // uma manual agendada nunca rodava. Agora toda automação mostra e controla o seu estado.
  const [ativa, setAtiva] = useState(automacao?.ativa ?? false);
  const [cadeia, setCadeia] = useState<Cadeia>(() =>
    normalizarCadeia(
      automacao && (automacao.cadeia?.nos?.length ?? 0) > 0
        ? automacao.cadeia!
        : cadeiaInicial(gatilhoDe(automacao).tipo),
    ),
  );
  // Comportamento do fluxo (perfil + ajustes). Nova automação nasce como "Processo
  // interno" (regra sensata); editando, carrega o que está salvo ({} legado = padrão
  // geral, e a tela avisa). O backend também planta esse padrão ao criar.
  const [configFluxo, setConfigFluxo] = useState<ConfiguracaoFluxo>(() =>
    automacao ? (automacao.configuracao ?? {}) : { perfil: "interno" },
  );
  const [mostrarConfig, setMostrarConfig] = useState(false);

  // PONTO ÚNICO de normalização: toda escrita da cadeia (vinda do construtor — add,
  // remove, conectar, mover, escolher início, editar saída) passa por aqui. Assim a
  // flag `inicial`, a saída do gatilho e os ids/tones de saída ficam SEMPRE coerentes
  // com `cadeia.inicial` — tela == banco == motor. `normalizarCadeia` não toca x/y,
  // então o arrastar segue barato.
  const setCadeiaNorm = (atualiza: (c: Cadeia) => Cadeia) =>
    setCadeia((c) => normalizarCadeia(atualiza(c)));

  const setGatilho = (patch: Partial<ConfigGatilho>) =>
    setGatilhoEstado((g) => ({ ...g, ...patch }));

  // Aviso (não bloqueia edição): nós-agente cujo `ref` aponta para um agente que não
  // existe mais no time. O save é barrado pelo cérebro; aqui só alertamos cedo.
  const agentesIds = new Set(agentes.map((a) => a.id));
  const refsOrfaos = (cadeia.nos ?? []).filter(
    (n) => n.tipo === "agente" && n.ref && !agentesIds.has(n.ref),
  ).length;

  // Duplicar: copia a versão SALVA (o cérebro lê do banco), pergunta só o nome e
  // cria uma cópia independente — que nasce SEMPRE pausada (decisão do maestro:
  // evita uma cópia de automação agendada/webhook disparar em dobro).
  const [dialogoDuplicar, setDialogoDuplicar] = useState(false);
  const [nomeDupla, setNomeDupla] = useState("");
  const [erroDupla, setErroDupla] = useState<string | null>(null);
  const [duplicando, setDuplicando] = useState(false);

  function abrirDuplicar() {
    if (!automacao) return;
    setNomeDupla(`Cópia de ${automacao.nome}`);
    setErroDupla(null);
    setDialogoDuplicar(true);
  }

  async function confirmarDuplicacao() {
    if (!automacao || duplicando) return;
    if (!nomeDupla.trim()) {
      setErroDupla("Dê um nome à cópia.");
      return;
    }
    setDuplicando(true);
    setErroDupla(null);
    try {
      const copia = await api.post<Automacao>(
        `/automacoes/${automacao.id}/duplicar`,
        { nome: nomeDupla.trim() },
      );
      toast.success(`Cópia criada: “${copia.nome}”.`);
      router.refresh();
      onCriou(copia); // adiciona à lista e seleciona a cópia (remonta o editor)
    } catch (e) {
      const msg = mensagemDeErro(e, "Falha ao duplicar a automação");
      setErroDupla(msg);
      toast.error(msg);
      setDuplicando(false);
    }
  }

  function tratar(e: unknown, padrao: string) {
    setErro(mensagemDeErro(e, padrao));
  }

  function montarConfigGatilho(): Record<string, unknown> {
    if (gatilho.tipo === "comentario_instagram") {
      const cfg: Record<string, unknown> = {
        midias:
          gatilho.midiasModo === "especificas"
            ? gatilho.midiasIds
                .split(/[\s,]+/)
                .map((s) => s.trim())
                .filter(Boolean)
            : "todas",
        teto_por_hora: gatilho.tetoPorHora,
      };
      if (gatilho.credencialId) cfg.credencial_id = gatilho.credencialId;
      if (gatilho.palavraChave.trim())
        cfg.palavra_chave = gatilho.palavraChave.trim();
      return cfg;
    }
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
    if (gatilho.tipo === "comentario_instagram" && ativa && !gatilho.credencialId) {
      setErro(
        "Escolha a conta do Instagram antes de ativar o gatilho de comentário.",
      );
      return;
    }
    const corpo = {
      nome: nome.trim(),
      tipo_gatilho: gatilho.tipo,
      configuracao_gatilho: montarConfigGatilho(),
      cadeia: normalizarCadeia(cadeia),
      ativa,
      configuracao: configFluxo,
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
        {/* Estado da PRÓPRIA automação (não do time): pílula sempre visível + interruptor
            para o operador. Vale para TODO gatilho, inclusive Manual — que pode ser
            disparada por agendamento e por isso também precisa poder ficar "ativa". */}
        <Badge variant={ativa ? "success" : "neutral"}>
          {ativa ? "ativa" : "em repouso"}
        </Badge>
        <Badge variant="neutral" className="gap-1">
          <Layers className="size-3" /> {nAgentes} agentes · {nBifurca} bifurcações
        </Badge>
        {souOperador && (
          <label
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
            title={
              gatilho.tipo === "manual"
                ? "Ativa: fica no ar para ser disparada por agendamento. O botão “Rodar” sempre funciona, mesmo em repouso."
                : "Ativa: o gatilho fica armado e a automação pode disparar."
            }
          >
            <input
              type="checkbox"
              className="accent-primary"
              checked={ativa}
              onChange={(e) => setAtiva(e.target.checked)}
            />
            Ativa
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
        {automacao && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/times/${time.id}/execucoes`)}
            title="Ver as execuções deste time"
          >
            <Activity /> Ver execuções
          </Button>
        )}
        {souOperador && automacao && (
          <Button
            variant="outline"
            size="sm"
            onClick={abrirDuplicar}
            disabled={duplicando}
          >
            <Copy /> Duplicar
          </Button>
        )}
        {souOperador && (
          <Button variant="outline" size="sm" onClick={onNova}>
            <Plus /> Nova
          </Button>
        )}
        {souOperador && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMostrarConfig(true)}
            title="Como o motor conduz este fluxo (espera, teto, atendimento)"
          >
            <Sliders /> Fluxo
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

      {refsOrfaos > 0 && (
        <Aviso className="mb-3">
          {refsOrfaos === 1
            ? "Um passo aponta para um agente que não existe mais no time. Troque-o ou remova-o antes de rodar."
            : `${refsOrfaos} passos apontam para agentes que não existem mais no time. Troque-os ou remova-os antes de rodar.`}
        </Aviso>
      )}

      {/* canvas + inspector */}
      <div className="h-[calc(100vh-17rem)] min-h-[480px] overflow-hidden rounded-xl border border-border bg-card">
        <AutomacaoBuilder
          cadeia={cadeia}
          setCadeia={setCadeiaNorm}
          agentes={agentes}
          podeEditar={souOperador}
          gatilho={gatilho}
          setGatilho={setGatilho}
          webhookUrl={
            automacao && gatilho.tipo === "webhook"
              ? `${URL_CEREBRO}/webhooks/automacoes/${automacao.id}`
              : null
          }
          credenciaisInstagram={credenciaisInstagram}
          configFluxo={configFluxo}
          cintos={cintos}
          instrumentosTime={instrumentos}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
        />
      </div>

      {automacao && (
        <AgendamentosAutomacao automacaoId={automacao.id} podeOperar={souOperador} />
      )}

      {mostrarConfig && (
        <DialogoConfigFluxo
          valor={configFluxo}
          onChange={setConfigFluxo}
          podeEditar={souOperador}
          onClose={() => setMostrarConfig(false)}
        />
      )}

      {dialogoDuplicar && automacao && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-foreground/20"
            onClick={() => !duplicando && setDialogoDuplicar(false)}
            aria-label="Fechar"
          />
          <div className="relative w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-lg font-medium text-foreground">
                Duplicar automação
              </h2>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setDialogoDuplicar(false)}
                disabled={duplicando}
                aria-label="Fechar"
              >
                <X className="size-4" />
              </Button>
            </div>

            {erroDupla && (
              <div className="mb-3">
                <Aviso>{erroDupla}</Aviso>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <Label className="flex-col items-start gap-1">
                Nome da cópia
                <Input
                  autoFocus
                  value={nomeDupla}
                  onChange={(e) => setNomeDupla(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") confirmarDuplicacao();
                  }}
                  placeholder="Nome da nova automação"
                  className="w-full"
                />
              </Label>
              <p className="text-xs text-muted-foreground">
                A cópia leva o mesmo gatilho, configuração e fluxo. Nasce{" "}
                <strong>pausada</strong> — revise e ative quando quiser.
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setDialogoDuplicar(false)}
                  disabled={duplicando}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={confirmarDuplicacao}
                  disabled={duplicando || !nomeDupla.trim()}
                >
                  {duplicando ? "Duplicando…" : "Duplicar"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────── lista + seleção ─────────────────────

export function AutomacoesCliente({
  time,
  inicial,
  agentes,
  cintos,
  instrumentos,
  credenciaisInstagram,
  tipos,
  meuPapel,
}: {
  time: Time;
  inicial: Automacao[];
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  instrumentos: Instrumento[];
  credenciaisInstagram: Credencial[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
}) {
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);

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
      cintos={cintos}
      instrumentos={instrumentos}
      credenciaisInstagram={credenciaisInstagram}
      tipos={tipos}
      meuPapel={meuPapel}
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
