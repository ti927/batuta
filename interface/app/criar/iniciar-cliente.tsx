"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { api, ErroDaApi, type ConversaCriacao, type Organizacao } from "@/lib/api";

// Abre uma conversa com a IA criadora numa organização escolhida. Com a primeira
// mensagem já enviada, o cérebro roda o primeiro turno; redirecionamos para a
// tela da conversa.
export function IniciarCliente({
  organizacoes,
  compacto = false,
}: {
  organizacoes: Organizacao[];
  // Quando já há projetos para retomar acima, a tela de novo time fica enxuta
  // (sem o herói centralizado), para não competir com a lista.
  compacto?: boolean;
}) {
  const router = useRouter();
  const [orgId, setOrgId] = useState(organizacoes[0]?.id ?? "");
  const [mensagem, setMensagem] = useState("");
  const [iniciando, setIniciando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (organizacoes.length === 0) {
    return (
      <EstadoVazio icone={Sparkles} titulo="Nenhuma organização para criar">
        Você precisa ser operador ou admin de alguma organização para montar um time
        com a IA. Fale com um admin da sua organização.
      </EstadoVazio>
    );
  }

  if (compacto) {
    return (
      <section className="text-left">
        <h2 className="font-heading text-xl font-semibold text-foreground">
          Criar um time novo
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Descreva o que você quer que esse time faça. A IA monta o time aqui mesmo —
          nada dispara até você ativar.
        </p>

        {organizacoes.length > 1 && (
          <div className="mt-4">
            <label htmlFor="org" className="mb-1.5 block text-sm font-medium text-foreground">
              Organização
            </label>
            <select
              id="org"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
            >
              {organizacoes.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.nome}
                </option>
              ))}
            </select>
          </div>
        )}

        <Textarea
          value={mensagem}
          onChange={(e) => setMensagem(e.target.value)}
          placeholder="Ex.: um time que escreve e publica artigos de blog otimizados para SEO toda semana."
          rows={3}
          className="mt-4 w-full"
        />

        {erro && <p className="mt-3 text-sm text-destructive">{erro}</p>}

        <Button className="mt-4" onClick={comecar} disabled={iniciando || !orgId}>
          <Sparkles />
          {iniciando ? "Abrindo conversa…" : "Começar a montar"}
        </Button>
      </section>
    );
  }

  async function comecar() {
    setIniciando(true);
    setErro(null);
    try {
      // Cria a conversa VAZIA (rápido). A primeira mensagem é enviada já dentro
      // do chat, com o indicador de "digitando" — assim a abertura é instantânea
      // mesmo com o Opus demorando no primeiro turno.
      const conversa = await api.post<ConversaCriacao>(
        `/organizacoes/${orgId}/conversas-criacao`,
        {},
      );
      const primeira = mensagem.trim();
      router.push(
        `/criar/${conversa.id}${primeira ? `?primeira=${encodeURIComponent(primeira)}` : ""}`,
      );
    } catch (e) {
      setErro(
        e instanceof ErroDaApi ? e.message : "Não consegui abrir a conversa.",
      );
      setIniciando(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center px-4 py-16 text-center sm:px-6">
      <Image
        src="/mascote.png"
        alt=""
        width={220}
        height={220}
        className="h-auto w-44 sm:w-56"
        priority
      />
      <h1 className="mt-6 text-2xl font-medium text-foreground">
        Criar um time com a IA
      </h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Descreva o que você quer que esse time faça. A IA criadora vai propor os
        agentes, os instrumentos e o fluxo, e monta tudo aqui — nada dispara até você
        ativar.
      </p>

      {organizacoes.length > 1 && (
        <div className="mt-6 w-full max-w-md text-left">
          <label
            htmlFor="org"
            className="mb-1.5 block text-sm font-medium text-foreground"
          >
            Organização
          </label>
          <select
            id="org"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          >
            {organizacoes.map((o) => (
              <option key={o.id} value={o.id}>
                {o.nome}
              </option>
            ))}
          </select>
        </div>
      )}

      <Textarea
        value={mensagem}
        onChange={(e) => setMensagem(e.target.value)}
        placeholder="Ex.: um time que escreve e publica artigos de blog otimizados para SEO toda semana."
        rows={3}
        className="mt-6 w-full max-w-md"
      />

      {erro && <p className="mt-3 text-sm text-destructive">{erro}</p>}

      <Button
        className="mt-6"
        onClick={comecar}
        disabled={iniciando || !orgId}
      >
        <Sparkles />
        {iniciando ? "Abrindo conversa…" : "Começar a montar"}
      </Button>
    </main>
  );
}
