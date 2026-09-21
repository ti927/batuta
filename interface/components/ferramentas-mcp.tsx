"use client";

// A ESCOLHA DAS FERRAMENTAS DE UM SERVIDOR MCP.
//
// Um servidor MCP (Zapier, Composio, um servidor próprio) publica muitas ferramentas —
// dezenas, no caso do Zapier. Até 2026-09-21 o instrumento levava TODAS para o cinto do
// agente, e por isso nunca foi usado: o cinto entope, o custo por passo sobe e o agente
// escolhe errado. Aqui a pessoa marca quais entram.
//
// E marca também o que cada uma é: **só lê** ou **pede aprovação**. Nasce pedindo,
// porque o servidor é de terceiro e o Batuta não tem como saber o que cada ferramenta
// faz — liberar é ato consciente, por ferramenta, nunca no atacado.
//
// O campo no formulário é um `array` de objetos; sem esta tela ele viraria uma caixa de
// texto pedindo JSON, o que é a mesma coisa que não ter escolha nenhuma.

import { useState } from "react";
import { AlertTriangle, RefreshCw, ShieldAlert, Unplug } from "lucide-react";

import { api, mensagemDeErro } from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";

export type FerramentaMCP = {
  nome: string;
  usar: boolean;
  irreversivel: boolean;
};

type DoServidor = { nome: string; descricao?: string | null };

function lerValor(valor: string): FerramentaMCP[] {
  if (!valor.trim()) return [];
  try {
    const bruto = JSON.parse(valor);
    if (!Array.isArray(bruto)) return [];
    return bruto
      .filter((f) => f && typeof f.nome === "string")
      .map((f) => ({
        nome: f.nome as string,
        usar: f.usar !== false,
        irreversivel: f.irreversivel !== false,
      }));
  } catch {
    return [];
  }
}

export function SeletorFerramentasMCP({
  valor,
  instrumentoId,
  onChange,
}: {
  valor: string;
  /** Sem id, o instrumento ainda não foi salvo — e sem ele não há o que perguntar. */
  instrumentoId: string | null;
  onChange: (v: string) => void;
}) {
  const escolhidas = lerValor(valor);
  const [doServidor, setDoServidor] = useState<DoServidor[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function buscar() {
    if (!instrumentoId) return;
    setBuscando(true);
    setErro(null);
    try {
      const r = await api.post<{ ferramentas?: DoServidor[] }>(
        `/instrumentos/${instrumentoId}/acionar`,
        { argumentos: {} },
      );
      const lista = r?.ferramentas ?? [];
      setDoServidor(lista);
      // Primeira busca: semeia a escolha com TUDO DESMARCADO. Marcar tudo sozinho
      // seria decidir pela pessoa justamente o que esta tela existe para ela decidir.
      if (!escolhidas.length && lista.length) {
        gravar(lista.map((f) => ({ nome: f.nome, usar: false, irreversivel: true })));
      }
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível falar com o servidor MCP"));
    } finally {
      setBuscando(false);
    }
  }

  function gravar(lista: FerramentaMCP[]) {
    onChange(JSON.stringify(lista));
  }

  function alterar(nome: string, patch: Partial<FerramentaMCP>) {
    const existe = escolhidas.some((f) => f.nome === nome);
    gravar(
      existe
        ? escolhidas.map((f) => (f.nome === nome ? { ...f, ...patch } : f))
        : [...escolhidas, { nome, usar: true, irreversivel: true, ...patch }],
    );
  }

  // O que mostrar: o que o servidor publica agora; e, se ainda não perguntamos, o que
  // está guardado. Uma escolhida que sumiu do servidor aparece marcada como sumida —
  // some do cinto em silêncio, e silêncio é o que não pode.
  const nomesServidor = new Set((doServidor ?? []).map((f) => f.nome));
  const linhas: (DoServidor & { sumiu?: boolean })[] = [
    ...(doServidor ?? escolhidas.map((f) => ({ nome: f.nome }))),
    ...(doServidor
      ? escolhidas
          .filter((f) => !nomesServidor.has(f.nome))
          .map((f) => ({ nome: f.nome, sumiu: true }))
      : []),
  ];

  const marcadas = escolhidas.filter((f) => f.usar).length;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={buscar}
          disabled={!instrumentoId || buscando}
        >
          {buscando ? (
            <RefreshCw className="size-3.5 animate-spin" />
          ) : (
            <Unplug className="size-3.5" />
          )}
          {doServidor ? "Buscar de novo" : "Conectar e listar ferramentas"}
        </Button>
        <span className="text-xs text-muted-foreground">
          {marcadas === 0
            ? "nenhuma no cinto — o agente não recebe ferramenta nenhuma"
            : `${marcadas} no cinto`}
        </span>
      </div>

      {!instrumentoId && (
        <p className="text-xs text-muted-foreground">
          Salve o instrumento primeiro (com o endereço do servidor). Só então dá para
          perguntar a ele quais ferramentas publica.
        </p>
      )}

      {erro && <Aviso>{erro}</Aviso>}

      {linhas.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-md border border-border p-2">
          {linhas.map((f) => {
            const atual = escolhidas.find((x) => x.nome === f.nome);
            const usar = atual?.usar ?? false;
            const irreversivel = atual?.irreversivel ?? true;
            return (
              <div
                key={f.nome}
                className="flex flex-col gap-1 rounded-md px-1.5 py-1.5 hover:bg-muted/40"
              >
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    className="mt-0.5 size-3.5 flex-none accent-primary"
                    checked={usar}
                    disabled={f.sumiu}
                    onChange={(e) => alterar(f.nome, { usar: e.target.checked })}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[12px] text-foreground">
                      {f.nome}
                    </span>
                    {f.descricao && (
                      <span className="block text-[11px] leading-snug text-muted-foreground">
                        {f.descricao}
                      </span>
                    )}
                    {f.sumiu && (
                      <span className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-warning">
                        <AlertTriangle className="size-3" />
                        não existe mais no servidor — o agente está sem ela
                      </span>
                    )}
                  </span>
                </label>
                {usar && !f.sumiu && (
                  <div className="ml-5 flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => alterar(f.nome, { irreversivel: false })}
                      className="rounded border px-1.5 py-0.5 text-[11px]"
                      style={
                        irreversivel
                          ? { borderColor: "var(--border)", color: "#8B88A0" }
                          : {
                              borderColor: "#79C295",
                              background: "#E6F4EA",
                              color: "#2F7D45",
                            }
                      }
                    >
                      só lê
                    </button>
                    <button
                      type="button"
                      onClick={() => alterar(f.nome, { irreversivel: true })}
                      className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]"
                      style={
                        irreversivel
                          ? {
                              borderColor: "#F0D9B4",
                              background: "#FDF1E3",
                              color: "#A9681A",
                            }
                          : { borderColor: "var(--border)", color: "#8B88A0" }
                      }
                    >
                      <ShieldAlert className="size-3" />
                      pede aprovação
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p className="text-[11px] leading-snug text-muted-foreground">
        Uma ferramenta marcada como <strong>pede aprovação</strong> para a execução e
        espera uma pessoa antes de rodar. Só marque <strong>só lê</strong> quando tiver
        certeza de que ela não muda nada lá fora — o Batuta não tem como conferir isso
        por você.
      </p>
    </div>
  );
}
