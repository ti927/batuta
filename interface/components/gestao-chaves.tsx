"use client";

// Componente compartilhado de gestão do cofre de chaves (Fase 7.5).
// Usado por duas telas: chaves da organização e chave-mãe da consultoria — a
// diferença é só o `basePath`. Mostra as chaves MASCARADAS (só os 4 últimos
// dígitos; o valor nunca volta do cérebro) e permite cadastrar/trocar/remover.
// Salvar um tipo de IA que já existe SUBSTITUI a chave (upsert no cérebro).

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi, type ChaveApiLer, type TipoIA } from "@/lib/api";
import {
  PROVEDORES,
  ROTULO_PROVEDOR,
  type Provedor,
} from "@/lib/modelos";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

// Dois tipos de IA consomem chave: a executora (os agentes do time) e a IA de
// conversa (a criadora/companheira — uma só conversa desde o pivô). A antiga
// "companheira" saiu do seletor: era a mesma conversa, então virava chave morta.
const TIPOS: TipoIA[] = ["executora", "criadora"];
const ROTULO_TIPO: Record<string, string> = {
  executora: "IA executora (agentes)",
  criadora: "IA de conversa",
  companheira: "IA de conversa",
};

export function GestaoChaves({
  basePath,
  chavesIniciais,
}: {
  basePath: string;
  chavesIniciais: ChaveApiLer[];
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [tipo, setTipo] = useState<TipoIA>("executora");
  const [provedor, setProvedor] = useState<Provedor>("anthropic");
  const [valor, setValor] = useState("");
  const [apelido, setApelido] = useState("");

  const jaTem = chavesIniciais.some(
    (c) => c.tipo_ia === tipo && c.provedor === provedor,
  );

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function salvar() {
    if (!valor.trim()) return;
    try {
      await api.put(basePath, {
        tipo_ia: tipo,
        provedor,
        valor: valor.trim(),
        apelido: apelido.trim() || null,
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
    if (!confirm(`Remover a chave ${chave.tipo_ia} (••••${chave.ultimos4})?`)) return;
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
                  {ROTULO_TIPO[c.tipo_ia] ?? c.tipo_ia}
                  <span className="text-xs font-normal text-muted-foreground">
                    {c.provedor}
                  </span>
                  {!c.ativa && <Badge>inativa</Badge>}
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
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoIA)}
          >
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {ROTULO_TIPO[t] ?? t}
              </option>
            ))}
          </Select>
          <Select
            className="w-auto"
            value={provedor}
            onChange={(e) => setProvedor(e.target.value as Provedor)}
          >
            {PROVEDORES.map((p) => (
              <option key={p} value={p}>
                {ROTULO_PROVEDOR[p]}
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
        {jaTem && (
          <p className="text-xs text-warning">
            Já existe uma chave “{tipo}” em {ROTULO_PROVEDOR[provedor]}. Salvar vai
            substituí-la.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          A <span className="font-medium">IA executora</span> roda os agentes do
          time (o modelo de cada agente é escolhido na edição do agente). A{" "}
          <span className="font-medium">IA de conversa</span> é a que ajuda a
          montar e ajustar o time — o modelo dela se escolhe logo abaixo.
        </p>
        <Button className="self-start" onClick={salvar}>
          Salvar chave
        </Button>
      </div>
    </div>
  );
}
