"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Pencil, X } from "lucide-react";

import { api, mensagemDeErro } from "@/lib/api";
import { RotuloSecao } from "@/components/conversa-ia/comum";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";

// Painel "Sobre este time" (Parte B da economia de tokens da IA criadora): o resumo
// rolante que a IA mantém do projeto, agora VISÍVEL e EDITÁVEL. Um card no painel
// direito mostra o começo do resumo e abre um drawer à direita (mesmo padrão da edição
// de agentes/instrumentos), onde o texto inteiro é lido e — por operador+ — editado. A
// edição humana VENCE a da IA (que segue refinando a partir dela).

const VAZIO =
  "A IA ainda está conhecendo o time — o resumo aparece conforme vocês conversam.";

export function PainelSobreTime({
  conversaId,
  resumoInicial,
  podeEditar,
}: {
  conversaId: string;
  resumoInicial: string | null;
  podeEditar: boolean;
}) {
  const [resumo, setResumo] = useState<string | null>(resumoInicial);
  const [aberto, setAberto] = useState(false);
  const previa = (resumo ?? "").trim();

  // Ao abrir, busca o resumo FRESCO: a IA pode tê-lo escrito/condensado durante a
  // conversa desta sessão, e o valor carregado com a página estaria defasado.
  async function abrir() {
    setAberto(true);
    try {
      const r = await api.get<{ resumo: string | null }>(
        `/conversas-criacao/${conversaId}/resumo`,
      );
      setResumo(r.resumo);
    } catch {
      /* mantém o que já tem — não trava a abertura por causa de rede */
    }
  }

  return (
    <div>
      <RotuloSecao Icone={FileText}>Sobre este time</RotuloSecao>
      <button
        onClick={abrir}
        className="w-full rounded-lg border border-border bg-card p-3.5 text-left transition-colors hover:border-[#D6D3E8]"
      >
        <div className="mb-1 flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">Resumo do projeto</span>
          <span className="text-[11px] text-muted-foreground">mantido pela IA</span>
        </div>
        {previa ? (
          <p className="line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">
            {previa}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground/70">{VAZIO}</p>
        )}
        <span className="mt-2 inline-block text-xs text-primary">
          {podeEditar ? "Abrir e editar →" : "Abrir →"}
        </span>
      </button>

      {aberto && (
        <DrawerResumo
          conversaId={conversaId}
          resumo={resumo}
          podeEditar={podeEditar}
          onResumo={setResumo}
          onFechar={() => setAberto(false)}
        />
      )}
    </div>
  );
}

function DrawerResumo({
  conversaId,
  resumo,
  podeEditar,
  onResumo,
  onFechar,
}: {
  conversaId: string;
  resumo: string | null;
  podeEditar: boolean;
  onResumo: (r: string | null) => void;
  onFechar: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [rascunho, setRascunho] = useState(resumo ?? "");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const sujo = editando && rascunho !== (resumo ?? "");

  function fecharGuardado() {
    if (sujo && !confirm("Você tem alterações não salvas. Fechar e descartar?")) return;
    onFechar();
  }

  // Esc fecha (protegendo a edição não salva) — mesma guarda do X e do clique no fundo.
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (sujo && !confirm("Você tem alterações não salvas. Fechar e descartar?")) return;
      onFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [sujo, onFechar]);

  async function salvar() {
    setOcupado(true);
    setErro(null);
    try {
      const limpo = rascunho.trim() || null;
      await api.put(`/conversas-criacao/${conversaId}/resumo`, { resumo: limpo });
      onResumo(limpo);
      setEditando(false);
      toast.success("Resumo atualizado");
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha ao salvar o resumo"));
    } finally {
      setOcupado(false);
    }
  }

  function cancelar() {
    if (sujo && !confirm("Descartar as alterações?")) return;
    setRascunho(resumo ?? "");
    setEditando(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={fecharGuardado}
        aria-label="Fechar"
      />
      <aside className="relative flex h-full w-full max-w-[460px] flex-col overflow-hidden border-l border-border bg-card shadow-xl">
        <header className="flex flex-none items-start gap-3 border-b border-border p-4">
          <FileText className="mt-0.5 size-5 text-primary" />
          <div className="min-w-0 flex-1">
            <h2 className="font-medium text-foreground">Sobre este time</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              O resumo do projeto que a IA mantém — corrija se algo estiver errado.
            </p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={fecharGuardado}
            aria-label="Fechar"
          >
            <X className="size-4" />
          </Button>
        </header>

        {erro && (
          <div className="px-4 pt-4">
            <Aviso>{erro}</Aviso>
          </div>
        )}

        {editando ? (
          <div className="flex min-h-0 flex-1 flex-col p-4">
            <textarea
              value={rascunho}
              onChange={(e) => setRascunho(e.target.value)}
              placeholder="Descreva o que este time é, faz, e o que foi combinado com a IA…"
              className="min-h-0 flex-1 resize-none rounded-md border border-border bg-background p-3 text-sm text-foreground outline-none focus:border-primary"
              autoFocus
            />
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={salvar} disabled={ocupado}>
                Salvar
              </Button>
              <Button size="sm" variant="outline" onClick={cancelar} disabled={ocupado}>
                Cancelar
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
            {podeEditar && (
              <div className="flex gap-2 border-b border-border p-4">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setRascunho(resumo ?? "");
                    setEditando(true);
                  }}
                >
                  <Pencil className="size-4" /> Editar
                </Button>
              </div>
            )}
            <div className="p-4">
              <p className="whitespace-pre-wrap rounded-md bg-background p-3 text-sm text-foreground">
                {(resumo ?? "").trim() || (
                  <span className="text-muted-foreground/70">{VAZIO}</span>
                )}
              </p>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
