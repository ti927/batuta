"use client";

import { useState } from "react";
import { CalendarClock, Pencil, Play, X } from "lucide-react";

import { api, mensagemDeErro } from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * O diálogo dos agendamentos: corrigir um que ainda vai disparar, ou resgatar um que
 * não disparou (rodando agora ou remarcando).
 *
 * Os três gestos são o mesmo formulário — o texto de entrada e, quando faz sentido, o
 * horário —, por isso um componente só. Quem cria estes agendamentos é um AGENTE, e o
 * texto que ele monta é a entrada do fluxo futuro: é justamente aqui que se percebe
 * que ele errou, e por isso o texto é editável também na hora do resgate.
 *
 * Todo horário é o de Brasília, como no resto da tela: o campo é preenchido e lido em
 * BRT e enviado sem fuso, que é como o cérebro (e o instrumento "Agendar automação")
 * já interpreta — uma regra só nas duas pontas.
 */

export type ModoAgendamento = "editar" | "disparar" | "reagendar";

/**
 * O texto que o agente montou, na linha do agendamento.
 *
 * Ficava só no banco: a lista mostrava a hora e nada do conteúdo, então um texto
 * inicial errado só se revelava depois, na execução já rodada. Mostrá-lo é o que
 * permite corrigir ANTES — e é a razão de a edição existir.
 */
export function TextoDoAgente({ entrada }: { entrada: string | null }) {
  if (!entrada?.trim()) {
    return (
      <span className="mt-1 block text-xs italic text-muted-foreground">
        sem texto inicial
      </span>
    );
  }
  return (
    <span
      className="mt-1 block truncate text-xs text-muted-foreground"
      title={entrada}
    >
      “{entrada}”
    </span>
  );
}

const FUSO = "America/Sao_Paulo";

/** ISO (UTC) → "AAAA-MM-DDTHH:mm" no horário de Brasília, que é o que o input pede. */
function paraCampo(iso: string): string {
  // "sv-SE" formata como "AAAA-MM-DD HH:mm" — o formato ISO sem o T, então basta trocar.
  const s = new Intl.DateTimeFormat("sv-SE", {
    timeZone: FUSO,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
  return s.replace(" ", "T");
}

/** Agora + uma folga, em BRT — o piso do campo (o cérebro exige futuro). */
function agoraNoCampo(minutos = 5): string {
  return paraCampo(new Date(Date.now() + minutos * 60_000).toISOString());
}

const TITULOS: Record<ModoAgendamento, string> = {
  editar: "Editar agendamento",
  disparar: "Disparar agora",
  reagendar: "Reagendar",
};

const ACOES: Record<ModoAgendamento, string> = {
  editar: "Salvar",
  disparar: "Disparar",
  reagendar: "Reagendar",
};

export function DialogoAgendamento({
  modo,
  agendamentoId,
  automacaoNome,
  entradaInicial,
  quandoInicial,
  automacaoAtiva,
  onFechar,
  onPronto,
}: {
  modo: ModoAgendamento;
  agendamentoId: string;
  automacaoNome?: string;
  entradaInicial: string | null;
  /** ISO do horário atual — só no modo "editar" (nos outros começa vazio/futuro). */
  quandoInicial?: string;
  /** Se a automação-alvo está ativa AGORA. `false` merece aviso honesto. */
  automacaoAtiva?: boolean;
  onFechar: () => void;
  /** Chamado após gravar, para a lista se atualizar. */
  onPronto: (resultado?: { modo: string; execucao_id?: string }) => void;
}) {
  const [entrada, setEntrada] = useState(entradaInicial ?? "");
  const quandoOriginal =
    modo === "editar" && quandoInicial ? paraCampo(quandoInicial) : "";
  const [quando, setQuando] = useState(quandoOriginal || agoraNoCampo(60));
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pedeHorario = modo === "editar" || modo === "reagendar";
  const Icone = modo === "disparar" ? Play : modo === "editar" ? Pencil : CalendarClock;

  async function confirmar() {
    setSalvando(true);
    setErro(null);
    try {
      if (modo === "editar") {
        await api.patch(`/agendamentos/${agendamentoId}`, {
          entrada,
          // Só manda o horário se ele MUDOU. O cérebro exige que um agendamento fique
          // no futuro; um pendente já vencido (o varredor roda a cada minuto, e pode
          // estar parado) seria recusado só por reenviar o horário que ele já tinha —
          // e aí não daria para corrigir justamente o texto de quem está para rodar.
          // Sem fuso: o cérebro lê como horário de Brasília, a mesma regra do
          // instrumento que criou este agendamento.
          ...(quando !== quandoOriginal ? { quando_executar: `${quando}:00` } : {}),
        });
        onPronto();
      } else {
        const r = await api.post<{ modo: string; execucao_id?: string }>(
          `/agendamentos/${agendamentoId}/recuperar`,
          {
            entrada,
            ...(modo === "reagendar" ? { quando_executar: `${quando}:00` } : {}),
          },
        );
        onPronto(r);
      }
      onFechar();
    } catch (e) {
      setErro(mensagemDeErro(e, "Não consegui salvar o agendamento."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={onFechar}
        aria-label="Fechar"
      />
      {/* Largo porque o "texto inicial" costuma ser o payload que o agente montou —
          às vezes um JSON de várias linhas —, e editar isso numa caixa estreita é
          sofrível. `max-h`/`overflow` em vez de altura fixa: no celular (e em tela
          baixa com o teclado aberto) o diálogo rola em vez de estourar para fora. */}
      <div className="relative max-h-[90dvh] w-full max-w-2xl overflow-y-auto rounded-xl border border-border bg-card p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-heading text-lg font-medium text-foreground">
            <Icone className="size-4" /> {TITULOS[modo]}
          </h2>
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </div>

        {automacaoNome && (
          <p className="mb-3 text-sm text-muted-foreground">{automacaoNome}</p>
        )}

        {erro && (
          <div className="mb-3">
            <Aviso>{erro}</Aviso>
          </div>
        )}

        {/* Aviso honesto: a automação desativada é o motivo mais comum de o disparo ter
            morrido. Disparar à mão funciona mesmo assim; reagendar, não — se ninguém a
            reativar, o agendamento novo morre pelo mesmo motivo. Avisar, não impedir. */}
        {automacaoAtiva === false && modo !== "editar" && (
          <div className="mb-3">
            <Aviso>
              {modo === "disparar"
                ? "Esta automação está desativada. O disparo manual roda mesmo assim — mas os próximos agendamentos dela vão continuar não disparando enquanto ela não for reativada."
                : "Esta automação está desativada. Se ela não for reativada até lá, este agendamento vai ser cancelado de novo, pelo mesmo motivo de agora."}
            </Aviso>
          </div>
        )}

        <div className="flex flex-col gap-3">
          <Label className="flex-col items-start gap-1">
            Texto inicial (o que o agente escreveu)
            {/* Alta o bastante para ler o que se está editando, e menor no celular
                para o botão Salvar não ficar fora do alcance. `resize-y` deixa
                esticar quando o texto é maior do que o previsto. */}
            <Textarea
              className="min-h-40 resize-y font-mono leading-relaxed sm:min-h-64"
              placeholder="O que esta execução deve fazer?"
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
            />
          </Label>

          {pedeHorario && (
            <Label className="flex-col items-start gap-1">
              Dispara em (horário de Brasília)
              <Input
                type="datetime-local"
                value={quando}
                min={agoraNoCampo(1)}
                onChange={(e) => setQuando(e.target.value)}
              />
            </Label>
          )}

          <Button
            className="self-start"
            onClick={confirmar}
            disabled={salvando || (pedeHorario && !quando)}
          >
            {salvando ? "Salvando…" : ACOES[modo]}
          </Button>
        </div>
      </div>
    </div>
  );
}
