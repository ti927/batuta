"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, FlaskConical, Loader2, XCircle } from "lucide-react";

import {
  api,
  mensagemDeErro,
  type ExecucaoComPassos,
  type Instrumento,
} from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const ESTADOS_FINAIS = ["concluida", "falhou", "cancelada"];

/**
 * "Testar este passo" (Onda 4, fatia 5).
 *
 * Roda UM passo com um texto escrito à mão, sem seguir as setas — para ajustar um
 * agente sem pagar os passos anteriores a cada tentativa.
 *
 * O resultado aparece AQUI, no próprio construtor (decisão do maestro): sair para a
 * tela de execução a cada teste quebraria o ciclo ajustar-testar-ajustar, que é a
 * razão de a fatia existir.
 *
 * O teste usa os instrumentos REAIS do agente. Por isso a confirmação nomeia os
 * irreversíveis antes de rodar: um "modo de mentira" enganaria justamente sobre o que
 * o teste deveria provar.
 */
export function TestarEstePasso({
  automacaoId,
  timeId,
  noId,
  cinto,
  podeEditar,
  naoSalvo,
}: {
  automacaoId: string | null;
  timeId: string;
  noId: string;
  cinto: Instrumento[];
  podeEditar: boolean;
  naoSalvo: boolean;
}) {
  const [entrada, setEntrada] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [execucao, setExecucao] = useState<ExecucaoComPassos | null>(null);
  const [disparando, setDisparando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Trocar de passo REMONTA este componente (o pai passa `key={no.id}`): o resultado
  // do passo anterior some junto, e o polling é cancelado pela limpeza abaixo. Resetar
  // por efeito faria render em cascata — remontar é o jeito idiomático.
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  function acompanhar(id: string) {
    timer.current = setTimeout(async () => {
      try {
        const r = await api.get<ExecucaoComPassos>(`/execucoes/${id}`);
        setExecucao(r);
        if (ESTADOS_FINAIS.includes(r.estado)) return;
      } catch {
        // erro transitório de rede: tenta de novo no próximo ciclo em vez de
        // desistir — o passo pode estar num instrumento lento.
      }
      acompanhar(id);
    }, 1500);
  }

  async function testar() {
    if (!automacaoId) return;
    setDisparando(true);
    setErro(null);
    setExecucao(null);
    try {
      const r = await api.post<ExecucaoComPassos>(
        `/automacoes/${automacaoId}/testar-no`,
        { no_id: noId, entrada },
      );
      setExecucao(r);
      setConfirmando(false);
      if (!ESTADOS_FINAIS.includes(r.estado)) acompanhar(r.id);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não consegui iniciar o teste"));
    } finally {
      setDisparando(false);
    }
  }

  if (!podeEditar || !automacaoId) return null;

  const irreversiveis = cinto.filter((i) => i.acao_irreversivel);
  const rodando = !!execucao && !ESTADOS_FINAIS.includes(execucao.estado);
  const passo = execucao?.passos?.[0];

  return (
    <div className="mt-4 border-t border-[#E8E6F0] pt-4">
      <div className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-[#1A1730]">
        <FlaskConical className="size-4" />
        Testar este passo
      </div>
      <p className="mb-2 text-[12.5px] leading-relaxed text-[#6B6880]">
        Roda <strong>só este passo</strong>, com o texto que você escrever abaixo — sem
        rodar o resto do fluxo.
      </p>

      <Textarea
        value={entrada}
        onChange={(e) => setEntrada(e.target.value)}
        placeholder="O que este passo receberia do passo anterior…"
        rows={3}
        disabled={rodando || disparando}
        className="text-[13px]"
      />

      {/* O teste roda o fluxo SALVO. Testar com edição pendente e não entender o
          resultado — porque a sua mudança não estava lá — é o erro mais confuso
          possível, então o botão espera o salvamento. */}
      {naoSalvo ? (
        <Aviso variant="atencao" className="mt-2 text-[12.5px]">
          Salve o fluxo antes de testar — o teste roda o que está salvo, não o que está
          na tela.
        </Aviso>
      ) : !confirmando ? (
        <Button
          variant="outline"
          size="sm"
          className="mt-2"
          disabled={rodando || disparando}
          onClick={() => setConfirmando(true)}
        >
          {rodando ? <Loader2 className="size-3.5 animate-spin" /> : <FlaskConical />}
          {rodando ? "Rodando…" : "Testar este passo"}
        </Button>
      ) : (
        <div className="mt-2 rounded-lg border border-border bg-background p-3">
          <p className="text-[13px] text-foreground">
            Isto roda o passo <strong>de verdade</strong>: o agente usa os instrumentos
            reais dele, e o que ele fizer acontece mesmo.
          </p>
          {irreversiveis.length > 0 && (
            <Aviso variant="atencao" className="mt-2 text-[12.5px]">
              {irreversiveis.length === 1 ? "O instrumento " : "Os instrumentos "}
              <strong>{irreversiveis.map((i) => i.nome).join(", ")}</strong>{" "}
              {irreversiveis.length === 1 ? "faz" : "fazem"} algo que não dá para
              desfazer (publicar, enviar, lançar). Testar aqui pode fazer isso de
              verdade.
            </Aviso>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" disabled={disparando} onClick={testar}>
              {disparando ? "Iniciando…" : "Rodar mesmo assim"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={disparando}
              onClick={() => setConfirmando(false)}
            >
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {erro && (
        <Aviso className="mt-2 text-[12.5px]">{erro}</Aviso>
      )}

      {/* Sinal de vida enquanto roda (§12-A): o passo pode chamar um instrumento lento
          (gerar imagem, publicar), e silêncio pareceria travamento. */}
      {rodando && (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-border bg-secondary/40 p-3 text-[12.5px] text-muted-foreground">
          <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin" />
          <span>{execucao?.atividade || "Rodando o passo…"}</span>
        </div>
      )}

      {execucao && !rodando && (
        <div className="mt-2 rounded-lg border border-border bg-background p-3">
          <div className="flex items-center gap-1.5 text-[13px] font-medium">
            {execucao.estado === "concluida" ? (
              <>
                <CheckCircle2 className="size-4 text-success" />
                <span className="text-foreground">Teste concluído</span>
              </>
            ) : (
              <>
                <XCircle className="size-4 text-destructive" />
                <span className="text-foreground">O teste falhou</span>
              </>
            )}
          </div>

          {passo?.saida?.texto ? (
            <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-[12.5px] leading-relaxed text-muted-foreground">
              {passo.saida.texto}
            </p>
          ) : null}

          {execucao.estado !== "concluida" && (
            <Aviso className="mt-2 text-[12.5px]">
              {String(execucao.resultado?.erro || "O passo não chegou ao fim.")}
            </Aviso>
          )}

          {/* Os instrumentos que ele REALMENTE acionou: é a prova do que aconteceu no
              mundo, e o texto do agente não serve como prova disso. */}
          {(passo?.saida?.instrumentos_acionados?.length ?? 0) > 0 && (
            <p className="mt-2 text-[12px] text-muted-foreground">
              Acionou:{" "}
              <strong>{passo!.saida!.instrumentos_acionados!.join(", ")}</strong>
            </p>
          )}

          {execucao.resultado?.avisos?.map((a) => (
            <Aviso key={a} variant="atencao" className="mt-2 text-[12.5px]">
              {a}
            </Aviso>
          ))}

          {/* O detalhe completo (ficha, uso, tempos) fica na inspeção — quem quiser
              cavar vai lá, sem perder o lugar no desenho de quem não quer. */}
          <Link
            href={`/times/${timeId}/execucoes/${execucao.id}`}
            className="mt-2 inline-block text-[12px] text-primary underline underline-offset-2 hover:no-underline"
          >
            Ver o passo a passo
          </Link>
        </div>
      )}
    </div>
  );
}
