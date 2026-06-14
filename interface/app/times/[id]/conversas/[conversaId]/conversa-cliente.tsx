"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronLeft } from "lucide-react";

import {
  api,
  ErroDaApi,
  type ConversaComMensagens,
  type MensagemDaConversa,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { ESTADO_CONVERSA } from "../conversas-cliente";

// Aparência de cada papel na thread (de quem é a fala, de que lado, com que cor).
const ESTILO_PAPEL: Record<
  string,
  { rotulo: string; lado: "esq" | "dir" | "centro"; classe: string }
> = {
  contato: { rotulo: "Contato", lado: "esq", classe: "bg-muted text-foreground" },
  agente: { rotulo: "Agente", lado: "dir", classe: "bg-primary text-primary-foreground" },
  operador: { rotulo: "Você", lado: "dir", classe: "bg-emerald-600 text-white" },
  sistema: { rotulo: "Sistema", lado: "centro", classe: "bg-transparent text-muted-foreground" },
};

export function ConversaCliente({
  time,
  conversa,
  meuPapel,
}: {
  time: Time;
  conversa: ConversaComMensagens;
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const fim = useRef<HTMLDivElement>(null);

  const operar = podeOperar(meuPapel);
  const assumida = conversa.estado === "humano_assumiu";
  const fechada = conversa.estado === "fechada";

  // Atualiza sozinha enquanto a conversa está viva (novas mensagens do contato
  // e respostas do bot chegam por fora desta aba). router.refresh() rebusca o
  // Server Component sem recarregar a página.
  useEffect(() => {
    if (fechada) return;
    const t = setInterval(() => router.refresh(), 4000);
    return () => clearInterval(t);
  }, [router, fechada]);

  useEffect(() => {
    fim.current?.scrollIntoView({ block: "end" });
  }, [conversa.mensagens.length]);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function acao(caminho: string, padrao: string, corpo?: unknown) {
    setOcupado(true);
    setErro(null);
    try {
      await api.post(caminho, corpo ?? {});
      router.refresh();
    } catch (e) {
      tratar(e, padrao);
    } finally {
      setOcupado(false);
    }
  }

  async function responder() {
    const t = texto.trim();
    if (!t) return;
    setOcupado(true);
    setErro(null);
    try {
      await api.post(`/conversas/${conversa.id}/responder-operador`, { texto: t });
      setTexto("");
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao enviar");
    } finally {
      setOcupado(false);
    }
  }

  const estado = ESTADO_CONVERSA[conversa.estado] ?? {
    rotulo: conversa.estado,
    variante: "neutral" as const,
  };

  return (
    <main className="mx-auto flex h-[calc(100vh-2rem)] w-full max-w-3xl flex-col px-4 py-6 sm:px-6">
      <Link
        href={`/times/${time.id}/conversas`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Conversas
      </Link>

      <div className="mt-2 flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-medium text-foreground">
            {conversa.contato_nome || conversa.contato_chave}
          </h1>
          <p className="text-xs text-muted-foreground">
            {conversa.canal} · {conversa.contato_chave}
          </p>
        </div>
        <Badge variant={estado.variante}>{estado.rotulo}</Badge>
      </div>

      {operar && !fechada && (
        <div className="mt-3 flex flex-wrap gap-2">
          {!assumida ? (
            <Button
              size="sm"
              variant="outline"
              disabled={ocupado}
              onClick={() => acao(`/conversas/${conversa.id}/assumir`, "Falha ao assumir")}
            >
              Assumir
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              disabled={ocupado}
              onClick={() => acao(`/conversas/${conversa.id}/devolver`, "Falha ao devolver")}
            >
              Devolver ao bot
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={ocupado}
            onClick={() => acao(`/conversas/${conversa.id}/fechar`, "Falha ao fechar")}
          >
            Encerrar
          </Button>
        </div>
      )}

      {erro && <Aviso className="mt-3">{erro}</Aviso>}

      <div className="mt-4 flex-1 space-y-2 overflow-y-auto rounded-lg border border-border bg-card p-4">
        {conversa.mensagens.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sem mensagens ainda.</p>
        ) : (
          conversa.mensagens.map((m: MensagemDaConversa) => {
            const est = ESTILO_PAPEL[m.papel] ?? ESTILO_PAPEL.sistema;
            if (est.lado === "centro") {
              return (
                <p key={m.id} className="py-1 text-center text-xs text-muted-foreground">
                  {m.conteudo}
                </p>
              );
            }
            return (
              <div
                key={m.id}
                className={`flex ${est.lado === "dir" ? "justify-end" : "justify-start"}`}
              >
                <div className="max-w-[80%]">
                  <div
                    className={`rounded-2xl px-3 py-2 text-sm ${est.classe} ${
                      m.entregue ? "" : "opacity-60"
                    }`}
                  >
                    {m.conteudo}
                  </div>
                  <div
                    className={`mt-0.5 text-[10px] text-muted-foreground ${
                      est.lado === "dir" ? "text-right" : "text-left"
                    }`}
                  >
                    {est.rotulo}
                    {!m.entregue && " · não entregue"}
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={fim} />
      </div>

      {operar && assumida && !fechada && (
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            responder();
          }}
        >
          <Input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Escreva sua resposta ao contato…"
            disabled={ocupado}
          />
          <Button type="submit" disabled={ocupado || !texto.trim()}>
            Enviar
          </Button>
        </form>
      )}
      {operar && !assumida && !fechada && (
        <p className="mt-3 text-center text-xs text-muted-foreground">
          O bot está atendendo. Clique em <strong>Assumir</strong> para responder
          você mesmo.
        </p>
      )}
    </main>
  );
}
