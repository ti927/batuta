"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Bot, ChevronLeft, Plus, Settings2, Zap } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Agente,
  type Papel,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import {
  MODELOS_POR_PROVEDOR,
  PROVEDORES,
  ROTULO_PROVEDOR,
} from "@/lib/modelos";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type Formulario = {
  nome: string;
  papel: Papel;
  modelo_ia: string;
  agent_md: string;
  skill_md: string;
  tools_md: string;
  soul_md: string;
};

const FORM_VAZIO: Formulario = {
  nome: "",
  papel: "agente",
  modelo_ia: "",
  agent_md: "",
  skill_md: "",
  tools_md: "",
  soul_md: "",
};

function deAgente(a: Agente): Formulario {
  return {
    nome: a.nome,
    papel: a.papel,
    modelo_ia: a.modelo_ia ?? "",
    agent_md: a.agent_md ?? "",
    skill_md: a.skill_md ?? "",
    tools_md: a.tools_md ?? "",
    soul_md: a.soul_md ?? "",
  };
}

export function AgentesCliente({
  time,
  inicial,
  meuPapel,
}: {
  time: Time;
  inicial: Agente[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);

  // modo: null = nenhum form aberto; "novo" = criando; id = editando aquele agente
  const [modo, setModo] = useState<null | "novo" | string>(null);
  const [form, setForm] = useState<Formulario>(FORM_VAZIO);

  function abrirNovo() {
    setForm(FORM_VAZIO);
    setModo("novo");
  }

  function abrirEdicao(a: Agente) {
    setForm(deAgente(a));
    setModo(a.id);
  }

  function fechar() {
    setModo(null);
    setErro(null);
  }

  function campo<K extends keyof Formulario>(chave: K, valor: Formulario[K]) {
    setForm((f) => ({ ...f, [chave]: valor }));
  }

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function corpo() {
    return {
      nome: form.nome.trim(),
      papel: form.papel,
      modelo_ia: form.modelo_ia || null,
      agent_md: form.agent_md || null,
      skill_md: form.skill_md || null,
      tools_md: form.tools_md || null,
      soul_md: form.soul_md || null,
    };
  }

  async function salvar() {
    if (!form.nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    try {
      if (modo === "novo") {
        await api.post<Agente>(`/times/${time.id}/agentes`, corpo());
      } else if (modo) {
        await api.put<Agente>(`/agentes/${modo}`, corpo());
      }
      setErro(null);
      setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar agente");
    }
  }

  async function remover(a: Agente) {
    if (!confirm(`Remover o agente "${a.nome}"?`)) return;
    try {
      await api.delete(`/agentes/${a.id}`);
      setErro(null);
      if (modo === a.id) setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover agente");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/organizacoes/${time.organizacao_id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar à organização
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">{time.nome}</h1>
      <div className="mb-6 mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
        <p className="text-sm text-muted-foreground">Agentes do time</p>
        <Link
          href={`/times/${time.id}/instrumentos`}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <Settings2 className="size-3.5" />
          Instrumentos do time
        </Link>
        <Link
          href={`/times/${time.id}/automacoes`}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <Zap className="size-3.5" />
          Automações do time
        </Link>
      </div>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {modo === null && souOperador && (
        <Button className="mb-6" onClick={abrirNovo}>
          <Plus />
          Novo agente
        </Button>
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium text-foreground">
            {modo === "novo" ? "Novo agente" : "Editar agente"}
          </h2>

          <div className="flex flex-wrap gap-3">
            <Label className="flex-1 flex-col items-start gap-1">
              Nome
              <Input
                value={form.nome}
                onChange={(e) => campo("nome", e.target.value)}
                autoFocus
              />
            </Label>
            <Label className="flex-col items-start gap-1">
              Papel
              <Select
                value={form.papel}
                onChange={(e) => campo("papel", e.target.value as Papel)}
              >
                <option value="agente">Agente</option>
                <option value="lider">Líder</option>
              </Select>
            </Label>
            <Label className="flex-col items-start gap-1">
              Modelo de IA
              <Select
                value={form.modelo_ia}
                onChange={(e) => campo("modelo_ia", e.target.value)}
              >
                <option value="">(não definido)</option>
                {PROVEDORES.map((p) => (
                  <optgroup key={p} label={ROTULO_PROVEDOR[p]}>
                    {MODELOS_POR_PROVEDOR[p].map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </Label>
          </div>

          {(
            [
              ["agent_md", "agent.md — quem o agente é, o que faz"],
              ["skill_md", "skill.md — as habilidades dele"],
              ["tools_md", "tools.md — os instrumentos do cinto"],
              ["soul_md", "soul.md — personalidade, tom, jeito de falar"],
            ] as const
          ).map(([chave, rotulo]) => (
            <Label key={chave} className="flex-col items-start gap-1">
              {rotulo}
              <Textarea
                className="min-h-24 font-mono"
                value={form[chave]}
                onChange={(e) => campo(chave, e.target.value)}
              />
            </Label>
          ))}

          <div className="flex gap-2">
            <Button onClick={salvar}>Salvar</Button>
            <Button variant="ghost" onClick={fechar}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {inicial.length === 0 ? (
        <EstadoVazio icone={Bot} titulo="Nenhum agente ainda.">
          {souOperador
            ? "Crie o primeiro agente para montar este time."
            : "Os agentes deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((a) => (
            <li key={a.id} className="flex items-center gap-2 p-3">
              <span className="flex flex-1 flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                {a.nome}
                <Badge variant={a.papel === "lider" ? "info" : "neutral"}>
                  {a.papel === "lider" ? "Líder" : "Agente"}
                </Badge>
                {a.modelo_ia && (
                  <span className="font-normal text-xs text-muted-foreground">
                    {a.modelo_ia}
                  </span>
                )}
              </span>
              <Link
                href={`/agentes/${a.id}`}
                className={buttonVariants({ size: "sm", variant: "outline" })}
              >
                Cinto
              </Link>
              {souOperador && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => abrirEdicao(a)}
                >
                  Editar
                </Button>
              )}
              {souAdmin && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => remover(a)}
                >
                  Remover
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
