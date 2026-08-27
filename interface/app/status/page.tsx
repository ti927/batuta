"use client";

// Página de STATUS dos elos — o painel "status.claude.com" do Batuta (§12-A).
//
// Nasceu do congelamento de 2026-08-27: a rede até o banco ficou ~30 min presa e
// ninguém tinha para onde olhar — o app respondia, o bot ficava mudo. Aqui cada
// ligação da corrente (banco, memória, provedores de IA, canais, borda, MCP,
// motores internos) aparece com o estado REAL, medido por sonda ativa no cérebro
// (`GET /saude/elos`), erro traduzido e, quando o elo tem cura, o botão
// "Reconectar". Estado nunca só por cor (DESIGN-SYSTEM): cor + ícone + texto.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";

import { api, mensagemDeErro } from "@/lib/api";

type EstadoElo = "ok" | "degradado" | "caido";

type Elo = {
  id: string;
  nome: string;
  grupo: string;
  estado: EstadoElo;
  detalhe: string | null;
  erro: string | null;
  latencia_ms: number;
  verificado_em: string;
  desde: string | null;
  reconectavel: boolean;
  auto_cura: boolean;
};

type FotoElos = {
  agora: string;
  elos: Elo[];
  caidos: string[];
  degradados: string[];
  saudavel: boolean;
};

const GRUPOS: { id: string; titulo: string }[] = [
  { id: "banco", titulo: "Banco de dados" },
  { id: "ia", titulo: "Inteligência artificial" },
  { id: "canais", titulo: "Canais" },
  { id: "borda", titulo: "Borda e serviços" },
  { id: "interno", titulo: "Motores internos" },
];

const ESTADO_ROTULO: Record<EstadoElo, string> = {
  ok: "operacional",
  degradado: "com limitação",
  caido: "fora do ar",
};

const ESTADO_COR: Record<EstadoElo, { ponto: string; texto: string; fundo: string }> = {
  ok: { ponto: "bg-[#3DAA5C]", texto: "text-[#3DAA5C]", fundo: "bg-[#E6F4EA]" },
  degradado: { ponto: "bg-[#E89638]", texto: "text-[#E89638]", fundo: "bg-[#FDF1E3]" },
  caido: { ponto: "bg-[#E5484D]", texto: "text-[#E5484D]", fundo: "bg-[#FDECEC]" },
};

function haQuanto(iso: string | null, agora: number): string {
  if (!iso) return "—";
  const s = Math.max(0, Math.round((agora - new Date(iso).getTime()) / 1000));
  if (s < 60) return `há ${s} s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  return `há ${Math.floor(s / 3600)} h`;
}

export default function PaginaStatus() {
  const [foto, setFoto] = useState<FotoElos | null>(null);
  const [erroLeitura, setErroLeitura] = useState<string | null>(null);
  const [agora, setAgora] = useState(() => Date.now());
  const [reconectando, setReconectando] = useState<string | null>(null);
  const [avisoReconexao, setAvisoReconexao] = useState<string | null>(null);
  const vivo = useRef(true);

  const ler = useCallback(async () => {
    try {
      const dados = await api.get<FotoElos>("/saude/elos");
      if (!vivo.current) return;
      setFoto(dados);
      setErroLeitura(null);
    } catch (e) {
      // A própria falha de leitura é o elo "interface → cérebro" caindo: mostrada
      // com honestidade, mantendo a última foto conhecida na tela.
      if (vivo.current) setErroLeitura(mensagemDeErro(e));
    }
  }, []);

  useEffect(() => {
    vivo.current = true;
    // Primeira leitura agendada (não síncrona no corpo do efeito — regra dos hooks).
    const primeira = setTimeout(ler, 0);
    const poll = setInterval(ler, 10_000); // a foto é cache no cérebro — barato
    const tique = setInterval(() => setAgora(Date.now()), 1_000);
    return () => {
      vivo.current = false;
      clearTimeout(primeira);
      clearInterval(poll);
      clearInterval(tique);
    };
  }, [ler]);

  async function reconectar(elo: Elo) {
    setReconectando(elo.id);
    setAvisoReconexao(null);
    try {
      await api.post(`/saude/elos/${elo.id}/reconectar`, {});
      await ler();
    } catch (e) {
      setAvisoReconexao(`${elo.nome}: ${mensagemDeErro(e)}`);
    } finally {
      setReconectando(null);
    }
  }

  const caidos = foto?.caidos.length ?? 0;
  const degradados = foto?.degradados.length ?? 0;
  const tudoBem = foto != null && caidos === 0 && degradados === 0;

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="font-heading text-2xl font-semibold text-[#1A1730]">
        Status do Batuta
      </h1>
      <p className="mt-1 text-sm text-[#6B6880]">
        Cada ligação da corrente é verificada de tempos em tempos pelo próprio
        Batuta. Quando algo não responde por aí, é aqui que se descobre o quê.
      </p>

      {/* Faixa-resumo */}
      <div
        className={`mt-5 flex items-center gap-3 rounded-lg border border-[#E8E6F0] p-4 ${
          foto == null
            ? "bg-white"
            : tudoBem
              ? ESTADO_COR.ok.fundo
              : caidos > 0
                ? ESTADO_COR.caido.fundo
                : ESTADO_COR.degradado.fundo
        }`}
      >
        {foto == null ? (
          <>
            <Loader2 className="size-5 animate-spin text-[#6B6880]" aria-hidden />
            <span className="text-sm text-[#6B6880]">Consultando o cérebro…</span>
          </>
        ) : tudoBem ? (
          <>
            <CheckCircle2 className="size-5 text-[#3DAA5C]" aria-hidden />
            <span className="text-sm font-medium text-[#1A1730]">
              Todos os elos operacionais
            </span>
          </>
        ) : (
          <>
            {caidos > 0 ? (
              <XCircle className="size-5 text-[#E5484D]" aria-hidden />
            ) : (
              <AlertTriangle className="size-5 text-[#E89638]" aria-hidden />
            )}
            <span className="text-sm font-medium text-[#1A1730]">
              {caidos > 0
                ? `${caidos} elo${caidos > 1 ? "s" : ""} fora do ar`
                : `${degradados} elo${degradados > 1 ? "s" : ""} com limitação`}
            </span>
          </>
        )}
        {foto && (
          <span className="ml-auto text-xs text-[#6B6880]">
            atualizado {haQuanto(foto.agora, agora)}
          </span>
        )}
      </div>

      {/* O cérebro em si inacessível = o elo interface → cérebro caiu */}
      {erroLeitura && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-[#E8E6F0] bg-[#FDECEC] p-3 text-sm text-[#1A1730]">
          <XCircle className="mt-0.5 size-4 shrink-0 text-[#E5484D]" aria-hidden />
          <span>
            Não estou conseguindo falar com o cérebro agora — {erroLeitura}{" "}
            {foto && "Abaixo está a última foto que recebi."}
          </span>
        </div>
      )}

      {avisoReconexao && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-[#E8E6F0] bg-[#FDF1E3] p-3 text-sm text-[#1A1730]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[#E89638]" aria-hidden />
          <span>{avisoReconexao}</span>
        </div>
      )}

      {/* Grupos de elos */}
      {foto &&
        GRUPOS.map((grupo) => {
          const elos = foto.elos.filter((e) => e.grupo === grupo.id);
          if (elos.length === 0) return null;
          return (
            <section key={grupo.id} className="mt-6">
              <h2 className="text-xs font-semibold tracking-wide text-[#6B6880] uppercase">
                {grupo.titulo}
              </h2>
              <div className="mt-2 flex flex-col gap-2">
                {elos.map((elo) => {
                  const cor = ESTADO_COR[elo.estado];
                  return (
                    <div
                      key={elo.id}
                      className="rounded-lg border border-[#E8E6F0] bg-white p-3"
                    >
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`size-2.5 shrink-0 rounded-full ${cor.ponto}`}
                          aria-hidden
                        />
                        <span className="text-sm font-medium text-[#1A1730]">
                          {elo.nome}
                        </span>
                        <span className={`text-xs font-medium ${cor.texto}`}>
                          {ESTADO_ROTULO[elo.estado]}
                        </span>
                        <span className="ml-auto text-xs text-[#A09DB8]">
                          {elo.latencia_ms} ms · verificado{" "}
                          {haQuanto(elo.verificado_em, agora)}
                        </span>
                      </div>
                      {(elo.erro || elo.detalhe) && (
                        <p
                          className={`mt-1.5 pl-5 text-xs ${
                            elo.erro ? "text-[#1A1730]" : "text-[#6B6880]"
                          }`}
                        >
                          {elo.erro ?? elo.detalhe}
                          {elo.estado !== "ok" && elo.desde && (
                            <span className="text-[#A09DB8]">
                              {" "}
                              (assim {haQuanto(elo.desde, agora)})
                            </span>
                          )}
                        </p>
                      )}
                      {elo.estado !== "ok" && elo.reconectavel && (
                        <div className="mt-2 pl-5">
                          <button
                            type="button"
                            onClick={() => reconectar(elo)}
                            disabled={reconectando === elo.id}
                            className="inline-flex items-center gap-1.5 rounded-md border border-[#D6D3E8] bg-white px-2.5 py-1.5 text-xs font-medium text-[#3D2A99] transition-colors hover:bg-[#EFEAFF] disabled:opacity-60"
                          >
                            {reconectando === elo.id ? (
                              <Loader2 className="size-3.5 animate-spin" aria-hidden />
                            ) : (
                              <RefreshCw className="size-3.5" aria-hidden />
                            )}
                            {reconectando === elo.id ? "Reconectando…" : "Reconectar"}
                          </button>
                        </div>
                      )}
                      {elo.estado === "caido" && elo.auto_cura && (
                        <p className="mt-1 pl-5 text-xs text-[#6B6880]">
                          Este elo se reconecta sozinho após falhas seguidas — a
                          tentativa automática já está em curso.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          );
        })}

      {foto && foto.elos.length === 0 && (
        <p className="mt-6 text-sm text-[#6B6880]">
          O vigia acabou de subir e ainda não sondou nenhum elo — em até 30
          segundos os primeiros resultados aparecem aqui.
        </p>
      )}

      <p className="mt-8 text-xs text-[#A09DB8]">
        As verificações rodam no cérebro (30 s para banco e motores internos, 60 s
        para serviços externos). Toda queda e volta fica registrada no histórico de
        eventos. Os instrumentos de cada time são testados sob demanda, pelo
        Construtor — não aqui.
      </p>
    </div>
  );
}
