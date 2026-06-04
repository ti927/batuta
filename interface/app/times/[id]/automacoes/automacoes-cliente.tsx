"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  URL_CEREBRO,
  type Agente,
  type Automacao,
  type Cadeia,
  type PapelAcesso,
  type SaidaCadeia,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { Button } from "@/components/ui/button";

type SaidasPorAgente = Record<string, SaidaCadeia[]>;
type PausaPorAgente = Record<string, boolean>;

type TipoGatilho = "manual" | "agendamento" | "webhook";
type Frequencia = "diaria" | "semanal" | "mensal";

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

const ROTULO_GATILHO: Record<string, string> = {
  manual: "Manual (botão)",
  agendamento: "Agendamento",
  webhook: "Webhook",
};

function horaParaTexto(h: number, m: number): string {
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function cadeiaParaForm(
  cadeia: Cadeia | null,
  agentes: Agente[],
): { inicio: string; saidas: SaidasPorAgente; pausa: PausaPorAgente } {
  const saidas: SaidasPorAgente = {};
  const pausa: PausaPorAgente = {};
  for (const a of agentes) {
    saidas[a.id] = cadeia?.nos?.[a.id]?.saidas ?? [];
    pausa[a.id] = cadeia?.nos?.[a.id]?.pausa_humano ?? false;
  }
  return { inicio: cadeia?.inicio ?? agentes[0]?.id ?? "", saidas, pausa };
}

function formParaCadeia(
  inicio: string,
  saidas: SaidasPorAgente,
  pausa: PausaPorAgente,
): Cadeia {
  const nos: Cadeia["nos"] = {};
  for (const [id, lista] of Object.entries(saidas))
    nos![id] = { saidas: lista, pausa_humano: pausa[id] ?? false };
  return { inicio, nos };
}

export function AutomacoesCliente({
  time,
  inicial,
  agentes,
  meuPapel,
}: {
  time: Time;
  inicial: Automacao[];
  agentes: Agente[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);

  const [modo, setModo] = useState<null | "novo" | string>(null);
  const [nome, setNome] = useState("");
  const [inicio, setInicio] = useState(agentes[0]?.id ?? "");
  const [saidas, setSaidas] = useState<SaidasPorAgente>({});
  const [pausa, setPausa] = useState<PausaPorAgente>({});

  // Gatilho: o que inicia o fluxo (PRODUTO §12).
  const [tipoGatilho, setTipoGatilho] = useState<TipoGatilho>("manual");
  const [frequencia, setFrequencia] = useState<Frequencia>("diaria");
  const [diaSemana, setDiaSemana] = useState(0);
  const [diaMes, setDiaMes] = useState(1);
  const [horario, setHorario] = useState("08:00");
  const [entradaAgendada, setEntradaAgendada] = useState("");
  const [ativa, setAtiva] = useState(true);

  const nomeAgente = (id: string | null) =>
    id === null ? "— fim (entrega ao usuário) —" : agentes.find((a) => a.id === id)?.nome ?? id;

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function carregarGatilho(a: Automacao | null) {
    const tipo = (a?.tipo_gatilho ?? "manual") as TipoGatilho;
    const cfg = (a?.configuracao_gatilho ?? {}) as Record<string, unknown>;
    setTipoGatilho(["agendamento", "webhook"].includes(tipo) ? tipo : "manual");
    setFrequencia((cfg.frequencia as Frequencia) ?? "diaria");
    setDiaSemana(Number(cfg.dia_semana ?? 0));
    setDiaMes(Number(cfg.dia_mes ?? 1));
    setHorario(horaParaTexto(Number(cfg.hora ?? 8), Number(cfg.minuto ?? 0)));
    setEntradaAgendada((cfg.entrada as string) ?? "");
    setAtiva(a ? a.ativa : true);
  }

  function abrirNovo() {
    const f = cadeiaParaForm(null, agentes);
    setNome("");
    setInicio(f.inicio);
    setSaidas(f.saidas);
    setPausa(f.pausa);
    carregarGatilho(null);
    setErro(null);
    setModo("novo");
  }

  function abrirEdicao(a: Automacao) {
    const f = cadeiaParaForm(a.cadeia, agentes);
    setNome(a.nome);
    setInicio(f.inicio);
    setSaidas(f.saidas);
    setPausa(f.pausa);
    carregarGatilho(a);
    setErro(null);
    setModo(a.id);
  }

  function addSaida(agenteId: string) {
    setSaidas((s) => ({
      ...s,
      [agenteId]: [...(s[agenteId] ?? []), { rotulo: "", quando: "", destino: null }],
    }));
  }

  function mudarSaida(agenteId: string, i: number, campo: keyof SaidaCadeia, valor: string | null) {
    setSaidas((s) => {
      const lista = [...(s[agenteId] ?? [])];
      lista[i] = { ...lista[i], [campo]: valor };
      return { ...s, [agenteId]: lista };
    });
  }

  function removerSaida(agenteId: string, i: number) {
    setSaidas((s) => {
      const lista = [...(s[agenteId] ?? [])];
      lista.splice(i, 1);
      return { ...s, [agenteId]: lista };
    });
  }

  function montarConfigGatilho(): Record<string, unknown> {
    if (tipoGatilho !== "agendamento") return {};
    const [h, m] = horario.split(":").map(Number);
    const cfg: Record<string, unknown> = {
      frequencia,
      hora: h,
      minuto: m,
      entrada: entradaAgendada,
    };
    if (frequencia === "semanal") cfg.dia_semana = diaSemana;
    if (frequencia === "mensal") cfg.dia_mes = diaMes;
    return cfg;
  }

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    if (!inicio) {
      setErro("Escolha o agente inicial.");
      return;
    }
    if (tipoGatilho === "agendamento" && !entradaAgendada.trim()) {
      setErro("No agendamento, escreva a mensagem que o gatilho envia ao fluxo.");
      return;
    }
    const corpo = {
      nome: nome.trim(),
      tipo_gatilho: tipoGatilho,
      configuracao_gatilho: montarConfigGatilho(),
      cadeia: formParaCadeia(inicio, saidas, pausa),
      // O interruptor liga/desliga só vale para gatilhos automáticos.
      ativa: tipoGatilho === "manual" ? false : ativa,
    };
    try {
      if (modo === "novo") {
        await api.post<Automacao>(`/times/${time.id}/automacoes`, corpo);
      } else if (modo) {
        await api.put<Automacao>(`/automacoes/${modo}`, corpo);
      }
      setErro(null);
      setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar automação");
    }
  }

  async function remover(a: Automacao) {
    if (!confirm(`Remover a automação "${a.nome}"?`)) return;
    try {
      await api.delete(`/automacoes/${a.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover automação");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <Link
        href={`/times/${time.id}`}
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Voltar ao time
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">{time.nome}</h1>
      <p className="mb-6 text-sm text-zinc-500">Automações do time</p>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {agentes.length === 0 ? (
        <p className="text-sm text-zinc-500">
          Crie agentes no time antes de montar uma automação.
        </p>
      ) : (
        modo === null &&
        souOperador && (
          <Button className="mb-6" onClick={abrirNovo}>
            + Nova automação
          </Button>
        )
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-4 rounded border border-zinc-300 bg-zinc-50 p-4">
          <h2 className="font-semibold">
            {modo === "novo" ? "Nova automação" : "Editar automação"}
          </h2>
          <label className="flex flex-col gap-1 text-xs text-zinc-600">
            Nome
            <input
              className="rounded border border-zinc-300 px-2 py-1 text-sm"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              autoFocus
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-600">
            Agente inicial (por onde a tarefa entra)
            <select
              className="rounded border border-zinc-300 px-2 py-1 text-sm"
              value={inicio}
              onChange={(e) => setInicio(e.target.value)}
            >
              {agentes.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nome}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col gap-2 rounded border border-zinc-200 bg-white p-3">
            <span className="text-xs font-semibold text-zinc-700">
              Gatilho — o que inicia este fluxo
            </span>
            <div className="flex flex-wrap gap-3 text-sm">
              {(["manual", "agendamento", "webhook"] as TipoGatilho[]).map((t) => (
                <label key={t} className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name="gatilho"
                    checked={tipoGatilho === t}
                    onChange={() => setTipoGatilho(t)}
                  />
                  {ROTULO_GATILHO[t]}
                </label>
              ))}
            </div>

            {tipoGatilho === "manual" && (
              <p className="text-xs text-zinc-500">
                Dispara apenas pelo botão de teste, na tela da automação.
              </p>
            )}

            {tipoGatilho === "agendamento" && (
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-end gap-2">
                  <label className="flex flex-col gap-1 text-xs text-zinc-600">
                    Frequência
                    <select
                      className="rounded border border-zinc-300 px-2 py-1 text-sm"
                      value={frequencia}
                      onChange={(e) => setFrequencia(e.target.value as Frequencia)}
                    >
                      <option value="diaria">Todo dia</option>
                      <option value="semanal">Toda semana</option>
                      <option value="mensal">Todo mês</option>
                    </select>
                  </label>
                  {frequencia === "semanal" && (
                    <label className="flex flex-col gap-1 text-xs text-zinc-600">
                      Dia da semana
                      <select
                        className="rounded border border-zinc-300 px-2 py-1 text-sm"
                        value={diaSemana}
                        onChange={(e) => setDiaSemana(Number(e.target.value))}
                      >
                        {DIAS_SEMANA.map((d, i) => (
                          <option key={i} value={i}>
                            {d}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {frequencia === "mensal" && (
                    <label className="flex flex-col gap-1 text-xs text-zinc-600">
                      Dia do mês
                      <input
                        type="number"
                        min={1}
                        max={31}
                        className="w-20 rounded border border-zinc-300 px-2 py-1 text-sm"
                        value={diaMes}
                        onChange={(e) => setDiaMes(Number(e.target.value))}
                      />
                    </label>
                  )}
                  <label className="flex flex-col gap-1 text-xs text-zinc-600">
                    Horário
                    <input
                      type="time"
                      className="rounded border border-zinc-300 px-2 py-1 text-sm"
                      value={horario}
                      onChange={(e) => setHorario(e.target.value)}
                    />
                  </label>
                </div>
                <label className="flex flex-col gap-1 text-xs text-zinc-600">
                  Mensagem que o gatilho envia ao fluxo (a entrada do agente inicial)
                  <textarea
                    className="min-h-16 rounded border border-zinc-300 px-2 py-1 text-sm"
                    placeholder="Ex.: Gere o lembrete mensal de fechamento."
                    value={entradaAgendada}
                    onChange={(e) => setEntradaAgendada(e.target.value)}
                  />
                </label>
                <p className="text-xs text-zinc-400">Horário no fuso de Brasília.</p>
              </div>
            )}

            {tipoGatilho === "webhook" && (
              <div className="flex flex-col gap-1 text-xs text-zinc-600">
                <p>
                  Um sistema externo dispara este fluxo por uma URL (POST). O corpo
                  enviado vira a entrada — o campo <code>entrada</code> do JSON, se
                  houver; senão, o corpo inteiro.
                </p>
                {modo !== "novo" ? (
                  <code className="break-all rounded bg-zinc-100 px-2 py-1 text-zinc-800">
                    {URL_CEREBRO}/webhooks/automacoes/{modo}
                  </code>
                ) : (
                  <p className="text-amber-700">
                    Salve a automação para gerar a URL do webhook.
                  </p>
                )}
              </div>
            )}

            {tipoGatilho !== "manual" && (
              <label className="flex items-center gap-1.5 text-xs text-zinc-600">
                <input
                  type="checkbox"
                  checked={ativa}
                  onChange={(e) => setAtiva(e.target.checked)}
                />
                Gatilho ativo (dispara automaticamente). Desmarque para pausar sem
                apagar a automação.
              </label>
            )}
          </div>

          <p className="text-xs text-zinc-500">
            Para cada agente, defina suas saídas: o rótulo, quando segui-la, e o
            destino (outro agente — pode ser anterior — ou o fim). Sem saídas = o
            agente encerra a cadeia.
          </p>

          <div className="flex flex-col gap-3">
            {agentes.map((a) => (
              <div key={a.id} className="rounded border border-zinc-200 bg-white p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {a.nome}
                    {a.id === inicio && (
                      <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                        inicial
                      </span>
                    )}
                  </span>
                  <Button size="xs" variant="outline" onClick={() => addSaida(a.id)}>
                    + saída
                  </Button>
                </div>
                <label className="mb-2 flex items-center gap-1.5 text-xs text-zinc-600">
                  <input
                    type="checkbox"
                    checked={pausa[a.id] ?? false}
                    onChange={(e) =>
                      setPausa((p) => ({ ...p, [a.id]: e.target.checked }))
                    }
                  />
                  Ao terminar, pausar e esperar sua decisão (portão de
                  aprovação): sua resposta escolhe por qual saída seguir (ex.:
                  &quot;aprovado&quot; / &quot;reprovado, mude X&quot;) e vai junto
                  com o trabalho do agente ao próximo
                </label>
                {pausa[a.id] && (saidas[a.id] ?? []).length === 0 && (
                  <p className="mb-2 text-xs text-amber-700">
                    ⚠ Este agente espera resposta mas não tem saída: ao responder,
                    o fluxo encerra. Para ele reagir à sua resposta, adicione uma
                    saída (pode apontar para este mesmo agente, criando uma
                    conversa de ida e volta).
                  </p>
                )}
                {(saidas[a.id] ?? []).length === 0 ? (
                  <p className="text-xs text-zinc-400">Sem saídas (encerra aqui).</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {(saidas[a.id] ?? []).map((s, i) => (
                      <div key={i} className="flex flex-wrap items-center gap-2">
                        <input
                          className="w-20 rounded border border-zinc-300 px-2 py-1 text-xs"
                          placeholder="rótulo"
                          value={s.rotulo}
                          onChange={(e) => mudarSaida(a.id, i, "rotulo", e.target.value)}
                        />
                        <input
                          className="flex-1 rounded border border-zinc-300 px-2 py-1 text-xs"
                          placeholder="quando seguir por aqui"
                          value={s.quando}
                          onChange={(e) => mudarSaida(a.id, i, "quando", e.target.value)}
                        />
                        <select
                          className="rounded border border-zinc-300 px-2 py-1 text-xs"
                          value={s.destino ?? ""}
                          onChange={(e) =>
                            mudarSaida(a.id, i, "destino", e.target.value || null)
                          }
                        >
                          <option value="">→ fim</option>
                          {agentes.map((d) => (
                            <option key={d.id} value={d.id}>
                              → {d.nome}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => removerSaida(a.id, i)}
                        >
                          ✕
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button onClick={salvar}>Salvar</Button>
            <Button variant="ghost" onClick={() => setModo(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {inicial.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhuma automação ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {inicial.map((a) => (
            <li key={a.id} className="flex items-center gap-2 p-3">
              <Link
                href={`/automacoes/${a.id}`}
                className="flex-1 text-sm text-blue-600 underline underline-offset-4"
              >
                {a.nome}
                <span className="ml-2 text-xs text-zinc-400">
                  {ROTULO_GATILHO[a.tipo_gatilho] ?? a.tipo_gatilho}
                  {a.tipo_gatilho !== "manual" && !a.ativa && " (pausado)"}
                  {" · início: "}
                  {nomeAgente(a.cadeia?.inicio ?? null)}
                </span>
              </Link>
              {souOperador && (
                <Button size="sm" variant="outline" onClick={() => abrirEdicao(a)}>
                  Editar
                </Button>
              )}
              {souAdmin && (
                <Button size="sm" variant="destructive" onClick={() => remover(a)}>
                  Remover
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
