"use client";

// "ESTE FLUXO" — o painel da direita quando nada está selecionado.
//
// Aqui morava o antigo botão "Fluxo", que abria um diálogo. O maestro nunca entendeu
// para que servia, e o motivo era duplo: (a) ele mostrava números que não estavam no
// dado da automação — moravam no código, atrás de uma etiqueta ("Tipo de fluxo"); e
// (b) ele mostrava as MESMAS opções que a tela do passo, sem nada dizer qual era qual.
//
// As duas coisas foram curadas antes desta tela existir: os números agora estão na
// automação (migração `prs00preset001`) e cada regra tem um dono declarado no cérebro
// (`CHAVES_DO_CANAL/AGENTE/FLUXO`). O que falta é a tela DIZER o dono — que é o que
// este painel faz, em três blocos:
//
//   1. os limites em português, sem abrir nada;
//   2. o que é do fluxo e ponto, e o que é só o PADRÃO que os agentes herdam;
//   3. para onde ir quando a regra é de outro dono (o canal, o agente).
//
// Sem botão: a coluna da direita sempre responde "o que está selecionado", e nada
// selecionado é o fluxo. A migalha no topo do painel é o que garante que isso seja
// descoberto sem depender de acertar o fundo do canvas.

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Gauge, Info, MessageSquare, User } from "lucide-react";

import {
  api,
  type Agente,
  type Cadeia,
  type ConfiguracaoFluxo,
  type Instrumento,
  type PainelConfigFluxo,
} from "@/lib/api";
import { CampoConfig } from "@/components/automacao-builder/config-fluxo";

import { CORES } from "./cores";

// Instrumentos que conversam com uma pessoa — espelha `CANAIS_TIPOS` no cérebro.
const CANAIS = ["enviar_telegram"];

function semChave(
  obj: Record<string, unknown>,
  chave: string,
): Record<string, unknown> {
  const resto = { ...obj };
  delete resto[chave];
  return resto;
}

function Secao({
  titulo,
  children,
  abertoInicial = false,
}: {
  titulo: React.ReactNode;
  children: React.ReactNode;
  abertoInicial?: boolean;
}) {
  const [aberto, setAberto] = useState(abertoInicial);
  return (
    <div className="rounded-[10px] border border-[#E8E6F0]">
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-2.5 text-left text-[12.5px] font-medium text-[#1A1730]"
      >
        {aberto ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        {titulo}
      </button>
      {aberto && <div className="flex flex-col gap-3 border-t border-[#E8E6F0] p-3">{children}</div>}
    </div>
  );
}

export function PainelDoFluxo({
  cadeia,
  agentes,
  cintos,
  valor,
  onChange,
  podeEditar,
  onEditarInstrumento,
  gatilhoTipo,
  configGatilho,
}: {
  cadeia: Cadeia;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  valor: ConfiguracaoFluxo;
  onChange: (v: ConfiguracaoFluxo) => void;
  podeEditar: boolean;
  onEditarInstrumento: (instrumentoId: string) => void;
  /** O gatilho COMO ESTÁ NA TELA (mesmo não salvo) — alguns limites moram nele. */
  gatilhoTipo: string;
  configGatilho: Record<string, unknown>;
}) {
  const [painel, setPainel] = useState<PainelConfigFluxo | null>(null);
  const [limites, setLimites] = useState<string[]>([]);

  useEffect(() => {
    api.get<PainelConfigFluxo>("/config/fluxo").then(setPainel).catch(() => {});
  }, []);

  const ajustes = valor.ajustes ?? {};
  // A redação dos limites vive no cérebro (`resumo_dos_limites`). Reescrevê-la aqui
  // faria as duas versões divergirem com o tempo — a origem clássica de bug recorrente
  // neste projeto.
  // Junto dos ajustes vai o CONTEXTO do desenho: há limites reais que não moram na
  // cascata (o teto de disparos do Instagram, o de itens do "Para cada item", o de
  // agendamentos pendentes). Sem mandá-los, o resumo mentiria por omissão.
  const serializado = JSON.stringify({
    ajustes,
    tipo_gatilho: gatilhoTipo,
    configuracao_gatilho: configGatilho,
    tem_no_cada: (cadeia.nos ?? []).some((n) => n.tipo === "cada"),
    tem_agendar_automacao: Object.values(cintos).some((c) =>
      c.some((i) => i.tipo === "agendar_automacao"),
    ),
  });
  useEffect(() => {
    let vivo = true;
    api
      .post<{ limites: string[] }>("/config/fluxo/limites", JSON.parse(serializado))
      .then((r) => vivo && setLimites(r.limites))
      .catch(() => vivo && setLimites([]));
    return () => {
      vivo = false;
    };
  }, [serializado]);

  // Os canais que este desenho usa, pelos cintos dos agentes que estão nele. É para
  // onde a pessoa vai quando procurar saudação/horário aqui e não achar.
  const canais: Instrumento[] = [];
  for (const no of cadeia.nos ?? []) {
    for (const i of cintos[no.ref ?? ""] ?? []) {
      if (CANAIS.includes(i.tipo) && !canais.some((c) => c.id === i.id)) canais.push(i);
    }
  }

  // Agentes DESTE desenho que já sobrepõem alguma regra — para o padrão abaixo não
  // parecer valer para todos quando não vale.
  const comRitmoProprio = agentes.filter(
    (a) =>
      (cadeia.nos ?? []).some((n) => n.ref === a.id) &&
      Object.keys(a.configuracao ?? {}).length > 0,
  );

  function campos(nivel: "fluxo" | "agente") {
    return (painel?.grupos ?? []).filter((g) => g.nivel === nivel);
  }

  function renderarGrupo(g: { grupo: string; campos: PainelConfigFluxo["grupos"][number]["campos"] }) {
    return (
      <div key={g.grupo} className="flex flex-col gap-2.5">
        <div className="text-[10.5px] font-semibold uppercase tracking-wide text-[#A09DB8]">
          {g.grupo}
        </div>
        {g.campos.map((campo) => {
          const ajustado = campo.chave in ajustes;
          return (
            <CampoConfig
              key={campo.chave}
              campo={campo}
              valor={ajustado ? ajustes[campo.chave] : painel?.padrao_global?.[campo.chave]}
              ajustado={ajustado}
              podeEditar={podeEditar}
              onChange={(v) => onChange({ ...valor, ajustes: { ...ajustes, [campo.chave]: v } })}
              onReset={() => onChange({ ...valor, ajustes: semChave(ajustes, campo.chave) })}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3.5 p-3.5">
      {/* 1. Os limites, sem abrir nada. Lei do maestro: nenhum teto existe sem a
          pessoa saber que existe. */}
      <div className="flex flex-col gap-2 rounded-[10px] border border-[#E8E6F0] bg-[#FAFAF7] p-3">
        <div className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-[#A09DB8]">
          <Gauge size={12} /> Limites deste fluxo
        </div>
        {limites.length ? (
          <ul className="flex list-disc flex-col gap-1 pl-4 text-[12px] leading-snug text-[#4A4860]">
            {limites.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-[#6B6880]">Carregando…</p>
        )}
      </div>

      {/* 2. O que é do fluxo, e o que é só o padrão herdado. Separados porque a
          confusão entre os dois foi o que originou esta arrumação. */}
      {painel && (
        <>
          <Secao titulo="Tetos deste fluxo" abertoInicial={false}>
            <p className="text-[11px] leading-snug text-[#6B6880]">
              Valem para a automação inteira.
            </p>
            {campos("fluxo").map(renderarGrupo)}
          </Secao>

          <Secao titulo="Padrão que os agentes herdam" abertoInicial={false}>
            <p className="text-[11px] leading-snug text-[#6B6880]">
              Cada agente pode usar um valor diferente, na aba{" "}
              <strong>Ritmo e espera</strong> dele.
            </p>
            {comRitmoProprio.length > 0 && (
              <p className="flex gap-1.5 rounded-md border border-[#E8E6F0] bg-[#FAFAF7] p-2 text-[11px] leading-snug text-[#6B6880]">
                <User size={12} className="mt-0.5 shrink-0" />
                <span>
                  Usam valores próprios:{" "}
                  <strong>{comRitmoProprio.map((a) => a.nome).join(", ")}</strong>.
                </span>
              </p>
            )}
            {campos("agente").map(renderarGrupo)}
          </Secao>
        </>
      )}

      {/* 3. O que NÃO é daqui — a metade "e a tela diz quem é" do princípio. Sem esta
          linha, tirar o atendimento do fluxo só esconderia a configuração. */}
      <div className="flex flex-col gap-2 rounded-[10px] border border-[#E8E6F0] p-3">
        <div className="flex gap-1.5 text-[11.5px] leading-snug text-[#6B6880]">
          <Info size={13} className="mt-0.5 shrink-0" />
          <span>
            Saudação, horário de atendimento e mensagens automáticas ficam no{" "}
            <strong className="text-[#1A1730]">bot</strong>, não aqui.
          </span>
        </div>
        {canais.length > 0 &&
          canais.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onEditarInstrumento(c.id)}
              className="inline-flex items-center gap-1.5 self-start rounded-md border border-[#E8E6F0] px-2 py-1 text-[11.5px] text-[#6D4AFF] hover:bg-[#F4F1FE]"
            >
              <MessageSquare size={12} /> abrir {c.nome}
            </button>
          ))}
      </div>

      <ComoLerODesenho />
    </div>
  );
}

export function ComoLerODesenho() {
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
      texto:
        "só é percorrido se o passo der erro — o erro segue por aqui em vez de derrubar tudo.",
    },
  ];
  return (
    <Secao titulo="Como ler este desenho">
      <p className="text-[11.5px] leading-snug text-[#6B6880]">
        Cada cartão é um passo. As linhas dentro do cartão são os caminhos que saem
        dele, e a cor diz o papel de cada um.
      </p>
      <div className="flex flex-col gap-2">
        {linhas.map((l) => (
          <div key={l.titulo} className="flex items-start gap-2">
            <span
              className="mt-1.5 h-0 w-5 shrink-0 border-t-2"
              style={{
                borderColor: l.cor,
                borderStyle: l.tracejado ? "dashed" : "solid",
              }}
            />
            <span className="text-[11.5px] leading-snug text-[#6B6880]">
              <strong className="text-[#1A1730]">{l.titulo}</strong> — {l.texto}
            </span>
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
    </Secao>
  );
}
