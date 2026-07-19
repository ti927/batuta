"use client";

import { useEffect, useRef, useState } from "react";

import {
  api,
  mensagemDeErro,
  type Organizacao,
} from "@/lib/api";
import { lerImagemRedimensionada } from "@/lib/imagem";
import { AvatarOrg } from "@/components/avatar-org";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Form de organização em modal, para CRIAR (organizacao=null) e EDITAR. Campos:
// nome + logo (a imagem é encolhida no navegador e enviada como data URI no mesmo
// JSON). Segue o espírito do FormularioAgente: salva e devolve em onSalvo.
export function FormularioOrganizacao({
  organizacao,
  onSalvo,
  onCancelar,
}: {
  organizacao: Organizacao | null;
  onSalvo: (salva: Organizacao) => void;
  onCancelar: () => void;
}) {
  const [nome, setNome] = useState(organizacao?.nome ?? "");
  const [logoUrl, setLogoUrl] = useState<string | null>(
    organizacao?.logo_url ?? null,
  );
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const inputArquivo = useRef<HTMLInputElement>(null);

  // Esc fecha o modal.
  useEffect(() => {
    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") onCancelar();
    }
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [onCancelar]);

  async function escolherArquivo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // permite re-escolher o mesmo arquivo depois
    if (!file) return;
    try {
      setLogoUrl(await lerImagemRedimensionada(file));
      setErro(null);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao ler a imagem");
    }
  }

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    setSalvando(true);
    try {
      const corpo = { nome: nome.trim(), logo_url: logoUrl };
      const salva = organizacao
        ? await api.put<Organizacao>(`/organizacoes/${organizacao.id}`, corpo)
        : await api.post<Organizacao>("/organizacoes", corpo);
      setErro(null);
      onSalvo(salva);
    } catch (err) {
      setErro(mensagemDeErro(err, "Falha ao salvar"));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onCancelar}
    >
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-medium text-foreground">
          {organizacao ? "Editar organização" : "Nova organização"}
        </h2>

        {erro && <Aviso className="mb-3">{erro}</Aviso>}

        <Label className="flex-col items-start gap-1">
          Nome
          <Input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && salvar()}
            autoFocus
          />
        </Label>

        <div className="mt-4">
          <span className="text-sm font-medium text-foreground">Logo</span>
          <div className="mt-1 flex items-center gap-3">
            <AvatarOrg
              nome={nome || "?"}
              logoUrl={logoUrl}
              className="size-14 text-xl"
            />
            <div className="flex flex-col gap-1">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => inputArquivo.current?.click()}
              >
                {logoUrl ? "Trocar imagem" : "Escolher imagem"}
              </Button>
              {logoUrl && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setLogoUrl(null)}
                >
                  Remover logo
                </Button>
              )}
            </div>
            <input
              ref={inputArquivo}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={escolherArquivo}
            />
          </div>
        </div>

        <div className="mt-6 flex gap-2">
          <Button onClick={salvar} disabled={salvando}>
            {salvando ? "Salvando…" : "Salvar"}
          </Button>
          <Button variant="ghost" onClick={onCancelar} disabled={salvando}>
            Cancelar
          </Button>
        </div>
      </div>
    </div>
  );
}
