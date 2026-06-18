"use client";

import { useEffect, useState } from "react";
import { Lock, ShieldCheck } from "lucide-react";

import {
  api,
  ErroDaApi,
  type Credencial,
  type Instrumento,
  type TipoCredencial,
  type TipoInstrumento,
  type Time,
} from "@/lib/api";
import { SeletorIcone } from "@/components/seletor-icone";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// Formulário de instrumento, compartilhado entre a tela "Instrumentos do time"
// (/times/[id]/instrumentos) e o drawer do dashboard. `instrumento=null` cria;
// com `instrumento` edita (o tipo fica fixo). Os campos da configuração são
// gerados do `esquema_config` do tipo; segredos vão como senha e cifrados.

type CampoConfig = {
  nome: string;
  rotulo: string; // rótulo amigável (title do schema); cai no nome se não houver
  tipo: string; // string | integer | number | boolean | array | object
  descricao: string;
  obrigatorio: boolean;
  secreto: boolean;
  opcoes?: string[]; // enum/Literal → vira Select
  padrao?: string; // valor padrão do schema (semeia o formulário ao criar)
  // Se este campo reusa uma chave de serviço da organização (ex.: gerar_imagem→
  // openai): aí é opcional — em branco usa a chave da org.
  compartilhada?: boolean;
  servico?: string;
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

// Campos da configuração de um tipo, com metadados para gerar o formulário.
export function camposDoTipo(tipo: TipoInstrumento | undefined): CampoConfig[] {
  if (!tipo) return [];
  const esquema = (tipo.esquema_config ?? {}) as Record<string, unknown>;
  const props =
    (esquema.properties as Record<string, Record<string, unknown>>) ?? {};
  const obrigatorios = new Set((esquema.required as string[]) ?? []);
  const secretos = new Set(tipo.campos_secretos ?? []);
  const [campoCompart, servicoCompart] = tipo.chave_compartilhada ?? [null, null];
  return Object.entries(props).map(([nome, prop]) => ({
    nome,
    rotulo: (prop.title as string) || nome,
    tipo: tipoDoCampo(prop),
    descricao: (prop.description as string) ?? "",
    obrigatorio: obrigatorios.has(nome),
    secreto: secretos.has(nome),
    opcoes: opcoesDoCampo(prop),
    padrao: prop.default !== undefined ? String(prop.default) : undefined,
    compartilhada: nome === campoCompart,
    servico: nome === campoCompart ? (servicoCompart ?? undefined) : undefined,
  }));
}

// Valores iniciais do formulário para um tipo: ao EDITAR usa o que está guardado
// (secretos sempre em branco); ao CRIAR (sem instrumento) semeia os PADRÕES do
// schema. Semear os padrões deixa os dropdowns dependentes (ex.: modelo→tamanho)
// já com um controlador válido escolhido, e a tela nunca começa numa combinação
// impossível.
function valoresIniciais(
  tipo: TipoInstrumento | undefined,
  instrumento: Instrumento | null,
): Record<string, string> {
  const config = (instrumento?.configuracao ?? {}) as Record<string, unknown>;
  const v: Record<string, string> = {};
  for (const campo of camposDoTipo(tipo)) {
    if (campo.secreto) {
      v[campo.nome] = "";
      continue;
    }
    const atual = instrumento ? config[campo.nome] : undefined;
    if (atual !== undefined && atual !== null) {
      v[campo.nome] =
        typeof atual === "object" ? JSON.stringify(atual) : String(atual);
    } else {
      v[campo.nome] = campo.padrao ?? "";
    }
  }
  return v;
}

// As opções ATIVAS de um campo: se ele depende de outro (controlado_por), só as
// válidas para o valor atual do controlador; senão, as opções fixas do schema.
function opcoesAtivas(
  campo: CampoConfig,
  deps: TipoInstrumento["dependencias"],
  valores: Record<string, string>,
): string[] | undefined {
  const regra = deps?.[campo.nome];
  if (!regra) return campo.opcoes;
  const controlador = valores[regra.controlado_por] ?? "";
  return regra.opcoes[controlador] ?? campo.opcoes ?? [];
}

// Um campo do formulário, desenhado conforme o tipo: senha p/ secretos, número
// p/ number/integer, sim/não p/ boolean, JSON p/ array/object, texto p/ o resto.
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
            : campo.secreto && campo.compartilhada
              ? "em branco para usar a chave da organização"
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
        {campo.rotulo}
        {campo.obrigatorio && <span className="text-destructive">*</span>}
      </span>
      {entrada}
      {campo.compartilhada && (
        <span className="text-xs font-normal text-muted-foreground">
          Opcional: em branco, usa a chave de {campo.servico} cadastrada em Chaves
          e credenciais da organização. Preencha só para uma chave exclusiva deste
          instrumento.
        </span>
      )}
      {campo.descricao && !campo.compartilhada && (
        <span className="text-xs font-normal text-muted-foreground">
          {campo.descricao}
        </span>
      )}
    </Label>
  );
}

export function FormularioInstrumento({
  time,
  instrumento,
  tipos,
  onSalvo,
  onCancelar,
}: {
  time: Time;
  instrumento: Instrumento | null;
  tipos: TipoInstrumento[];
  onSalvo: (salvo: Instrumento) => void;
  onCancelar: () => void;
}) {
  const criando = instrumento === null;

  const [nome, setNome] = useState(instrumento?.nome ?? "");
  const [icone, setIcone] = useState<string | null>(instrumento?.icone ?? null);
  const [tipoSel, setTipoSel] = useState(
    instrumento?.tipo ?? tipos[0]?.tipo ?? "",
  );
  // Valor (texto) de cada campo. Secretos começam vazios — nunca reexibidos;
  // em branco = manter o que já está guardado. Ao criar, semeia os padrões do
  // schema (ver `valoresIniciais`).
  const [valores, setValores] = useState<Record<string, string>>(() =>
    valoresIniciais(
      tipos.find((t) => t.tipo === (instrumento?.tipo ?? tipos[0]?.tipo)),
      instrumento,
    ),
  );
  const [aprovacao, setAprovacao] = useState<"auto" | "sim" | "nao">(
    instrumento?.exige_aprovacao == null
      ? "auto"
      : instrumento.exige_aprovacao
        ? "sim"
        : "nao",
  );
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  // Caixa-forte: credencial nomeada da central que este instrumento usa (ou null
  // = segredo próprio inline). As credenciais disponíveis e seus tipos são
  // buscados sob demanda (a tela é uma ilha cliente; evita threading pelos
  // servidores). A GET é operador+ — quem edita instrumento já tem o papel.
  const [credencialId, setCredencialId] = useState<string | null>(
    instrumento?.credencial_id ?? null,
  );
  const [credenciais, setCredenciais] = useState<Credencial[]>([]);
  const [tiposCredencial, setTiposCredencial] = useState<TipoCredencial[]>([]);

  useEffect(() => {
    let ativo = true;
    (async () => {
      try {
        const [creds, tiposC] = await Promise.all([
          api.get<Credencial[]>(
            `/organizacoes/${time.organizacao_id}/credenciais`,
          ),
          api.get<TipoCredencial[]>(`/credenciais/tipos`),
        ]);
        if (ativo) {
          setCredenciais(creds);
          setTiposCredencial(tiposC);
        }
      } catch {
        // Sem credenciais disponíveis: o seletor simplesmente não aparece.
      }
    })();
    return () => {
      ativo = false;
    };
  }, [time.organizacao_id]);

  const tipoAtual = tipos.find((t) => t.tipo === tipoSel);
  const deps = tipoAtual?.dependencias ?? null;
  const aceitos = tipoAtual?.tipos_credencial_aceitos ?? [];
  const aceitaCredencial = aceitos.length > 0;
  const credenciaisCompat = credenciais.filter((c) => aceitos.includes(c.tipo));
  // Campos que a credencial selecionada fornece — ocultados do formulário e
  // omitidos da config (o valor vem da credencial na borda).
  const credSelecionada = credenciais.find((c) => c.id === credencialId) ?? null;
  const camposCobertos = new Set<string>(
    credSelecionada
      ? (tiposCredencial.find((t) => t.tipo === credSelecionada.tipo)?.campos ?? [])
          .map((c) => c.nome)
      : [],
  );

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    // Monta a configuração a partir dos campos, coagindo cada um pelo seu tipo.
    // Segredo preenchido vai cifrado; segredo em branco é OMITIDO (mantém).
    const config: Record<string, unknown> = {};
    for (const campo of camposDoTipo(tipoAtual)) {
      // Campo fornecido pela credencial da central: não vai na config (a borda
      // injeta o valor da credencial na execução).
      if (camposCobertos.has(campo.nome)) continue;
      const bruto = (valores[campo.nome] ?? "").trim();
      if (campo.secreto) {
        if (bruto) config[campo.nome] = bruto;
        else if (campo.obrigatorio && criando) {
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
    const exige_aprovacao = aprovacao === "auto" ? null : aprovacao === "sim";
    setSalvando(true);
    try {
      const credencial_id = aceitaCredencial ? credencialId : null;
      const salvo = criando
        ? await api.post<Instrumento>(`/times/${time.id}/instrumentos`, {
            nome: nome.trim(),
            tipo: tipoSel,
            configuracao: config,
            icone,
            exige_aprovacao,
            credencial_id,
          })
        : await api.put<Instrumento>(`/instrumentos/${instrumento.id}`, {
            nome: nome.trim(),
            configuracao: config,
            icone,
            exige_aprovacao,
            credencial_id,
          });
      setErro(null);
      onSalvo(salvo);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao salvar instrumento");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {erro && <Aviso>{erro}</Aviso>}

      <Label className="flex-col items-start gap-1">
        Nome
        <Input value={nome} onChange={(e) => setNome(e.target.value)} autoFocus />
      </Label>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-foreground">Ícone</span>
        <SeletorIcone valor={icone} onChange={setIcone} />
        <span className="text-xs text-muted-foreground">
          Opcional. Escolha um ícone para identificar este instrumento — sem
          escolha, fica o ícone padrão.
        </span>
      </div>
      <Label className="flex-col items-start gap-1">
        Tipo
        <Select
          value={tipoSel}
          onChange={(e) => {
            const novo = e.target.value;
            setTipoSel(novo);
            setCredencialId(null); // credencial pode não servir ao novo tipo
            // Tipo novo → semeia os padrões dele (some o estado do tipo anterior).
            setValores(valoresIniciais(tipos.find((t) => t.tipo === novo), null));
          }}
          disabled={!criando}
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

      {aceitaCredencial && (
        <Label className="flex-col items-start gap-1">
          <span className="flex items-center gap-1.5">
            <Lock className="size-3 text-muted-foreground" />
            Credencial da central
          </span>
          <Select
            value={credencialId ?? ""}
            onChange={(e) => setCredencialId(e.target.value || null)}
          >
            <option value="">Usar segredo próprio (preencher abaixo)</option>
            {credenciaisCompat.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
                {c.organizacao_id === null ? " (consultoria)" : ""}
              </option>
            ))}
          </Select>
          <span className="text-xs font-normal text-muted-foreground">
            {credencialId
              ? "Os campos fornecidos por esta credencial ficam ocultos — para trocá-los, edite a credencial em Chaves e credenciais."
              : "Aponte para uma credencial nomeada da central (troca num lugar só) ou preencha um segredo próprio abaixo."}
          </span>
        </Label>
      )}

      {(tipoAtual?.campos_secretos?.length ?? 0) > 0 && !credencialId && (
        <Aviso variant="atencao" className="text-xs">
          Os campos com cadeado são secretos: vão guardados cifrados e nunca são
          reexibidos. Ao editar, deixe um secreto em branco para manter o atual.
        </Aviso>
      )}

      {camposDoTipo(tipoAtual)
        .filter((campo) => !camposCobertos.has(campo.nome))
        .map((campo) => (
          <CampoConfigInput
            key={campo.nome}
            campo={{ ...campo, opcoes: opcoesAtivas(campo, deps, valores) }}
            valor={valores[campo.nome] ?? ""}
            jaGuardado={instrumento?.segredos?.[campo.nome]}
            onChange={(v) =>
              setValores((atual) => {
                const proximo = { ...atual, [campo.nome]: v };
                // Se este campo CONTROLA outros (dropdown dependente), reseta os
                // dependentes para a 1ª opção válida do novo valor — o estado
                // nunca guarda uma combinação impossível.
                for (const [dep, regra] of Object.entries(deps ?? {})) {
                  if (regra.controlado_por === campo.nome) {
                    const ops = regra.opcoes[v] ?? [];
                    if (ops.length && !ops.includes(proximo[dep] ?? "")) {
                      proximo[dep] = ops[0];
                    }
                  }
                }
                return proximo;
              })
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
        <Button onClick={salvar} disabled={salvando}>
          {salvando ? "Salvando…" : "Salvar"}
        </Button>
        <Button variant="ghost" onClick={onCancelar} disabled={salvando}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
