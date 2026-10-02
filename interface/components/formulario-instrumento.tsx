"use client";

import { useEffect, useState } from "react";
import { Lock } from "lucide-react";

import {
  api,
  mensagemDeErro,
  type Instrumento,
  type ModelosDisponiveis,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import {
  provedorDoModelo,
  provedoresParaSeletor,
  type Provedor,
  type ProvedoresDisponiveis,
} from "@/lib/modelos";
import { OpcoesModelo, useCatalogoModelos } from "@/components/opcoes-modelo";
import { IlustracaoProporcao } from "@/components/ilustracao-proporcao";
import { SeletorIcone } from "@/components/seletor-icone";
import { Aviso } from "@/components/ui/aviso";
import { SeletorFerramentasMCP } from "@/components/ferramentas-mcp";
import {
  CAMPOS_CONEXAO_MCP,
  ConexaoMCP,
  modoInicialMCP,
} from "@/components/conexao-mcp";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { type QuadroResumo } from "@/lib/quadros";

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
  // Dica de UI do schema (json_schema_extra.ui). "modelo_ia" = seletor de modelo
  // agrupado por provedor, filtrado pelos provedores com chave na organização.
  ui?: string;
  // Com "modelo_ia": as empresas de IA que este instrumento aceita (o resto some).
  provedores?: string[];
  // Se este campo reusa uma chave de serviço da organização (ex.: gerar_imagem→
  // openai): aí é opcional — em branco usa a chave da org.
  compartilhada?: boolean;
  servico?: string;
};

// Automação da organização, para o seletor de alvo do `agendar_automacao`.
type AutomacaoOrg = { id: string; nome: string; time_id: string; time_nome: string };

// Lê o tipo de um campo do JSON Schema, lidando com Optional (anyOf [tipo, null]).
function tipoDoCampo(prop: Record<string, unknown>): string {
  if (typeof prop.type === "string") return prop.type;
  const anyOf = prop.anyOf as Array<Record<string, unknown>> | undefined;
  const achado = anyOf?.find((p) => p.type && p.type !== "null");
  return (achado?.type as string) ?? "string";
}

// Um campo enum é de RESOLUÇÃO quando TODAS as opções batem "LxA", "L×A" ou "L:A"
// (ex.: 864x1536, 9:16). Nesse caso mostramos a ilustração da proporção ao lado do
// dropdown — vale para qualquer instrumento de imagem/vídeo, sem tag no backend.
const RE_RESOLUCAO = /^\d+\s*[x×:]\s*\d+$/i;
function ehEnumResolucao(opcoes: string[] | undefined): boolean {
  return (
    !!opcoes && opcoes.length > 0 && opcoes.every((o) => RE_RESOLUCAO.test(o.trim()))
  );
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
// Ordem dos grupos no dropdown de tipo de instrumento. Categorias não listadas
// (instrumento novo, ou "Outros") caem no fim.
const ORDEM_CATEGORIAS = ["Conteúdo", "Mensageria", "Integrações e dados"];

// Agrupa os tipos por categoria, na ORDEM_CATEGORIAS, alfabético dentro do grupo.
function agruparTiposPorCategoria(
  tipos: TipoInstrumento[],
): [string, TipoInstrumento[]][] {
  const porGrupo = new Map<string, TipoInstrumento[]>();
  for (const t of tipos) {
    const grupo = t.categoria || "Outros";
    const lista = porGrupo.get(grupo) ?? [];
    lista.push(t);
    porGrupo.set(grupo, lista);
  }
  const ordem = (g: string) => {
    const i = ORDEM_CATEGORIAS.indexOf(g);
    return i === -1 ? ORDEM_CATEGORIAS.length : i; // desconhecidos por último
  };
  return [...porGrupo.entries()]
    .sort((a, b) => ordem(a[0]) - ordem(b[0]) || a[0].localeCompare(b[0]))
    .map(
      ([grupo, lista]) =>
        [
          grupo,
          [...lista].sort((a, b) =>
            a.nome_exibicao.localeCompare(b.nome_exibicao),
          ),
        ] as [string, TipoInstrumento[]],
    );
}

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
    ui: (prop.ui as string) ?? undefined,
    provedores: (prop.provedores as string[]) ?? undefined,
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

// MCP: o modo de identificação de um instrumento salvo antes do campo existir é
// deduzido (token = Bearer), para a tela mostrar o que ele de fato faz.
function semearMCP(
  v: Record<string, string>,
  tipo: string | undefined,
  instrumento: Instrumento | null,
): Record<string, string> {
  if (tipo !== "conectar_mcp") return v;
  return {
    ...v,
    auth_modo: modoInicialMCP(v.auth_modo, instrumento?.segredos, instrumento === null),
  };
}

// O segredo que cada modo de identificação do MCP exige (além do endereço).
const SEGREDO_DO_MODO_MCP: Record<string, [string, string] | undefined> = {
  bearer: ["token_bearer", "o token"],
  cabecalho: ["auth_segredo", "o valor do cabeçalho"],
  query: ["auth_segredo", "o valor da chave"],
  basic: ["auth_segredo", "a senha"],
  oauth_cliente: ["auth_segredo", "o Client Secret"],
};

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
  instrumentoId,
  conexao,
  jaGuardado,
  disponiveis,
  automacoes,
  canais,
  quadros,
  onChange,
}: {
  campo: CampoConfig;
  valor: string;
  // O instrumento JÁ SALVO (null enquanto é criação): o seletor de ferramentas MCP
  // precisa dele para perguntar ao servidor o que ele publica.
  instrumentoId: string | null;
  conexao?: Instrumento["conexao"]; // o que o último "Conectar" descobriu (MCP)
  jaGuardado: string | undefined; // 4 últimos dígitos, se já há segredo guardado
  disponiveis: ProvedoresDisponiveis | undefined; // p/ o seletor de modelo de IA
  automacoes: AutomacaoOrg[]; // p/ o seletor de automação-alvo (agendar_automacao)
  canais: Instrumento[]; // p/ o seletor de canal (ui:canal_mensageria)
  quadros: QuadroResumo[]; // p/ o seletor de quadro (ui:quadro — instrumento `quadro`)
  onChange: (v: string) => void;
}) {
  const catalogoModelos = useCatalogoModelos();
  let entrada;
  if (campo.tipo === "boolean") {
    entrada = (
      <Select value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">—</option>
        <option value="true">Sim</option>
        <option value="false">Não</option>
      </Select>
    );
  } else if (campo.ui === "modelo_ia" && !campo.secreto) {
    // Seletor de modelo de IA: agrupado por provedor e filtrado pelos provedores
    // com chave na org (mesmo padrão do seletor do agente). O provedor do valor já
    // salvo continua visível mesmo se a chave sumir.
    const provedores = provedoresParaSeletor(disponiveis, provedorDoModelo(valor)).filter(
      (p) => !campo.provedores || campo.provedores.includes(p),
    );
    entrada = (
      <Select value={valor} onChange={(e) => onChange(e.target.value)}>
        {!campo.obrigatorio && <option value="">(padrão)</option>}
        <OpcoesModelo provedores={provedores} catalogo={catalogoModelos} atual={valor} />
      </Select>
    );
  } else if (campo.ui === "automacao_alvo" && !campo.secreto) {
    // Seletor da automação-alvo do agendamento: as automações da organização,
    // agrupadas por time (o valor guardado é o id da automação).
    const porTime = new Map<string, { id: string; nome: string }[]>();
    for (const a of automacoes) {
      const lista = porTime.get(a.time_nome) ?? [];
      lista.push({ id: a.id, nome: a.nome });
      porTime.set(a.time_nome, lista);
    }
    entrada = (
      <Select value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">(escolha uma automação)</option>
        {[...porTime.entries()].map(([nomeTime, lista]) => (
          <optgroup key={nomeTime} label={nomeTime}>
            {lista.map((a) => (
              <option key={a.id} value={a.id}>
                {a.nome}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
    );
  } else if (campo.ui === "quadro" && !campo.secreto) {
    // O quadro do cérebro que este instrumento usa: seletor com os quadros da
    // organização + prévia do que ele tem (colunas e quem já usa). O valor guardado é
    // o id do quadro (renomear o quadro não quebra o instrumento).
    const escolhido = quadros.find((q) => q.id === valor || q.nome.toLowerCase() === valor.toLowerCase());
    entrada = (
      <div className="flex flex-col gap-2">
        <Select value={escolhido?.id ?? valor} onChange={(e) => onChange(e.target.value)}>
          <option value="">(escolha um quadro)</option>
          {quadros.map((q) => (
            <option key={q.id} value={q.id}>
              {q.nome}
            </option>
          ))}
        </Select>
        {escolhido && (
          <div className="flex flex-col gap-0.5 rounded-md border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
            <span className="text-foreground">
              {escolhido.nome} · {escolhido.linhas.toLocaleString("pt-BR")} linhas
            </span>
            <span>Colunas: {escolhido.colunas.join(", ")}</span>
            {escolhido.usado_por.length > 0 && (
              <span>
                Já usado por:{" "}
                {escolhido.usado_por
                  .map((u) => `${u.agentes.join(", ") || u.instrumento} (${u.acesso === "ler_e_escrever" ? "grava" : "lê"})`)
                  .join("; ")}
              </span>
            )}
          </div>
        )}
        {quadros.length === 0 && (
          <span className="text-xs text-muted-foreground">
            Esta organização ainda não tem quadros. Crie um no Cérebro (menu à esquerda).
          </span>
        )}
      </div>
    );
  } else if (campo.ui === "acesso_quadro" && !campo.secreto) {
    const opcoes = [
      { v: "ler", titulo: "Só ler", texto: "Consultar linhas, somar e conferir o que já existe." },
      { v: "ler_e_escrever", titulo: "Ler e gravar", texto: "Também acrescentar linhas e mudar as que existem. Não apaga." },
    ];
    const atual = valor || "ler";
    entrada = (
      <div className="flex flex-col gap-2" role="radiogroup">
        {opcoes.map((o) => (
          <button
            key={o.v}
            type="button"
            role="radio"
            aria-checked={atual === o.v}
            onClick={() => onChange(o.v)}
            className={`flex items-start gap-3 rounded-md border px-3 py-2.5 text-left text-sm transition-colors ${
              atual === o.v ? "border-primary bg-accent/40" : "border-border hover:border-[#D6D3E8]"
            }`}
          >
            <span className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border ${atual === o.v ? "border-primary" : "border-[#D6D3E8]"}`}>
              {atual === o.v && <span className="size-2 rounded-full bg-primary" />}
            </span>
            <span>
              <span className="block font-medium text-foreground">{o.titulo}</span>
              <span className="text-muted-foreground">{o.texto}</span>
            </span>
          </button>
        ))}
      </div>
    );
  } else if (campo.ui === "ferramentas_mcp") {
    // Quais ferramentas de um servidor MCP entram no cinto, e quais alteram algo lá fora.
    // O formulário genérico desenharia este `array` como uma caixa pedindo JSON — o
    // que é a mesma coisa que não ter escolha nenhuma.
    entrada = (
      <SeletorFerramentasMCP
        valor={valor}
        instrumentoId={instrumentoId}
        conexaoInicial={conexao ?? null}
        onChange={onChange}
      />
    );
  } else if (campo.ui === "canal_mensageria" && !campo.secreto) {
    // Seletor do canal por onde o pedido de aprovação é apresentado: os canais de
    // mensageria DESTE time. Vazio = a pessoa aprova pela tela da execução.
    entrada = (
      <div className="flex flex-col gap-1.5">
        <Select value={valor} onChange={(e) => onChange(e.target.value)}>
          <option value="">Só pela tela da execução</option>
          {canais.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </Select>
        {valor &&
          !(
            (canais.find((c) => c.id === valor)?.configuracao
              ?.destinatario_padrao as string | undefined) ?? ""
          ).trim() && (
            <span className="text-xs text-warning">
              ⚠ Este canal não tem destinatário configurado — sem ele não há para quem
              mandar o pedido nem de quem esperar a resposta. Preencha o destinatário
              na configuração do canal.
            </span>
          )}
        {canais.length === 0 && (
          <span className="text-xs text-muted-foreground">
            Este time ainda não tem canal de mensageria. Crie um instrumento de canal
            (Telegram) para pedir aprovação por mensagem — ou deixe em branco e aprove
            pela tela.
          </span>
        )}
      </div>
    );
  } else if (ehEnumResolucao(campo.opcoes) && !campo.secreto) {
    // Enum de resolução: dropdown normal + ilustração da proporção do valor atual.
    entrada = (
      <div className="flex flex-col gap-2">
        <Select value={valor} onChange={(e) => onChange(e.target.value)}>
          {!campo.obrigatorio && <option value="">(padrão)</option>}
          {(campo.opcoes ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </Select>
        <IlustracaoProporcao valor={valor} />
      </div>
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
          de IA da organização. Preencha só para uma chave exclusiva deste
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
  souAdmin = false,
  tipoFixo,
}: {
  time: Time;
  instrumento: Instrumento | null;
  tipos: TipoInstrumento[];
  /** Só admin escolhe "toda a organização" e mexe em instrumento da organização. */
  souAdmin?: boolean;
  /** Construtor de um tipo personalizado (ex.: servidor MCP): tipo fixo, sem seletor. */
  tipoFixo?: string;
  onSalvo: (salvo: Instrumento) => void;
  onCancelar: () => void;
}) {
  const criando = instrumento === null;

  const [nome, setNome] = useState(instrumento?.nome ?? "");
  const [icone, setIcone] = useState<string | null>(instrumento?.icone ?? null);
  // Tipos PERSONALIZADOS nascem no Construtor ("Criar instrumento"), não na lista de
  // prontos. Continuam no catálogo (a tela de edição precisa do esquema deles).
  // A regra vem do cérebro (fonte única): personalizado com Construtor próprio, ou tipo
  // substituído na criação (a chamada de API avulsa → conector).
  const tiposProntos = tipos.filter((t) => !t.criado_no_construtor && !t.substituido_por);
  const [tipoSel, setTipoSel] = useState(
    instrumento?.tipo ?? tipoFixo ?? tiposProntos[0]?.tipo ?? "",
  );
  // Valor (texto) de cada campo. Secretos começam vazios — nunca reexibidos;
  // em branco = manter o que já está guardado. Ao criar, semeia os padrões do
  // schema (ver `valoresIniciais`).
  const [valores, setValores] = useState<Record<string, string>>(() => {
    const tipoInicial = instrumento?.tipo ?? tipoFixo ?? tiposProntos[0]?.tipo;
    return semearMCP(
      valoresIniciais(tipos.find((t) => t.tipo === tipoInicial), instrumento),
      tipoInicial,
      instrumento,
    );
  });
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [escopo, setEscopo] = useState<"time" | "organizacao">(
    instrumento?.escopo ?? "time",
  );
  const daOrganizacao = (instrumento?.escopo ?? "time") === "organizacao";
  // Instrumento da organização vale para todos os times: só admin muda.
  const bloqueado = daOrganizacao && !souAdmin;

  // Provedores com chave na org — para um campo de modelo de IA (ui:modelo_ia) só
  // oferecer modelos cujo provedor tem chave. Fallback (falha/carregando): mostra todos.
  const [disponiveis, setDisponiveis] = useState<ProvedoresDisponiveis>();
  // Automações da organização — para o campo `ui:automacao_alvo` (agendar_automacao).
  const [automacoesOrg, setAutomacoesOrg] = useState<AutomacaoOrg[]>([]);
  // Canais de mensageria DESTE time — para o campo `ui:canal_mensageria` (o canal
  // por onde `pedir_aprovacao` apresenta o pedido).
  const [canaisDoTime, setCanaisDoTime] = useState<Instrumento[]>([]);

  useEffect(() => {
    let vivo = true;
    api
      .get<ModelosDisponiveis>(
        `/organizacoes/${time.organizacao_id}/modelos-disponiveis`,
      )
      .then((d) => {
        if (vivo) setDisponiveis(d);
      })
      .catch(() => {
        /* sem disponibilidade: o seletor de modelo mostra todos (fallback seguro) */
      });
    return () => {
      vivo = false;
    };
  }, [time.organizacao_id]);

  // Pronto de IA só aparece para criar se a organização tem a chave de uma das IAs
  // dele (o cérebro recusa do mesmo jeito). Enquanto a disponibilidade não chega,
  // mostra todos.
  const tiposOferecidos = tiposProntos.filter(
    (t) =>
      !t.provedores_ia?.length ||
      !disponiveis ||
      t.provedores_ia.some((p) => disponiveis[p as Provedor]),
  );

  useEffect(() => {
    let vivo = true;
    api
      .get<AutomacaoOrg[]>(`/organizacoes/${time.organizacao_id}/automacoes`)
      .then((d) => {
        if (vivo) setAutomacoesOrg(d);
      })
      .catch(() => {
        /* sem automações: o seletor de alvo fica vazio */
      });
    return () => {
      vivo = false;
    };
  }, [time.organizacao_id]);

  useEffect(() => {
    let vivo = true;
    api
      .get<Instrumento[]>(`/times/${time.id}/instrumentos`)
      .then((d) => {
        if (vivo) setCanaisDoTime(d.filter((i) => i.tipo === "enviar_telegram"));
      })
      .catch(() => {
        /* sem instrumentos: o seletor de canal fica vazio (aprova pela tela) */
      });
    return () => {
      vivo = false;
    };
  }, [time.id]);

  // Quadros do cérebro da organização — para o campo `ui:quadro` (instrumento `quadro`).
  const [quadrosOrg, setQuadrosOrg] = useState<QuadroResumo[]>([]);
  useEffect(() => {
    let vivo = true;
    api
      .get<QuadroResumo[]>(`/organizacoes/${time.organizacao_id}/quadros`)
      .then((d) => {
        if (vivo) setQuadrosOrg(d);
      })
      .catch(() => {
        /* sem quadros: o seletor mostra o aviso para criar um no Cérebro */
      });
    return () => {
      vivo = false;
    };
  }, [time.organizacao_id]);

  const tipoAtual = tipos.find((t) => t.tipo === tipoSel);
  const ehMCP = tipoSel === "conectar_mcp";
  // O modo que está salvo (para saber se a pessoa trocou de modo nesta edição).
  const modoSalvoMCP = modoInicialMCP(
    (instrumento?.configuracao?.auth_modo as string | undefined) || undefined,
    instrumento?.segredos,
    criando,
  );
  const deps = tipoAtual?.dependencias ?? null;

  async function salvar() {
    if (!nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    if (ehMCP) {
      // Trocar de modo sem preencher o segredo do modo novo faria o Batuta usar o
      // segredo do modo anterior (a senha virando valor de cabeçalho, por exemplo).
      const guardados = instrumento?.segredos ?? {};
      if (!valores.url?.trim() && !guardados.url) {
        setErro("Preencha o endereço do servidor.");
        return;
      }
      if (valores.auth_modo === "oauth_cliente" && !valores.oauth_client_id?.trim()) {
        setErro("Preencha o Client ID em “Como o Batuta se conecta”.");
        return;
      }
      const exigido = SEGREDO_DO_MODO_MCP[valores.auth_modo ?? ""];
      if (exigido && !valores[exigido[0]]?.trim()) {
        if (valores.auth_modo !== modoSalvoMCP || !guardados[exigido[0]]) {
          setErro(`Preencha ${exigido[1]} em “Como o Batuta se conecta”.`);
          return;
        }
      }
    }
    // Monta a configuração a partir dos campos, coagindo cada um pelo seu tipo.
    // Segredo preenchido vai cifrado; segredo em branco é OMITIDO (mantém).
    const config: Record<string, unknown> = {};
    for (const campo of camposDoTipo(tipoAtual)) {
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
    setSalvando(true);
    try {
      const salvo = criando
        ? await api.post<Instrumento>(`/times/${time.id}/instrumentos`, {
            nome: nome.trim(),
            tipo: tipoSel,
            configuracao: config,
            icone,
            escopo,
          })
        : await api.put<Instrumento>(`/instrumentos/${instrumento.id}`, {
            nome: nome.trim(),
            configuracao: config,
            icone,
            ...(souAdmin ? { escopo } : {}),
          });
      setErro(null);
      onSalvo(salvo);
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha ao salvar instrumento"));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {daOrganizacao && (
        <Aviso variant="info" className="text-xs">
          {bloqueado
            ? "Este instrumento é da organização: só um administrador muda a configuração dele."
            : "Este instrumento é da organização: o que você mudar aqui vale para todos os times que o usam."}
        </Aviso>
      )}

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
      {!tipoFixo && (
      <Label className="flex-col items-start gap-1">
        Tipo
        <Select
          value={tipoSel}
          onChange={(e) => {
            const novo = e.target.value;
            setTipoSel(novo);
            // Tipo novo → semeia os padrões dele (some o estado do tipo anterior).
            setValores(
              semearMCP(valoresIniciais(tipos.find((t) => t.tipo === novo), null), novo, null),
            );
          }}
          disabled={!criando}
        >
          {agruparTiposPorCategoria(criando ? tiposOferecidos : tipos).map(([grupo, lista]) => (
            <optgroup key={grupo} label={grupo}>
              {lista.map((t) => (
                <option key={t.tipo} value={t.tipo}>
                  {t.nome_exibicao}
                </option>
              ))}
            </optgroup>
          ))}
        </Select>
      </Label>
      )}
      {!tipoFixo && tipoAtual?.descricao && (
        <p className="text-xs text-muted-foreground">{tipoAtual.descricao}</p>
      )}

      {(tipoAtual?.campos_secretos?.length ?? 0) > 0 && (
        <Aviso variant="atencao" className="text-xs">
          Os campos com cadeado são secretos: vão guardados cifrados e nunca são
          reexibidos. Ao editar, deixe um secreto em branco para manter o atual.
        </Aviso>
      )}

      {camposDoTipo(tipoAtual).length > 0 && (
        <Aviso variant="info" className="text-xs">
          O que você preenche aqui vale como está — o agente <strong>não</strong>{" "}
          troca esses valores pelo texto dele. Na hora de usar o instrumento, ele só
          fornece o conteúdo (a mensagem, o prompt, a consulta…).
        </Aviso>
      )}

      {ehMCP && (
        <ConexaoMCP
          valores={valores}
          mudar={(campo, v) => setValores((atual) => ({ ...atual, [campo]: v }))}
          guardados={instrumento?.segredos ?? {}}
          modoSalvo={modoSalvoMCP}
          instrumentoId={instrumento?.id ?? null}
          conexao={instrumento?.conexao ?? null}
        />
      )}

      {camposDoTipo(tipoAtual)
        .filter((campo) => !(ehMCP && CAMPOS_CONEXAO_MCP.has(campo.nome)))
        .map((campo) => (
          <CampoConfigInput
            key={campo.nome}
            campo={{ ...campo, opcoes: opcoesAtivas(campo, deps, valores) }}
            valor={valores[campo.nome] ?? ""}
            instrumentoId={instrumento?.id ?? null}
            conexao={instrumento?.conexao ?? null}
            jaGuardado={instrumento?.segredos?.[campo.nome]}
            disponiveis={disponiveis}
            automacoes={automacoesOrg}
            canais={canaisDoTime}
            quadros={quadrosOrg}
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

      {souAdmin && (
        <Label className="flex-col items-start gap-1">
          Quem pode usar
          <Select
            value={escopo}
            onChange={(e) => setEscopo(e.target.value as "time" | "organizacao")}
          >
            <option value="time">Só este time</option>
            <option value="organizacao">Todos os times da organização</option>
          </Select>
          {escopo === "organizacao" && tipoSel === "enviar_telegram" && (
            <span className="text-xs font-normal text-muted-foreground">
              Um bot da organização só envia avisos e pedidos de aprovação — para conversar
              com clientes, use um bot do time.
            </span>
          )}
        </Label>
      )}

      {/* O erro aparece junto do botão: no topo, num formulário longo, ficava fora
          da vista e o "Salvar" parecia não fazer nada. */}
      {erro && <Aviso>{erro}</Aviso>}
      <div className="flex gap-2">
        <Button onClick={salvar} disabled={salvando || bloqueado}>
          {salvando ? "Salvando…" : "Salvar"}
        </Button>
        <Button variant="ghost" onClick={onCancelar} disabled={salvando}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
