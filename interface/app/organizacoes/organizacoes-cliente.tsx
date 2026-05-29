"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi, type Organizacao } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function OrganizacoesCliente({ inicial }: { inicial: Organizacao[] }) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);

  const [nomeNovo, setNomeNovo] = useState("");
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [nomeEdicao, setNomeEdicao] = useState("");

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function criar() {
    if (!nomeNovo.trim()) return;
    try {
      await api.post<Organizacao>("/organizacoes", { nome: nomeNovo.trim() });
      setNomeNovo("");
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao criar");
    }
  }

  async function salvarEdicao(id: string) {
    if (!nomeEdicao.trim()) return;
    try {
      await api.put<Organizacao>(`/organizacoes/${id}`, { nome: nomeEdicao.trim() });
      setEditandoId(null);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao editar");
    }
  }

  async function remover(id: string, nome: string) {
    if (!confirm(`Remover a organização "${nome}"?`)) return;
    try {
      await api.delete(`/organizacoes/${id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover");
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-8">
      <h1 className="mb-6 text-2xl font-bold">Organizações</h1>

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      <div className="mb-6 flex gap-2">
        <input
          className="flex-1 rounded border border-zinc-300 px-3 py-1.5 text-sm"
          placeholder="Nome da nova organização"
          value={nomeNovo}
          onChange={(e) => setNomeNovo(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && criar()}
        />
        <Button onClick={criar}>Criar</Button>
      </div>

      {inicial.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhuma organização ainda.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {inicial.map((org) => (
            <li key={org.id} className="flex items-center gap-2 p-3">
              {editandoId === org.id ? (
                <>
                  <input
                    className="flex-1 rounded border border-zinc-300 px-2 py-1 text-sm"
                    value={nomeEdicao}
                    onChange={(e) => setNomeEdicao(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && salvarEdicao(org.id)}
                    autoFocus
                  />
                  <Button size="sm" onClick={() => salvarEdicao(org.id)}>
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setEditandoId(null)}
                  >
                    Cancelar
                  </Button>
                </>
              ) : (
                <>
                  <Link
                    href={`/organizacoes/${org.id}`}
                    className="flex-1 text-sm text-blue-600 underline underline-offset-4"
                  >
                    {org.nome}
                  </Link>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditandoId(org.id);
                      setNomeEdicao(org.nome);
                    }}
                  >
                    Editar
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => remover(org.id, org.nome)}
                  >
                    Remover
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
