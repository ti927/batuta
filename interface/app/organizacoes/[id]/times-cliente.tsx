"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, Copy, KeyRound, Users, UsersRound, X } from "lucide-react";
import { toast } from "sonner";

import {
  api,
  mensagemDeErro,
  type Organizacao,
  type PapelAcesso,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

  // Duplicar: copia o time inteiro (agentes, instrumentos, cinto, automações e a
  // memória da IA) na mesma organização. As automações nascem pausadas e os canais
  // desconectados. Pergunta só o nome.
  const [duplicando, setDuplicando] = useState<Time | null>(null);
  const [nomeDupla, setNomeDupla] = useState("");
  const [erroDupla, setErroDupla] = useState<string | null>(null);
  const [salvandoDupla, setSalvandoDupla] = useState(false);

  function tratar(e: unknown, padrao: string) {
    setErro(mensagemDeErro(e, padrao));
  }

  function abrirDuplicar(time: Time) {
    setNomeDupla(`Cópia de ${time.nome}`);
    setErroDupla(null);
    setDuplicando(time);
  }

  async function confirmarDuplicacao() {
    if (!duplicando || salvandoDupla) return;
    if (!nomeDupla.trim()) {
      setErroDupla("Dê um nome à cópia.");
      return;
    }
    setSalvandoDupla(true);
    setErroDupla(null);
    try {
      const novo = await api.post<Time>(`/times/${duplicando.id}/duplicar`, {
        nome: nomeDupla.trim(),
      });
      toast.success(`Time copiado: “${novo.nome}”.`);
      router.push(`/times/${novo.id}`);
    } catch (e) {
      const msg = mensagemDeErro(e, "Falha ao duplicar o time");
      setErroDupla(msg);
      toast.error(msg);
      setSalvandoDupla(false);
    }
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
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href="/organizacoes"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Organizações
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">
        {organizacao.nome}
      </h1>
      <div className="mb-6 mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
        <p className="text-sm text-muted-foreground">Times da organização</p>
        {souAdmin && (
          <>
            <Link
              href={`/organizacoes/${organizacao.id}/acesso`}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              <UsersRound className="size-3.5" />
              Gerir acesso
            </Link>
            <Link
              href={`/organizacoes/${organizacao.id}/chaves`}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              <KeyRound className="size-3.5" />
              Chaves e credenciais
            </Link>
          </>
        )}
      </div>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {souAdmin && (
        <div className="mb-6 flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <Input
            placeholder="Nome do novo time"
            value={nomeNovo}
            onChange={(e) => setNomeNovo(e.target.value)}
          />
          <Input
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
        <EstadoVazio icone={Users} titulo="Nenhum time ainda.">
          {souAdmin
            ? "Crie o primeiro time acima para começar."
            : "Os times desta organização aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((time) => (
            <li key={time.id} className="p-3">
              {editandoId === time.id ? (
                <div className="flex flex-col gap-2">
                  <Input
                    className="h-8"
                    value={nomeEdicao}
                    onChange={(e) => setNomeEdicao(e.target.value)}
                    autoFocus
                  />
                  <Input
                    className="h-8"
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
                  <Link href={`/times/${time.id}`} className="group flex-1">
                    <span className="text-sm font-medium text-foreground group-hover:text-primary group-hover:underline">
                      {time.nome}
                    </span>
                    {time.descricao && (
                      <span className="block text-xs text-muted-foreground">
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
                      variant="outline"
                      onClick={() => abrirDuplicar(time)}
                      title="Duplicar este time (agentes, instrumentos, automações e a memória da IA)"
                    >
                      <Copy /> Duplicar
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

      {duplicando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-foreground/20"
            onClick={() => !salvandoDupla && setDuplicando(null)}
            aria-label="Fechar"
          />
          <div className="relative w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-lg font-medium text-foreground">
                Duplicar time
              </h2>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setDuplicando(null)}
                disabled={salvandoDupla}
                aria-label="Fechar"
              >
                <X className="size-4" />
              </Button>
            </div>

            {erroDupla && (
              <div className="mb-3">
                <Aviso>{erroDupla}</Aviso>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <Label className="flex-col items-start gap-1">
                Nome da cópia
                <Input
                  autoFocus
                  value={nomeDupla}
                  onChange={(e) => setNomeDupla(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") confirmarDuplicacao();
                  }}
                  placeholder="Nome do novo time"
                  className="w-full"
                />
              </Label>
              <p className="text-xs text-muted-foreground">
                A cópia leva os agentes, instrumentos, automações e a memória da IA.
                As automações nascem <strong>pausadas</strong> e os canais
                (Telegram/WhatsApp) <strong>desconectados</strong> — reconecte e
                ative quando quiser.
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setDuplicando(null)}
                  disabled={salvandoDupla}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={confirmarDuplicacao}
                  disabled={salvandoDupla || !nomeDupla.trim()}
                >
                  {salvandoDupla ? "Duplicando…" : "Duplicar"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
