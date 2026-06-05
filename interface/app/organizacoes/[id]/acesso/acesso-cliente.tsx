"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  api,
  ErroDaApi,
  type ConviteCriado,
  type ConviteLer,
  type MembroLer,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { Button } from "@/components/ui/button";

const PAPEIS: PapelAcesso[] = ["admin", "operador", "observador"];

function dataCurta(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR");
}

export function AcessoCliente({
  organizacao,
  meuPapel,
  meuId,
  membros,
  convites,
}: {
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  meuId: string;
  membros: MembroLer[];
  convites: ConviteLer[];
}) {
  const router = useRouter();
  const souAdmin = meuPapel === "admin";
  const [erro, setErro] = useState<string | null>(null);

  const [emailNovo, setEmailNovo] = useState("");
  const [papelNovo, setPapelNovo] = useState<PapelAcesso>("operador");
  const [aviso, setAviso] = useState<string | null>(null);

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function alterarPapel(usuarioId: string, papel: PapelAcesso) {
    try {
      await api.post(
        `/organizacoes/${organizacao.id}/membros/${usuarioId}/papel`,
        { papel },
      );
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao alterar o papel");
    }
  }

  async function removerMembro(usuarioId: string, nome: string) {
    if (!confirm(`Remover ${nome} desta organização?`)) return;
    try {
      await api.delete(`/organizacoes/${organizacao.id}/membros/${usuarioId}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover o membro");
    }
  }

  async function definirAtivo(usuarioId: string, ativar: boolean) {
    try {
      await api.post(
        `/usuarios/${usuarioId}/${ativar ? "reativar" : "desativar"}`,
        {},
      );
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao alterar o status do usuário");
    }
  }

  async function convidar() {
    if (!emailNovo.trim()) return;
    try {
      const r = await api.post<ConviteCriado>(
        `/organizacoes/${organizacao.id}/convites`,
        { email: emailNovo.trim(), papel: papelNovo },
      );
      setEmailNovo("");
      setErro(null);
      // Quem já tem conta não recebe e-mail (o Supabase não reenvia); verá o
      // aviso dentro do Batuta ao entrar. Avisa o admin para não achar que falhou.
      setAviso(
        r.email_enviado
          ? "Convite enviado por e-mail."
          : "Convite criado. Esta pessoa já tem conta — verá o aviso ao entrar no Batuta (nenhum e-mail foi enviado).",
      );
      router.refresh();
    } catch (e) {
      setAviso(null);
      tratar(e, "Falha ao convidar");
    }
  }

  async function revogar(conviteId: string, email: string) {
    if (!confirm(`Revogar o convite de ${email}?`)) return;
    try {
      await api.delete(`/convites/${conviteId}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao revogar o convite");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <div className="mb-1 text-sm">
        <Link
          href={`/organizacoes/${organizacao.id}`}
          className="text-blue-600 underline underline-offset-4"
        >
          ← {organizacao.nome}
        </Link>
      </div>
      <h1 className="mb-6 text-2xl font-bold">Gerir acesso</h1>

      {!souAdmin && (
        <p className="mb-4 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
          Somente administradores desta organização podem gerir o acesso. Você
          está vendo a lista em modo leitura.
        </p>
      )}

      {erro && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {/* ───────────────── Membros ───────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Membros</h2>
        {membros.length === 0 ? (
          <p className="text-sm text-zinc-500">Nenhum membro ainda.</p>
        ) : (
          <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
            {membros.map((m) => (
              <li
                key={m.usuario_id}
                className="flex flex-wrap items-center gap-2 p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {m.nome}
                    {m.usuario_id === meuId && (
                      <span className="ml-1 text-xs text-zinc-400">(você)</span>
                    )}
                    {!m.ativo && (
                      <span className="ml-2 rounded bg-zinc-200 px-1.5 py-0.5 text-xs text-zinc-600">
                        desativado
                      </span>
                    )}
                  </p>
                  <p className="truncate text-xs text-zinc-500">{m.email}</p>
                </div>

                {souAdmin ? (
                  <>
                    <select
                      className="rounded border border-zinc-300 px-2 py-1 text-sm"
                      value={m.papel}
                      onChange={(e) =>
                        alterarPapel(m.usuario_id, e.target.value as PapelAcesso)
                      }
                    >
                      {PAPEIS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                    {m.usuario_id !== meuId && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => definirAtivo(m.usuario_id, !m.ativo)}
                      >
                        {m.ativo ? "Desativar" : "Reativar"}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => removerMembro(m.usuario_id, m.nome)}
                    >
                      Remover
                    </Button>
                  </>
                ) : (
                  <span className="rounded bg-zinc-100 px-2 py-1 text-sm text-zinc-600">
                    {m.papel}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ───────────────── Convites (só admin) ───────────────── */}
      {souAdmin && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Convites</h2>

          <div className="mb-4 flex flex-wrap gap-2">
            <input
              type="email"
              className="min-w-[16rem] flex-1 rounded border border-zinc-300 px-3 py-1.5 text-sm"
              placeholder="email@convidado.com"
              value={emailNovo}
              onChange={(e) => setEmailNovo(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && convidar()}
            />
            <select
              className="rounded border border-zinc-300 px-2 py-1.5 text-sm"
              value={papelNovo}
              onChange={(e) => setPapelNovo(e.target.value as PapelAcesso)}
            >
              {PAPEIS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <Button onClick={convidar}>Convidar</Button>
          </div>

          {aviso && (
            <p className="mb-4 rounded border border-blue-300 bg-blue-50 p-2 text-sm text-blue-800">
              {aviso}
            </p>
          )}

          {convites.length === 0 ? (
            <p className="text-sm text-zinc-500">Nenhum convite.</p>
          ) : (
            <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
              {convites.map((c) => (
                <li key={c.id} className="flex items-center gap-2 p-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{c.email}</p>
                    <p className="text-xs text-zinc-500">
                      {c.papel} · {c.status} · expira {dataCurta(c.expira_em)}
                    </p>
                  </div>
                  {c.status === "pendente" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => revogar(c.id, c.email)}
                    >
                      Revogar
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}
