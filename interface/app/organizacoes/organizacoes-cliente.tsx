"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Building2, KeyRound } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { podeAdmin } from "@/lib/permissoes";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";

export function OrganizacoesCliente({
  inicial,
  papeis,
  adminConsultoria,
}: {
  inicial: Organizacao[];
  papeis: Record<string, PapelAcesso>;
  adminConsultoria: boolean;
}) {
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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-1">
        <h1 className="text-2xl font-medium text-foreground">Organizações</h1>
        {adminConsultoria && (
          <Link
            href="/chaves-consultoria"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <KeyRound className="size-3.5" />
            Chave-mãe da consultoria
          </Link>
        )}
      </div>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      <div className="mb-6 flex gap-2">
        <Input
          placeholder="Nome da nova organização"
          value={nomeNovo}
          onChange={(e) => setNomeNovo(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && criar()}
        />
        <Button onClick={criar}>Criar</Button>
      </div>

      {inicial.length === 0 ? (
        <EstadoVazio icone={Building2} titulo="Você ainda não tem organizações.">
          Crie a primeira acima para começar.
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((org) => (
            <li key={org.id} className="flex items-center gap-2 p-3">
              {editandoId === org.id ? (
                <>
                  <Input
                    className="h-8 flex-1"
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
                    className="flex-1 text-sm font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {org.nome}
                  </Link>
                  {podeAdmin(papeis[org.id]) && (
                    <>
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
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
