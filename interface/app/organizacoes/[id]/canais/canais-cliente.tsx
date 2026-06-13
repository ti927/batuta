"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, Trash2 } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Canal,
  type IdentidadeCanal,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

// Tipos de canal que a interface oferece hoje. O WhatsApp entra como mais um
// quando sua implementação estiver pronta (mesma abstração).
const TIPOS_CANAL = [{ valor: "telegram", rotulo: "Telegram" }];

function mensagemDeErro(e: unknown, padrao: string): string {
  return e instanceof ErroDaApi ? e.message : padrao;
}

export function CanaisCliente({
  organizacao,
  meuPapel,
  canais,
  identidadesPorCanal,
}: {
  organizacao: Organizacao;
  meuPapel: PapelAcesso | null;
  canais: Canal[];
  identidadesPorCanal: Record<string, IdentidadeCanal[]>;
}) {
  const router = useRouter();
  const souAdmin = meuPapel === "admin";
  const podeOperar = meuPapel === "admin" || meuPapel === "operador";
  const basePath = `/organizacoes/${organizacao.id}/canais`;

  const [erro, setErro] = useState<string | null>(null);
  const [tipo, setTipo] = useState("telegram");
  const [nome, setNome] = useState("");
  const [token, setToken] = useState("");

  async function criarCanal() {
    if (!nome.trim() || !token.trim()) return;
    try {
      await api.post(basePath, { tipo, nome: nome.trim(), config: { token: token.trim() } });
      setNome("");
      setToken("");
      setErro(null);
      router.refresh();
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha ao criar o canal"));
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
      <h1 className="mb-2 mt-2 text-2xl font-medium text-foreground">
        Canais de mensageria
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Os canais por onde os times conversam com pessoas (Telegram hoje). O token
        do bot é guardado em cofre e nunca reexibido. As identidades dizem quem é
        cada contato, para o Batuta saber com quem está falando.
      </p>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {/* Lista de canais */}
      {canais.length === 0 ? (
        <p className="mb-6 text-sm text-muted-foreground">
          Nenhum canal configurado ainda.
        </p>
      ) : (
        <ul className="mb-6 flex flex-col gap-3">
          {canais.map((c) => (
            <CartaoCanal
              key={c.id}
              canal={c}
              identidades={identidadesPorCanal[c.id] ?? []}
              basePath={basePath}
              souAdmin={souAdmin}
              podeOperar={podeOperar}
              onErro={setErro}
            />
          ))}
        </ul>
      )}

      {/* Criar canal (só admin) */}
      {souAdmin ? (
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-medium text-foreground">Adicionar um canal</h3>
          <div className="flex flex-wrap gap-2">
            <Select
              className="w-auto"
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
            >
              {TIPOS_CANAL.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.rotulo}
                </option>
              ))}
            </Select>
            <Input
              className="flex-1"
              placeholder="Nome (ex.: Telegram interno da Lure)"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
            />
          </div>
          <Input
            type="password"
            autoComplete="off"
            placeholder="Token do bot (BotFather) — não será reexibido"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && criarCanal()}
          />
          <Button className="self-start" onClick={criarCanal}>
            Adicionar canal
          </Button>
        </div>
      ) : (
        <Aviso variant="atencao">
          Somente administradores podem adicionar ou configurar canais. Operadores
          podem gerir as identidades de cada canal.
        </Aviso>
      )}
    </main>
  );
}

function CartaoCanal({
  canal,
  identidades,
  basePath,
  souAdmin,
  podeOperar,
  onErro,
}: {
  canal: Canal;
  identidades: IdentidadeCanal[];
  basePath: string;
  souAdmin: boolean;
  podeOperar: boolean;
  onErro: (m: string | null) => void;
}) {
  const router = useRouter();
  const [editando, setEditando] = useState(false);
  const [nome, setNome] = useState(canal.nome);
  const [token, setToken] = useState("");
  const [ativo, setAtivo] = useState(canal.ativo);

  async function salvar() {
    if (!nome.trim()) return;
    try {
      const config = token.trim() ? { token: token.trim() } : {};
      await api.put(`${basePath}/${canal.id}`, { nome: nome.trim(), config, ativo });
      setToken("");
      setEditando(false);
      onErro(null);
      router.refresh();
    } catch (e) {
      onErro(mensagemDeErro(e, "Falha ao salvar o canal"));
    }
  }

  async function remover() {
    if (!confirm(`Remover o canal “${canal.nome}” e suas identidades?`)) return;
    try {
      await api.delete(`${basePath}/${canal.id}`);
      onErro(null);
      router.refresh();
    } catch (e) {
      onErro(mensagemDeErro(e, "Falha ao remover o canal"));
    }
  }

  const tokenResumo = canal.segredos?.token;

  return (
    <li className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-medium text-foreground">
            {canal.nome}
            <Badge>{canal.tipo}</Badge>
            {!canal.ativo && <Badge>inativo</Badge>}
          </p>
          <p className="text-xs text-muted-foreground">
            {tokenResumo ? `token termina em ••••${tokenResumo}` : "sem token"}
          </p>
        </div>
        {souAdmin && !editando && (
          <>
            <Button size="sm" variant="secondary" onClick={() => setEditando(true)}>
              Editar
            </Button>
            <Button size="sm" variant="destructive" onClick={remover}>
              Remover
            </Button>
          </>
        )}
      </div>

      {/* Edição do canal (admin) */}
      {souAdmin && editando && (
        <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
          <Input
            placeholder="Nome do canal"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
          />
          <Input
            type="password"
            autoComplete="off"
            placeholder="Trocar o token (em branco mantém o atual)"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={ativo}
              onChange={(e) => setAtivo(e.target.checked)}
            />
            Canal ativo
          </label>
          <div className="flex gap-2">
            <Button size="sm" onClick={salvar}>
              Salvar
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setEditando(false);
                setNome(canal.nome);
                setToken("");
                setAtivo(canal.ativo);
              }}
            >
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {/* Identidades do canal */}
      <IdentidadesDoCanal
        identidades={identidades}
        basePath={`${basePath}/${canal.id}/identidades`}
        podeOperar={podeOperar}
        onErro={onErro}
      />
    </li>
  );
}

function IdentidadesDoCanal({
  identidades,
  basePath,
  podeOperar,
  onErro,
}: {
  identidades: IdentidadeCanal[];
  basePath: string;
  podeOperar: boolean;
  onErro: (m: string | null) => void;
}) {
  const router = useRouter();
  const [identificador, setIdentificador] = useState("");
  const [rotulo, setRotulo] = useState("");

  async function adicionar() {
    if (!identificador.trim()) return;
    try {
      await api.post(basePath, {
        identificador_externo: identificador.trim(),
        rotulo: rotulo.trim() || null,
      });
      setIdentificador("");
      setRotulo("");
      onErro(null);
      router.refresh();
    } catch (e) {
      onErro(mensagemDeErro(e, "Falha ao adicionar a identidade"));
    }
  }

  async function remover(id: string) {
    try {
      await api.delete(`${basePath}/${id}`);
      onErro(null);
      router.refresh();
    } catch (e) {
      onErro(mensagemDeErro(e, "Falha ao remover a identidade"));
    }
  }

  return (
    <div className="mt-3 border-t border-border pt-3">
      <Label className="text-xs uppercase tracking-wide text-muted-foreground">
        Identidades ({identidades.length})
      </Label>
      {identidades.length > 0 && (
        <ul className="mb-2 mt-1 flex flex-col gap-1">
          {identidades.map((i) => (
            <li
              key={i.id}
              className="flex items-center gap-2 text-sm text-foreground"
            >
              <span className="min-w-0 flex-1 truncate">
                {i.rotulo ? (
                  <>
                    {i.rotulo}{" "}
                    <span className="text-xs text-muted-foreground">
                      ({i.identificador_externo})
                    </span>
                  </>
                ) : (
                  <span className="text-muted-foreground">{i.identificador_externo}</span>
                )}
              </span>
              {podeOperar && (
                <button
                  type="button"
                  onClick={() => remover(i.id)}
                  className="text-muted-foreground hover:text-destructive"
                  aria-label="Remover identidade"
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {podeOperar && (
        <div className="mt-1 flex flex-wrap gap-2">
          <Input
            className="w-40"
            placeholder="Identificador (chat_id)"
            value={identificador}
            onChange={(e) => setIdentificador(e.target.value)}
          />
          <Input
            className="flex-1"
            placeholder="Rótulo (ex.: João, consultor)"
            value={rotulo}
            onChange={(e) => setRotulo(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && adicionar()}
          />
          <Button size="sm" variant="secondary" onClick={adicionar}>
            Adicionar
          </Button>
        </div>
      )}
    </div>
  );
}
