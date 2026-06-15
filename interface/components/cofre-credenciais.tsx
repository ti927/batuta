"use client";

// Caixa-forte de credenciais nomeadas (FASE Caixa-forte, Passo 6). Substitui o
// antigo "inventário por-instrumento". O usuário cria credenciais nomeadas
// ("WordPress Blog" = usuario+senha_app); os instrumentos as referenciam. Trocar
// num lugar só vale para todos. Valores secretos nunca voltam (só os 4 últimos).
//
// Serve a duas telas pela diferença de caminho:
// - organização: lista = /organizacoes/{id}/credenciais (POST); item = /credenciais/{id}
// - consultoria: lista = /credenciais-consultoria (POST/item) + toggle "compartilhável"
//
// Na tela da organização a lista inclui as credenciais da consultoria marcadas
// como compartilháveis — exibidas como somente-leitura (geridas na consultoria).

import { useRouter } from "next/navigation";
import { useState } from "react";
import { KeyRound } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Credencial,
  type TipoCredencial,
} from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

type Edicao = { modo: "criar" } | { modo: "editar"; cred: Credencial } | null;

export function CofreCredenciais({
  credenciais,
  tipos,
  organizacaoId,
  ehConsultoria = false,
}: {
  credenciais: Credencial[];
  tipos: TipoCredencial[];
  organizacaoId?: string;
  ehConsultoria?: boolean;
}) {
  const router = useRouter();
  const [edicao, setEdicao] = useState<Edicao>(null);
  const [erro, setErro] = useState<string | null>(null);

  const caminhoCriar = ehConsultoria
    ? "/credenciais-consultoria"
    : `/organizacoes/${organizacaoId}/credenciais`;
  const caminhoItem = (id: string) =>
    ehConsultoria ? `/credenciais-consultoria/${id}` : `/credenciais/${id}`;

  // Uma credencial é gerível nesta tela se for do mesmo escopo (org vs consultoria).
  const gerivel = (c: Credencial) =>
    ehConsultoria ? c.organizacao_id === null : c.organizacao_id !== null;

  function rotuloTipo(tipo: string) {
    return tipos.find((t) => t.tipo === tipo)?.nome_exibicao ?? tipo;
  }

  async function apagar(c: Credencial) {
    if (!confirm(`Apagar a credencial "${c.nome}"?`)) return;
    try {
      await api.delete(caminhoItem(c.id));
      setErro(null);
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao apagar a credencial");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {erro && <Aviso>{erro}</Aviso>}

      {credenciais.length === 0 ? (
        <EstadoVazio icone={KeyRound} titulo="Nenhuma credencial">
          Crie credenciais nomeadas (senha do WordPress, banco, bot…) e os
          instrumentos passam a apontar para elas — você troca num lugar só.
        </EstadoVazio>
      ) : (
        <ul className="flex flex-col gap-2">
          {credenciais.map((c) => {
            const resumo = c.resumo ?? {};
            return (
              <li
                key={c.id}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-sm font-medium text-foreground">
                    {c.nome}
                  </span>
                  <Badge>{rotuloTipo(c.tipo)}</Badge>
                  {!ehConsultoria && c.organizacao_id === null && (
                    <Badge>da consultoria</Badge>
                  )}
                  {ehConsultoria && (
                    <Badge variant={c.compartilhavel ? "success" : "neutral"}>
                      {c.compartilhavel ? "compartilhável" : "privada"}
                    </Badge>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">
                    usado por {c.usado_por}{" "}
                    {c.usado_por === 1 ? "instrumento" : "instrumentos"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {Object.entries(resumo).map(([campo, r], i) => (
                    <span key={campo}>
                      {i > 0 && " · "}
                      {campo}:{" "}
                      {r.secreto ? `••••${r.ultimos4 || "—"}` : r.valor || "—"}
                    </span>
                  ))}
                </p>
                {gerivel(c) && (
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEdicao({ modo: "editar", cred: c });
                        setErro(null);
                      }}
                    >
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => apagar(c)}
                    >
                      Apagar
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {edicao ? (
        <FormularioCredencial
          key={edicao.modo === "editar" ? edicao.cred.id : "criar"}
          tipos={tipos}
          ehConsultoria={ehConsultoria}
          credencial={edicao.modo === "editar" ? edicao.cred : null}
          caminhoCriar={caminhoCriar}
          caminhoItem={caminhoItem}
          onPronto={() => {
            setEdicao(null);
            router.refresh();
          }}
          onCancelar={() => setEdicao(null)}
          onErro={setErro}
        />
      ) : (
        <Button
          className="self-start"
          variant="outline"
          onClick={() => {
            setEdicao({ modo: "criar" });
            setErro(null);
          }}
        >
          Nova credencial
        </Button>
      )}
    </div>
  );
}

function FormularioCredencial({
  tipos,
  ehConsultoria,
  credencial,
  caminhoCriar,
  caminhoItem,
  onPronto,
  onCancelar,
  onErro,
}: {
  tipos: TipoCredencial[];
  ehConsultoria: boolean;
  credencial: Credencial | null; // null = criar
  caminhoCriar: string;
  caminhoItem: (id: string) => string;
  onPronto: () => void;
  onCancelar: () => void;
  onErro: (m: string | null) => void;
}) {
  const editando = credencial !== null;
  const [tipoSel, setTipoSel] = useState(credencial?.tipo ?? tipos[0]?.tipo ?? "");
  const [nome, setNome] = useState(credencial?.nome ?? "");
  const [compartilhavel, setCompartilhavel] = useState(
    credencial?.compartilhavel ?? false,
  );
  // Valor por campo. Na edição, identidade vem pré-preenchida do resumo; segredo
  // fica em branco (em branco = manter o atual).
  const [valores, setValores] = useState<Record<string, string>>(() => {
    const inicial: Record<string, string> = {};
    if (credencial?.resumo) {
      for (const [campo, r] of Object.entries(credencial.resumo)) {
        if (!r.secreto && r.valor) inicial[campo] = r.valor;
      }
    }
    return inicial;
  });
  const [salvando, setSalvando] = useState(false);

  const tipo = tipos.find((t) => t.tipo === tipoSel);

  async function salvar() {
    if (!nome.trim()) {
      onErro("Dê um nome à credencial.");
      return;
    }
    setSalvando(true);
    try {
      const dados: Record<string, string> = {};
      for (const c of tipo?.campos ?? []) {
        const v = (valores[c.nome] ?? "").trim();
        if (v) dados[c.nome] = v;
      }
      if (editando) {
        await api.put(caminhoItem(credencial!.id), {
          nome: nome.trim(),
          dados,
          compartilhavel,
        });
      } else {
        await api.post(caminhoCriar, {
          nome: nome.trim(),
          tipo: tipoSel,
          dados,
          compartilhavel,
        });
      }
      onErro(null);
      onPronto();
    } catch (e) {
      onErro(e instanceof ErroDaApi ? e.message : "Falha ao salvar a credencial");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-foreground">
        {editando ? "Editar credencial" : "Nova credencial"}
      </h3>

      <div className="flex flex-col gap-1">
        <Label htmlFor="cred-tipo">Tipo</Label>
        <Select
          id="cred-tipo"
          value={tipoSel}
          disabled={editando}
          onChange={(e) => {
            setTipoSel(e.target.value);
            setValores({});
          }}
        >
          {tipos.map((t) => (
            <option key={t.tipo} value={t.tipo}>
              {t.nome_exibicao}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="cred-nome">Nome</Label>
        <Input
          id="cred-nome"
          placeholder="Ex.: WordPress do Blog"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
      </div>

      {tipo?.campos.map((campo) => (
        <div key={campo.nome} className="flex flex-col gap-1">
          <Label htmlFor={`cred-${campo.nome}`}>{campo.rotulo}</Label>
          <Input
            id={`cred-${campo.nome}`}
            type={campo.secreto ? "password" : "text"}
            autoComplete={campo.secreto ? "new-password" : "off"}
            placeholder={
              campo.secreto && editando
                ? "Deixe em branco para manter"
                : campo.rotulo
            }
            value={valores[campo.nome] ?? ""}
            onChange={(e) =>
              setValores((v) => ({ ...v, [campo.nome]: e.target.value }))
            }
          />
        </div>
      ))}

      {ehConsultoria && (
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="size-4 rounded border-border"
            checked={compartilhavel}
            onChange={(e) => setCompartilhavel(e.target.checked)}
          />
          Pode ser compartilhada com as organizações
        </label>
      )}

      <div className="flex gap-2">
        <Button disabled={salvando} onClick={salvar}>
          {salvando ? "Salvando…" : "Salvar"}
        </Button>
        <Button variant="ghost" disabled={salvando} onClick={onCancelar}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
