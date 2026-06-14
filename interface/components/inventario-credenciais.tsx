"use client";

// Inventário unificado das credenciais POR-INSTÂNCIA dos instrumentos da
// organização (tela "Chaves e credenciais", seção B). Lista todas, mostra onde
// cada uma está (instrumento + time) e ROTACIONA qualquer uma inline — sem caçar
// o formulário de cada instrumento. Os valores nunca são reexibidos (só os 4
// últimos dígitos). Espelha GET /organizacoes/{id}/credenciais e
// PUT /instrumentos/{id}/segredos.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { KeyRound, Lock } from "lucide-react";

import { api, ErroDaApi, type CredencialInstrumento } from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";

export function InventarioCredenciais({
  credenciais,
}: {
  credenciais: CredencialInstrumento[];
}) {
  const router = useRouter();
  // Qual (instrumento, campo) está em edição, e o valor digitado.
  const [editando, setEditando] = useState<string | null>(null);
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  if (credenciais.length === 0) {
    return (
      <EstadoVazio icone={KeyRound} titulo="Nenhuma credencial de instrumento">
        Quando um instrumento usar senha ou token (WordPress, bot, banco…), ele
        aparece aqui para você gerir num lugar só.
      </EstadoVazio>
    );
  }

  async function rotacionar(instrumentoId: string, campo: string) {
    if (!valor.trim()) return;
    setSalvando(true);
    try {
      await api.put(`/instrumentos/${instrumentoId}/segredos`, {
        segredos: { [campo]: valor.trim() },
      });
      setEditando(null);
      setValor("");
      setErro(null);
      router.refresh();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao trocar a credencial");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {erro && <Aviso>{erro}</Aviso>}
      {credenciais.map((c) => (
        <div
          key={c.instrumento_id}
          className="rounded-lg border border-border bg-card p-4"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-sm font-medium text-foreground">
              {c.instrumento_nome}
            </span>
            <span className="text-xs text-muted-foreground">
              {c.tipo_nome} · {c.time_nome}
            </span>
          </div>

          <ul className="mt-2 flex flex-col gap-2">
            {c.campos.map((campo) => {
              const chaveEdicao = `${c.instrumento_id}:${campo.campo}`;
              const emEdicao = editando === chaveEdicao;
              return (
                <li key={campo.campo} className="text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex items-center gap-1.5 text-foreground">
                      <Lock className="size-3 text-muted-foreground" />
                      {campo.campo}
                    </span>
                    {campo.definido ? (
                      <span className="text-xs text-muted-foreground">
                        termina em ••••{campo.ultimos4}
                      </span>
                    ) : campo.compartilhada ? (
                      <Badge>usa a chave da organização</Badge>
                    ) : (
                      <Badge variant="warning">faltando</Badge>
                    )}
                    {!emEdicao && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="ml-auto"
                        onClick={() => {
                          setEditando(chaveEdicao);
                          setValor("");
                          setErro(null);
                        }}
                      >
                        {campo.definido ? "Trocar" : "Definir"}
                      </Button>
                    )}
                  </div>

                  {campo.compartilhada && !campo.definido && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Reusa a chave de {campo.servico} da organização. Defina uma
                      aqui só se quiser uma chave exclusiva deste instrumento.
                    </p>
                  )}

                  {emEdicao && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Input
                        type="password"
                        autoComplete="new-password"
                        className="max-w-xs"
                        placeholder="Cole o novo valor (não será reexibido)"
                        value={valor}
                        onChange={(e) => setValor(e.target.value)}
                        onKeyDown={(e) =>
                          e.key === "Enter" &&
                          rotacionar(c.instrumento_id, campo.campo)
                        }
                        autoFocus
                      />
                      <Button
                        size="sm"
                        disabled={salvando}
                        onClick={() => rotacionar(c.instrumento_id, campo.campo)}
                      >
                        {salvando ? "Salvando…" : "Salvar"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={salvando}
                        onClick={() => {
                          setEditando(null);
                          setValor("");
                        }}
                      >
                        Cancelar
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
