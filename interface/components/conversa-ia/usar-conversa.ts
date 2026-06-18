"use client";

import { useEffect, useRef, useState } from "react";

import {
  api,
  ErroDaApi,
  type MemoriaProjeto,
  type MensagemConversa,
  type RespostaTurno,
  type SnapshotTime,
} from "@/lib/api";

/** Traduz a "parede de ativação" (erro 422 com {problemas:[...]}) em texto humano. */
export function traduzirErroParede(e: unknown): string {
  if (e instanceof ErroDaApi) {
    try {
      const corpo = JSON.parse(e.message);
      if (Array.isArray(corpo?.problemas)) {
        return "Não dá para ativar ainda: " + corpo.problemas.join(" ");
      }
    } catch {
      // mensagem não era JSON
    }
    return e.message;
  }
  return "Falha ao ativar o time.";
}

/**
 * Centraliza a conversa com a IA criadora/companheira: o estado (mensagens, snapshot
 * do time, memória) e as ações (enviar turno, ativar/desativar). É a MESMA mecânica
 * usada na tela de criação (`/criar/[id]`) e no painel do time (`/times/[id]`).
 *
 * - `aoCriarTime(id)`: chamado quando um turno cria o time (antes não havia `time`) —
 *   o /criar usa para levar o usuário à tela do time.
 * - `aoMudar()`: chamado depois de cada turno/ativação que alterou o time — o painel
 *   do time usa para `router.refresh()` e atualizar o dashboard ao vivo.
 */
export function useConversaCriacao({
  conversaId,
  mensagensIniciais,
  timeInicial,
  memoriaInicial,
  podeConversar,
  primeiraMensagem,
  aoCriarTime,
  aoMudar,
}: {
  conversaId: string;
  mensagensIniciais: MensagemConversa[];
  timeInicial: SnapshotTime | null;
  memoriaInicial: MemoriaProjeto[];
  podeConversar: boolean;
  primeiraMensagem?: string;
  aoCriarTime?: (timeId: string) => void;
  aoMudar?: () => void;
}) {
  const [mensagens, setMensagens] = useState<MensagemConversa[]>(mensagensIniciais);
  const [time, setTime] = useState<SnapshotTime | null>(timeInicial);
  const [memoria, setMemoria] = useState<MemoriaProjeto[]>(memoriaInicial);
  const [enviando, setEnviando] = useState(false);
  const [ativando, setAtivando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const temTime = time != null;

  async function enviar(conteudo: string) {
    const limpo = conteudo.trim();
    if (!limpo || enviando || !podeConversar) return;
    setErro(null);
    setMensagens((m) => [...m, { papel: "usuario", conteudo: limpo }]);
    setEnviando(true);
    const tinhaTime = time != null;
    try {
      const r = await api.post<RespostaTurno>(
        `/conversas-criacao/${conversaId}/mensagens`,
        { mensagem: limpo },
      );
      setMensagens((m) => [...m, { papel: "ia", conteudo: r.resposta, chips: r.chips }]);
      setTime(r.time);
      setMemoria(r.memoria ?? []);
      if (!tinhaTime && r.time_id) aoCriarTime?.(r.time_id);
      aoMudar?.();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao enviar a mensagem.");
    } finally {
      setEnviando(false);
    }
  }

  /** Liga/desliga o time. Devolve o novo estado (para o chamador dar o toast) ou
   *  `undefined` se falhou/sem automação. */
  async function alternarAtivacao(): Promise<boolean | undefined> {
    const automacao = time?.automacao;
    if (!automacao || ativando || !podeConversar) return;
    const ativo = automacao.ativa;
    setAtivando(true);
    setErro(null);
    try {
      await api.put(`/automacoes/${automacao.id}`, {
        nome: automacao.nome,
        tipo_gatilho: automacao.tipo_gatilho,
        configuracao_gatilho: automacao.configuracao_gatilho ?? {},
        cadeia: automacao.cadeia,
        ativa: !ativo,
      });
      setTime((t) =>
        t && t.automacao ? { ...t, automacao: { ...t.automacao, ativa: !ativo } } : t,
      );
      aoMudar?.();
      return !ativo;
    } catch (e) {
      setErro(traduzirErroParede(e));
      return undefined;
    } finally {
      setAtivando(false);
    }
  }

  // Primeira mensagem (vinda da tela de início via ?primeira=): enviada uma vez, já
  // dentro do chat, para a abertura ser instantânea mesmo com o Opus lento.
  const primeiraEnviada = useRef(false);
  useEffect(() => {
    if (
      primeiraMensagem &&
      !primeiraEnviada.current &&
      mensagensIniciais.length === 0 &&
      podeConversar
    ) {
      primeiraEnviada.current = true;
      void enviar(primeiraMensagem);
    }
    // só na montagem
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    mensagens,
    time,
    memoria,
    enviando,
    ativando,
    erro,
    temTime,
    enviar,
    alternarAtivacao,
  };
}
