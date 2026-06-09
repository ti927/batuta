"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, Lock, Plus, ShieldCheck, Wrench } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Instrumento,
  type PapelAcesso,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { podeAdmin, podeOperar } from "@/lib/permissoes";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// Tenta interpretar um texto como objeto JSON. Devolve [valor, null] ou
// [null, mensagemDeErro]. Vazio vira objeto vazio.
function lerJson(texto: string): [Record<string, unknown> | null, string | null] {
  const t = texto.trim();
  if (!t) return [{}, null];
  try {
    const v = JSON.parse(t);
    if (typeof v !== "object" || v === null || Array.isArray(v))
      return [null, "A configuração precisa ser um objeto JSON { ... }"];
    return [v as Record<string, unknown>, null];
  } catch {
    return [null, "JSON inválido."];
  }
}

// Um campo da configuração, com o que o formulário precisa para se desenhar.
type CampoConfig = {
  nome: string;
  tipo: string; // "string" | "integer" | "number" | "boolean" | "array" | "object"
  descricao: string;
  obrigatorio: boolean;
  secreto: boolean;
  opcoes?: string[]; // valores fixos (enum/Literal, ex.: metodo) → vira Select
};

// Lê o tipo de um campo do JSON Schema, lidando com Optional (anyOf [tipo, null]).
function tipoDoCampo(prop: Record<string, unknown>): string {
  if (typeof prop.type === "string") return prop.type;
  const anyOf = prop.anyOf as Array<Record<string, unknown>> | undefined;
  const achado = anyOf?.find((p) => p.type && p.type !== "null");
  return (achado?.type as string) ?? "string";
}

// Valores fixos de um campo (Literal/enum), inclusive dentro de anyOf (Optional).
function opcoesDoCampo(prop: Record<string, unknown>): string[] | undefined {
  if (Array.isArray(prop.enum)) return (prop.enum as unknown[]).map(String);
  const anyOf = prop.anyOf as Array<Record<string, unknown>> | undefined;
  const comEnum = anyOf?.find((p) => Array.isArray(p.enum));
  if (comEnum) return (comEnum.enum as unknown[]).map(String);
  return undefined;
}

// Campos da configuração de um tipo, com metadados para gerar o formulário —
// inclusive quais são secretos (vão como senha e cifrados; Fase 7-B).
function camposDoTipo(tipo: TipoInstrumento | undefined): CampoConfig[] {
  if (!tipo) return [];
  const esquema = (tipo.esquema_config ?? {}) as Record<string, unknown>;
  const props =
    (esquema.properties as Record<string, Record<string, unknown>>) ?? {};
  const obrigatorios = new Set((esquema.required as string[]) ?? []);
  const secretos = new Set(tipo.campos_secretos ?? []);
  return Object.entries(props).map(([nome, prop]) => ({
    nome,
    tipo: tipoDoCampo(prop),
    descricao: (prop.description as string) ?? "",
    obrigatorio: obrigatorios.has(nome),
    secreto: secretos.has(nome),
    opcoes: opcoesDoCampo(prop),
  }));
}

// Um campo do formulário de configuração, desenhado conforme o tipo: senha para
// secretos, número para number/integer, sim/não para boolean, JSON para
// array/object, texto para o resto.
function CampoConfigInput({
  campo,
  valor,
  jaGuardado,
  onChange,
}: {
  campo: CampoConfig;
  valor: string;
  jaGuardado: string | undefined; // 4 últimos dígitos, se já há segredo guardado
  onChange: (v: string) => void;
}) {
  let entrada;
  if (campo.tipo === "boolean") {
    entrada = (
      <Select value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">—</option>
        <option value="true">Sim</option>
        <option value="false">Não</option>
      </Select>
    );
  } else if (campo.opcoes && !campo.secreto) {
    entrada = (
      <Select value={valor} onChange={(e) => onChange(e.target.value)}>
        {!campo.obrigatorio && <option value="">(padrão)</option>}
        {campo.opcoes.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </Select>
    );
  } else if (campo.tipo === "array" || campo.tipo === "object") {
    entrada = (
      <Textarea
        className="min-h-20 font-mono"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        placeholder={campo.tipo === "array" ? '["a", "b"]' : '{ "chave": "valor" }'}
      />
    );
  } else {
    entrada = (
      <Input
        type={
          campo.secreto
            ? "password"
            : campo.tipo === "integer" || campo.tipo === "number"
              ? "number"
              : "text"
        }
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={campo.secreto ? "new-password" : undefined}
        placeholder={
          campo.secreto && jaGuardado
            ? `•••• ${jaGuardado} — em branco para manter`
            : campo.secreto
              ? "deixe em branco se não tiver"
              : undefined
        }
      />
    );
  }
  return (
    <Label className="flex-col items-start gap-1">
      <span className="flex items-center gap-1.5">
        {campo.secreto && <Lock className="size-3 text-muted-foreground" />}
        {campo.nome}
        {campo.obrigatorio && <span className="text-destructive">*</span>}
      </span>
      {entrada}
      {campo.descricao && (
        <span className="text-xs font-normal text-muted-foreground">
          {campo.descricao}
        </span>
      )}
    </Label>
  );
}

export function InstrumentosCliente({
  time,
  inicial,
  tipos,
  meuPapel,
}: {
  time: Time;
  inicial: Instrumento[];
  tipos: TipoInstrumento[];
  meuPapel: PapelAcesso | null;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const souOperador = podeOperar(meuPapel);
  const souAdmin = podeAdmin(meuPapel);

  const [modo, setModo] = useState<null | "novo" | string>(null);
  const [nome, setNome] = useState("");
  const [tipoSel, setTipoSel] = useState(tipos[0]?.tipo ?? "");
  // Valor (como texto) de cada campo da configuração. Campos secretos começam
  // vazios — nunca são reexibidos; em branco = manter o que já está guardado.
  const [valores, setValores] = useState<Record<string, string>>({});
  // Interruptor de aprovação humana: "auto" (deriva), "sim" (sempre), "nao" (nunca).
  const [aprovacao, setAprovacao] = useState<"auto" | "sim" | "nao">("auto");

  // Estado do "Testar": instrumento sendo testado, argumentos e resultado.
  const [testandoId, setTestandoId] = useState<string | null>(null);
  const [argsTexto, setArgsTexto] = useState("{}");
  const [resultado, setResultado] = useState<string | null>(null);

  const tipoAtual = tipos.find((t) => t.tipo === tipoSel);
  const instEditando =
    modo && modo !== "novo" ? inicial.find((i) => i.id === modo) : undefined;

  function tratar(e: unknown, padrao: string) {
    setErro(e instanceof ErroDaApi ? e.message : padrao);
  }

  function abrirNovo() {
    setNome("");
    setTipoSel(tipos[0]?.tipo ?? "");
    setValores({});
    setAprovacao("auto");
    setErro(null);
    setModo("novo");
  }

  function abrirEdicao(inst: Instrumento) {
    const tipo = tipos.find((t) => t.tipo === inst.tipo);
    const config = (inst.configuracao ?? {}) as Record<string, unknown>;
    const v: Record<string, string> = {};
    for (const campo of camposDoTipo(tipo)) {
      if (campo.secreto) {
        v[campo.nome] = ""; // segredo nunca é reexibido; em branco = manter
        continue;
      }
      const atual = config[campo.nome];
      if (atual === undefined || atual === null) v[campo.nome] = "";
      else if (typeof atual === "object") v[campo.nome] = JSON.stringify(atual);
      else v[campo.nome] = String(atual);
    }
    setNome(inst.nome);
    setTipoSel(inst.tipo);
    setValores(v);
    setAprovacao(
      inst.exige_aprovacao == null ? "auto" : inst.exige_aprovacao ? "sim" : "nao",
    );
    setErro(null);
    setModo(inst.id);
  }

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    // Monta a configuração a partir dos campos do formulário, coagindo cada um
    // pelo seu tipo. Segredo preenchido vai cifrado; segredo em branco é OMITIDO
    // (o cérebro mantém o que já está guardado).
    const config: Record<string, unknown> = {};
    for (const campo of camposDoTipo(tipoAtual)) {
      const bruto = (valores[campo.nome] ?? "").trim();
      if (campo.secreto) {
        if (bruto) config[campo.nome] = bruto;
        else if (campo.obrigatorio && modo === "novo") {
          setErro(`Preencha o campo "${campo.nome}".`);
          return;
        }
        continue;
      }
      if (bruto === "") {
        if (campo.obrigatorio) {
          setErro(`Preencha o campo "${campo.nome}".`);
          return;
        }
        continue;
      }
      if (campo.tipo === "integer" || campo.tipo === "number") {
        const n = Number(bruto);
        if (Number.isNaN(n)) {
          setErro(`O campo "${campo.nome}" precisa ser um número.`);
          return;
        }
        config[campo.nome] = campo.tipo === "integer" ? Math.trunc(n) : n;
      } else if (campo.tipo === "boolean") {
        config[campo.nome] = bruto === "true";
      } else if (campo.tipo === "array" || campo.tipo === "object") {
        try {
          config[campo.nome] = JSON.parse(bruto);
        } catch {
          setErro(`O campo "${campo.nome}" precisa ser um JSON válido.`);
          return;
        }
      } else {
        config[campo.nome] = bruto;
      }
    }
    const exige_aprovacao =
      aprovacao === "auto" ? null : aprovacao === "sim";
    try {
      if (modo === "novo") {
        await api.post<Instrumento>(`/times/${time.id}/instrumentos`, {
          nome: nome.trim(),
          tipo: tipoSel,
          configuracao: config,
          exige_aprovacao,
        });
      } else if (modo) {
        await api.put<Instrumento>(`/instrumentos/${modo}`, {
          nome: nome.trim(),
          configuracao: config,
          exige_aprovacao,
        });
      }
      setErro(null);
      setModo(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao salvar instrumento");
    }
  }

  async function remover(inst: Instrumento) {
    if (!confirm(`Remover o instrumento "${inst.nome}"?`)) return;
    try {
      await api.delete(`/instrumentos/${inst.id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      tratar(e, "Falha ao remover instrumento");
    }
  }

  function abrirTeste(inst: Instrumento) {
    setTestandoId(inst.id);
    setArgsTexto("{}");
    setResultado(null);
    setErro(null);
  }

  async function acionar(inst: Instrumento) {
    const [args, erroJson] = lerJson(argsTexto);
    if (erroJson) {
      setErro(erroJson);
      return;
    }
    try {
      const r = await api.post<unknown>(`/instrumentos/${inst.id}/acionar`, {
        argumentos: args,
      });
      setResultado(JSON.stringify(r, null, 2));
      setErro(null);
    } catch (e) {
      tratar(e, "Falha ao acionar instrumento");
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href={`/times/${time.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Voltar ao time
      </Link>
      <h1 className="mt-2 text-2xl font-medium text-foreground">{time.nome}</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        Instrumentos do time
      </p>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      {modo === null && souOperador && (
        <Button className="mb-6" onClick={abrirNovo} disabled={tipos.length === 0}>
          <Plus />
          Novo instrumento
        </Button>
      )}

      {modo !== null && (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium text-foreground">
            {modo === "novo" ? "Novo instrumento" : "Editar instrumento"}
          </h2>
          <Label className="flex-col items-start gap-1">
            Nome
            <Input
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              autoFocus
            />
          </Label>
          <Label className="flex-col items-start gap-1">
            Tipo
            <Select
              value={tipoSel}
              onChange={(e) => setTipoSel(e.target.value)}
              disabled={modo !== "novo"}
            >
              {tipos.map((t) => (
                <option key={t.tipo} value={t.tipo}>
                  {t.nome_exibicao}
                </option>
              ))}
            </Select>
          </Label>
          {tipoAtual?.descricao && (
            <p className="text-xs text-muted-foreground">{tipoAtual.descricao}</p>
          )}

          {(tipoAtual?.campos_secretos?.length ?? 0) > 0 && (
            <Aviso variant="atencao" className="text-xs">
              Os campos com cadeado são secretos: vão guardados cifrados e nunca são
              reexibidos. Ao editar, deixe um secreto em branco para manter o atual.
            </Aviso>
          )}

          {camposDoTipo(tipoAtual).map((campo) => (
            <CampoConfigInput
              key={campo.nome}
              campo={campo}
              valor={valores[campo.nome] ?? ""}
              jaGuardado={instEditando?.segredos?.[campo.nome]}
              onChange={(v) =>
                setValores((atual) => ({ ...atual, [campo.nome]: v }))
              }
            />
          ))}

          {camposDoTipo(tipoAtual).length === 0 && (
            <p className="text-xs text-muted-foreground">
              Este tipo não precisa de configuração.
            </p>
          )}

          <div className="mt-1 border-t border-border pt-3">
            <Label className="flex-col items-start gap-1">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="size-3.5 text-muted-foreground" />
                Aprovação humana antes de agir
              </span>
              <Select
                value={aprovacao}
                onChange={(e) =>
                  setAprovacao(e.target.value as "auto" | "sim" | "nao")
                }
              >
                <option value="auto">Automático (recomendado)</option>
                <option value="sim">Sempre exigir aprovação</option>
                <option value="nao">Nunca exigir (rodar direto)</option>
              </Select>
              <span className="text-xs font-normal text-muted-foreground">
                Automático: consultas (leitura) rodam direto; ações que escrevem ou
                enviam exigem um humano aprovando antes.
              </span>
            </Label>
            {aprovacao === "nao" && tipoAtual?.acao_irreversivel && (
              <Aviso variant="atencao" className="mt-2 text-xs">
                Este tipo pode alterar ou enviar dados de verdade. Desligar a aprovação
                remove a checagem humana — use só se tiver certeza de que esta
                configuração é segura (ex.: uma leitura).
              </Aviso>
            )}
          </div>

          <div className="flex gap-2">
            <Button onClick={salvar}>Salvar</Button>
            <Button variant="ghost" onClick={() => setModo(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {inicial.length === 0 ? (
        <EstadoVazio icone={Wrench} titulo="Nenhum instrumento ainda.">
          {souOperador
            ? "Crie o primeiro instrumento para este time."
            : "Os instrumentos deste time aparecerão aqui."}
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((inst) => (
            <li key={inst.id} className="flex flex-col gap-2 p-3">
              <div className="flex items-center gap-2">
                <span className="flex flex-1 flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                  {inst.nome}
                  <span className="rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-xs font-normal text-muted-foreground">
                    {inst.tipo}
                  </span>
                </span>
                {souOperador && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => abrirTeste(inst)}
                  >
                    Testar
                  </Button>
                )}
                {souOperador && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => abrirEdicao(inst)}
                  >
                    Editar
                  </Button>
                )}
                {souAdmin && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => remover(inst)}
                  >
                    Remover
                  </Button>
                )}
              </div>

              {testandoId === inst.id && (
                <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
                  <Label className="flex-col items-start gap-1">
                    Argumentos (JSON)
                    <Textarea
                      className="min-h-20 font-mono"
                      value={argsTexto}
                      onChange={(e) => setArgsTexto(e.target.value)}
                    />
                  </Label>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => acionar(inst)}>
                      Acionar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setTestandoId(null)}
                    >
                      Fechar
                    </Button>
                  </div>
                  {resultado && (
                    <pre className="max-h-72 overflow-auto rounded-md bg-foreground p-3 text-xs text-background">
                      {resultado}
                    </pre>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
