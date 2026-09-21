// OS CARTÕES DO ESTÚDIO — um nó que mostra as próprias saídas.
//
// A diferença para o construtor clássico está aqui: naquele, o cartão mostra só
// QUEM é o passo, e as saídas moram no painel da direita — para ver a ramificação a
// pessoa precisa clicar em cada nó, um por um, e guardar tudo de cabeça. Aqui cada
// saída é uma LINHA no corpo do cartão, com a condição escrita, o destino e a porta
// (o pontinho de onde o fio sai) alinhada à sua própria linha — o padrão dos editores
// de grafo de verdade (Blueprints, Node-RED, n8n).
//
// Consequência prática: dá para ler o quebra-cabeça inteiro sem clicar em nada.

import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  CornerDownLeft,
  Hourglass,
  Layers,
  Pencil,
  Repeat2,
  Shield,
  ShieldAlert,
  Sparkles,
  Zap,
} from "lucide-react";

import type { Agente, Instrumento, NoCadeia, SaidaCadeia } from "@/lib/api";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { RobotFace } from "@/components/robot-face";

import { papel, type Problema } from "./problemas";
import { corDaSaida } from "./cores";

/** Largura de todo cartão. Mora aqui porque é uma medida DO cartão, não do canvas. */
export const LARGURA_NO = 268;

export type DadosNoEstudio = {
  no: NoCadeia;
  agente?: Agente;
  indice?: number;
  cinto?: Instrumento[];
  automacoes?: { id: string; nome: string }[];
  /** Problemas deste nó (selo no cartão) e das suas saídas (linha em vermelho). */
  problemas?: Problema[];
  /** Nome legível de qualquer nó — a linha da saída mostra para onde ela vai. */
  nomeDe?: (id: string) => string;
  /** O destino está ATRÁS deste nó no desenho? Então a linha mostra "volta para". */
  ehVolta?: (destino: string) => boolean;
  saidaSelecionada?: string | null;
  onSelecionarSaida?: (noId: string, saidaId: string) => void;
  onEditarAgente?: (agenteId: string) => void;
  onEditarInstrumento?: (instrumentoId: string) => void;
};

function selo(problemas: Problema[] | undefined) {
  if (!problemas?.length) return null;
  const temErro = problemas.some((p) => p.nivel === "erro");
  return (
    <span
      title={problemas.map((p) => `• ${p.titulo}`).join("\n")}
      className="inline-flex flex-none items-center gap-1 rounded-full border px-1.5 py-px text-[10.5px] font-medium"
      style={{
        color: temErro ? "#B42318" : "#A9681A",
        background: temErro ? "#FDECEC" : "#FDF1E3",
        borderColor: temErro ? "#F5C2C0" : "#F0D9B4",
      }}
    >
      {temErro ? <ShieldAlert size={10} /> : <AlertTriangle size={10} />}
      {problemas.length}
    </span>
  );
}

/**
 * Uma saída = uma linha com porta própria.
 *
 * O texto grande é a CONDIÇÃO (`quando`) — não o nome interno. O nome vira legenda
 * miúda ao lado, porque ele ainda importa (é a palavra que o agente declara), mas não
 * é o que responde a pergunta que a pessoa faz ao olhar o desenho: "e por aqui, quando
 * é que vai?".
 */
function LinhaSaida({
  no,
  sa,
  d,
  ultima,
}: {
  no: NoCadeia;
  sa: SaidaCadeia;
  d: DadosNoEstudio;
  ultima: boolean;
}) {
  const pp = papel(sa);
  const cor = corDaSaida(sa);
  const problemas = (d.problemas ?? []).filter((p) => p.saidaId === sa.id);
  const temErro = problemas.some((p) => p.nivel === "erro");
  const selecionada = d.saidaSelecionada === sa.id;
  const volta = d.ehVolta?.(sa.destino) ?? false;
  const destino = d.nomeDe?.(sa.destino) ?? sa.destino;

  // O texto da linha. Só é VERMELHO quando a condição é de fato obrigatória: o motor
  // a exige quando o passo bifurca (2+ condicionais). Com um caminho só, ele é sempre
  // tomado — e dizer "falta a condição" ali seria cobrar o que ninguém deve.
  const condicionais = (no.saidas ?? []).filter((s) => papel(s) === "condicional");
  const obrigatoria =
    pp === "condicional" &&
    (no.tipo === "agente" || no.tipo === "roteador") &&
    condicionais.length >= 2;
  const escrita = (sa.quando ?? "").trim();
  const condicao =
    pp === "erro"
      ? "quando este passo falhar"
      : pp === "senao"
        ? "quando nenhuma das de cima valer"
        : no.tipo === "gatilho"
          ? "o fluxo começa por aqui"
          : escrita || (obrigatoria ? "" : "assim que este passo terminar");

  return (
    <div
      className="nodrag relative cursor-pointer px-2.5 py-[7px] transition-colors"
      style={{
        borderTop: "1px solid #F0EEF7",
        borderBottomLeftRadius: ultima ? 11 : 0,
        borderBottomRightRadius: ultima ? 11 : 0,
        background: selecionada ? "#F4F1FE" : temErro ? "#FEF7F7" : "transparent",
      }}
      onClick={(e) => {
        e.stopPropagation();
        if (sa.id) d.onSelecionarSaida?.(no.id, sa.id);
      }}
      title={problemas.length ? problemas.map((p) => `• ${p.titulo}`).join("\n") : undefined}
    >
      <div className="flex items-start gap-1.5">
        <span
          className="mt-[5px] size-[7px] flex-none rounded-full"
          style={{ background: cor.dot }}
        />
        <div className="min-w-0 flex-1">
          <div
            className="truncate text-[12px] leading-[1.35]"
            style={{
              color: !condicao ? "#B42318" : escrita || pp !== "condicional" ? "#1A1730" : "#8B88A0",
              fontWeight: escrita ? 500 : 400,
              fontStyle: escrita || pp !== "condicional" ? "normal" : "italic",
            }}
          >
            {condicao || "falta dizer quando seguir por aqui"}
          </div>
          <div
            className="mt-px flex items-center gap-1 truncate text-[10.5px]"
            style={{ color: "#8B88A0" }}
          >
            {volta ? (
              <CornerDownLeft size={10} className="flex-none" />
            ) : (
              <span className="flex-none">→</span>
            )}
            <span className="truncate">{destino}</span>
            {sa.regra?.campo && (
              <span
                className="flex-none rounded px-1 text-[9.5px] font-medium"
                style={{ color: "#3D2A99", background: "#EFEAFF" }}
                title={`O motor confere “${sa.regra.campo}” — não a IA.`}
              >
                regra
              </span>
            )}
          </div>
        </div>
        <span
          className="mt-[3px] flex-none truncate text-[10px]"
          style={{ color: "#B6B3C7", maxWidth: 76 }}
          title={`Nome do caminho (é esta palavra que o agente declara): ${sa.rotulo}`}
        >
          {sa.rotulo}
        </span>
      </div>
      {/* A porta fica na borda do cartão, na altura DESTA linha. */}
      {sa.id && (
        <Handle
          type="source"
          position={Position.Right}
          id={sa.id}
          title={sa.rotulo}
          style={{
            // `right: 0` + o `translate(50%)` do React Flow = a porta fica exatamente
            // em cima da borda do cartão, na altura desta linha.
            right: 0,
            top: "50%",
            width: 11,
            height: 11,
            background: "#fff",
            border: `2px solid ${cor.dot}`,
          }}
        />
      )}
    </div>
  );
}

function HandleEntrada() {
  return (
    <Handle
      type="target"
      position={Position.Left}
      style={{
        left: 0,
        // A entrada fica na altura do CABEÇALHO, não no meio do cartão: com as saídas
        // listadas embaixo, o meio cairia no meio da lista e o fio entraria torto.
        top: 28,
        width: 11,
        height: 11,
        background: "#fff",
        border: "2px solid #C3BFD6",
      }}
    />
  );
}

/** A casca comum: borda, seleção, selo de problema e a lista de saídas. */
function Cartao({
  d,
  selected,
  fundo = "#fff",
  borda = "#E8E6F0",
  comEntrada = true,
  comSaidas = true,
  children,
}: {
  d: DadosNoEstudio;
  selected?: boolean;
  fundo?: string;
  borda?: string;
  comEntrada?: boolean;
  comSaidas?: boolean;
  children: React.ReactNode;
}) {
  const saidas = d.no.saidas ?? [];
  const temErro = (d.problemas ?? []).some((p) => p.nivel === "erro");
  const temAviso = (d.problemas ?? []).length > 0;
  const corBorda = selected
    ? "#6D4AFF"
    : temErro
      ? "#E5484D"
      : temAviso
        ? "#E3BB7C"
        : borda;
  return (
    <div
      style={{
        width: LARGURA_NO,
        background: fundo,
        border: `1px solid ${corBorda}`,
        borderRadius: 12,
        boxShadow: selected
          ? "0 0 0 3px rgba(109,74,255,.14)"
          : temErro
            ? "0 0 0 3px rgba(229,72,77,.10)"
            : "0 1px 2px rgba(26,23,48,.05)",
        transition: "box-shadow .12s, border-color .12s",
      }}
    >
      {children}
      {comSaidas && saidas.length > 0 && (
        <div>
          {saidas.map((sa, i) => (
            <LinhaSaida
              key={sa.id ?? i}
              no={d.no}
              sa={sa}
              d={d}
              ultima={i === saidas.length - 1}
            />
          ))}
        </div>
      )}
      {comEntrada && <HandleEntrada />}
    </div>
  );
}

/** Cabeçalho padrão: ícone quadrado + categoria + nome, e o selo de problema. */
function Cabeca({
  d,
  Icone,
  categoria,
  titulo,
  corIcone = "#6D4AFF",
  fundoIcone = "#EFEAFF",
  tituloVermelho = false,
  extra,
}: {
  d: DadosNoEstudio;
  Icone: typeof Layers;
  categoria: string;
  titulo: string;
  corIcone?: string;
  fundoIcone?: string;
  tituloVermelho?: boolean;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5">
      <span
        className="grid size-8 flex-none place-items-center rounded-[9px]"
        style={{ background: fundoIcone }}
      >
        <Icone size={17} color={corIcone} />
      </span>
      <div className="min-w-0 flex-1">
        <div
          className="text-[10.5px] font-medium uppercase tracking-wide"
          style={{ color: "#A09DB8" }}
        >
          {categoria}
        </div>
        <div
          className="truncate text-[14px] font-medium"
          style={{ color: tituloVermelho ? "#B42318" : "#1A1730" }}
        >
          {titulo}
        </div>
      </div>
      {extra}
      {selo(d.problemas)}
    </div>
  );
}

export function GatilhoNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  const tipo = d.no.gatilho;
  const rotulo =
    tipo === "agendamento"
      ? "Agendamento"
      : tipo === "webhook"
        ? "Webhook"
        : tipo === "comentario_instagram"
          ? "Comentário do Instagram"
          : "Manual";
  return (
    <Cartao d={d} selected={selected} comEntrada={false}>
      <Cabeca
        d={d}
        Icone={Zap}
        categoria="Começa por"
        titulo={rotulo}
        corIcone="#fff"
        fundoIcone="#6D4AFF"
      />
    </Cartao>
  );
}

export function FimNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  return (
    <Cartao d={d} selected={selected} fundo="#F4FAF6" borda="#CDE9D5" comSaidas={false}>
      <div className="flex items-center gap-2.5 px-3 py-3">
        <CheckCircle2 size={20} color="#3DAA5C" />
        <div className="text-[14px] font-medium" style={{ color: "#2F7D45" }}>
          Fim · entrega o resultado
        </div>
      </div>
    </Cartao>
  );
}

export function RoteadorNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  return (
    <Cartao d={d} selected={selected} fundo="#FBFAFF" borda="#E0DAF6">
      <Cabeca d={d} Icone={Layers} categoria="Decisão" titulo={d.no.nome || "Decisão"} />
    </Cartao>
  );
}

export function CadaNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  const lista = (d.no.lista ?? "").trim();
  return (
    <Cartao d={d} selected={selected} fundo="#FBFAFF" borda="#E0DAF6">
      <Cabeca
        d={d}
        Icone={Repeat2}
        categoria="Para cada item"
        titulo={lista ? `de ${lista}` : "escolha a lista"}
        tituloVermelho={!lista}
      />
    </Cartao>
  );
}

export function EsperarNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  const quanto = Number(d.no.espera?.quanto ?? 0);
  const unidade = d.no.espera?.unidade ?? "minutos";
  return (
    <Cartao d={d} selected={selected} fundo="#FBFAFF" borda="#E0DAF6">
      <Cabeca
        d={d}
        Icone={Hourglass}
        categoria="Esperar"
        titulo={quanto > 0 ? `${quanto} ${unidade}` : "defina o tempo"}
        tituloVermelho={!(quanto > 0)}
      />
    </Cartao>
  );
}

export function ChamarNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  const alvoId = d.no.chamar?.automacao_id ?? "";
  const alvo = (d.automacoes ?? []).find((a) => a.id === alvoId);
  const titulo = alvo?.nome ?? (alvoId ? "automação não encontrada" : "escolha a automação");
  return (
    <Cartao d={d} selected={selected} fundo="#FBFAFF" borda="#E0DAF6">
      <Cabeca
        d={d}
        Icone={ArrowRightLeft}
        categoria="Chamar automação"
        titulo={titulo}
        tituloVermelho={!alvo}
      />
    </Cartao>
  );
}

export function AgenteNode({ data, selected }: NodeProps) {
  const d = data as DadosNoEstudio;
  const ag = d.agente;
  const modelo = (ag?.modelo_ia ?? "").replace("claude-", "");
  // O CINTO INTEIRO no cartão. Antes o excedente virava "+3 mais…", e esconder
  // instrumento no cartão é esconder o que o agente sabe fazer — justamente o que se
  // vem ver aqui. Cartão mais alto é o preço, e é barato.
  const cinto = d.cinto ?? [];
  const esperaPessoa = cinto.some((i) => i.tipo === "pedir_aprovacao");

  return (
    <Cartao d={d} selected={selected}>
      <div className="relative">
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
        <div className="flex flex-col gap-1.5 px-3 py-2.5">
          <div className="flex items-center gap-2.5">
            <RobotFace size={28} indice={d.indice ?? 0} lider={ag?.papel === "lider"} />
            <span
              className="min-w-0 flex-1 truncate text-[14px] font-medium"
              style={{ color: "#1A1730" }}
            >
              {ag?.nome ?? "Agente sem dono"}
            </span>
            {d.no.inicial && (
              <span
                className="flex-none rounded-full px-1.5 py-px text-[10px] font-medium"
                style={{ color: "#3D2A99", background: "#EFEAFF" }}
              >
                início
              </span>
            )}
            {selo(d.problemas)}
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
            {esperaPessoa && (
              <span
                className="inline-flex items-center gap-1 rounded-full border px-1.5 py-px text-[10.5px] font-medium"
                style={{ color: "#A9681A", background: "#FDF1E3", borderColor: "#F0D9B4" }}
                title="Este passo PARA e pergunta a uma pessoa — porque tem o instrumento de pedir aprovação no cinto."
              >
                <Shield size={10} /> para e pergunta
              </span>
            )}
          </div>
          {cinto.length > 0 && (
            <div className="mt-0.5 flex flex-col gap-1">
              {cinto.map((inst) => (
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
                  <span className="truncate text-[11px] text-[#4A4860]">{inst.nome}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </Cartao>
  );
}

export const tiposDeNoEstudio = {
  gatilho: GatilhoNode,
  agente: AgenteNode,
  roteador: RoteadorNode,
  cada: CadaNode,
  esperar: EsperarNode,
  chamar: ChamarNode,
  fim: FimNode,
};
