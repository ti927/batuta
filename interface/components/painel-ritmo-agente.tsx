"use client";

// A aba "Ritmo e espera" do popup do agente: quanto ESTE trabalhador pode trabalhar
// num passo, e quanto/como ele espera uma pessoa.
//
// Por que isto é do agente e não do desenho
// -----------------------------------------
// Até 2026-09-22 estas regras moravam no NÓ da automação, e a decisão ficava partida
// ao meio: QUEM é perguntado numa aprovação já era do agente (o instrumento
// "Pedir aprovação e aguardar", no cinto dele), mas QUANTO TEMPO se espera era do nó.
// Duas metades da mesma decisão, em duas telas — e a tela do nó mostrava as MESMAS
// opções da tela do fluxo, sem nada dizer qual era qual.
//
// A regra que ficou: a configuração pertence ao nível em que a coisa medida EXISTE.
// Contador que acumula (mensagens e custo de uma conversa) só pode ter um teto, e é do
// fluxo. Propriedade de UM ATO — esta espera, este trabalho — varia legitimamente de
// passo para passo, e é do agente. Um fluxo com duas aprovações (uma confirmação
// rápida com quem pediu, e um diretor financeiro que viaja) precisa das duas réguas.
//
// O que a tela PRECISA dizer, e diz
// ---------------------------------
// O agente pode estar em vários fluxos. Mudar aqui muda em todos eles. Omitir isso
// recriaria a sobreposição silenciosa que esta arrumação veio curar — então os fluxos
// afetados aparecem pelo nome.

import { useEffect, useState } from "react";
import { Clock, Info, TriangleAlert } from "lucide-react";

import {
  api,
  type Agente,
  type CampoConfigFluxo,
  type Instrumento,
  type PainelConfigFluxo,
  type Time,
} from "@/lib/api";
import { CampoConfig } from "@/components/automacao-builder/config-fluxo";

// O agente só "espera uma pessoa" se tiver como perguntar a alguém. Mesma expressão
// usada no Estúdio (`estudio/problemas.ts`, `estudio/nos.tsx`) — uma regra, um lugar.
const TIPO_APROVACAO = "pedir_aprovacao";

function semChave(
  obj: Record<string, unknown>,
  chave: string,
): Record<string, unknown> {
  const resto = { ...obj };
  delete resto[chave];
  return resto;
}

export function PainelRitmoAgente({
  agente,
  time,
  cinto,
  valor,
  onChange,
  podeEditar,
}: {
  /** Nulo enquanto o agente está sendo criado (aí não há cinto nem fluxos ainda). */
  agente: Agente | null;
  time: Time;
  cinto: Instrumento[];
  valor: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
  podeEditar: boolean;
}) {
  const [painel, setPainel] = useState<PainelConfigFluxo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [fluxos, setFluxos] = useState<string[]>([]);

  useEffect(() => {
    api
      .get<PainelConfigFluxo>("/config/fluxo")
      .then(setPainel)
      .catch(() =>
        setErro("Não consegui carregar as opções. Tente fechar e abrir de novo."),
      );
  }, []);

  // Em quais automações deste time este agente aparece. Falha em silêncio de
  // propósito: sem a lista o aviso fica genérico ("em todos os fluxos onde ele
  // aparece") em vez de sumir — o recado importante não depende dela.
  useEffect(() => {
    if (!agente) return;
    let vivo = true;
    api
      .get<{ id: string; nome: string; cadeia: { nos?: { ref?: string }[] } | null }[]>(
        `/times/${time.id}/automacoes`,
      )
      .then((lista) => {
        if (!vivo) return;
        setFluxos(
          lista
            .filter((a) =>
              (a.cadeia?.nos ?? []).some((n) => n.ref === agente.id),
            )
            .map((a) => a.nome),
        );
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [agente, time.id]);

  const esperaPessoa = cinto.some((i) => i.tipo === TIPO_APROVACAO);

  function grupo(nome: string): CampoConfigFluxo[] {
    return (painel?.grupos ?? [])
      .filter((g) => g.nivel === "agente" && g.grupo === nome)
      .flatMap((g) => g.campos);
  }

  function renderar(campos: CampoConfigFluxo[]) {
    return campos.map((campo) => {
      const ajustado = campo.chave in valor;
      return (
        <CampoConfig
          key={campo.chave}
          campo={campo}
          valor={
            ajustado ? valor[campo.chave] : painel?.padrao_global?.[campo.chave]
          }
          ajustado={ajustado}
          podeEditar={podeEditar}
          rotuloHerdado="herda do fluxo"
          onChange={(v) => onChange({ ...valor, [campo.chave]: v })}
          onReset={() => onChange(semChave(valor, campo.chave))}
        />
      );
    });
  }

  if (erro) {
    return <p className="text-sm text-destructive">{erro}</p>;
  }
  if (!painel) {
    return <p className="text-sm text-muted-foreground">Carregando…</p>;
  }

  const trabalho = grupo("Quanto um passo pode trabalhar");
  const espera = grupo("Enquanto espera uma pessoa");

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pr-1">
      <p className="flex gap-2 rounded-lg border border-border bg-muted/40 p-3 text-[12.5px] leading-relaxed text-muted-foreground">
        <Info className="mt-0.5 size-4 shrink-0" />
        <span>
          Ajuste só o que for diferente neste agente. O que você não mexer segue o
          valor da automação.
        </span>
      </p>

      <div className="flex flex-col gap-3 rounded-lg border border-border p-3">
        <div>
          <div className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
            <Clock className="size-3.5 text-muted-foreground" />
            Quanto ele pode trabalhar num passo
          </div>
          <p className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">
            Depois disso ele é interrompido. Quem gera vídeo precisa de bem mais que
            quem escreve um parágrafo.
          </p>
        </div>
        {renderar(trabalho)}
      </div>

      {esperaPessoa ? (
        <div className="flex flex-col gap-3 rounded-lg border border-border p-3">
          <div>
            <div className="text-[13px] font-medium text-foreground">
              Quando ele espera uma pessoa
            </div>
            <p className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">
              Quanto tempo esperar, e o que fazer se ninguém responder.
            </p>
          </div>
          {renderar(espera)}
        </div>
      ) : (
        <p className="rounded-lg border border-dashed border-border p-3 text-[12px] leading-relaxed text-muted-foreground">
          Este agente não pede confirmação a ninguém, então não há espera a
          configurar. Para ele passar a pedir, dê a ele{" "}
          <strong>Pedir aprovação e aguardar</strong> na aba Instrumentos.
        </p>
      )}

      {/* Leg 3 da arrumação: o agente é de vários fluxos. Calar isto seria recriar a
          sobreposição silenciosa que esta frente veio curar. */}
      {agente && (
        <p className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[12px] leading-relaxed text-amber-900">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span>
            {fluxos.length ? (
              <>
                Isto muda o agente em <strong>{fluxos.join(", ")}</strong>.
              </>
            ) : (
              <>Isto muda o agente em toda automação em que ele for usado.</>
            )}
          </span>
        </p>
      )}
    </div>
  );
}
