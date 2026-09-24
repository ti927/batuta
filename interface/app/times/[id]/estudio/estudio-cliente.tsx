"use client";

// O cliente do estúdio: escolhe a automação, segura o desenho em edição e salva.
//
// Salva pela MESMA porta da tela clássica (PUT /automacoes/{id}) e normaliza com a
// MESMA função (`normalizarCadeia`). Isso é regra, não conveniência: se as duas telas
// escrevessem de jeitos diferentes, alternar entre elas viraria a pior categoria de
// bug — a que só aparece depois, em produção, sem ninguém saber qual das duas mexeu.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Copy,
  MoreHorizontal,
  Plus,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import {
  URL_CEREBRO,
  api,
  mensagemDeErro,
  type Agente,
  type Automacao,
  type AutomacaoDaOrg,
  type Cadeia,
  type ConfiguracaoFluxo,
  type Credencial,
  type Instrumento,
  type NoCadeia,
  type PapelAcesso,
  type SaidaCadeia,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { normalizarCadeia } from "@/components/automacao-builder/nucleo";
import type { ConfigGatilho } from "@/components/automacao-builder/nucleo";
import { CanvasEstudio } from "@/components/estudio/canvas";
import { PainelEstudio } from "@/components/estudio/painel";
import type { Problema } from "@/components/estudio/problemas";
import { DrawerAgente } from "@/components/drawer-agente";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { AgendamentosAutomacao } from "@/components/agendamentos-automacao";
import { BotaoRodarAgora } from "@/components/botao-rodar-agora";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

function hhmm(h: unknown, m: unknown): string {
  return `${String(Number(h ?? 8)).padStart(2, "0")}:${String(Number(m ?? 0)).padStart(2, "0")}`;
}

/** O estado do gatilho a partir da automação salva — espelho do cliente clássico. */
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

export function EstudioCliente({
  versao,
  time,
  inicial,
  agentes,
  cintos,
  instrumentos,
  credenciaisInstagram,
  tipos,
  meuPapel,
}: {
  // Assinatura do dado PERSISTIDO. Era a `key` deste componente — e por isso todo
  // salvamento remontava a tela e jogava a seleção de volta na PRIMEIRA automação.
  // Virou prop: quem remonta é só o editor, e a escolha da pessoa fica de pé.
  versao: string;
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
  const [automacoes, setAutomacoes] = useState(inicial);
  const [selId, setSelId] = useState<string | null>(inicial[0]?.id ?? null);

  // Dado novo do servidor: recarrega a lista, sem mexer na seleção (padrão oficial de
  // "resetar estado quando a prop muda": setState no render, com guarda).
  const [versaoVista, setVersaoVista] = useState(versao);
  if (versao !== versaoVista) {
    setVersaoVista(versao);
    setAutomacoes(inicial);
  }

  // A selecionada sumiu? cai na primeira, em vez de abrir um editor vazio.
  const selEfetivo = automacoes.some((a) => a.id === selId)
    ? selId
    : (automacoes[0]?.id ?? null);
  const automacao = automacoes.find((a) => a.id === selEfetivo) ?? null;

  // O passo aberto no painel também vive AQUI, pelo mesmo motivo: o editor remonta a
  // cada salvamento, e perder de vista o passo que você acabou de mexer é a mesma
  // chateação, só menor. Trocar de automação limpa (o id seria de outro desenho).
  const [noSel, setNoSel] = useState<string | null>(null);
  const [saidaSel, setSaidaSel] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);
  const [autVista, setAutVista] = useState(selEfetivo);
  if (selEfetivo !== autVista) {
    setAutVista(selEfetivo);
    setNoSel(null);
    setSaidaSel(null);
  }

  // Time sem nenhuma automação: o Estúdio CRIA. Isto mandava a pessoa para a aba
  // Automações — e essa aba está saindo, então o estado vazio viraria um beco.
  async function criarPrimeira() {
    if (criando) return;
    setCriando(true);
    try {
      const criada = await api.post<Automacao>(`/times/${time.id}/automacoes`, {
        nome: "Nova automação",
        tipo_gatilho: "manual",
      });
      setAutomacoes((l) => [...l, criada]);
      setSelId(criada.id);
      toast.success("Automação criada. Desenhe o fluxo e salve.");
    } catch (e) {
      toast.error(mensagemDeErro(e, "Falha ao criar a automação"));
    } finally {
      setCriando(false);
    }
  }

  if (!automacoes.length) {
    return (
      <div className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
        <EstadoVazio
          titulo="Nenhuma automação ainda"
          acao={
            souOperador ? (
              <Button onClick={criarPrimeira} disabled={criando}>
                <Plus className="size-4" />{" "}
                {criando ? "Criando…" : "Criar a primeira automação"}
              </Button>
            ) : undefined
          }
        >
          Uma automação é o fluxo que encadeia os agentes deste time: o que dispara,
          quem faz o quê, e por qual caminho a tarefa segue.
        </EstadoVazio>
      </div>
    );
  }

  return (
    <EditorEstudio
      // Remonta ao TROCAR de automação ou quando o dado salvo muda — que era o motivo
      // da `key` na página. Quem guarda a seleção não remonta mais.
      key={`${selEfetivo ?? "nenhuma"}::${versao}`}
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
      noSel={noSel}
      setNoSel={setNoSel}
      saidaSel={saidaSel}
      setSaidaSel={setSaidaSel}
      onSelecionar={setSelId}
      onAtualizou={(a) => setAutomacoes((l) => l.map((x) => (x.id === a.id ? a : x)))}
      onCriou={(a) => {
        setAutomacoes((l) => [...l, a]);
        setSelId(a.id);
      }}
      onRemoveu={(id) => {
        setAutomacoes((l) => l.filter((x) => x.id !== id));
        setSelId(null);
      }}
    />
  );
}

function EditorEstudio({
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
  noSel,
  setNoSel,
  saidaSel,
  setSaidaSel,
  onSelecionar,
  onAtualizou,
  onCriou,
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
  noSel: string | null;
  setNoSel: (id: string | null) => void;
  saidaSel: string | null;
  setSaidaSel: (id: string | null) => void;
  onSelecionar: (id: string) => void;
  onAtualizou: (a: Automacao) => void;
  onCriou: (a: Automacao) => void;
  onRemoveu: (id: string) => void;
}) {
  const router = useRouter();
  const souAdmin = podeAdmin(meuPapel);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [problemas, setProblemas] = useState<Problema[]>([]);
  const [editAgenteId, setEditAgenteId] = useState<string | null>(null);
  const [editInstrumentoId, setEditInstrumentoId] = useState<string | null>(null);
  const [maisAberto, setMaisAberto] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  // A automação está no ar? É estado DELA, não do time, e vale para todo gatilho —
  // inclusive o manual, que pode ser disparado por agendamento.
  const [ativa, setAtiva] = useState(automacao?.ativa ?? false);

  const [nome, setNome] = useState(automacao?.nome ?? "");
  const [gatilho, setGatilhoEstado] = useState<ConfigGatilho>(() => gatilhoDe(automacao));
  const [cadeia, setCadeia] = useState<Cadeia>(() =>
    normalizarCadeia(automacao?.cadeia ?? { nos: [] }),
  );
  // O comportamento do fluxo (perfil, tetos, portão) é editado na tela clássica; aqui
  // ele viaja intacto para o salvamento — nunca zerado por omissão.
  // As REGRAS DO FLUXO agora são editáveis aqui (painel da direita, nada selecionado).
  // Eram só repassadas intactas: quem editava pelo Estúdio não via os ajustes — nem que
  // eles existiam.
  // Não precisa de efeito para ressincronizar: o `EditorEstudio` inteiro remonta por
  // `key` quando a automação troca ou quando o dado salvo muda, então o inicializador
  // já roda de novo com o valor certo.
  const [configFluxo, setConfigFluxo] = useState<ConfiguracaoFluxo>(
    () => automacao?.configuracao ?? {},
  );

  const setGatilho = useCallback(
    (patch: Partial<ConfigGatilho>) => setGatilhoEstado((g) => ({ ...g, ...patch })),
    [],
  );

  // PONTO ÚNICO de normalização — a mesma disciplina do construtor clássico.
  const setCadeiaNorm = useCallback(
    (atualiza: (c: Cadeia) => Cadeia) => setCadeia((c) => normalizarCadeia(atualiza(c))),
    [],
  );

  const [automacoesOrg, setAutomacoesOrg] = useState<AutomacaoDaOrg[]>([]);
  useEffect(() => {
    let vivo = true;
    api
      .get<AutomacaoDaOrg[]>(`/organizacoes/${time.organizacao_id}/automacoes`)
      .then((d) => vivo && setAutomacoesOrg(d))
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [time.organizacao_id]);

  const idx = useMemo(
    () => new Map((cadeia.nos ?? []).map((n) => [n.id, n])),
    [cadeia],
  );
  const no = noSel ? (idx.get(noSel) ?? null) : null;
  const agenteEdit = editAgenteId
    ? (agentes.find((a) => a.id === editAgenteId) ?? null)
    : null;
  const instrumentoEdit = editInstrumentoId
    ? (instrumentos.find((i) => i.id === editInstrumentoId) ?? null)
    : null;

  // ── mutações do desenho ──
  const patchNode = useCallback(
    (id: string, patch: Partial<NoCadeia>) =>
      setCadeiaNorm((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) => (n.id === id ? { ...n, ...patch } : n)),
      })),
    [setCadeiaNorm],
  );

  const patchSaida = useCallback(
    (id: string, sid: string, patch: Partial<SaidaCadeia>) =>
      setCadeiaNorm((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) =>
          n.id === id
            ? {
                ...n,
                saidas: (n.saidas ?? []).map((s) => (s.id === sid ? { ...s, ...patch } : s)),
              }
            : n,
        ),
      })),
    [setCadeiaNorm],
  );

  const addSaida = useCallback(
    (id: string) =>
      setCadeiaNorm((c) => {
        const alvo =
          (c.nos ?? []).find((n) => n.tipo !== "gatilho" && n.id !== id)?.id ??
          (c.nos ?? []).find((n) => n.tipo === "fim")?.id ??
          "fim";
        return {
          ...c,
          nos: (c.nos ?? []).map((n) =>
            n.id === id
              ? {
                  ...n,
                  saidas: [
                    ...(n.saidas ?? []),
                    {
                      id: `s_${Math.random().toString(36).slice(2, 8)}`,
                      rotulo: "novo caminho",
                      quando: "",
                      tipo: "condicional" as const,
                      destino: alvo,
                      tone: "normal" as const,
                    },
                  ],
                }
              : n,
          ),
        };
      }),
    [setCadeiaNorm],
  );

  const removeSaida = useCallback(
    (id: string, sid: string) => {
      setCadeiaNorm((c) => ({
        ...c,
        nos: (c.nos ?? []).map((n) =>
          n.id === id ? { ...n, saidas: (n.saidas ?? []).filter((s) => s.id !== sid) } : n,
        ),
      }));
      if (saidaSel === sid) setSaidaSel(null);
    },
    [setCadeiaNorm, saidaSel, setSaidaSel],
  );

  const deleteNode = useCallback(
    (id: string) => {
      setCadeiaNorm((c) => ({
        ...c,
        inicial: c.inicial === id ? undefined : c.inicial,
        nos: (c.nos ?? [])
          .filter((n) => n.id !== id)
          .map((n) => ({ ...n, saidas: (n.saidas ?? []).filter((s) => s.destino !== id) })),
      }));
      setNoSel(null);
      setSaidaSel(null);
    },
    [setCadeiaNorm, setNoSel, setSaidaSel],
  );

  const definirInicial = useCallback(
    (id: string) => setCadeiaNorm((c) => ({ ...c, inicial: id || undefined })),
    [setCadeiaNorm],
  );

  // ── ações da automação ──
  async function nova() {
    if (ocupado) return;
    setOcupado(true);
    try {
      const criada = await api.post<Automacao>(`/times/${time.id}/automacoes`, {
        nome: "Nova automação",
        tipo_gatilho: "manual",
      });
      toast.success("Automação criada. Desenhe o fluxo e salve.");
      onCriou(criada);
      router.refresh();
    } catch (e) {
      const msg = mensagemDeErro(e, "Falha ao criar a automação");
      setErro(msg);
      toast.error(msg);
    } finally {
      setOcupado(false);
    }
  }

  async function duplicar() {
    if (!automacao || ocupado) return;
    const nomeCopia = prompt("Nome da cópia:", `Cópia de ${automacao.nome}`);
    if (!nomeCopia?.trim()) return;
    setOcupado(true);
    try {
      const copia = await api.post<Automacao>(`/automacoes/${automacao.id}/duplicar`, {
        nome: nomeCopia.trim(),
      });
      toast.success(`Cópia criada: “${copia.nome}”.`);
      onCriou(copia);
      router.refresh();
    } catch (e) {
      const msg = mensagemDeErro(e, "Falha ao duplicar a automação");
      setErro(msg);
      toast.error(msg);
    } finally {
      setOcupado(false);
    }
  }

  async function remover() {
    if (!automacao || ocupado) return;
    // Apagar uma automação leva o desenho junto e não tem volta — a confirmação diz o
    // nome para ninguém apagar a errada por reflexo.
    if (!confirm(`Remover a automação “${automacao.nome}”? Isso não tem volta.`)) return;
    setOcupado(true);
    try {
      await api.delete(`/automacoes/${automacao.id}`);
      toast.success("Automação removida.");
      onRemoveu(automacao.id);
      router.refresh();
    } catch (e) {
      const msg = mensagemDeErro(e, "Falha ao remover a automação");
      setErro(msg);
      toast.error(msg);
    } finally {
      setOcupado(false);
    }
  }

  // ── salvar ──
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
      if (gatilho.palavraChave.trim()) cfg.palavra_chave = gatilho.palavraChave.trim();
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
    if (!automacao) return;
    if (!nome.trim()) {
      setErro("Dê um nome à automação.");
      return;
    }
    if (gatilho.tipo === "agendamento" && !gatilho.entrada.trim()) {
      setErro("No agendamento, escreva a mensagem que o gatilho entrega ao fluxo.");
      return;
    }
    // Gatilho de comentário ATIVO sem conta escolhida não dispara nunca — e falha
    // calado, que é o pior desfecho: a automação parece ligada e não é. A tela
    // clássica já barrava isto; sem a mesma trava aqui, alternar entre as duas telas
    // decidiria se o fluxo nasce quebrado.
    if (
      gatilho.tipo === "comentario_instagram" &&
      automacao.ativa &&
      !gatilho.credencialId
    ) {
      setErro("Escolha a conta do Instagram antes de ativar o gatilho de comentário.");
      return;
    }
    setSalvando(true);
    try {
      const atual = await api.put<Automacao>(`/automacoes/${automacao.id}`, {
        nome: nome.trim(),
        tipo_gatilho: gatilho.tipo,
        configuracao_gatilho: montarConfigGatilho(),
        cadeia: normalizarCadeia(cadeia),
        ativa,
        configuracao: configFluxo,
      });
      onAtualizou(atual);
      setErro(null);
      toast.success("Desenho salvo.");
      router.refresh();
    } catch (e) {
      const msg = mensagemDeErro(e, "Falha ao salvar o desenho");
      setErro(msg);
      toast.error(msg);
    } finally {
      setSalvando(false);
    }
  }

  // Desligada pelo disjuntor: falhou 3× seguidas rodando sozinha. Some assim que o
  // operador remarca "Ativa" — religar zera a contagem no servidor, e manter o aviso
  // depois disso seria mentir sobre o estado atual.
  const desligadaPorFalhas = !ativa && !!automacao?.desligada_por_falhas_em;

  const erros = problemas.filter((p) => p.nivel === "erro");
  const avisos = problemas.filter((p) => p.nivel === "aviso");
  // Há edição pendente? Compara o gatilho INTEIRO, não só o tipo. Comparar só o tipo
  // parecia bastar e não bastava: o botão Salvar é `disabled={!naoSalvo}`, então mudar
  // o horário, a frequência, a palavra-chave ou o teto deixava o botão morto em
  // "Salvo" — a pessoa ajustava, saía da tela e o trabalho sumia sem um aviso sequer.
  // Comparar demais só faz o botão acender à toa; comparar de menos perde trabalho.
  const naoSalvo =
    !!automacao &&
    JSON.stringify([nome, normalizarCadeia(cadeia), gatilho, configFluxo, ativa]) !==
      JSON.stringify([
        automacao.nome,
        normalizarCadeia(automacao.cadeia ?? { nos: [] }),
        gatilhoDe(automacao),
        automacao.configuracao ?? {},
        automacao.ativa,
      ]);

  return (
    <div className="flex w-full flex-col px-4 py-4 sm:px-6">
      {/* ── barra de cima ── */}
      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <Select
          value={automacao?.id ?? ""}
          onChange={(e) => onSelecionar(e.target.value)}
          className="h-9 w-56"
        >
          {automacoes.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nome}
              {a.ativa ? "" : " (pausada)"}
            </option>
          ))}
        </Select>
        <Input
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Nome da automação"
          disabled={!souOperador}
          className="h-9 w-56"
        />

        {/* O veredito do desenho, sempre visível — não só quando alguém abre o painel. */}
        <span
          className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium"
          style={
            erros.length
              ? { color: "#B42318", background: "#FDECEC", borderColor: "#F5C2C0" }
              : avisos.length
                ? { color: "#8A5A12", background: "#FDF1E3", borderColor: "#F0D9B4" }
                : { color: "#2F7D45", background: "#E6F4EA", borderColor: "#BEE3CB" }
          }
        >
          {erros.length ? (
            <ShieldAlert size={13} />
          ) : avisos.length ? (
            <AlertTriangle size={13} />
          ) : (
            <CheckCircle2 size={13} />
          )}
          {erros.length
            ? `${erros.length} ${erros.length === 1 ? "erro" : "erros"} no desenho`
            : avisos.length
              ? `${avisos.length} ${avisos.length === 1 ? "aviso" : "avisos"}`
              : "sem furos no desenho"}
        </span>

        {/* Estado da PRÓPRIA automação. Desligada pelo DISJUNTOR ela ganha pílula
            própria: "em repouso" faria uma que quebrou parecer igual a uma que você
            mesmo desligou. */}
        {desligadaPorFalhas ? (
          <Badge variant="warning" className="gap-1">
            <AlertCircle className="size-3" /> desligada por falhas
          </Badge>
        ) : (
          <Badge variant={ativa ? "success" : "neutral"}>
            {ativa ? "ativa" : "em repouso"}
          </Badge>
        )}
        {souOperador && (
          <label
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
            title={
              gatilho.tipo === "manual"
                ? "Ativa: fica no ar para ser disparada por agendamento. O botão “Rodar” funciona mesmo em repouso."
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
            <Activity /> Execuções
          </Button>
        )}
        {souOperador && (
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMaisAberto((v) => !v)}
              aria-label="Mais ações"
              disabled={ocupado}
            >
              <MoreHorizontal />
            </Button>
            {maisAberto && (
              <>
                <button
                  className="fixed inset-0 z-20 cursor-default"
                  aria-label="Fechar"
                  onClick={() => setMaisAberto(false)}
                />
                <div className="absolute right-0 top-10 z-30 w-52 rounded-[10px] border border-border bg-card p-1.5 shadow-lg">
                  <button
                    type="button"
                    onClick={() => {
                      setMaisAberto(false);
                      nova();
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-muted"
                  >
                    <Plus className="size-3.5" /> Nova automação
                  </button>
                  {automacao && (
                    <button
                      type="button"
                      onClick={() => {
                        setMaisAberto(false);
                        duplicar();
                      }}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-muted"
                    >
                      <Copy className="size-3.5" /> Duplicar esta
                    </button>
                  )}
                  {souAdmin && automacao && (
                    <>
                      <div className="my-1 h-px bg-border" />
                      <button
                        type="button"
                        onClick={() => {
                          setMaisAberto(false);
                          remover();
                        }}
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="size-3.5" /> Remover esta
                      </button>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        )}
        {souOperador && (
          <Button onClick={salvar} disabled={salvando || !naoSalvo}>
            {salvando ? "Salvando…" : naoSalvo ? "Salvar" : "Salvo"}
          </Button>
        )}
      </div>

      {erro && <Aviso className="mb-3">{erro}</Aviso>}

      {/* O Batuta desligou esta automação sozinho. Dizer só "em repouso" transformaria
          uma automação quebrada num mistério: quem abre a tela dias depois não teria
          como saber por que ela parou. */}
      {desligadaPorFalhas && (
        <Aviso variant="atencao" className="mb-3">
          O Batuta desligou esta automação — ela falhou 3 vezes seguidas rodando
          sozinha. Veja o que quebrou e conserte antes de ativar de novo; religar dá
          três chances novas, então reativar sem consertar só adia o mesmo
          desligamento.{" "}
          <button
            type="button"
            onClick={() => router.push(`/times/${time.id}/execucoes`)}
            className="underline underline-offset-2 hover:no-underline"
          >
            Ver execuções que falharam
          </button>
        </Aviso>
      )}

      {/* ── canvas + painel ── */}
      <div className="flex h-[calc(100vh-16rem)] min-h-[520px] overflow-hidden rounded-xl border border-border bg-card">
        <div className="relative min-w-0 flex-1">
          <CanvasEstudio
            cadeia={cadeia}
            setCadeia={setCadeiaNorm}
            agentes={agentes}
            cintos={cintos}
            automacoesOrg={automacoesOrg}
            podeEditar={souOperador}
            gatilhoTipo={gatilho.tipo}
            selId={noSel}
            setSelId={setNoSel}
            saidaSel={saidaSel}
            setSaidaSel={setSaidaSel}
            onEditarAgente={setEditAgenteId}
            onEditarInstrumento={setEditInstrumentoId}
            onProblemas={setProblemas}
          />
        </div>
        <div className="w-[352px] flex-none overflow-hidden border-l border-[#E8E6F0] bg-white">
          <PainelEstudio
            no={no}
            cadeia={cadeia}
            agentes={agentes}
            cintos={cintos}
            configFluxo={configFluxo}
            setConfigFluxo={setConfigFluxo}
            nomeDoFluxo={nome || "(sem nome)"}
            automacaoId={automacao?.id ?? null}
            timeId={time.id}
            naoSalvo={naoSalvo}
            onSubirAoFluxo={() => {
              setNoSel(null);
              setSaidaSel(null);
            }}
            onEditarInstrumento={setEditInstrumentoId}
            podeEditar={souOperador}
            problemas={problemas}
            saidaSelecionada={saidaSel}
            gatilho={gatilho}
            setGatilho={setGatilho}
            webhookUrl={
              automacao ? `${URL_CEREBRO}/webhooks/automacoes/${automacao.id}` : null
            }
            credenciaisInstagram={credenciaisInstagram}
            automacoesOrg={automacoesOrg}
            onPatchNode={patchNode}
            onPatchSaida={patchSaida}
            onAddSaida={addSaida}
            onRemoveSaida={removeSaida}
            onDeleteNode={deleteNode}
            onDefinirInicial={definirInicial}
            onEditarAgente={setEditAgenteId}
          />
        </div>
      </div>

      {automacao && (
        <AgendamentosAutomacao automacaoId={automacao.id} podeOperar={souOperador} />
      )}

      {agenteEdit && (
        <DrawerAgente
          key={agenteEdit.id}
          agente={agenteEdit}
          indice={agentes.findIndex((a) => a.id === agenteEdit.id)}
          cinto={cintos[agenteEdit.id] ?? []}
          abrirEditando
          instrumentosTime={instrumentos}
          time={time}
          meuPapel={meuPapel}
          tipos={tipos}
          conversaId={null}
          onFechar={() => setEditAgenteId(null)}
        />
      )}

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
