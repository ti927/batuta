"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, X, Zap } from "lucide-react";

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
import { BotaoRodarAgora } from "@/components/botao-rodar-agora";
import { UrlCopiavel } from "@/components/url-copiavel";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h2 className="text-sm font-medium text-foreground">Automações do time</h2>
        <p className="text-sm text-muted-foreground">
          Como a tarefa entra, por quais agentes passa e quando para pra você decidir.
        </p>
      </div>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {agentes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Crie agentes no time antes de montar uma automação.
        </p>
      ) : (
        modo === null &&
        souOperador && (
          <Button className="mb-6" onClick={abrirNovo}>
            <Plus />
            Nova automação
          </Button>
        )
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-4 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium text-foreground">
            {modo === "novo" ? "Nova automação" : "Editar automação"}
          </h2>
          <Label className="flex-col items-start gap-1">
            Nome
            <Input
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              autoFocus
            />
          </Label>
          <Label className="flex-col items-start gap-1">
            Agente inicial (por onde a tarefa entra)
            <Select value={inicio} onChange={(e) => setInicio(e.target.value)}>
              {agentes.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nome}
                </option>
              ))}
            </Select>
          </Label>

          <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-4">
            <span className="text-sm font-medium text-foreground">
              Gatilho — o que inicia este fluxo
            </span>
            <div className="flex flex-wrap gap-3 text-sm">
              {(["manual", "agendamento", "webhook"] as TipoGatilho[]).map((t) => (
                <label key={t} className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name="gatilho"
                    className="accent-primary"
                    checked={tipoGatilho === t}
                    onChange={() => setTipoGatilho(t)}
                  />
                  {ROTULO_GATILHO[t]}
                </label>
              ))}
            </div>

            {tipoGatilho === "manual" && (
              <p className="text-xs text-muted-foreground">
                Dispara apenas pelo botão de teste, na tela da automação.
              </p>
            )}

            {tipoGatilho === "agendamento" && (
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-end gap-2">
                  <Label className="flex-col items-start gap-1">
                    Frequência
                    <Select
                      className="w-auto"
                      value={frequencia}
                      onChange={(e) => setFrequencia(e.target.value as Frequencia)}
                    >
                      <option value="diaria">Todo dia</option>
                      <option value="semanal">Toda semana</option>
                      <option value="mensal">Todo mês</option>
                    </Select>
                  </Label>
                  {frequencia === "semanal" && (
                    <Label className="flex-col items-start gap-1">
                      Dia da semana
                      <Select
                        className="w-auto"
                        value={diaSemana}
                        onChange={(e) => setDiaSemana(Number(e.target.value))}
                      >
                        {DIAS_SEMANA.map((d, i) => (
                          <option key={i} value={i}>
                            {d}
                          </option>
                        ))}
                      </Select>
                    </Label>
                  )}
                  {frequencia === "mensal" && (
                    <Label className="flex-col items-start gap-1">
                      Dia do mês
                      <Input
                        type="number"
                        min={1}
                        max={31}
                        className="w-20"
                        value={diaMes}
                        onChange={(e) => setDiaMes(Number(e.target.value))}
                      />
                    </Label>
                  )}
                  <Label className="flex-col items-start gap-1">
                    Horário
                    <Input
                      type="time"
                      className="w-auto"
                      value={horario}
                      onChange={(e) => setHorario(e.target.value)}
                    />
                  </Label>
                </div>
                <Label className="flex-col items-start gap-1">
                  Mensagem que o gatilho envia ao fluxo (a entrada do agente inicial)
                  <Textarea
                    className="min-h-16"
                    placeholder="Ex.: Gere o lembrete mensal de fechamento."
                    value={entradaAgendada}
                    onChange={(e) => setEntradaAgendada(e.target.value)}
                  />
                </Label>
                <p className="text-xs text-muted-foreground">
                  Horário no fuso de Brasília.
                </p>
              </div>
            )}

            {tipoGatilho === "webhook" && (
              <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                <p>
                  Um sistema externo dispara este fluxo por uma URL (POST). O corpo
                  enviado vira a entrada — o campo <code>entrada</code> do JSON, se
                  houver; senão, o corpo inteiro.
                </p>
                {modo !== "novo" ? (
                  <UrlCopiavel
                    url={`${URL_CEREBRO}/webhooks/automacoes/${modo}`}
                  />
                ) : (
                  <p className="text-warning">
                    Salve a automação para gerar a URL do webhook.
                  </p>
                )}
              </div>
            )}

            {tipoGatilho !== "manual" && (
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={ativa}
                  onChange={(e) => setAtiva(e.target.checked)}
                />
                Gatilho ativo (dispara automaticamente). Desmarque para pausar sem
                apagar a automação.
              </label>
            )}
          </div>

          <p className="text-xs text-muted-foreground">
            Para cada agente, defina suas saídas: o rótulo, quando segui-la, e o
            destino (outro agente — pode ser anterior — ou o fim). Sem saídas = o
            agente encerra a cadeia.
          </p>

          <div className="flex flex-col gap-3">
            {agentes.map((a) => (
              <div
                key={a.id}
                className="rounded-md border border-border bg-background p-3"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                    {a.nome}
                    {a.id === inicio && <Badge variant="info">inicial</Badge>}
                  </span>
                  <Button size="xs" variant="outline" onClick={() => addSaida(a.id)}>
                    <Plus />
                    saída
                  </Button>
                </div>
                <label className="mb-2 flex items-start gap-1.5 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-primary"
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
                  <p className="mb-2 text-xs text-warning">
                    ⚠ Este agente espera resposta mas não tem saída: ao responder,
                    o fluxo encerra. Para ele reagir à sua resposta, adicione uma
                    saída (pode apontar para este mesmo agente, criando uma
                    conversa de ida e volta).
                  </p>
                )}
                {(saidas[a.id] ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Sem saídas (encerra aqui).
                  </p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {(saidas[a.id] ?? []).map((s, i) => (
                      <div key={i} className="flex flex-wrap items-center gap-2">
                        <Input
                          className="h-8 w-20 text-xs"
                          placeholder="rótulo"
                          value={s.rotulo}
                          onChange={(e) => mudarSaida(a.id, i, "rotulo", e.target.value)}
                        />
                        <Input
                          className="h-8 flex-1 text-xs"
                          placeholder="quando seguir por aqui"
                          value={s.quando}
                          onChange={(e) => mudarSaida(a.id, i, "quando", e.target.value)}
                        />
                        <Select
                          className="h-8 w-auto text-xs"
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
                        </Select>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="Remover saída"
                          onClick={() => removerSaida(a.id, i)}
                        >
                          <X />
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
        <EstadoVazio icone={Zap} titulo="Nenhuma automação ainda.">
          {souOperador && agentes.length > 0
            ? "Monte a primeira automação encadeando os agentes do time."
            : "As automações deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((a) => (
            <li key={a.id} className="flex items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                {souOperador ? (
                  <button
                    onClick={() => abrirEdicao(a)}
                    className="text-left text-sm font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {a.nome}
                  </button>
                ) : (
                  <span className="text-sm font-medium text-foreground">
                    {a.nome}
                  </span>
                )}
                <span className="block text-xs text-muted-foreground">
                  {ROTULO_GATILHO[a.tipo_gatilho] ?? a.tipo_gatilho}
                  {a.tipo_gatilho !== "manual" && !a.ativa && " (pausado)"}
                  {" · início: "}
                  {nomeAgente(a.cadeia?.inicio ?? null)}
                </span>
              </div>
              {souOperador && (
                <BotaoRodarAgora
                  timeId={time.id}
                  automacoes={[{ id: a.id, nome: a.nome }]}
                  rotulo="Rodar"
                  variant="outline"
                  size="sm"
                />
              )}
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
