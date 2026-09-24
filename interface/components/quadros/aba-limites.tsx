"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro } from "@/lib/api";
import { type LimiteQuadro, type QuadroDetalhe, type Resposta, rotaQuadros } from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AbaLimites({
  organizacaoId,
  detalhe,
  opera,
  aoMudar,
}: {
  organizacaoId: string;
  detalhe: QuadroDetalhe;
  opera: boolean;
  aoMudar: () => void;
}) {
  const base = rotaQuadros(organizacaoId, detalhe.quadro.id);
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Quando um limite é atingido, quem estava gravando recebe o aviso dizendo o que fazer. Todos podem ser ajustados.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {detalhe.quadro.limites.map((l) => (
          <CartaoLimite key={l.chave} base={base} limite={l} opera={opera} aoMudar={aoMudar} />
        ))}
      </div>
    </div>
  );
}

function CartaoLimite({
  base,
  limite,
  opera,
  aoMudar,
}: {
  base: string;
  limite: LimiteQuadro;
  opera: boolean;
  aoMudar: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState(String(limite.valor));
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function salvar(novo: number | null) {
    setOcupado(true);
    setErro(null);
    try {
      const r = await api.post<Resposta<object>>(`${base}/estrutura`, {
        operacoes: [{ acao: "ajustar_limite", limite: limite.chave, valor: novo }],
      });
      if (!r.ok) return setErro(r.erro);
      toast.success(novo === null ? "Limite voltou ao padrão" : "Limite ajustado");
      setEditando(false);
      aoMudar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-sm font-medium text-foreground">{limite.rotulo}</div>
      {editando ? (
        <div className="mt-2 flex flex-col gap-2">
          <Input
            id={`limite-${limite.chave}`}
            aria-label={limite.rotulo}
            inputMode="numeric"
            value={valor}
            onChange={(e) => setValor(e.target.value.replace(/\D/g, ""))}
          />
          {erro && <Aviso>{erro}</Aviso>}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={ocupado || !valor} onClick={() => salvar(Number(valor))}>Salvar</Button>
            {limite.ajustado && (
              <Button size="sm" variant="outline" disabled={ocupado} onClick={() => salvar(null)}>Voltar ao padrão</Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setEditando(false)}>Cancelar</Button>
          </div>
        </div>
      ) : (
        <>
          <div className="mt-1 font-heading text-2xl font-medium tabular-nums text-foreground">
            {limite.valor.toLocaleString("pt-BR")}
          </div>
          <div className="text-xs text-muted-foreground">
            {limite.ajustado ? `ajustado · padrão ${limite.padrao.toLocaleString("pt-BR")}` : "padrão"} · máximo{" "}
            {limite.teto.toLocaleString("pt-BR")}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">Ao passar: {limite.ao_estourar}.</div>
          {opera && (
            <Button size="sm" variant="ghost" className="mt-2 -ml-2" onClick={() => setEditando(true)}>
              <Pencil /> Ajustar
            </Button>
          )}
        </>
      )}
    </div>
  );
}
