"use client";

// Componente compartilhado de gestão do cofre de chaves de SERVIÇO (Fase 7.5;
// unificação de chaves). Usado em duas telas: chaves da organização e chave-mãe
// da consultoria — a diferença é só o `basePath`. Mostra as chaves MASCARADAS (só
// os 4 últimos dígitos; o valor nunca volta do cérebro) e permite cadastrar/
// trocar/remover. Salvar um serviço (e tipo de IA) que já existe SUBSTITUI a chave.
// Inclui serviços não-modelo compartilháveis (Tavily/busca), que os instrumentos
// reusam — por isso "serviço", não só "provedor de IA".

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ErroDaApi, type ChaveApiLer, type TipoIA } from "@/lib/api";
import {
  ROTULO_SERVICO,
  SERVICOS,
  USADA_POR,
  type Servico,
} from "@/lib/modelos";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

// Dois tipos de IA consomem chave: a executora (os agentes do time) e a IA de
// conversa (a criadora/companheira). Serviços não-IA (Tavily) não têm essa
// distinção — usam sempre o bucket "executora".
const TIPOS: TipoIA[] = ["executora", "criadora"];
const ROTULO_TIPO: Record<string, string> = {
  executora: "IA executora (agentes)",
  criadora: "IA de conversa",
  companheira: "IA de conversa",
};

// Serviços que distinguem papel (executora × conversa). Tavily não distingue.
function temPapel(servico: string): boolean {
  return servico !== "tavily";
}

export function GestaoChaves({
  basePath,
  chavesIniciais,
}: {
  basePath: string;
  chavesIniciais: ChaveApiLer[];
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [tipo, setTipo] = useState<TipoIA>("executora");
  const [servico, setServico] = useState<Servico>("anthropic");
  const [valor, setValor] = useState("");
  const [apelido, setApelido] = useState("");

  // Tavily não tem papel: força executora.
  const tipoEfetivo: TipoIA = temPapel(servico) ? tipo : "executora";
  const jaTem = chavesIniciais.some(
    (c) => c.tipo_ia === tipoEfetivo && c.provedor === servico,
  );

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  async function salvar() {
    if (!valor.trim()) return;
    try {
      await api.put(basePath, {
        tipo_ia: tipoEfetivo,
        provedor: servico,
        valor: valor.trim(),
        apelido: apelido.trim() || null,
      });
      setValor("");
      setApelido("");
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar a chave");
    }
  }

  async function remover(chave: ChaveApiLer) {
    const rotulo = ROTULO_SERVICO[chave.provedor as Servico] ?? chave.provedor;
    if (!confirm(`Remover a chave ${rotulo} (••••${chave.ultimos4})?`)) return;
    try {
      await api.delete(`${basePath}/${chave.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover a chave");
    }
  }

  return (
    <div>
      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {/* Lista das chaves cadastradas (mascaradas) */}
      {chavesIniciais.length === 0 ? (
        <p className="mb-6 text-sm text-muted-foreground">
          Nenhuma chave cadastrada.
        </p>
      ) : (
        <ul className="mb-6 divide-y divide-border rounded-lg border border-border bg-card">
          {chavesIniciais.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                  {ROTULO_SERVICO[c.provedor as Servico] ?? c.provedor}
                  {temPapel(c.provedor) && (
                    <span className="text-xs font-normal text-muted-foreground">
                      {ROTULO_TIPO[c.tipo_ia] ?? c.tipo_ia}
                    </span>
                  )}
                  {!c.ativa && <Badge>inativa</Badge>}
                </p>
                <p className="text-xs text-muted-foreground">
                  termina em ••••{c.ultimos4}
                  {c.apelido ? ` · ${c.apelido}` : ""}
                </p>
              </div>
              <Button size="sm" variant="destructive" onClick={() => remover(c)}>
                Remover
              </Button>
            </li>
          ))}
        </ul>
      )}

      {/* Formulário de cadastro/troca */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-medium text-foreground">
          Cadastrar ou trocar uma chave
        </h3>
        <div className="flex flex-wrap gap-2">
          <Select
            className="w-auto"
            value={servico}
            onChange={(e) => setServico(e.target.value as Servico)}
          >
            {SERVICOS.map((s) => (
              <option key={s} value={s}>
                {ROTULO_SERVICO[s]}
              </option>
            ))}
          </Select>
          {temPapel(servico) && (
            <Select
              className="w-auto"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoIA)}
            >
              {TIPOS.map((t) => (
                <option key={t} value={t}>
                  {ROTULO_TIPO[t] ?? t}
                </option>
              ))}
            </Select>
          )}
        </div>
        <Input
          type="password"
          autoComplete="off"
          placeholder="Cole o valor da chave (não será reexibido)"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
        />
        <Input
          placeholder="Apelido (opcional)"
          value={apelido}
          onChange={(e) => setApelido(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && salvar()}
        />
        {jaTem && (
          <p className="text-xs text-warning">
            Já existe uma chave de {ROTULO_SERVICO[servico]}
            {temPapel(servico) ? ` (${ROTULO_TIPO[tipoEfetivo]})` : ""}. Salvar vai
            substituí-la.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Usada por: <span className="font-medium">{USADA_POR[servico]}</span>.
        </p>
        <Button className="self-start" onClick={salvar}>
          Salvar chave
        </Button>
      </div>
    </div>
  );
}
