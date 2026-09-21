"use client";

// O PAINEL DA DIREITA do estúdio.
//
// Mesmos campos do construtor clássico — a diferença é a ORDEM e o peso. Ali, o
// primeiro campo de uma saída é o `Nome`, e a condição vem depois, como um detalhe.
// Aqui a CONDIÇÃO vem primeiro e grande, porque é ela que decide o fluxo; o nome vem
// depois, explicado como o que ele de fato é: a palavra que o agente declara.
//
// O painel também repete, em cima, os problemas do passo selecionado — para quem
// clicou num cartão vermelho não precisar procurar o motivo em outro canto da tela.

import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Pencil,
  Plus,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";

import {
  OPERADORES_REGRA,
  OPERADORES_SEM_VALOR,
  type Agente,
  type AutomacaoDaOrg,
  type Cadeia,
  type Credencial,
  type NoCadeia,
  type OperadorRegra,
  type RegraSaida,
  type SaidaCadeia,
  type TipoSaida,
  type ToneSaida,
} from "@/lib/api";
import type { ConfigGatilho } from "@/components/automacao-builder/inspector";

import { CORES, corDaSaida } from "./cores";
import { nomeDoNo, papel, type Problema } from "./problemas";

const campo =
  "w-full rounded-md border border-[#E8E6F0] bg-white px-2.5 py-1.5 text-[13px] text-[#1A1730] outline-none focus:border-[#6D4AFF]";
const rotuloCls = "mb-1 block text-[11px] text-[#6B6880]";

const DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

const PAPEIS: { chave: TipoSaida; rotulo: string; ajuda: string }[] = [
  {
    chave: "condicional",
    rotulo: "Condição",
    ajuda: "O agente lê a frase e segue por aqui se ela for verdade.",
  },
  {
    chave: "erro",
    rotulo: "Se falhar",
    ajuda: "Só quando ESTE passo falha. O erro segue por aqui em vez de derrubar tudo.",
  },
  {
    chave: "senao",
    rotulo: "Se nenhuma",
    ajuda: "Rede de segurança: só quando nenhuma condição acima foi atendida.",
  },
];

const TONS: { chave: ToneSaida; rotulo: string }[] = [
  { chave: "normal", rotulo: "segue" },
  { chave: "ok", rotulo: "deu certo" },
  { chave: "loop", rotulo: "volta" },
];

function ListaDeProblemas({ problemas }: { problemas: Problema[] }) {
  if (!problemas.length) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {problemas.map((p) => {
        const erro = p.nivel === "erro";
        return (
          <div
            key={p.id}
            className="rounded-[10px] border p-2.5"
            style={{
              borderColor: erro ? "#F5C2C0" : "#F0D9B4",
              background: erro ? "#FDECEC" : "#FDF1E3",
            }}
          >
            <div
              className="flex items-start gap-1.5 text-[12px] font-medium"
              style={{ color: erro ? "#B42318" : "#8A5A12" }}
            >
              {erro ? (
                <ShieldAlert size={13} className="mt-px flex-none" />
              ) : (
                <AlertTriangle size={13} className="mt-px flex-none" />
              )}
              {p.titulo}
            </div>
            <p
              className="mt-1 text-[11.5px] leading-snug"
              style={{ color: erro ? "#B42318" : "#8A5A12" }}
            >
              {p.comoResolver}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function EditorRegra({
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
        + Deixar o sistema decidir (regra exata)
      </button>
    );
  }
  return (
    <div className="rounded-md border border-[#E0DAF6] bg-[#FBFAFF] p-2">
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className="text-[11px] font-medium text-[#3D2A99]">
          Quem confere é o sistema
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
          className={`${campo} min-w-24 flex-1`}
          value={r?.campo ?? ""}
          placeholder="campo (ex.: total)"
          disabled={!podeEditar}
          onChange={(e) => patch({ campo: e.target.value })}
        />
        <select
          className={`${campo} w-auto flex-1 cursor-pointer`}
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
            className={`${campo} min-w-16 flex-1`}
            value={r?.valor ?? ""}
            placeholder="valor"
            disabled={!podeEditar}
            onChange={(e) => patch({ valor: e.target.value })}
          />
        )}
        {r?.operador === "entre" && (
          <input
            className={`${campo} min-w-16 flex-1`}
            value={r?.valor2 ?? ""}
            placeholder="e"
            disabled={!podeEditar}
            onChange={(e) => patch({ valor2: e.target.value })}
          />
        )}
      </div>
      <p className="mt-1.5 text-[11px] leading-normal text-[#6B6880]">
        Com regra, a IA não opina: o Batuta compara o campo da ficha e pronto. Use o
        mesmo nome que um passo anterior guardou com <span className="font-mono">anotar</span>
        {" "}(ou <span className="font-mono">entrada</span>, que é o que o gatilho trouxe).
      </p>
    </div>
  );
}

function CartaoSaida({
  no,
  sa,
  indice,
  cadeia,
  agentes,
  podeEditar,
  exigeCondicao,
  problemas,
  selecionada,
  onChange,
  onRemove,
}: {
  no: NoCadeia;
  sa: SaidaCadeia;
  indice: number;
  cadeia: Cadeia;
  agentes: Agente[];
  podeEditar: boolean;
  exigeCondicao: boolean;
  problemas: Problema[];
  selecionada: boolean;
  onChange: (patch: Partial<SaidaCadeia>) => void;
  onRemove: () => void;
}) {
  const pp = papel(sa);
  const c = corDaSaida(sa);
  const destinos = (cadeia.nos ?? []).filter((n) => n.tipo !== "gatilho");
  const faltaCondicao = pp === "condicional" && exigeCondicao && !(sa.quando ?? "").trim();

  return (
    <div
      id={`saida-${sa.id}`}
      className="flex flex-col gap-2.5 rounded-[10px] border p-2.5"
      style={{
        borderColor: selecionada ? "#6D4AFF" : problemas.length ? "#F0D9B4" : "#E8E6F0",
        background: selecionada ? "#FBFAFF" : "#FAFAF7",
        boxShadow: selecionada ? "0 0 0 3px rgba(109,74,255,.10)" : undefined,
      }}
    >
      <div className="flex items-center gap-2">
        <span className="size-2.5 flex-none rounded-full" style={{ background: c.dot }} />
        <span className="text-[11.5px] font-medium text-[#A09DB8]">
          Caminho {indice + 1}
        </span>
        <div className="flex-1" />
        {podeEditar && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remover este caminho"
            className="p-0.5 text-[#A09DB8] hover:text-foreground"
          >
            <X size={15} />
          </button>
        )}
      </div>

      <ListaDeProblemas problemas={problemas} />

      {/* Papel da saída: é o que o motor lê. */}
      <div className="flex gap-1.5">
        {PAPEIS.map((p) => {
          const on = pp === p.chave;
          const cc = p.chave === "erro" ? CORES.erro : CORES.normal;
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
                    : { tipo: p.chave, quando: "", regra: null },
                )
              }
              className="flex-1 rounded-md border px-1 py-1.5 text-[11px]"
              style={{
                borderColor: on ? cc.dot : "#E8E6F0",
                background: on ? cc.pilulaBg : "#fff",
                color: on ? cc.pilulaFg : "#A09DB8",
                fontWeight: on ? 500 : 400,
              }}
            >
              {p.rotulo}
            </button>
          );
        })}
      </div>

      {/* A CONDIÇÃO — primeiro campo, e o maior. É ela que aparece no fio. */}
      {pp === "condicional" ? (
        <div>
          <label className={rotuloCls}>
            <span className="font-medium text-[#1A1730]">Siga por aqui quando…</span>{" "}
            (é isto que aparece no fio)
          </label>
          <textarea
            className={`${campo} resize-none leading-snug`}
            rows={2}
            style={faltaCondicao ? { borderColor: "#E5484D" } : undefined}
            value={sa.quando ?? ""}
            placeholder={
              no.tipo === "roteador"
                ? "ex.: a tarefa que chega for sobre cobrança"
                : "ex.: a pessoa aprovar a imagem"
            }
            disabled={!podeEditar}
            onChange={(e) => onChange({ quando: e.target.value })}
          />
          {faltaCondicao && (
            <p className="mt-1 text-[11px] text-[#B42318]">
              Este passo bifurca. Sem esta frase o agente escolhe no escuro — e o
              salvamento é recusado.
            </p>
          )}
          <div className="mt-2 flex flex-col">
            <EditorRegra
              regra={sa.regra}
              podeEditar={podeEditar}
              onChange={(regra) => onChange({ regra })}
            />
          </div>
        </div>
      ) : (
        <p className="text-[11.5px] leading-snug text-[#6B6880]">
          {PAPEIS.find((p) => p.chave === pp)?.ajuda}
        </p>
      )}

      <div>
        <label className={rotuloCls}>
          Nome do caminho — a palavra que o agente declara
        </label>
        <input
          className={campo}
          value={sa.rotulo}
          placeholder={pp === "erro" ? "ex.: deu erro" : "ex.: aprovado"}
          disabled={!podeEditar}
          onChange={(e) => onChange({ rotulo: e.target.value })}
        />
        <p className="mt-1 text-[11px] leading-snug text-[#6B6880]">
          Escreva esta mesma palavra no texto do agente. Se as duas não baterem
          (inclusive por um erro de digitação), este caminho nunca é tomado.
        </p>
      </div>

      <div>
        <label className="mb-1 flex items-center gap-1.5 text-[11px] text-[#6B6880]">
          <ArrowRight size={12} color="#A09DB8" /> vai para
        </label>
        <select
          className={`${campo} cursor-pointer`}
          value={sa.destino}
          disabled={!podeEditar}
          onChange={(e) => onChange({ destino: e.target.value })}
        >
          {destinos.map((dn) => (
            <option key={dn.id} value={dn.id}>
              {nomeDoNo(dn, agentes)}
            </option>
          ))}
        </select>
      </div>

      {pp !== "erro" && (
        <div className="flex gap-1.5">
          {TONS.map((t) => {
            const cc = CORES[t.chave];
            const on = (sa.tone ?? "normal") === t.chave;
            return (
              <button
                key={t.chave}
                type="button"
                disabled={!podeEditar}
                onClick={() => onChange({ tone: t.chave })}
                title={cc.legenda}
                className="inline-flex flex-1 items-center justify-center gap-1 rounded-md border px-1 py-1.5 text-[11px]"
                style={{
                  borderColor: on ? cc.dot : "#E8E6F0",
                  background: on ? cc.pilulaBg : "#fff",
                  color: on ? cc.pilulaFg : "#A09DB8",
                  fontWeight: on ? 500 : 400,
                }}
              >
                <span className="size-[7px] rounded-full" style={{ background: cc.dot }} />
                {t.rotulo}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export type PainelProps = {
  no: NoCadeia | null;
  cadeia: Cadeia;
  agentes: Agente[];
  podeEditar: boolean;
  problemas: Problema[];
  saidaSelecionada: string | null;
  gatilho: ConfigGatilho;
  setGatilho: (patch: Partial<ConfigGatilho>) => void;
  webhookUrl?: string | null;
  credenciaisInstagram: Credencial[];
  automacoesOrg: AutomacaoDaOrg[];
  onPatchNode: (id: string, patch: Partial<NoCadeia>) => void;
  onPatchSaida: (id: string, sid: string, patch: Partial<SaidaCadeia>) => void;
  onAddSaida: (id: string) => void;
  onRemoveSaida: (id: string, sid: string) => void;
  onDeleteNode: (id: string) => void;
  onDefinirInicial: (id: string) => void;
  onEditarAgente: (agenteId: string) => void;
};

export function PainelEstudio({
  no,
  cadeia,
  agentes,
  podeEditar,
  problemas,
  saidaSelecionada,
  gatilho,
  setGatilho,
  webhookUrl,
  credenciaisInstagram,
  automacoesOrg,
  onPatchNode,
  onPatchSaida,
  onAddSaida,
  onRemoveSaida,
  onDeleteNode,
  onDefinirInicial,
  onEditarAgente,
}: PainelProps) {
  if (!no) return <PainelVazio />;

  const doNo = problemas.filter((p) => p.noId === no.id && !p.saidaId);
  const saidas = no.saidas ?? [];
  const condicionais = saidas.filter((s) => papel(s) === "condicional");
  const exigeCondicao =
    (no.tipo === "agente" || no.tipo === "roteador") && condicionais.length >= 2;
  const agente = no.tipo === "agente" ? agentes.find((a) => a.id === no.ref) : undefined;
  const executavel = no.tipo === "agente" || no.tipo === "roteador";

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[#E8E6F0] bg-white px-3.5 py-3">
        <div className="min-w-0 flex-1">
          <div className="text-[10.5px] font-medium uppercase tracking-wide text-[#A09DB8]">
            {no.tipo === "gatilho"
              ? "Gatilho"
              : no.tipo === "agente"
                ? "Passo · agente"
                : no.tipo === "fim"
                  ? "Fim"
                  : "Passo"}
          </div>
          <div className="truncate text-[15px] font-medium text-[#1A1730]">
            {nomeDoNo(no, agentes)}
          </div>
        </div>
        {agente && (
          <button
            type="button"
            onClick={() => onEditarAgente(agente.id)}
            className="inline-flex items-center gap-1 rounded-md border border-[#E8E6F0] px-2 py-1 text-[11.5px] text-[#6D4AFF] hover:bg-[#F4F1FE]"
            title="Abrir o texto do agente"
          >
            <Pencil size={12} /> texto
          </button>
        )}
      </div>

      <div className="flex flex-col gap-3.5 p-3.5">
        <ListaDeProblemas problemas={doNo} />

        {/* ── o que este passo é ── */}
        {no.tipo === "gatilho" && (
          <ConfigGatilhoBloco
            gatilho={gatilho}
            setGatilho={setGatilho}
            webhookUrl={webhookUrl}
            credenciaisInstagram={credenciaisInstagram}
            cadeia={cadeia}
            agentes={agentes}
            podeEditar={podeEditar}
            onDefinirInicial={onDefinirInicial}
          />
        )}

        {no.tipo === "agente" && (
          <div>
            <label className={rotuloCls}>Quem faz este passo</label>
            <select
              className={`${campo} cursor-pointer`}
              value={no.ref ?? ""}
              disabled={!podeEditar}
              onChange={(e) => onPatchNode(no.id, { ref: e.target.value })}
            >
              <option value="">— escolha um agente —</option>
              {agentes.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nome}
                </option>
              ))}
            </select>
          </div>
        )}

        {no.tipo === "roteador" && (
          <div>
            <label className={rotuloCls}>Nome desta decisão</label>
            <input
              className={campo}
              value={no.nome ?? ""}
              placeholder="ex.: é reclamação ou elogio?"
              disabled={!podeEditar}
              onChange={(e) => onPatchNode(no.id, { nome: e.target.value })}
            />
            <p className="mt-1 text-[11px] leading-snug text-[#6B6880]">
              O roteador não roda agente nem gasta IA: ele só encaminha, olhando as
              condições dos caminhos abaixo.
            </p>
          </div>
        )}

        {no.tipo === "cada" && (
          <div className="flex flex-col gap-2.5">
            <div>
              <label className={rotuloCls}>Repetir para cada item de qual lista</label>
              <input
                className={campo}
                value={no.lista ?? ""}
                placeholder="ex.: artigos"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { lista: e.target.value })}
              />
            </div>
            <div>
              <label className={rotuloCls}>Como o item se chama em cada repetição</label>
              <input
                className={campo}
                value={no.item_em ?? ""}
                placeholder="item"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { item_em: e.target.value })}
              />
            </div>
            <div>
              <label className={rotuloCls}>Somar os resultados em (opcional)</label>
              <input
                className={campo}
                value={no.acumular_em ?? ""}
                placeholder="ex.: posts_gerados"
                disabled={!podeEditar}
                onChange={(e) => onPatchNode(no.id, { acumular_em: e.target.value })}
              />
            </div>
          </div>
        )}

        {no.tipo === "esperar" && (
          <div>
            <label className={rotuloCls}>O fluxo fica parado aqui por</label>
            <div className="flex gap-1.5">
              <input
                className={`${campo} w-20`}
                type="number"
                min={0}
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
              <select
                className={`${campo} flex-1 cursor-pointer`}
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
              </select>
            </div>
          </div>
        )}

        {no.tipo === "chamar" && (
          <div>
            <label className={rotuloCls}>Qual automação este passo roda</label>
            <select
              className={`${campo} cursor-pointer`}
              value={no.chamar?.automacao_id ?? ""}
              disabled={!podeEditar}
              onChange={(e) => onPatchNode(no.id, { chamar: { automacao_id: e.target.value } })}
            >
              <option value="">— escolha a automação —</option>
              {automacoesOrg.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nome} · {a.time_nome}
                  {a.ativa ? "" : " (pausada)"}
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] leading-snug text-[#6B6880]">
              Este passo espera a outra automação terminar e segue com o resultado dela.
            </p>
          </div>
        )}

        {no.tipo === "fim" && (
          <p className="text-[12px] leading-snug text-[#6B6880]">
            Onde o fluxo termina e o resultado é entregue. Todo caminho deveria chegar
            aqui — o painel de problemas avisa quando algum não chega.
          </p>
        )}

        {/* ── começar por aqui ── */}
        {executavel && !no.inicial && podeEditar && (
          <button
            type="button"
            onClick={() => onDefinirInicial(no.id)}
            className="self-start rounded-md border border-[#E8E6F0] px-2.5 py-1.5 text-[12px] text-[#6D4AFF] hover:bg-[#F4F1FE]"
          >
            Fazer deste o primeiro passo
          </button>
        )}

        {/* ── os caminhos que saem daqui ── */}
        {no.tipo !== "fim" && (
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-medium text-[#1A1730]">
                Caminhos que saem daqui
              </span>
              <span className="text-[11px] text-[#A09DB8]">
                {saidas.length === 0
                  ? "nenhum"
                  : saidas.length === 1
                    ? "1 caminho"
                    : `${saidas.length} caminhos`}
              </span>
              <div className="flex-1" />
              {podeEditar && no.tipo !== "gatilho" && (
                <button
                  type="button"
                  onClick={() => onAddSaida(no.id)}
                  className="inline-flex items-center gap-1 rounded-md border border-[#E8E6F0] px-2 py-1 text-[11.5px] text-[#6D4AFF] hover:bg-[#F4F1FE]"
                >
                  <Plus size={12} /> caminho
                </button>
              )}
            </div>

            {no.tipo === "gatilho" ? (
              <p className="text-[11.5px] leading-snug text-[#6B6880]">
                O gatilho tem um caminho só: o primeiro passo do fluxo. Escolha-o acima
                (ou puxe o fio no desenho).
              </p>
            ) : saidas.length === 0 ? (
              <p className="text-[11.5px] leading-snug text-[#B42318]">
                Sem caminho de saída, o fluxo morre neste passo, sem passar pelo Fim.
              </p>
            ) : (
              saidas.map((sa, i) => (
                <CartaoSaida
                  key={sa.id ?? i}
                  no={no}
                  sa={sa}
                  indice={i}
                  cadeia={cadeia}
                  agentes={agentes}
                  podeEditar={podeEditar}
                  exigeCondicao={exigeCondicao}
                  problemas={problemas.filter((p) => p.saidaId === sa.id)}
                  selecionada={saidaSelecionada === sa.id}
                  onChange={(patch) => sa.id && onPatchSaida(no.id, sa.id, patch)}
                  onRemove={() => sa.id && onRemoveSaida(no.id, sa.id)}
                />
              ))
            )}
          </div>
        )}

        {podeEditar && no.tipo !== "gatilho" && no.tipo !== "fim" && (
          <button
            type="button"
            onClick={() => onDeleteNode(no.id)}
            className="mt-1 inline-flex items-center gap-1.5 self-start rounded-md border border-[#F5C2C0] px-2.5 py-1.5 text-[12px] text-[#B42318] hover:bg-[#FDECEC]"
          >
            <Trash2 size={13} /> Apagar este passo
          </button>
        )}
      </div>
    </div>
  );
}

function ConfigGatilhoBloco({
  gatilho,
  setGatilho,
  webhookUrl,
  credenciaisInstagram,
  cadeia,
  agentes,
  podeEditar,
  onDefinirInicial,
}: {
  gatilho: ConfigGatilho;
  setGatilho: (patch: Partial<ConfigGatilho>) => void;
  webhookUrl?: string | null;
  credenciaisInstagram: Credencial[];
  cadeia: Cadeia;
  agentes: Agente[];
  podeEditar: boolean;
  onDefinirInicial: (id: string) => void;
}) {
  const executaveis = (cadeia.nos ?? []).filter(
    (n) => n.tipo === "agente" || n.tipo === "roteador",
  );
  const tipos: { chave: ConfigGatilho["tipo"]; rotulo: string }[] = [
    { chave: "manual", rotulo: "Manual" },
    { chave: "agendamento", rotulo: "Na hora marcada" },
    { chave: "webhook", rotulo: "Por webhook" },
    { chave: "comentario_instagram", rotulo: "Comentário no Instagram" },
  ];
  return (
    <div className="flex flex-col gap-2.5">
      <div>
        <label className={rotuloCls}>O que dispara esta automação</label>
        <div className="grid grid-cols-2 gap-1.5">
          {tipos.map((t) => {
            const on = gatilho.tipo === t.chave;
            return (
              <button
                key={t.chave}
                type="button"
                disabled={!podeEditar}
                onClick={() => setGatilho({ tipo: t.chave })}
                className="rounded-md border px-2 py-1.5 text-[11.5px]"
                style={{
                  borderColor: on ? "#6D4AFF" : "#E8E6F0",
                  background: on ? "#F4F1FE" : "#fff",
                  color: on ? "#3D2A99" : "#6B6880",
                  fontWeight: on ? 500 : 400,
                }}
              >
                {t.rotulo}
              </button>
            );
          })}
        </div>
      </div>

      {gatilho.tipo === "agendamento" && (
        <>
          <div className="flex gap-1.5">
            <select
              className={`${campo} flex-1 cursor-pointer`}
              value={gatilho.frequencia}
              disabled={!podeEditar}
              onChange={(e) =>
                setGatilho({ frequencia: e.target.value as ConfigGatilho["frequencia"] })
              }
            >
              <option value="diaria">Todo dia</option>
              <option value="semanal">Toda semana</option>
              <option value="mensal">Todo mês</option>
            </select>
            <input
              type="time"
              className={`${campo} w-28`}
              value={gatilho.horario}
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ horario: e.target.value })}
            />
          </div>
          {gatilho.frequencia === "semanal" && (
            <select
              className={`${campo} cursor-pointer`}
              value={gatilho.diaSemana}
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ diaSemana: Number(e.target.value) })}
            >
              {DIAS_SEMANA.map((d, i) => (
                <option key={d} value={i}>
                  {d}
                </option>
              ))}
            </select>
          )}
          {gatilho.frequencia === "mensal" && (
            <input
              type="number"
              min={1}
              max={28}
              className={`${campo} w-24`}
              value={gatilho.diaMes}
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ diaMes: Number(e.target.value) })}
            />
          )}
          <div>
            <label className={rotuloCls}>A mensagem que o gatilho entrega ao fluxo</label>
            <textarea
              className={`${campo} resize-none leading-snug`}
              rows={2}
              value={gatilho.entrada}
              placeholder="ex.: gere os posts da semana"
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ entrada: e.target.value })}
            />
          </div>
        </>
      )}

      {gatilho.tipo === "webhook" && (
        <div>
          <label className={rotuloCls}>Endereço a chamar</label>
          <div className="break-all rounded-md border border-[#E8E6F0] bg-[#FAFAF7] px-2 py-1.5 font-mono text-[11px] text-[#4A4860]">
            {webhookUrl ?? "aparece depois de salvar a automação"}
          </div>
        </div>
      )}

      {gatilho.tipo === "comentario_instagram" && (
        <>
          <div>
            <label className={rotuloCls}>Conta do Instagram</label>
            <select
              className={`${campo} cursor-pointer`}
              value={gatilho.credencialId}
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ credencialId: e.target.value })}
            >
              <option value="">— escolha a conta —</option>
              {credenciaisInstagram.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={rotuloCls}>Só comentários que contenham (opcional)</label>
            <input
              className={campo}
              value={gatilho.palavraChave}
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ palavraChave: e.target.value })}
            />
          </div>
          <div>
            <label className={rotuloCls}>Teto de disparos por hora</label>
            <input
              type="number"
              min={1}
              className={`${campo} w-24`}
              value={gatilho.tetoPorHora}
              disabled={!podeEditar}
              onChange={(e) => setGatilho({ tetoPorHora: Number(e.target.value) })}
            />
          </div>
        </>
      )}

      <div>
        <label className={rotuloCls}>Começa em</label>
        <select
          className={`${campo} cursor-pointer`}
          value={cadeia.inicial ?? ""}
          disabled={!podeEditar}
          onChange={(e) => onDefinirInicial(e.target.value)}
        >
          <option value="">— escolha o primeiro passo —</option>
          {executaveis.map((n) => (
            <option key={n.id} value={n.id}>
              {nomeDoNo(n, agentes)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/** Nada selecionado: em vez de um vazio, a legenda de como ler o desenho. */
function PainelVazio() {
  const linhas: { cor: string; tracejado?: boolean; titulo: string; texto: string }[] = [
    {
      cor: CORES.normal.dot,
      titulo: "segue adiante",
      texto: "o caminho comum, quando a condição escrita nele for atendida.",
    },
    {
      cor: CORES.ok.dot,
      titulo: "deu certo / aprovaram",
      texto: "o caminho bom — costuma ser o que sai de um passo que parou para perguntar.",
    },
    {
      cor: CORES.loop.dot,
      tracejado: true,
      titulo: "volta atrás",
      texto: "o passo é refeito. Tracejado porque é desvio, não avanço.",
    },
    {
      cor: CORES.erro.dot,
      tracejado: true,
      titulo: "quando falhar",
      texto: "só é percorrido se o passo der erro — o erro segue por aqui em vez de derrubar tudo.",
    },
  ];
  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <div className="text-[14px] font-medium text-[#1A1730]">Como ler este desenho</div>
        <p className="mt-1 text-[12px] leading-snug text-[#6B6880]">
          Cada cartão é um passo. As linhas dentro do cartão são os caminhos que saem
          dele — cada uma com a sua própria porta na borda. O que está escrito no fio é
          a <strong className="font-medium text-[#1A1730]">condição</strong>: quando o
          fluxo vai por ali.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {linhas.map((l) => (
          <div key={l.titulo} className="flex items-start gap-2.5">
            <svg width="30" height="14" className="mt-0.5 flex-none" aria-hidden>
              <line
                x1="1"
                y1="7"
                x2="29"
                y2="7"
                stroke={l.cor}
                strokeWidth="2"
                strokeDasharray={l.tracejado ? "5 4" : undefined}
              />
            </svg>
            <div className="min-w-0">
              <div className="text-[12px] font-medium text-[#1A1730]">{l.titulo}</div>
              <div className="text-[11.5px] leading-snug text-[#6B6880]">{l.texto}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3">
        <div className="text-[12px] font-medium text-[#1A1730]">
          Quem decide por qual caminho ir
        </div>
        <p className="mt-1 text-[11.5px] leading-snug text-[#6B6880]">
          Em regra, o <strong className="font-medium">agente</strong>: ele lê a condição
          escrita no fio e declara o nome do caminho que tomou. Quando a comparação
          precisa ser exata (um número, uma data), marque{" "}
          <strong className="font-medium">regra</strong> no caminho — aí quem confere é o
          Batuta, e a IA não opina.
        </p>
      </div>

      <div className="rounded-[10px] border border-[#F0D9B4] bg-[#FDF1E3] p-3">
        <div className="text-[12px] font-medium text-[#8A5A12]">
          Quando um passo para e pergunta
        </div>
        <p className="mt-1 text-[11.5px] leading-snug text-[#8A5A12]">
          Não existe interruptor para isso no desenho: o passo para porque o agente tem
          o instrumento <strong className="font-medium">Pedir aprovação</strong> no
          cinto. O cartão mostra o selo “para e pergunta” quando é o caso — e aí ele
          precisa de dois caminhos, um para quem aprova, outro para quem pede ajuste.
        </p>
      </div>

      <p className="text-[11.5px] leading-snug text-[#6B6880]">
        Clique num cartão para editar o passo, ou numa linha de caminho para editar só
        aquele fio.
      </p>
    </div>
  );
}
