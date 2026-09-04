// Inspector do construtor: edita o nó selecionado (gatilho/agente/roteador/fim).
// É onde nascem as bifurcações do fluxo.
//
// Cada saída tem três coisas que o motor lê: o NOME (o que aparece na seta), a
// CONDIÇÃO ("siga por aqui quando…") e o PAPEL (condição | se der erro | se nenhuma).
// A condição existia no motor desde sempre e NÃO tinha caixa em tela nenhuma até
// 2026-08-31 — por isso toda automação vinha com a condição vazia e o agente escolhia
// o caminho no escuro. É a causa-raiz da Onda 1.

import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowRightLeft,
  CheckCircle2,
  CircleHelp,
  Clock,
  Hourglass,
  Layers,
  MessageCircle,
  Play,
  Plus,
  Repeat2,
  Shield,
  X,
  Zap,
} from "lucide-react";

import type {
  Agente,
  AutomacaoDaOrg,
  Cadeia,
  CampoConfigFluxo,
  ConfiguracaoFluxo,
  Credencial,
  Instrumento,
  NoCadeia,
  OperadorRegra,
  PainelConfigFluxo,
  RegraSaida,
  SaidaCadeia,
  TipoSaida,
  ToneSaida,
} from "@/lib/api";
import { OPERADORES_REGRA, OPERADORES_SEM_VALOR, api } from "@/lib/api";
import { RobotFace } from "@/components/robot-face";
import { Select } from "@/components/ui/select";
import { UrlCopiavel } from "@/components/url-copiavel";

import { CampoConfig, efetivoDoFluxo } from "./config-fluxo";
import { TONE_KEYS, tone } from "./nucleo";
import { TestarEstePasso } from "./testar-no";

// As chaves de config que fazem sentido AJUSTAR por-passo (e que o backend honra
// por-nó via `com_ajuste_do_no`). Fora daqui: atendimento (saudação/horário) e chaves
// internas — essas ficam só no Tipo de fluxo.
const CHAVES_PORTAO = [
  "portao_forma",
  "portao_acao_abandono",
  "portao_max_rodadas",
  "timeout_min",
  "nudge_timeout_min",
  "encerrar_por_inatividade",
  "max_turnos",
  "teto_usd",
];

function semChave(
  obj: Record<string, unknown>,
  chave: string,
): Record<string, unknown> {
  const resto = { ...obj };
  delete resto[chave];
  return resto;
}

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
  tipo: "manual" | "agendamento" | "webhook" | "comentario_instagram";
  frequencia: "diaria" | "semanal" | "mensal";
  diaSemana: number;
  diaMes: number;
  horario: string;
  entrada: string;
  // gatilho de comentário do Instagram
  credencialId: string; // "" = conta a conectar (o humano escolhe)
  midiasModo: "todas" | "especificas";
  midiasIds: string; // texto: media_ids separados por vírgula
  palavraChave: string;
  tetoPorHora: number;
};

function nomeNo(no: NoCadeia, agentes: Agente[]): string {
  if (no.tipo === "agente")
    return agentes.find((a) => a.id === no.ref)?.nome ?? "Agente";
  if (no.tipo === "roteador") return no.nome || "Roteador";
  if (no.tipo === "fim") return "Fim · entrega ao usuário";
  if (no.tipo === "cada") return no.nome || "Para cada item";
  if (no.tipo === "esperar") return no.nome || "Esperar";
  if (no.tipo === "chamar") return no.nome || "Chamar outra automação";
  return "Gatilho";
}

const inputCls =
  "w-full rounded-md border border-[#E8E6F0] bg-white px-2.5 py-1.5 text-[13px] text-[#1A1730] outline-none focus:border-primary";

// Teto de itens de UMA lista no nó "Para cada item" — espelho de
// `orquestracao/cadeia.py::MAX_ITENS_CADA`. Só informativo aqui (quem corta é o
// motor), mas o usuário precisa saber antes de montar o fluxo.
const MAX_ITENS_CADA = 20;

// Os três papéis de uma saída, na ordem em que aparecem no seletor.
const PAPEIS: { chave: TipoSaida; rotulo: string; ajuda: string }[] = [
  {
    chave: "condicional",
    rotulo: "Condição",
    ajuda: "O agente avalia a condição e segue por aqui se ela for atendida.",
  },
  {
    chave: "erro",
    rotulo: "Se der erro",
    ajuda:
      "Percorrida só quando este passo FALHA. O erro segue por aqui em vez de derrubar a automação.",
  },
  {
    chave: "senao",
    rotulo: "Se nenhuma",
    ajuda: "Rede de segurança: só roda quando nenhuma condição acima for atendida.",
  },
];

export function papelDaSaida(sa: SaidaCadeia): TipoSaida {
  const t = sa.tipo;
  return t === "erro" || t === "senao" ? t : "condicional";
}

/**
 * REGRA EXATA de uma saída (Onda 2) — opcional, e quando existe quem decide é o
 * MOTOR, não a IA.
 *
 * Serve para a comparação que um modelo erra: `total entre 1 e 10` é inclusivo, e 11
 * cai do outro lado — sempre, sem depender de o agente interpretar a frase. O campo é
 * lido da ficha da execução (o que o gatilho trouxe + o que os agentes guardaram com
 * `anotar`), então o nome escrito aqui precisa ser o MESMO que alguém guarda lá.
 */
function RegraExata({
  regra,
  podeEditar,
  onChange,
}: {
  regra: RegraSaida | null | undefined;
  podeEditar: boolean;
  onChange: (r: RegraSaida | null) => void;
}) {
  const [aberta, setAberta] = useState(!!regra?.campo);
  const r = regra ?? null;
  const precisaValor = r && !OPERADORES_SEM_VALOR.includes(r.operador);
  const patch = (p: Partial<RegraSaida>) =>
    onChange({ campo: "", operador: "igual", ...(r ?? {}), ...p });

  if (!aberta) {
    return (
      <button
        type="button"
        disabled={!podeEditar}
        onClick={() => {
          setAberta(true);
          patch({});
        }}
        className="self-start text-[11px] text-[#6D4AFF] hover:underline disabled:opacity-50"
      >
        + Regra exata (opcional)
      </button>
    );
  }
  return (
    <div className="rounded-md border border-[#E8E6F0] bg-white p-2">
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className="text-[11px] font-medium" style={{ color: "#3D2A99" }}>
          Regra exata
        </span>
        <div className="flex-1" />
        {podeEditar && (
          <button
            type="button"
            onClick={() => {
              setAberta(false);
              onChange(null);
            }}
            aria-label="Remover a regra exata"
            className="p-0.5 text-[#A09DB8] hover:text-foreground"
          >
            <X size={13} />
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <input
          className={`${inputCls} min-w-24 flex-1`}
          value={r?.campo ?? ""}
          placeholder="campo (ex.: total)"
          disabled={!podeEditar}
          onChange={(e) => patch({ campo: e.target.value })}
        />
        <select
          className={`${inputCls} w-auto flex-1 cursor-pointer`}
          value={r?.operador ?? "igual"}
          disabled={!podeEditar}
          onChange={(e) => patch({ operador: e.target.value as OperadorRegra })}
        >
          {OPERADORES_REGRA.map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.rotulo}
            </option>
          ))}
        </select>
        {precisaValor && (
          <input
            className={`${inputCls} min-w-16 flex-1`}
            value={r?.valor ?? ""}
            placeholder="valor"
            disabled={!podeEditar}
            onChange={(e) => patch({ valor: e.target.value })}
          />
        )}
        {r?.operador === "entre" && (
          <input
            className={`${inputCls} min-w-16 flex-1`}
            value={r?.valor2 ?? ""}
            placeholder="e"
            disabled={!podeEditar}
            onChange={(e) => patch({ valor2: e.target.value })}
          />
        )}
      </div>
      <p className="mt-1.5 text-[11px] leading-normal" style={{ color: "#6B6880" }}>
        Com regra, quem confere é o sistema — não a IA. O campo vem da ficha da
        execução: use o mesmo nome que um passo anterior guarda com{" "}
        <span className="font-mono">anotar</span> (ou{" "}
        <span className="font-mono">entrada</span>, que é o que o gatilho trouxe).
      </p>
    </div>
  );
}

function LinhaSaida({
  no,
  sa,
  idx,
  cadeia,
  agentes,
  podeEditar,
  exigeCondicao,
  onChange,
  onRemove,
}: {
  no: NoCadeia;
  sa: SaidaCadeia;
  idx: number;
  cadeia: Cadeia;
  agentes: Agente[];
  podeEditar: boolean;
  /** O nó bifurca (2+ condicionais): sem condição escrita, o agente escolhe no escuro. */
  exigeCondicao: boolean;
  onChange: (patch: Partial<SaidaCadeia>) => void;
  onRemove: () => void;
}) {
  const papel = papelDaSaida(sa);
  // A seta de erro é vermelha por definição — o papel manda na cor, não o contrário.
  const tn = tone(papel === "erro" ? "erro" : sa.tone);
  const destinos = (cadeia.nos ?? []).filter((n) => n.tipo !== "gatilho");
  const faltaCondicao =
    papel === "condicional" && exigeCondicao && !(sa.quando ?? "").trim();
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

      {/* PAPEL da saída — é o que o motor lê para saber quando percorrê-la. */}
      <div className="flex gap-1.5">
        {PAPEIS.map((p) => {
          const on = papel === p.chave;
          const cor = p.chave === "erro" ? tone("erro") : tone("normal");
          return (
            <button
              key={p.chave}
              type="button"
              disabled={!podeEditar}
              title={p.ajuda}
              onClick={() =>
                onChange(
                  p.chave === "condicional"
                    ? { tipo: "condicional" }
                    : // Erro e "senão" são do MOTOR: nem condição nem regra fazem
                      // sentido neles (uma é acionada pela falha, a outra pela
                      // ausência de condição atendida).
                      { tipo: p.chave, quando: "", regra: null },
                )
              }
              className="flex-1 rounded-md border px-1 py-1.5 text-[11px]"
              style={{
                borderColor: on ? cor.dot : "#E8E6F0",
                background: on ? cor.pillBg : "#fff",
                color: on ? cor.pillFg : "#A09DB8",
                fontWeight: on ? 500 : 400,
              }}
            >
              {p.rotulo}
            </button>
          );
        })}
      </div>

      <div>
        <label className="mb-1 block text-[11px]" style={{ color: "#6B6880" }}>
          Nome (aparece na seta)
        </label>
        <input
          className={inputCls}
          value={sa.rotulo}
          placeholder={papel === "erro" ? "ex.: deu erro" : "ex.: aprovado"}
          disabled={!podeEditar}
          onChange={(e) => onChange({ rotulo: e.target.value })}
        />
      </div>

      {/* A CONDIÇÃO. Até 2026-08-31 este campo existia no motor e NÃO tinha caixa em
          tela nenhuma: toda automação tinha condição vazia e o agente decidia às
          cegas. É esta frase que ele lê. */}
      {papel === "condicional" && (
        <div>
          <label className="mb-1 block text-[11px]" style={{ color: "#6B6880" }}>
            {no.tipo === "roteador"
              ? "Siga por aqui quando a tarefa que chega…"
              : "Siga por aqui quando…"}
          </label>
          <input
            className={inputCls}
            style={faltaCondicao ? { borderColor: "#E5484D" } : undefined}
            value={sa.quando ?? ""}
            placeholder="ex.: o texto estiver aprovado"
            disabled={!podeEditar}
            onChange={(e) => onChange({ quando: e.target.value })}
          />
          {faltaCondicao && (
            <p className="mt-1 text-[11px]" style={{ color: "#B42318" }}>
              Este passo bifurca — sem esta frase o agente não tem como saber quando
              seguir por aqui. Preencha para poder salvar.
            </p>
          )}
          <div className="mt-2 flex flex-col">
            <RegraExata
              regra={sa.regra}
              podeEditar={podeEditar}
              onChange={(regra) => onChange({ regra })}
            />
          </div>
        </div>
      )}
      {papel !== "condicional" && (
        <p className="text-[11px] leading-normal" style={{ color: "#6B6880" }}>
          {PAPEIS.find((p) => p.chave === papel)?.ajuda}
        </p>
      )}

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

      {/* Cor da seta (cosmético). A saída de erro tem cor própria — nada a escolher. */}
      {papel !== "erro" && (
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
                <span
                  className="size-[7px] rounded-full"
                  style={{ background: t.dot }}
                />
                {t.rotulo.split(" ")[0]}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function Inspector({
  no,
  cadeia,
  agentes,
  podeEditar,
  gatilho,
  setGatilho,
  webhookUrl,
  credenciaisInstagram,
  configFluxo,
  onDefinirInicial,
  onPatchNode,
  onPatchSaida,
  onAddSaida,
  onRemoveSaida,
  onDeleteNode,
  automacaoId,
  timeId,
  cintos,
  naoSalvo,
  automacoesOrg,
}: {
  no: NoCadeia | null;
  cadeia: Cadeia;
  agentes: Agente[];
  podeEditar: boolean;
  // "Testar este passo": a automação onde o passo vive (nula = ainda não salva), o
  // time (para o link da inspeção), o cinto de cada agente (para nomear os
  // instrumentos irreversíveis) e se há edição pendente na tela.
  automacaoId: string | null;
  timeId: string;
  cintos: Record<string, Instrumento[]>;
  naoSalvo: boolean;
  // Automações da organização — o seletor do nó "Chamar outra automação". Vem do
  // construtor (que já as busca para os cartões) em vez de ser buscada de novo aqui:
  // duas buscas do mesmo dado é como duas telas passam a discordar.
  automacoesOrg: AutomacaoDaOrg[];
  gatilho: ConfigGatilho;
  setGatilho: (patch: Partial<ConfigGatilho>) => void;
  webhookUrl?: string | null;
  credenciaisInstagram: Credencial[];
  configFluxo: ConfiguracaoFluxo;
  onDefinirInicial: (nodeId: string) => void;
  onPatchNode: (id: string, patch: Partial<NoCadeia>) => void;
  onPatchSaida: (id: string, sid: string, patch: Partial<SaidaCadeia>) => void;
  onAddSaida: (id: string) => void;
  onRemoveSaida: (id: string, sid: string) => void;
  onDeleteNode: (id: string) => void;
}) {
  // Metadados de config (perfis/campos/defaults) — fonte única do backend, p/ o
  // passo herdar do Tipo de fluxo e sobrepor por-nó. Buscado uma vez.
  const [painel, setPainel] = useState<PainelConfigFluxo | null>(null);
  useEffect(() => {
    api.get<PainelConfigFluxo>("/config/fluxo").then(setPainel).catch(() => {});
  }, []);
  const campoPorChave: Record<string, CampoConfigFluxo> = {};
  for (const g of painel?.grupos ?? [])
    for (const c of g.campos) campoPorChave[c.chave] = c;
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

  // Quantas saídas são CONDICIONAIS (as de erro/"senão" não contam como bifurcação:
  // elas não são escolhidas pelo agente, são acionadas pelo motor).
  const condicionaisDoNo = (no.saidas ?? []).filter(
    (s) => papelDaSaida(s) === "condicional",
  ).length;
  const temSenao = (no.saidas ?? []).some((s) => papelDaSaida(s) === "senao");

  const ag = no.tipo === "agente" ? agentes.find((a) => a.id === no.ref) : undefined;
  const indice = ag ? agentes.findIndex((a) => a.id === ag.id) : 0;
  // A automação que o nó "Chamar outra automação" roda — para avisar quando ela está
  // desativada. Chamar uma automação desligada FUNCIONA (avisar, não impedir), então o
  // aviso é o que separa a escolha deliberada do engano.
  const alvoEscolhido =
    no.tipo === "chamar"
      ? automacoesOrg.find((a) => a.id === no.chamar?.automacao_id)
      : undefined;
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
                  ["manual", Play, "Dispara pelo botão de teste.", "Manual"],
                  ["agendamento", Clock, "Roda sozinho num horário fixo.", "Agendamento"],
                  ["webhook", Zap, "Um sistema externo dispara via URL.", "Webhook"],
                  [
                    "comentario_instagram",
                    MessageCircle,
                    "Um comentário num post dispara o fluxo.",
                    "Comentário do Instagram",
                  ],
                ] as const
              ).map(([k, Ic, hint, rotulo]) => {
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
                      <div className="text-[13.5px] font-medium text-[#1A1730]">
                        {rotulo}
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
              <div className="flex flex-col gap-2 rounded-[9px] border border-[#E8E6F0] p-3">
                {webhookUrl ? (
                  <>
                    <p className="text-[12px] leading-relaxed text-[#6B6880]">
                      Um sistema externo dispara este fluxo por esta URL (POST). O
                      corpo enviado vira a entrada.
                    </p>
                    <UrlCopiavel
                      url={webhookUrl}
                      aviso="O fluxo precisa estar ativo para o webhook disparar."
                    />
                  </>
                ) : (
                  <p className="text-[12px] leading-relaxed text-[#6B6880]">
                    Salve a automação para gerar a URL do webhook.
                  </p>
                )}
              </div>
            )}

            {gatilho.tipo === "comentario_instagram" && (
              <div className="flex flex-col gap-2.5 rounded-[9px] border border-[#E8E6F0] p-3">
                <p className="text-[12px] leading-relaxed text-[#6B6880]">
                  Cada comentário nos posts da conta escolhida dispara este fluxo.
                </p>

                {/* Conta do Instagram */}
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Conta do Instagram
                  {credenciaisInstagram.length > 0 ? (
                    <select
                      className={`${inputCls} mt-1 cursor-pointer`}
                      value={gatilho.credencialId}
                      disabled={!podeEditar}
                      onChange={(e) => setGatilho({ credencialId: e.target.value })}
                    >
                      <option value="">Escolha a conta…</option>
                      {credenciaisInstagram.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nome}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span
                      className="mt-1 block text-[11.5px]"
                      style={{ color: "#A09DB8" }}
                    >
                      Nenhuma conta do Instagram conectada nesta organização. Conecte
                      uma em Chaves &amp; credenciais para usar este gatilho.
                    </span>
                  )}
                </label>
                {credenciaisInstagram.length > 0 && !gatilho.credencialId && (
                  <span className="text-[11px] text-warning">
                    ⚠ Escolha a conta antes de ativar — sem ela o gatilho não dispara.
                  </span>
                )}

                {/* Quais posts */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px]" style={{ color: "#6B6880" }}>
                    Quais posts
                  </span>
                  {(
                    [
                      ["todas", "Todos os posts do perfil"],
                      ["especificas", "Posts específicos"],
                    ] as const
                  ).map(([modo, rotulo]) => (
                    <label
                      key={modo}
                      className="flex cursor-pointer items-center gap-2 text-[12.5px] text-[#1A1730]"
                    >
                      <input
                        type="radio"
                        name="midiasModo"
                        checked={gatilho.midiasModo === modo}
                        disabled={!podeEditar}
                        onChange={() => setGatilho({ midiasModo: modo })}
                      />
                      {rotulo}
                    </label>
                  ))}
                  {gatilho.midiasModo === "especificas" && (
                    <textarea
                      className={`${inputCls} mt-1 min-h-14`}
                      placeholder="IDs dos posts (media_id), separados por vírgula"
                      value={gatilho.midiasIds}
                      disabled={!podeEditar}
                      onChange={(e) => setGatilho({ midiasIds: e.target.value })}
                    />
                  )}
                </div>

                {/* Palavra-chave */}
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Palavra-chave (opcional)
                  <input
                    className={`${inputCls} mt-1`}
                    placeholder="Só dispara se o comentário contiver…"
                    value={gatilho.palavraChave}
                    disabled={!podeEditar}
                    onChange={(e) => setGatilho({ palavraChave: e.target.value })}
                  />
                </label>

                {/* Teto por hora */}
                <label className="text-[11px]" style={{ color: "#6B6880" }}>
                  Teto de disparos por hora
                  <input
                    type="number"
                    min={0}
                    className={`${inputCls} mt-1`}
                    value={gatilho.tetoPorHora}
                    disabled={!podeEditar}
                    onChange={(e) =>
                      setGatilho({ tetoPorHora: Number(e.target.value) })
                    }
                  />
                  <span
                    className="mt-0.5 block text-[11px]"
                    style={{ color: "#A09DB8" }}
                  >
                    Protege seu custo se um post viralizar. 0 = sem limite.
                  </span>
                </label>

                {/* dica do portão */}
                <p className="flex gap-1.5 rounded-md bg-[#FAFAF7] p-2 text-[11px] leading-snug text-[#6B6880]">
                  <MessageCircle
                    size={13}
                    color="#6D4AFF"
                    className="mt-px flex-none"
                  />
                  A resposta é pública. Se quiser revisar antes de responder, dê ao
                  agente que responde o instrumento &ldquo;Pedir aprovação e
                  aguardar&rdquo;.
                </p>
              </div>
            )}
          </div>
        )}

        {/* agente: o que fazer quando este passo precisar de uma pessoa */}
        {no.tipo === "agente" && (
          <div className="mb-4 flex flex-col gap-2.5">
            <div className="flex items-start gap-3 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3">
              <Shield size={17} color="#A09DB8" className="mt-0.5" />
              <div className="flex-1">
                <div className="text-[13.5px] font-medium text-[#1A1730]">
                  Aprovação é do agente
                </div>
                <div className="mt-0.5 text-[11.5px] leading-snug text-[#6B6880]">
                  Não há mais interruptor de portão aqui. Para este passo esperar
                  alguém, dê ao agente o instrumento{" "}
                  <strong>Pedir aprovação e aguardar</strong> e escreva na
                  documentação dele quando usá-lo. Ele apresenta, o fluxo para, e
                  continua quando a pessoa responde.
                </div>
              </div>
            </div>

            {/* Teto de TEMPO deste passo (Onda 3, fatia 2) — bloco próprio, e não
                junto do de espera: um diz quanto o AGENTE pode trabalhar, o outro
                quanto esperar uma PESSOA responder. Assuntos diferentes. */}
            {painel && campoPorChave["teto_min_passo"] && (
              <div className="flex flex-col gap-3 rounded-[10px] border border-[#E8E6F0] p-3">
                <div>
                  <div className="text-[12.5px] font-medium text-[#1A1730]">
                    Tempo deste passo
                  </div>
                  <p className="mt-0.5 text-[11px] leading-snug text-[#6B6880]">
                    Quanto ele pode trabalhar antes de ser interrompido. Segue o{" "}
                    <strong>Tipo de fluxo</strong>; ajuste aqui só se este passo for
                    diferente (uma geração de vídeo, por exemplo). O limite vale para o
                    trabalho todo do agente — cada chamada tem o seu próprio.
                  </p>
                </div>
                {(() => {
                  const cfg = no.config ?? {};
                  const ajustado = "teto_min_passo" in cfg;
                  return (
                    <CampoConfig
                      campo={campoPorChave["teto_min_passo"]}
                      valor={
                        ajustado
                          ? cfg["teto_min_passo"]
                          : efetivoDoFluxo(painel, configFluxo, "teto_min_passo")
                      }
                      ajustado={ajustado}
                      podeEditar={podeEditar}
                      rotuloHerdado="herdado do fluxo"
                      onChange={(v) =>
                        onPatchNode(no.id, { config: { ...cfg, teto_min_passo: v } })
                      }
                      onReset={() =>
                        onPatchNode(no.id, {
                          config: semChave(cfg, "teto_min_passo"),
                        })
                      }
                    />
                  );
                })()}
              </div>
            )}

            {/* Regras da espera (sobrepõem o Tipo de fluxo — cascata `no.config`) */}
            {painel && (
              <div className="flex flex-col gap-3 rounded-[10px] border border-[#E8E6F0] p-3">
                <div>
                  <div className="text-[12.5px] font-medium text-[#1A1730]">
                    Se este passo esperar uma pessoa
                  </div>
                  <p className="mt-0.5 text-[11px] leading-snug text-[#6B6880]">
                    Quanto tempo esperar e o que fazer no silêncio. Segue o{" "}
                    <strong>Tipo de fluxo</strong>; ajuste abaixo só o que quiser
                    valer <strong>só neste passo</strong>.
                  </p>
                </div>
                {CHAVES_PORTAO.map((chave) => {
                  const campo = campoPorChave[chave];
                  if (!campo) return null;
                  const cfg = no.config ?? {};
                  const ajustado = chave in cfg;
                  const valor = ajustado
                    ? cfg[chave]
                    : efetivoDoFluxo(painel, configFluxo, chave);
                  return (
                    <CampoConfig
                      key={chave}
                      campo={campo}
                      valor={valor}
                      ajustado={ajustado}
                      podeEditar={podeEditar}
                      rotuloHerdado="herdado do fluxo"
                      onChange={(v) =>
                        onPatchNode(no.id, { config: { ...cfg, [chave]: v } })
                      }
                      onReset={() =>
                        onPatchNode(no.id, { config: semChave(cfg, chave) })
                      }
                    />
                  );
                })}
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

        {/* "Esperar": quanto tempo o fluxo fica parado aqui. */}
        {no.tipo === "esperar" && (
          <div className="mb-4 flex flex-col gap-3">
            <p className="flex gap-2 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3 text-[11.5px] leading-relaxed text-[#6B6880]">
              <Hourglass size={14} color="#6D4AFF" className="mt-px flex-none" />
              <span>
                Este passo não faz trabalho: ele <b>segura o fluxo</b> e o solta depois
                do tempo. A <b>ficha</b> e o ponto do fluxo são preservados — a execução
                volta exatamente daqui, com tudo o que já se sabia. É diferente de
                agendar outra automação, que começaria do zero.
              </span>
            </p>
            <div className="flex items-end gap-2">
              <label
                className="block flex-1 text-[12px] font-medium"
                style={{ color: "#6B6880" }}
              >
                Esperar
                <input
                  type="number"
                  min={0}
                  className={`${inputCls} mt-1.5`}
                  style={
                    !Number(no.espera?.quanto ?? 0)
                      ? { borderColor: "#E5484D" }
                      : undefined
                  }
                  value={no.espera?.quanto ?? 0}
                  disabled={!podeEditar}
                  onChange={(e) =>
                    onPatchNode(no.id, {
                      espera: {
                        quanto: Number(e.target.value || 0),
                        unidade: no.espera?.unidade ?? "minutos",
                      },
                    })
                  }
                />
              </label>
              <label
                className="block flex-1 text-[12px] font-medium"
                style={{ color: "#6B6880" }}
              >
                Unidade
                <Select
                  className="mt-1.5"
                  value={no.espera?.unidade ?? "minutos"}
                  disabled={!podeEditar}
                  onChange={(e) =>
                    onPatchNode(no.id, {
                      espera: {
                        quanto: Number(no.espera?.quanto ?? 0),
                        unidade: e.target.value as "minutos" | "horas" | "dias",
                      },
                    })
                  }
                >
                  <option value="minutos">minutos</option>
                  <option value="horas">horas</option>
                  <option value="dias">dias</option>
                </Select>
              </label>
            </div>
            {!Number(no.espera?.quanto ?? 0) && (
              <span className="text-[11px]" style={{ color: "#B42318" }}>
                Sem tempo definido, este passo não segura nada: o fluxo passa direto e
                o rastro avisa. Melhor seguir do que parar para sempre — mas defina o
                tempo.
              </span>
            )}
          </div>
        )}

        {/* "Chamar outra automação": qual automação roda aqui. O alvo é fixado pelo
            HUMANO (nunca escolhido pelo agente) — mesma regra do instrumento
            `agendar_automacao`, e pela mesma razão: agente que escolhe alvo pode
            apontar para o lugar errado. */}
        {no.tipo === "chamar" && (
          <div className="mb-4 flex flex-col gap-3">
            <p className="flex gap-2 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3 text-[11.5px] leading-relaxed text-[#6B6880]">
              <ArrowRightLeft size={14} color="#6D4AFF" className="mt-px flex-none" />
              <span>
                Este passo roda <b>outra automação inteira</b> e <b>espera o resultado
                dela</b> para seguir. A automação chamada recebe a ficha desta execução
                e devolve o que produziu — inclusive se ela mesma parar para pedir uma
                aprovação, caso em que este fluxo continua parado até lá.
              </span>
            </p>
            <label
              className="block text-[12px] font-medium"
              style={{ color: "#6B6880" }}
            >
              Automação a chamar
              <Select
                className="mt-1.5"
                style={
                  !no.chamar?.automacao_id ? { borderColor: "#E5484D" } : undefined
                }
                value={no.chamar?.automacao_id ?? ""}
                disabled={!podeEditar}
                onChange={(e) =>
                  onPatchNode(no.id, { chamar: { automacao_id: e.target.value } })
                }
              >
                <option value="">— escolha a automação —</option>
                {automacoesOrg.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.time_nome ? `${a.time_nome} · ${a.nome}` : a.nome} (
                    {a.ativa ? "ativa" : "desativada"})
                  </option>
                ))}
              </Select>
            </label>
            {alvoEscolhido && !alvoEscolhido.ativa && (
              <p
                className="rounded-md px-2.5 py-2 text-[11px] leading-relaxed"
                style={{ background: "#FDF1E3", color: "#A9681A" }}
              >
                {alvoEscolhido.desligada_por_falhas ? (
                  <>
                    <b>{alvoEscolhido.nome}</b> foi <b>desligada pelo disjuntor</b> — ela
                    falhou 3 vezes seguidas rodando sozinha. Este passo vai chamá-la assim
                    mesmo, mas veja o que quebrou nela antes de confiar no resultado.
                  </>
                ) : (
                  <>
                    <b>{alvoEscolhido.nome}</b> está <b>desativada</b>. Este passo vai
                    chamá-la assim mesmo — chamar não depende de a automação estar ativa,
                    porque uma automação que só existe para ser chamada não tem gatilho
                    próprio. Confira se é isso que você quer.
                  </>
                )}
              </p>
            )}
            {!no.chamar?.automacao_id && (
              <span className="text-[11px]" style={{ color: "#B42318" }}>
                Sem automação escolhida este passo não chama nada — e não dá para
                salvar o fluxo assim. Diferente do &quot;Esperar&quot; sem tempo, aqui
                seguir adiante entregaria ao próximo passo uma entrada vazia como se
                estivesse tudo certo.
              </span>
            )}
            <p className="text-[11px] leading-relaxed text-[#6B6880]">
              Desenhe uma saída <b>&quot;Se der erro&quot;</b> se quiser tratar a falha
              da automação chamada. Sem ela, se a chamada falhar, esta execução falha
              junto.
            </p>
          </div>
        )}

        {no.tipo === "cada" && (
          <div className="mb-4 flex flex-col gap-3">
            <p className="flex gap-2 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3 text-[11.5px] leading-relaxed text-[#6B6880]">
              <Repeat2 size={14} color="#6D4AFF" className="mt-px flex-none" />
              <span>
                Este passo não roda agente: ele lê uma <b>lista da ficha da execução</b>{" "}
                e repete o trecho seguinte <b>uma vez por item</b>. Cada repetição é um
                caminho próprio — elas não se misturam. Até {MAX_ITENS_CADA} itens por
                vez; acima disso o excedente não roda e o rastro diz quantos ficaram de
                fora.
              </span>
            </p>
            <label
              className="block text-[12px] font-medium"
              style={{ color: "#6B6880" }}
            >
              Percorrer a lista guardada em
              <input
                className={`${inputCls} mt-1.5`}
                style={
                  !(no.lista ?? "").trim() ? { borderColor: "#E5484D" } : undefined
                }
                value={no.lista ?? ""}
                placeholder="ex.: pedidos"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { lista: e.target.value })}
              />
              {!(no.lista ?? "").trim() && (
                <span className="mt-1 block text-[11px]" style={{ color: "#B42318" }}>
                  Sem isto o passo não sabe o que repetir. Use o mesmo nome que um passo
                  anterior guarda com <span className="font-mono">anotar</span>.
                </span>
              )}
            </label>
            <label
              className="block text-[12px] font-medium"
              style={{ color: "#6B6880" }}
            >
              Cada item se chama
              <input
                className={`${inputCls} mt-1.5`}
                value={no.item_em ?? ""}
                placeholder="item"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { item_em: e.target.value })}
              />
              <span className="mt-1 block text-[11px] leading-normal text-[#6B6880]">
                É por este nome que os agentes da repetição leem o item na ficha, junto
                com <span className="font-mono">item_numero</span> e{" "}
                <span className="font-mono">item_total</span>.
              </span>
            </label>
            <label
              className="block text-[12px] font-medium"
              style={{ color: "#6B6880" }}
            >
              Somar o resultado de cada repetição em (opcional)
              <input
                className={`${inputCls} mt-1.5`}
                value={no.acumular_em ?? ""}
                placeholder="ex.: relatorio"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { acumular_em: e.target.value })}
              />
            </label>
          </div>
        )}

        {/* saídas (todos menos fim) */}
        {no.tipo !== "fim" && no.tipo !== "gatilho" && (
          <div>
            <div className="mb-1.5 inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[#1A1730]">
              <Zap size={14} color="#6D4AFF" /> Saídas
              {condicionaisDoNo > 1 ? ` · bifurca em ${condicionaisDoNo}` : ""}
            </div>
            {condicionaisDoNo > 1 && (
              <p className="mb-2.5 flex gap-1.5 text-[11.5px] leading-normal text-[#6B6880]">
                <CircleHelp size={13} color="#A09DB8" className="mt-px flex-none" />
                O agente avalia cada condição e segue por <b>todas</b> as que forem
                atendidas. Duas saídas com a mesma condição = as duas rodam.
              </p>
            )}
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
                  exigeCondicao={condicionaisDoNo > 1}
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
            {condicionaisDoNo > 1 && !temSenao && (
              <p className="mt-2 flex gap-1.5 text-[11.5px] leading-normal text-[#6B6880]">
                <CircleHelp size={13} color="#A09DB8" className="mt-px flex-none" />
                Se nenhuma condição for atendida, o fluxo termina aqui e o motivo fica
                no rastro da execução. Para tratar esse caso, acrescente uma saída
                &ldquo;Se nenhuma&rdquo;.
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

        {/* "Testar este passo" (Onda 4, fatia 5): só nos nós que o motor executa —
            gatilho, fim e "Para cada item" não rodam nada, então testá-los não faria
            sentido (e o backend recusa, pela mesma razão). */}
        {(no.tipo === "agente" || no.tipo === "roteador") && (
          <TestarEstePasso
            key={no.id}
            automacaoId={automacaoId}
            timeId={timeId}
            noId={no.id}
            cinto={no.tipo === "agente" && no.ref ? (cintos[no.ref] ?? []) : []}
            podeEditar={podeEditar}
            naoSalvo={naoSalvo}
          />
        )}
      </div>

      {/* rodapé: remover (os nós que o usuário acrescentou; gatilho e fim são fixos).
          A regra é por EXCLUSÃO de propósito: enquanto era uma lista do que PODE
          (`agente|roteador|cada`), todo tipo de nó novo nascia sem botão de remover — foi
          o que aconteceu com "Esperar" e "Chamar outra automação". Assim, tipo novo já
          nasce removível, e só os dois nós fixos ficam de fora. */}
      {podeEditar && no.tipo !== "gatilho" && no.tipo !== "fim" && (
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
