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
import { Button } from "@/components/ui/button";

const TIPOS: TipoIA[] = ["executora", "criadora", "companheira"];

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
      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {/* Lista das chaves cadastradas (mascaradas) */}
      {chavesIniciais.length === 0 ? (
        <p className="mb-6 text-sm text-zinc-500">Nenhuma chave cadastrada.</p>
      ) : (
        <ul className="mb-6 divide-y divide-zinc-200 rounded border border-zinc-200">
          {chavesIniciais.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {c.tipo_ia}
                  <span className="ml-2 text-xs text-zinc-500">{c.provedor}</span>
                  {!c.ativa && (
                    <span className="ml-2 rounded bg-zinc-200 px-1.5 py-0.5 text-xs text-zinc-600">
                      inativa
                    </span>
                  )}
                </p>
                <p className="text-xs text-zinc-500">
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
      <div className="flex flex-col gap-2 rounded border border-zinc-200 p-3">
        <h3 className="text-sm font-semibold">Cadastrar ou trocar uma chave</h3>
        <div className="flex flex-wrap gap-2">
          <select
            className="rounded border border-zinc-300 px-2 py-1.5 text-sm"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoIA)}
          >
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-zinc-300 px-2 py-1.5 text-sm"
            value={provedor}
            onChange={(e) => setProvedor(e.target.value as Provedor)}
          >
            {PROVEDORES.map((p) => (
              <option key={p} value={p}>
                {ROTULO_PROVEDOR[p]}
              </option>
            ))}
          </select>
        </div>
        <input
          type="password"
          autoComplete="off"
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
          placeholder="Cole o valor da chave (não será reexibido)"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
        />
        <input
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
          placeholder="Apelido (opcional)"
          value={apelido}
          onChange={(e) => setApelido(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && salvar()}
        />
        {jaTem && (
          <p className="text-xs text-amber-700">
            Já existe uma chave “{tipo}” em {ROTULO_PROVEDOR[provedor]}. Salvar vai
            substituí-la.
          </p>
        )}
        <p className="text-xs text-zinc-500">
          Nesta fase só a IA <strong>executora</strong> é usada pelo motor; as
          demais ficam reservadas para fases futuras.
        </p>
        <Button className="self-start" onClick={salvar}>
          Salvar chave
        </Button>
      </div>
    </div>
  );
}
