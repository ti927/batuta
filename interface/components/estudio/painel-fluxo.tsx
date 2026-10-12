"use client";

// O painel da direita quando nada está selecionado.
//
// As regras da automação moraram aqui até 2026-10-12, empilhadas em duas sanfonas numa
// coluna estreita. Viraram uma janela própria, por assunto
// (`configuracoes-automacao.tsx`); daqui sobra o atalho para ela e a legenda do desenho.

import { useState } from "react";
import { ChevronDown, ChevronRight, MousePointerClick, Settings } from "lucide-react";

import { CORES } from "./cores";

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
  onAbrirConfiguracoes,
}: {
  onAbrirConfiguracoes: () => void;
}) {
  return (
    <div className="flex flex-col gap-3.5 p-3.5">
      <div className="flex flex-col items-start gap-2.5 rounded-[10px] border border-dashed border-[#E8E6F0] p-3.5">
        <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-[#1A1730]">
          <MousePointerClick size={14} className="text-[#A09DB8]" />
          Nenhum passo selecionado
        </div>
        <p className="text-[12px] leading-snug text-[#6B6880]">
          Clique num passo do desenho para editá-lo.
        </p>
      </div>

      <button
        type="button"
        onClick={onAbrirConfiguracoes}
        className="flex items-center gap-2 rounded-[10px] border border-[#E8E6F0] p-3 text-left hover:bg-[#FAFAF7]"
      >
        <Settings size={15} className="shrink-0 text-[#6D4AFF]" />
        <span className="flex flex-col">
          <span className="text-[12.5px] font-medium text-[#1A1730]">
            Configurações da automação
          </span>
          <span className="text-[11.5px] leading-snug text-[#6B6880]">
            Limites de conversa, execução, tempo e aprovação.
          </span>
        </span>
      </button>

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
