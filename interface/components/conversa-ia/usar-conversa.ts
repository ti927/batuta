"use client";

import { useEffect, useRef, useState } from "react";

import {
  api,
  ErroDaApi,
  mensagemDeErro,
  type MemoriaProjeto,
  type MensagemConversa,
  type TurnoCriacaoLer,
  type TurnoEnfileirado,
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
  }
  return mensagemDeErro(e, "Falha ao ativar o time.");
}

const INTERVALO_POLL_MS = 1500;
const esperar = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Centraliza a conversa com a IA criadora/companheira: o estado (mensagens, snapshot do
 * time, memória) e as ações (enviar turno, ativar/desativar). É a MESMA mecânica usada na
 * tela de criação (`/criar/[id]`) e no painel do time (`/times/[id]`).
 *
 * O turno roda em SEGUNDO PLANO (o cérebro só ENFILEIRA e devolve na hora): `enviar`
 * dispara o turno e depois ACOMPANHA o andamento (~1,5s), mostrando "o que a IA está
 * fazendo agora" + um cronômetro. Uma queda de rede no meio NÃO derruba a conversa — o
 * acompanhamento reconecta sozinho e o turno segue rodando no servidor; se algo falha de
 * verdade, a mensagem do usuário fica marcada e há um botão Reenviar (nada se perde).
 *
 * - `aoCriarTime(id)`: chamado quando um turno cria o time (antes não havia `time`).
 * - `aoMudar()`: chamado após cada turno/ativação que alterou o time (o painel dá refresh).
 * - `turnoInicial`: turno em voo quando a página carregou — retoma o acompanhamento.
 */
export function useConversaCriacao({
  conversaId,
  mensagensIniciais,
  timeInicial,
  memoriaInicial,
  podeConversar,
  primeiraMensagem,
  turnoInicial,
  aoCriarTime,
  aoMudar,
}: {
  conversaId: string;
  mensagensIniciais: MensagemConversa[];
  timeInicial: SnapshotTime | null;
  memoriaInicial: MemoriaProjeto[];
  podeConversar: boolean;
  primeiraMensagem?: string;
  turnoInicial?: TurnoCriacaoLer | null;
  aoCriarTime?: (timeId: string) => void;
  aoMudar?: () => void;
}) {
  // Turno que já estava em voo quando a página carregou (reload no meio de um turno):
  // seed do estado inicial, para retomar o acompanhamento sem flash nem setState no efeito.
  const turnoEmVoo =
    turnoInicial &&
    (turnoInicial.estado === "aguardando" || turnoInicial.estado === "em_andamento")
      ? turnoInicial
      : null;

  const [mensagens, setMensagens] = useState<MensagemConversa[]>(() =>
    turnoEmVoo
      ? [
          ...mensagensIniciais,
          // A pergunta ainda não está no histórico (só entra ao concluir): mostra pendente.
          { papel: "usuario", conteudo: turnoEmVoo.pergunta, estado: "pendente" },
        ]
      : mensagensIniciais,
  );
  const [time, setTime] = useState<SnapshotTime | null>(timeInicial);
  const [memoria, setMemoria] = useState<MemoriaProjeto[]>(memoriaInicial);
  const [enviando, setEnviando] = useState(() => turnoEmVoo != null);
  const [ativando, setAtivando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  // Feedback ao vivo do turno em andamento.
  const [atividadeAtual, setAtividadeAtual] = useState<string | null>(() =>
    turnoEmVoo ? (turnoEmVoo.atividade ?? "Pensando…") : null,
  );
  const [turnoIniciadoEm, setTurnoIniciadoEm] = useState<string | null>(() =>
    turnoEmVoo ? (turnoEmVoo.atividade_em ?? turnoEmVoo.criado_em) : null,
  );
  const [reconectando, setReconectando] = useState(false);

  const temTime = time != null;

  // A montagem/desmontagem guarda o polling (não mexe em estado após desmontar).
  const montadoRef = useRef(true);
  useEffect(() => {
    montadoRef.current = true;
    return () => {
      montadoRef.current = false;
    };
  }, []);
  // Texto da última fala do usuário em voo (para o Reenviar).
  const ultimoTextoRef = useRef<string | null>(null);

  function limparPendentes(m: MensagemConversa[]): MensagemConversa[] {
    return m.map((x) =>
      x.papel === "usuario" && x.estado === "pendente" ? { ...x, estado: undefined } : x,
    );
  }

  function marcarUltimaFalhou() {
    setMensagens((m) => {
      const copia = [...m];
      for (let i = copia.length - 1; i >= 0; i--) {
        if (copia[i].papel === "usuario") {
          copia[i] = { ...copia[i], estado: "falhou" };
          break;
        }
      }
      return copia;
    });
  }

  function encerrar() {
    setEnviando(false);
    setAtividadeAtual(null);
    setTurnoIniciadoEm(null);
    setReconectando(false);
  }

  /** Acompanha um turno até concluir/falhar — resiliente a quedas de rede. */
  async function acompanhar(turnoId: string, tinhaTime: boolean) {
    while (montadoRef.current) {
      let t: TurnoCriacaoLer;
      try {
        t = await api.get<TurnoCriacaoLer>(
          `/conversas-criacao/${conversaId}/turnos/${turnoId}`,
        );
        setReconectando(false);
      } catch {
        // Consulta caiu (rede/servidor reiniciando): NÃO derruba — avisa e tenta de novo.
        // O turno segue rodando no servidor (e o sweeper o encerra se travar de vez).
        setReconectando(true);
        await esperar(INTERVALO_POLL_MS);
        continue;
      }
      if (!montadoRef.current) return;
      setAtividadeAtual(t.atividade ?? null);

      if (t.estado === "concluido" && t.resultado) {
        const r = t.resultado;
        setMensagens((m) => [
          ...limparPendentes(m),
          { papel: "ia", conteudo: r.resposta, chips: r.chips },
        ]);
        setTime(r.time);
        setMemoria(r.memoria ?? []);
        ultimoTextoRef.current = null;
        if (!tinhaTime && r.time_id) aoCriarTime?.(r.time_id);
        aoMudar?.();
        encerrar();
        return;
      }
      if (t.estado === "erro") {
        marcarUltimaFalhou();
        setErro(
          t.erro_mensagem ??
            "Não consegui responder desta vez. Sua mensagem foi preservada — toque em Reenviar.",
        );
        encerrar();
        return;
      }
      await esperar(INTERVALO_POLL_MS);
    }
  }

  async function enviar(conteudo: string) {
    const limpo = conteudo.trim();
    if (!limpo || enviando || !podeConversar) return;
    setErro(null);
    ultimoTextoRef.current = limpo;
    setMensagens((m) => [...m, { papel: "usuario", conteudo: limpo, estado: "pendente" }]);
    setEnviando(true);
    setTurnoIniciadoEm(new Date().toISOString());
    setAtividadeAtual("Pensando…");
    const tinhaTime = time != null;
    let turnoId: string;
    try {
      const r = await api.post<TurnoEnfileirado>(
        `/conversas-criacao/${conversaId}/mensagens`,
        { mensagem: limpo },
      );
      turnoId = r.turno_id;
    } catch (e) {
      // Nem entrou na fila (queda de rede, ou 409 se um turno anterior ainda roda):
      // marca para reenviar, com mensagem honesta.
      marcarUltimaFalhou();
      setErro(mensagemDeErro(e));
      encerrar();
      return;
    }
    await acompanhar(turnoId, tinhaTime);
  }

  /** Reenvia a última fala do usuário que falhou (nada se perdeu). */
  function reenviar() {
    const texto = ultimoTextoRef.current;
    if (!texto || enviando) return;
    setMensagens((m) => {
      const copia = [...m];
      for (let i = copia.length - 1; i >= 0; i--) {
        if (copia[i].papel === "usuario" && copia[i].estado === "falhou") {
          copia.splice(i, 1);
          break;
        }
      }
      return copia;
    });
    setErro(null);
    void enviar(texto);
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

  // Na montagem, uma vez: (1) retoma o acompanhamento de um turno que já estava em voo
  // (reload no meio — o estado inicial já semeou a mensagem pendente); senão (2) envia a
  // primeira mensagem vinda da tela de início (?primeira=). São mutuamente exclusivos.
  const iniciouRef = useRef(false);
  useEffect(() => {
    if (iniciouRef.current) return;
    iniciouRef.current = true;
    // acompanhar/enviar são ASSÍNCRONOS: só chamam setState APÓS um await (como um
    // callback de sistema externo — a assinatura de subscription que o efeito existe para
    // fazer). Não há setState síncrono no render; o aviso do lint é falso-positivo aqui.
    if (turnoEmVoo) {
      ultimoTextoRef.current = turnoEmVoo.pergunta;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void acompanhar(turnoEmVoo.id, time != null);
      return;
    }
    if (primeiraMensagem && mensagensIniciais.length === 0 && podeConversar) {
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
    atividadeAtual,
    turnoIniciadoEm,
    reconectando,
    enviar,
    reenviar,
    alternarAtivacao,
  };
}
