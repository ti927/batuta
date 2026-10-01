"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { ConstrutorInstrumento } from "@/components/construtor-instrumento";
import { ConstrutorMCP } from "@/components/construtor-mcp";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { buscarUso, emUso, quemUsa } from "@/components/uso-instrumento";
import { ListaInstrumentos } from "@/components/lista-instrumentos";
import { Button } from "@/components/ui/button";
import { Aviso } from "@/components/ui/aviso";

export function InstrumentosCliente({
  time,
  inicial,
  tipos,
  meuPapel,
}: {
  time: Time;
  inicial: Instrumento[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const souOperador = podeOperar(meuPapel);
  // null = fechado; "novo" = criando; instrumento = editando.
  // Volta do login de um instrumento MCP quando o pop-up foi bloqueado e o login
  // aconteceu na página inteira: avisa e já reabre o instrumento.
  const busca = useSearchParams();
  const voltaLogin = busca.get("mcp_oauth");
  const [aberto, setAberto] = useState<null | "novo" | Instrumento>(() => {
    const id = busca.get("instrumento");
    return (voltaLogin && id && inicial.find((i) => i.id === id)) || null;
  });
  // Construtor de Instrumento (conector): overlay de tela cheia, separado do
  // formulário genérico. "novo" = criar; instrumento = editar um conector.
  const [construtor, setConstrutor] = useState<null | "novo" | Instrumento>(
    null,
  );
  // Servidor MCP: instrumento personalizado, com o seu próprio Construtor.
  const [construtorMcp, setConstrutorMcp] = useState<
    null | "novo" | Instrumento
  >(null);
  // "Criar instrumento": primeiro a pessoa diz o que quer conectar.
  const [escolhendo, setEscolhendo] = useState(false);

  async function excluir(inst: Instrumento) {
    try {
      const uso = await buscarUso(inst.id);
      if (emUso(uso)) {
        toast.error(
          `Não dá para excluir: “${inst.nome}” é usado por ${quemUsa(uso)}. ` +
            "Tire-o do cinto desses agentes antes.",
        );
        return;
      }
    } catch {
      /* sem a checagem, o cérebro recusa do mesmo jeito se estiver em uso */
    }
    const daOrg =
      inst.escopo === "organizacao"
        ? " Ele some de todos os times da organização."
        : "";
    if (
      !confirm(
        `Excluir o instrumento “${inst.nome}”?${daOrg} Isso não pode ser desfeito.`,
      )
    )
      return;
    try {
      await api.delete(`/instrumentos/${inst.id}`);
      toast.success("Instrumento excluído");
      router.refresh();
    } catch (e) {
      toast.error(
        mensagemDeErro(e, "Não consegui excluir o instrumento. Tente de novo."),
      );
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1000px] px-5 py-8 sm:px-8">
      {voltaLogin === "ok" && (
        <Aviso variant="sucesso" className="mb-4">
          Conta conectada.
        </Aviso>
      )}
      {voltaLogin === "erro" && (
        <Aviso className="mb-4">
          O login não foi concluído. Abra o instrumento e clique em “Conectar”
          de novo.
        </Aviso>
      )}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-foreground">
            Instrumentos do time
          </h2>
          <p className="text-sm text-muted-foreground">
            As ferramentas que os agentes podem usar.
          </p>
        </div>
        {souOperador && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setEscolhendo(true)}>
              🌟 Criar instrumento
            </Button>
            <Button
              variant="outline"
              onClick={() => setAberto("novo")}
              disabled={tipos.length === 0}
            >
              <Plus className="size-4" /> Instrumento pronto
            </Button>
          </div>
        )}
      </div>

      <ListaInstrumentos
        instrumentos={inicial}
        tipos={tipos}
        souOperador={souOperador}
        onExcluir={podeAdmin(meuPapel) ? excluir : undefined}
        onAbrir={(inst) =>
          inst.tipo === "conector"
            ? setConstrutor(inst)
            : inst.tipo === "conectar_mcp"
              ? setConstrutorMcp(inst)
              : setAberto(inst)
        }
      />

      {aberto && (
        <DrawerInstrumento
          key={aberto === "novo" ? "novo" : aberto.id}
          instrumento={aberto === "novo" ? null : aberto}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
          onFechar={() => setAberto(null)}
          onSalvou={(salvo) => setAberto(salvo)}
        />
      )}

      {escolhendo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-foreground/20"
            onClick={() => setEscolhendo(false)}
            aria-label="Fechar"
          />
          <div className="relative w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl">
            <h3 className="mb-3 font-medium text-foreground">
              O que você quer conectar?
            </h3>
            <div className="flex flex-col gap-2">
              <button
                className="rounded-md border border-border p-3 text-left hover:border-primary hover:bg-accent/40"
                onClick={() => {
                  setEscolhendo(false);
                  setConstrutor("novo");
                }}
              >
                <span className="block text-sm font-medium text-foreground">
                  Uma API
                </span>
                <span className="text-xs text-muted-foreground">
                  Você descreve as operações (endereço, campos) a partir da
                  documentação.
                </span>
              </button>
              <button
                className="rounded-md border border-border p-3 text-left hover:border-primary hover:bg-accent/40"
                onClick={() => {
                  setEscolhendo(false);
                  setConstrutorMcp("novo");
                }}
              >
                <span className="block text-sm font-medium text-foreground">
                  Um servidor MCP
                </span>
                <span className="text-xs text-muted-foreground">
                  O serviço já publica as ferramentas (Zernio, Zapier,
                  WordPress…); você escolhe quais entram no cinto.
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {construtorMcp && (
        <ConstrutorMCP
          key={construtorMcp === "novo" ? "novo" : construtorMcp.id}
          time={time}
          instrumento={construtorMcp === "novo" ? null : construtorMcp}
          tipos={tipos}
          souAdmin={podeAdmin(meuPapel)}
          onFechar={() => setConstrutorMcp(null)}
          onSalvou={(salvo) => setConstrutorMcp(salvo)}
        />
      )}

      {construtor && (
        <ConstrutorInstrumento
          key={construtor === "novo" ? "novo" : construtor.id}
          time={time}
          instrumento={construtor === "novo" ? null : construtor}
          souAdmin={podeAdmin(meuPapel)}
          onFechar={() => setConstrutor(null)}
          onSalvou={(salvo) => setConstrutor(salvo)}
        />
      )}
    </main>
  );
}
