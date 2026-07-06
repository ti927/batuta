"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FlaskConical, Radio, Trash2, X } from "lucide-react";

import {
  api,
  ErroDaApi,
  type AlcanceCanal,
  type Instrumento,
  type PapelAcesso,
  type StatusCanal,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { FormularioInstrumento } from "@/components/formulario-instrumento";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

// A mensagem de aviso quando o bot NÃO alcança o destinatário (senão, null).
function mensagemAlcance(a: AlcanceCanal): string | null {
  if (!a.aplicavel || a.alcancavel !== false) return null;
  const bot = a.bot_username ? `@${a.bot_username}` : "o bot";
  return (
    `O ${bot} ainda não consegue enviar mensagens para o destinatário ${a.destino}. ` +
    `Peça para essa pessoa abrir o Telegram e mandar /start para ${bot} — ` +
    `sem isso, as mensagens não chegam.`
  );
}

// Interpreta um texto como objeto JSON. [valor, null] ou [null, mensagem]. Vazio = {}.
function lerJson(texto: string): [Record<string, unknown> | null, string | null] {
  const t = texto.trim();
  if (!t) return [{}, null];
  try {
    const v = JSON.parse(t);
    if (typeof v !== "object" || v === null || Array.isArray(v))
      return [null, "Os argumentos precisam ser um objeto JSON."];
    return [v as Record<string, unknown>, null];
  } catch {
    return [null, "JSON inválido nos argumentos."];
  }
}

/**
 * Editor de instrumento em drawer (sobre a aba, sem navegar). Reúne tudo num
 * lugar: editar a configuração, conectar o canal (Telegram) e testar o
 * instrumento isoladamente. `Esc` fecha. Reusado pela aba Instrumentos e Início.
 */
export function DrawerInstrumento({
  instrumento,
  tipos,
  time,
  meuPapel,
  onFechar,
  onSalvou,
}: {
  instrumento: Instrumento | null;
  tipos: TipoInstrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
  onFechar: () => void;
  // Avisa o pai do instrumento salvo. O drawer NÃO fecha sozinho ao salvar
  // (decisão do maestro: fica aberto até fechar manualmente). Ao criar, o pai
  // troca para o recém-criado e o drawer passa de "criar" para "editar".
  onSalvou: (salvo: Instrumento) => void;
}) {
  const router = useRouter();
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);
  const criando = instrumento === null;
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  // Estado do "Testar": argumentos (JSON) e resultado do acionamento isolado.
  const [testando, setTestando] = useState(false);
  const [argsTexto, setArgsTexto] = useState("{}");
  const [resultado, setResultado] = useState<string | null>(null);

  // Canal (Telegram): status de conexão (RECEBER suas respostas) e alcance do
  // destinatário (o bot consegue ENVIAR?). Carregados ao abrir e re-checados ao
  // conectar/salvar — o aviso de alcance é o "automático ao salvar".
  const [statusCanal, setStatusCanal] = useState<StatusCanal | null>(null);
  const [avisoAlcance, setAvisoAlcance] = useState<string | null>(null);
  // De qual instrumento é o status carregado — evita mostrar o de outro canal ao
  // trocar de instrumento antes de a nova checagem chegar.
  const [canalDe, setCanalDe] = useState<string | null>(null);

  const aplicarCanal = useCallback(
    (id: string, st: StatusCanal, al: AlcanceCanal) => {
      setStatusCanal(st);
      setAvisoAlcance(mensagemAlcance(al));
      setCanalDe(id);
    },
    [],
  );

  // Recarrega status + alcance (usado por eventos: conectar/salvar).
  const carregarCanal = useCallback(
    async (id: string) => {
      try {
        const [st, al] = await Promise.all([
          api.get<StatusCanal>(`/mensageria/${id}/canal`),
          api.get<AlcanceCanal>(`/mensageria/${id}/alcance`),
        ]);
        aplicarCanal(id, st, al);
      } catch {
        /* informativo: não bloqueia o drawer se a checagem falhar */
      }
    },
    [aplicarCanal],
  );

  // Ao abrir/trocar o instrumento, carrega o estado do canal (Telegram). O
  // setState acontece só no retorno da rede (não síncrono no efeito).
  useEffect(() => {
    if (instrumento?.tipo !== "enviar_telegram") return;
    const id = instrumento.id;
    let vivo = true;
    Promise.all([
      api.get<StatusCanal>(`/mensageria/${id}/canal`),
      api.get<AlcanceCanal>(`/mensageria/${id}/alcance`),
    ])
      .then(([st, al]) => {
        if (vivo) aplicarCanal(id, st, al);
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [instrumento, aplicarCanal]);

  // Só mostra o status quando ele é DESTE instrumento (não de um anterior).
  const canalCarregado = !!instrumento && canalDe === instrumento.id;
  const statusMostrado = canalCarregado ? statusCanal : null;
  const alcanceMostrado = canalCarregado ? avisoAlcance : null;

  // Esc fecha o drawer (handoff §4).
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [onFechar]);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function remover() {
    if (!instrumento) return;
    if (!confirm(`Remover o instrumento "${instrumento.nome}"?`)) return;
    setOcupado(true);
    setErro(null);
    try {
      await api.delete(`/instrumentos/${instrumento.id}`);
      toast.success("Instrumento removido");
      onFechar();
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover instrumento");
      setOcupado(false);
    }
  }

  async function conectarCanal() {
    if (!instrumento) return;
    setErro(null);
    try {
      await api.post(`/mensageria/${instrumento.id}/ativar-canal`, {});
      toast.success("Canal conectado ao Telegram");
      carregarCanal(instrumento.id);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao conectar o canal");
    }
  }

  async function acionar() {
    if (!instrumento) return;
    const [args, erroJson] = lerJson(argsTexto);
    if (erroJson) {
      setErro(erroJson);
      return;
    }
    try {
      const r = await api.post<unknown>(`/instrumentos/${instrumento.id}/acionar`, {
        argumentos: args,
      });
      setResultado(JSON.stringify(r, null, 2));
      setErro(null);
    } catch (e) {
      tratar(e, "Falha ao acionar instrumento");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={onFechar}
        aria-label="Fechar"
      />
      <aside className="relative flex h-full w-full max-w-[460px] flex-col overflow-y-auto border-l border-border bg-card shadow-xl">
        <header className="flex items-center gap-3 border-b border-border p-4">
          <span className="flex size-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <IconeInstrumento
              icone={instrumento?.icone}
              className="size-4.5"
            />
          </span>
          <h2 className="min-w-0 flex-1 truncate font-medium text-foreground">
            {criando ? "Novo instrumento" : instrumento.nome}
          </h2>
          {souAdmin && !criando && (
            <Button
              size="sm"
              variant="destructive"
              onClick={remover}
              disabled={ocupado}
            >
              <Trash2 className="size-4" /> Remover
            </Button>
          )}
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>

        <div className="p-4">
          {erro && (
            <div className="mb-3">
              <Aviso>{erro}</Aviso>
            </div>
          )}
          <FormularioInstrumento
            time={time}
            instrumento={instrumento}
            tipos={tipos}
            onSalvo={(salvo) => {
              toast.success(criando ? "Instrumento criado" : "Instrumento salvo");
              onSalvou(salvo);
              router.refresh();
              // "Automático ao salvar": re-checa alcance do destinatário (Telegram).
              if (salvo.tipo === "enviar_telegram") carregarCanal(salvo.id);
            }}
            onCancelar={onFechar}
          />

          {/* Ações do instrumento existente: conectar canal (Telegram) e testar. */}
          {!criando && souOperador && (
            <div className="mt-6 space-y-3 border-t border-border pt-4">
              {instrumento.tipo === "enviar_telegram" && (
                <div className="space-y-2">
                  {statusMostrado &&
                    (statusMostrado.conectado ? (
                      <Aviso variant="sucesso">
                        Canal conectado — as respostas enviadas ao bot chegam ao
                        Batuta.
                      </Aviso>
                    ) : (
                      <Aviso variant="atencao">
                        Canal não conectado — conecte para o Batuta receber as
                        respostas enviadas ao bot.
                      </Aviso>
                    ))}
                  {alcanceMostrado && (
                    <Aviso variant="atencao">{alcanceMostrado}</Aviso>
                  )}
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={conectarCanal}
                  >
                    <Radio className="size-4" />{" "}
                    {statusMostrado?.conectado
                      ? "Reconectar canal ao Telegram"
                      : "Conectar canal ao Telegram"}
                  </Button>
                </div>
              )}

              {!testando ? (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    setTestando(true);
                    setArgsTexto("{}");
                    setResultado(null);
                    setErro(null);
                  }}
                >
                  <FlaskConical className="size-4" /> Testar instrumento
                </Button>
              ) : (
                <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
                  <Label className="flex-col items-start gap-1">
                    Argumentos (JSON)
                    <Textarea
                      className="min-h-20 font-mono"
                      value={argsTexto}
                      onChange={(e) => setArgsTexto(e.target.value)}
                    />
                  </Label>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={acionar}>
                      Acionar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setTestando(false)}
                    >
                      Fechar
                    </Button>
                  </div>
                  {resultado && (
                    <pre className="max-h-72 overflow-auto rounded-md bg-foreground p-3 text-xs text-background">
                      {resultado}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
