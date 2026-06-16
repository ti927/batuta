"use client";

// Componente compartilhado de gestão do cofre de chaves de SERVIÇO (Fase 7.5;
// unificação de chaves). Usado em duas telas: chaves da organização e chave-mãe
// da consultoria — a diferença é só o `basePath`. Mostra as chaves MASCARADAS (só
// os 4 últimos dígitos; o valor nunca volta do cérebro) e permite cadastrar/
// trocar/remover. A chave é UMA por serviço/provedor (unificação 2026-06-15):
// salvar um serviço que já existe SUBSTITUI a chave — quem escolhe a IA é o
// modelo (da conversa e de cada agente), não a chave. Inclui serviços não-modelo
// compartilháveis (Tavily/busca), que os instrumentos reusam.

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi, type ChaveApiLer } from "@/lib/api";
import {
  ROTULO_SERVICO,
  SERVICOS,
  USADA_POR,
  type Servico,
} from "@/lib/modelos";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export function GestaoChaves({
  basePath,
  chavesIniciais,
  ehConsultoria = false,
}: {
  basePath: string;
  chavesIniciais: ChaveApiLer[];
  // Na consultoria, a chave pode ser marcada como compartilhável (serve de
  // reserva às organizações). Nas chaves da organização isso é irrelevante.
  ehConsultoria?: boolean;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [servico, setServico] = useState<Servico>("anthropic");
  const [valor, setValor] = useState("");
  const [apelido, setApelido] = useState("");
  const [compartilhavel, setCompartilhavel] = useState(true);

  const jaTem = chavesIniciais.some((c) => c.provedor === servico);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function salvar() {
    if (!valor.trim()) return;
    try {
      await api.put(basePath, {
        provedor: servico,
        valor: valor.trim(),
        apelido: apelido.trim() || null,
        compartilhavel: ehConsultoria ? compartilhavel : true,
      });
      setValor("");
      setApelido("");
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar a chave");
    }
  }

  async function remover(chave: ChaveApiLer) {
    const rotulo = ROTULO_SERVICO[chave.provedor as Servico] ?? chave.provedor;
    if (!confirm(`Remover a chave ${rotulo} (••••${chave.ultimos4})?`)) return;
    try {
      await api.delete(`${basePath}/${chave.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover a chave");
    }
  }

  return (
    <div>
      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {/* Lista das chaves cadastradas (mascaradas) */}
      {chavesIniciais.length === 0 ? (
        <p className="mb-6 text-sm text-muted-foreground">
          Nenhuma chave cadastrada.
        </p>
      ) : (
        <ul className="mb-6 divide-y divide-border rounded-lg border border-border bg-card">
          {chavesIniciais.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                  {ROTULO_SERVICO[c.provedor as Servico] ?? c.provedor}
                  {!c.ativa && <Badge>inativa</Badge>}
                  {ehConsultoria && (
                    <Badge variant={c.compartilhavel ? "success" : "neutral"}>
                      {c.compartilhavel ? "compartilhável" : "privada"}
                    </Badge>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  termina em ••••{c.ultimos4}
                  {c.apelido ? ` · ${c.apelido}` : ""}
                </p>
              </div>
              <Button size="sm" variant="destructive" onClick={() => remover(c)}>
                Remover
              </Button>
            </li>
          ))}
        </ul>
      )}

      {/* Formulário de cadastro/troca */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-medium text-foreground">
          Cadastrar ou trocar uma chave
        </h3>
        <div className="flex flex-wrap gap-2">
          <Select
            className="w-auto"
            value={servico}
            onChange={(e) => setServico(e.target.value as Servico)}
          >
            {SERVICOS.map((s) => (
              <option key={s} value={s}>
                {ROTULO_SERVICO[s]}
              </option>
            ))}
          </Select>
        </div>
        <Input
          type="password"
          autoComplete="off"
          placeholder="Cole o valor da chave (não será reexibido)"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
        />
        <Input
          placeholder="Apelido (opcional)"
          value={apelido}
          onChange={(e) => setApelido(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && salvar()}
        />
        {ehConsultoria && (
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="size-4 rounded border-border"
              checked={compartilhavel}
              onChange={(e) => setCompartilhavel(e.target.checked)}
            />
            Pode servir de reserva às organizações (compartilhável)
          </label>
        )}
        {jaTem && (
          <p className="text-xs text-warning">
            Já existe uma chave de {ROTULO_SERVICO[servico]}. Salvar vai
            substituí-la.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Usada por: <span className="font-medium">{USADA_POR[servico]}</span>.
        </p>
        <Button className="self-start" onClick={salvar}>
          Salvar chave
        </Button>
      </div>
    </div>
  );
}
