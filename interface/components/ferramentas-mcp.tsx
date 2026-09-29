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
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldAlert, Unplug } from "lucide-react";

import { api, mensagemDeErro, type ConexaoInstrumento, type Instrumento } from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";

export type FerramentaMCP = {
  nome: string;
  usar: boolean;
  irreversivel: boolean;
};

// `sugestao` é o que o SERVIDOR diz da ferramenta — só pista, quem decide é a pessoa.
type DoServidor = {
  nome: string;
  descricao?: string | null;
  sugestao?: "so_le" | "altera" | null;
};

type Inventario = {
  ferramentas?: DoServidor[];
  recursos?: { nome: string; uri: string; descricao?: string }[];
  prompts?: { nome: string; descricao?: string }[];
  conexao?: ConexaoInstrumento;
};

function quando(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const dia = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${dia} às ${hora}`;
}

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
  conexaoInicial,
  onChange,
}: {
  valor: string;
  /** Sem id, o instrumento ainda não foi salvo — e sem ele não há o que perguntar. */
  instrumentoId: string | null;
  /** O que o último "Conectar" descobriu (guardado no instrumento). */
  conexaoInicial: ConexaoInstrumento | null;
  onChange: (v: string) => void;
}) {
  const escolhidas = lerValor(valor);
  const [doServidor, setDoServidor] = useState<DoServidor[] | null>(null);
  const [extras, setExtras] = useState<Pick<Inventario, "recursos" | "prompts"> | null>(null);
  const [conexao, setConexao] = useState<ConexaoInstrumento | null>(conexaoInicial);
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function buscar() {
    if (!instrumentoId) return;
    setBuscando(true);
    setErro(null);
    try {
      const r = await api.post<Inventario>(
        `/instrumentos/${instrumentoId}/acionar`,
        { argumentos: {} },
      );
      const lista = r?.ferramentas ?? [];
      setDoServidor(lista);
      setExtras({ recursos: r?.recursos ?? [], prompts: r?.prompts ?? [] });
      if (r?.conexao) setConexao(r.conexao);
      // Primeira busca: semeia a escolha com TUDO DESMARCADO. Marcar tudo sozinho
      // seria decidir pela pessoa justamente o que esta tela existe para ela decidir.
      if (!escolhidas.length && lista.length) {
        gravar(lista.map((f) => ({ nome: f.nome, usar: false, irreversivel: true })));
      }
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível falar com o servidor MCP"));
      // O código da falha fica guardado no instrumento (a mensagem já veio acima).
      try {
        const atual = await api.get<Instrumento>(`/instrumentos/${instrumentoId}`);
        setConexao(atual.conexao ?? null);
      } catch {
        /* sem o código: a mensagem basta */
      }
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

  // Ao MARCAR uma ferramenta que o servidor diz que só lê, a escolha já vem em "só
  // lê"; nas demais, em "pede aprovação". A pessoa pode trocar — é pré-marcação.
  function marcar(f: DoServidor, usar: boolean) {
    const atual = escolhidas.find((x) => x.nome === f.nome);
    if (usar && !atual?.usar) {
      alterar(f.nome, { usar: true, irreversivel: f.sugestao !== "so_le" });
    } else {
      alterar(f.nome, { usar });
    }
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

      {conexao?.estado === "conectado" && !erro && (
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <CheckCircle2 className="size-3.5 text-success" />
          Conectado em {quando(conexao.verificado_em)}
          {conexao.servidor?.nome ? ` · Servidor: ${conexao.servidor.nome}` : ""}
        </span>
      )}
      {conexao?.estado === "falhou" && !erro && conexao.mensagem && (
        <Aviso>
          A última tentativa falhou: {conexao.mensagem}
          {conexao.codigo && (
            <span className="mt-1 block text-[11px] opacity-70">{conexao.codigo}</span>
          )}
        </Aviso>
      )}

      {!instrumentoId && (
        <p className="text-xs text-muted-foreground">
          Salve o instrumento primeiro (com o endereço do servidor). Só então dá para
          perguntar a ele quais ferramentas publica.
        </p>
      )}

      {erro && (
        <Aviso>
          {erro}
          {conexao?.estado === "falhou" && conexao.codigo && (
            <span className="mt-1 block text-[11px] opacity-70">{conexao.codigo}</span>
          )}
        </Aviso>
      )}

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
                    onChange={(e) => marcar(f, e.target.checked)}
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
                    {f.sugestao && (
                      <span className="mt-0.5 inline-block rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        o servidor diz: {f.sugestao === "so_le" ? "só lê" : "apaga ou altera"}
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

      {extras && ((extras.recursos?.length ?? 0) > 0 || (extras.prompts?.length ?? 0) > 0) && (
        <details className="text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground">
            O que mais o servidor oferece
          </summary>
          <div className="mt-1.5 flex flex-col gap-1 pl-4 text-muted-foreground">
            <span className="italic">O agente ainda não usa estes itens.</span>
            {(extras.recursos ?? []).map((r) => (
              <span key={r.uri}>
                <span className="font-mono text-foreground">{r.nome}</span>
                {r.descricao ? ` — ${r.descricao}` : ""}
              </span>
            ))}
            {(extras.prompts ?? []).map((p) => (
              <span key={p.nome}>
                <span className="font-mono text-foreground">{p.nome}</span> (prompt)
                {p.descricao ? ` — ${p.descricao}` : ""}
              </span>
            ))}
          </div>
        </details>
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
