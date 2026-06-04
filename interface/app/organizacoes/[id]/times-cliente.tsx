"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  type Organizacao,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { Button } from "@/components/ui/button";

export function TimesCliente({
  organizacao,
  inicial,
  meuPapel,
}: {
  organizacao: Organizacao;
  inicial: Time[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souAdmin = podeAdmin(meuPapel);
  const souOperador = podeOperar(meuPapel);

  const [nomeNovo, setNomeNovo] = useState("");
  const [descNova, setDescNova] = useState("");
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [nomeEdicao, setNomeEdicao] = useState("");
  const [descEdicao, setDescEdicao] = useState("");

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function criar() {
    if (!nomeNovo.trim()) return;
    try {
      await api.post<Time>(`/organizacoes/${organizacao.id}/times`, {
        nome: nomeNovo.trim(),
        descricao: descNova.trim() || null,
      });
      setNomeNovo("");
      setDescNova("");
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao criar time");
    }
  }

  async function salvarEdicao(id: string) {
    if (!nomeEdicao.trim()) return;
    try {
      await api.put<Time>(`/times/${id}`, {
        nome: nomeEdicao.trim(),
        descricao: descEdicao.trim() || null,
      });
      setEditandoId(null);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao editar time");
    }
  }

  async function remover(id: string, nome: string) {
    if (!confirm(`Remover o time "${nome}"?`)) return;
    try {
      await api.delete(`/times/${id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover time");
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-8">
      <Link
        href="/organizacoes"
        className="text-sm text-blue-600 underline underline-offset-4"
      >
        ← Organizações
      </Link>
      <h1 className="mt-2 mb-1 text-2xl font-bold">{organizacao.nome}</h1>
      <div className="mb-6 flex items-center gap-3">
        <p className="text-sm text-zinc-500">Times da organização</p>
        {souAdmin && (
          <Link
            href={`/organizacoes/${organizacao.id}/acesso`}
            className="text-sm text-blue-600 underline underline-offset-4"
          >
            Gerir acesso →
          </Link>
        )}
      </div>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {souAdmin && (
        <div className="mb-6 flex flex-col gap-2 rounded border border-zinc-200 p-3">
          <input
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
            placeholder="Nome do novo time"
            value={nomeNovo}
            onChange={(e) => setNomeNovo(e.target.value)}
          />
          <input
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
            placeholder="Descrição (opcional)"
            value={descNova}
            onChange={(e) => setDescNova(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && criar()}
          />
          <Button className="self-start" onClick={criar}>
            Criar time
          </Button>
        </div>
      )}

      {inicial.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhum time ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {inicial.map((time) => (
            <li key={time.id} className="p-3">
              {editandoId === time.id ? (
                <div className="flex flex-col gap-2">
                  <input
                    className="rounded border border-zinc-300 px-2 py-1 text-sm"
                    value={nomeEdicao}
                    onChange={(e) => setNomeEdicao(e.target.value)}
                    autoFocus
                  />
                  <input
                    className="rounded border border-zinc-300 px-2 py-1 text-sm"
                    placeholder="Descrição (opcional)"
                    value={descEdicao}
                    onChange={(e) => setDescEdicao(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && salvarEdicao(time.id)}
                  />
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => salvarEdicao(time.id)}>
                      Salvar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditandoId(null)}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href={`/times/${time.id}`}
                    className="flex-1 text-blue-600 underline underline-offset-4"
                  >
                    <span className="text-sm">{time.nome}</span>
                    {time.descricao && (
                      <span className="block text-xs text-zinc-500 no-underline">
                        {time.descricao}
                      </span>
                    )}
                  </Link>
                  {souOperador && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditandoId(time.id);
                        setNomeEdicao(time.nome);
                        setDescEdicao(time.descricao ?? "");
                      }}
                    >
                      Editar
                    </Button>
                  )}
                  {souAdmin && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => remover(time.id, time.nome)}
                    >
                      Remover
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
