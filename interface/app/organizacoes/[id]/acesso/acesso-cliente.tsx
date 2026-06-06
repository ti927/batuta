"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft } from "lucide-react";

import {
  api,
  ErroDaApi,
  type ConviteCriado,
  type ConviteLer,
  type MembroLer,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/organizacoes/${organizacao.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        {organizacao.nome}
      </Link>
      <h1 className="mb-6 mt-2 text-2xl font-medium text-foreground">
        Gerir acesso
      </h1>

      {!souAdmin && (
        <Aviso variant="atencao" className="mb-4">
          Somente administradores desta organização podem gerir o acesso. Você
          está vendo a lista em modo leitura.
        </Aviso>
      )}

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {/* ───────────────── Membros ───────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-lg font-medium text-foreground">Membros</h2>
        {membros.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum membro ainda.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border bg-card">
            {membros.map((m) => (
              <li
                key={m.usuario_id}
                className="flex flex-wrap items-center gap-2 p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 truncate text-sm font-medium text-foreground">
                    {m.nome}
                    {m.usuario_id === meuId && (
                      <span className="text-xs font-normal text-muted-foreground">
                        (você)
                      </span>
                    )}
                    {!m.ativo && <Badge>desativado</Badge>}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {m.email}
                  </p>
                </div>

                {souAdmin ? (
                  <>
                    <Select
                      className="h-8 w-auto"
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
                    </Select>
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
                  <Badge variant="info">{m.papel}</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ───────────────── Convites (só admin) ───────────────── */}
      {souAdmin && (
        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Convites</h2>

          <div className="mb-4 flex flex-wrap gap-2">
            <Input
              type="email"
              className="min-w-[16rem] flex-1"
              placeholder="email@convidado.com"
              value={emailNovo}
              onChange={(e) => setEmailNovo(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && convidar()}
            />
            <Select
              className="w-auto"
              value={papelNovo}
              onChange={(e) => setPapelNovo(e.target.value as PapelAcesso)}
            >
              {PAPEIS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
            <Button onClick={convidar}>Convidar</Button>
          </div>

          {aviso && (
            <Aviso variant="info" className="mb-4">
              {aviso}
            </Aviso>
          )}

          {convites.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum convite.</p>
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border bg-card">
              {convites.map((c) => (
                <li key={c.id} className="flex items-center gap-2 p-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {c.email}
                    </p>
                    <p className="text-xs text-muted-foreground">
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
