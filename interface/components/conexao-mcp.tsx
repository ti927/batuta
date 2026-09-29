"use client";

// "COMO O BATUTA SE CONECTA" — a identificação de um servidor MCP, dentro do instrumento.
//
// Até 2026-09-29 o instrumento MCP só aceitava endereço + token, e o token morava numa
// credencial da central. Servidores reais pedem outras coisas: o WordPress quer usuário
// e senha de aplicativo, muita API quer um cabeçalho próprio (X-API-Key). Decisão do
// maestro: a identificação de um instrumento mora NO instrumento.
//
// Os valores continuam no mesmo `valores` do formulário (texto por campo), para o
// salvamento genérico não mudar: segredo em branco = manter o que está guardado.

import { useState } from "react";
import { ChevronDown, Lock, Plus, Trash2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

// Os campos da configuração que ESTA seção desenha (o formulário genérico os pula).
export const CAMPOS_CONEXAO_MCP = new Set([
  "url",
  "transport",
  "auth_modo",
  "auth_nome",
  "auth_usuario",
  "auth_segredo",
  "cabecalhos",
  "cabecalhos_secretos",
  "token_bearer",
]);

const MODOS = [
  { v: "nenhuma", rotulo: "Não pede identificação" },
  { v: "url_secreta", rotulo: "A chave já está no endereço (Make, Zapier)" },
  { v: "bearer", rotulo: "Token" },
  { v: "cabecalho", rotulo: "Cabeçalho próprio (ex.: X-API-Key)" },
  { v: "query", rotulo: "Chave no endereço, como parâmetro" },
  { v: "basic", rotulo: "Usuário e senha" },
] as const;

const TRANSPORTES = [
  { v: "automatico", rotulo: "Automático" },
  { v: "streamable_http", rotulo: "HTTP" },
  { v: "sse", rotulo: "SSE (servidores antigos)" },
];

type Linha = { nome: string; valor: string; protegido: boolean };

function lerCabecalhosPublicos(texto: string): Linha[] {
  try {
    const obj = JSON.parse(texto || "{}");
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      return Object.entries(obj).map(([nome, valor]) => ({
        nome,
        valor: String(valor),
        protegido: false,
      }));
    }
  } catch {
    /* texto inválido: começa vazio */
  }
  return [];
}

/** O modo de um instrumento salvo antes do campo existir: token = Bearer, senão nenhum. */
export function modoInicialMCP(
  configurado: string | undefined,
  segredos: Record<string, string> | undefined,
  criando: boolean,
): string {
  if (configurado) return configurado;
  if (criando) return "nenhuma";
  return segredos?.token_bearer ? "bearer" : "nenhuma";
}

export function ConexaoMCP({
  valores,
  mudar,
  guardados,
  modoSalvo,
  cobertos,
}: {
  valores: Record<string, string>;
  mudar: (campo: string, valor: string) => void;
  /** Segredos já guardados: campo → 4 últimos caracteres. */
  guardados: Record<string, string>;
  /** O modo que está salvo — trocar de modo não reaproveita o segredo do anterior. */
  modoSalvo: string;
  /** Campos que uma credencial antiga da central ainda fornece (não aparecem aqui). */
  cobertos: Set<string>;
}) {
  const modo = valores.auth_modo || "nenhuma";
  const [linhas, setLinhas] = useState<Linha[]>(() =>
    lerCabecalhosPublicos(valores.cabecalhos ?? ""),
  );
  const [extrasAbertos, setExtrasAbertos] = useState(
    () => linhas.length > 0 || Boolean(guardados.cabecalhos_secretos),
  );

  function gravarLinhas(novas: Linha[]) {
    setLinhas(novas);
    const publicos: Record<string, string> = {};
    const protegidos: Record<string, string> = {};
    for (const l of novas) {
      if (!l.nome.trim()) continue;
      (l.protegido ? protegidos : publicos)[l.nome.trim()] = l.valor;
    }
    mudar("cabecalhos", JSON.stringify(publicos));
    // Protegido em branco = manter os guardados (a regra de todo campo secreto).
    mudar(
      "cabecalhos_secretos",
      Object.keys(protegidos).length ? JSON.stringify(protegidos) : "",
    );
  }

  function campoSecreto(campo: string, rotulo: string, ajuda?: string) {
    const guardado = modo === modoSalvo ? guardados[campo] : undefined;
    return (
      <Label className="flex-col items-start gap-1">
        <span className="flex items-center gap-1.5">
          <Lock className="size-3 text-muted-foreground" />
          {rotulo}
        </span>
        <Input
          type="password"
          autoComplete="new-password"
          value={valores[campo] ?? ""}
          onChange={(e) => mudar(campo, e.target.value)}
          placeholder={guardado ? `guardado •••• ${guardado} — deixe em branco para manter` : ""}
        />
        {ajuda && <span className="text-xs font-normal text-muted-foreground">{ajuda}</span>}
      </Label>
    );
  }

  function campoAberto(campo: string, rotulo: string, exemplo: string) {
    return (
      <Label className="flex-col items-start gap-1">
        {rotulo}
        <Input
          value={valores[campo] ?? ""}
          onChange={(e) => mudar(campo, e.target.value)}
          placeholder={exemplo}
        />
      </Label>
    );
  }

  return (
    <section className="flex flex-col gap-3 rounded-md border border-border p-3">
      <h3 className="text-sm font-semibold text-foreground">Como o Batuta se conecta</h3>

      {cobertos.has("url") ? (
        <p className="text-xs text-muted-foreground">
          O endereço vem da credencial da central indicada acima.
        </p>
      ) : (
        campoSecreto(
          "url",
          "Endereço do servidor",
          "Se o endereço já traz a chave, como no Make e no Zapier, basta ele.",
        )
      )}

      <Label className="flex-col items-start gap-1">
        Como o servidor pede identificação
        <Select value={modo} onChange={(e) => mudar("auth_modo", e.target.value)}>
          {MODOS.map((m) => (
            <option key={m.v} value={m.v}>
              {m.rotulo}
            </option>
          ))}
        </Select>
      </Label>

      {modo === "bearer" &&
        !cobertos.has("token_bearer") &&
        campoSecreto("token_bearer", "Token")}
      {modo === "cabecalho" && (
        <>
          {campoAberto("auth_nome", "Nome do cabeçalho", "X-API-Key")}
          {campoSecreto("auth_segredo", "Valor")}
        </>
      )}
      {modo === "query" && (
        <>
          {campoAberto("auth_nome", "Nome do parâmetro", "api_key")}
          {campoSecreto("auth_segredo", "Valor")}
        </>
      )}
      {modo === "basic" && (
        <>
          {campoAberto("auth_usuario", "Usuário", "")}
          {campoSecreto(
            "auth_segredo",
            "Senha",
            "No WordPress, use uma senha de aplicativo, não a senha de entrar.",
          )}
        </>
      )}

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => setExtrasAbertos((v) => !v)}
          className="flex items-center gap-1 self-start text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ChevronDown
            className={`size-3.5 transition-transform ${extrasAbertos ? "" : "-rotate-90"}`}
          />
          Cabeçalhos extras
        </button>
        {extrasAbertos && (
          <div className="flex flex-col gap-2 pl-4">
            {guardados.cabecalhos_secretos && (
              <span className="text-xs text-muted-foreground">
                Há cabeçalhos protegidos guardados. Os protegidos que você adicionar aqui
                substituem os guardados.
              </span>
            )}
            {linhas.map((l, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <Input
                  className="w-36"
                  value={l.nome}
                  placeholder="nome"
                  onChange={(e) =>
                    gravarLinhas(linhas.map((x, j) => (j === i ? { ...x, nome: e.target.value } : x)))
                  }
                />
                <Input
                  className="min-w-0 flex-1"
                  type={l.protegido ? "password" : "text"}
                  autoComplete="new-password"
                  value={l.valor}
                  placeholder="valor"
                  onChange={(e) =>
                    gravarLinhas(linhas.map((x, j) => (j === i ? { ...x, valor: e.target.value } : x)))
                  }
                />
                <label className="flex items-center gap-1 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    className="size-3.5 accent-primary"
                    checked={l.protegido}
                    onChange={(e) =>
                      gravarLinhas(
                        linhas.map((x, j) => (j === i ? { ...x, protegido: e.target.checked } : x)),
                      )
                    }
                  />
                  protegido
                </label>
                <button
                  type="button"
                  aria-label="Remover cabeçalho"
                  onClick={() => gravarLinhas(linhas.filter((_, j) => j !== i))}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => gravarLinhas([...linhas, { nome: "", valor: "", protegido: false }])}
              className="flex items-center gap-1 self-start text-xs font-medium text-primary"
            >
              <Plus className="size-3.5" />
              adicionar
            </button>
          </div>
        )}
      </div>

      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground">
          Avançado
        </summary>
        <Label className="mt-2 flex-col items-start gap-1">
          Tipo de conexão
          <Select
            value={valores.transport || "automatico"}
            onChange={(e) => mudar("transport", e.target.value)}
          >
            {TRANSPORTES.map((t) => (
              <option key={t.v} value={t.v}>
                {t.rotulo}
              </option>
            ))}
          </Select>
        </Label>
      </details>
    </section>
  );
}
