"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Contact,
  Eye,
  FlaskConical,
  KeyRound,
  ListChecks,
  Lock,
  Play,
  Plus,
  Rocket,
  ShieldAlert,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  api,
  mensagemDeErro,
  type CampoConector,
  type CampoDetectado,
  type ConfigConector,
  type Instrumento,
  type MetodoHttp,
  type OperacaoConector,
  type PapelCampoConector,
  type RespostaTeste,
  type TipoAuthConector,
  type Time,
} from "@/lib/api";
import { SeletorIcone } from "@/components/seletor-icone";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// O Construtor de Instrumento (Framework de Instrumentos, Fatia 2). Overlay de tela
// cheia que monta um CONECTOR: várias operações de uma API, cada uma virando uma
// ferramenta do agente — sem código. Grava um Instrumento de `tipo: "conector"`; o
// motor (cerebro/instrumentos/conector.py) o executa. Segue o mockup validado.

type Secao = "operacoes" | "identidade" | "auth" | "testar" | "publicar";

const METODOS: MetodoHttp[] = ["GET", "POST", "PUT", "PATCH", "DELETE"];
const SO_LEITURA = new Set<string>(["GET", "HEAD", "OPTIONS"]);

const SECOES: {
  id: Secao;
  rotulo: string;
  grupo: string;
  Icone: typeof ListChecks;
}[] = [
  { id: "operacoes", rotulo: "Operações", grupo: "Definição", Icone: ListChecks },
  { id: "identidade", rotulo: "Identidade", grupo: "Definição", Icone: Contact },
  { id: "auth", rotulo: "Autenticação", grupo: "Definição", Icone: KeyRound },
  { id: "testar", rotulo: "Testar conexão", grupo: "Antes de publicar", Icone: FlaskConical },
  { id: "publicar", rotulo: "Publicar", grupo: "Antes de publicar", Icone: Rocket },
];

const AUTHS: { valor: TipoAuthConector; rotulo: string }[] = [
  { valor: "nenhuma", rotulo: "Sem autenticação" },
  { valor: "bearer", rotulo: "Token de acesso (Bearer)" },
  { valor: "cabecalho", rotulo: "Chave no cabeçalho" },
  { valor: "query", rotulo: "Chave na URL (query)" },
  { valor: "basic", rotulo: "Usuário e senha (Basic)" },
  { valor: "oauth2", rotulo: "OAuth 2.0 (o Batuta renova o token)" },
];

function opVazia(n: number): OperacaoConector {
  return {
    nome: `Operação ${n}`,
    descricao: "",
    metodo: "GET",
    url: "",
    cabecalhos: {},
    campos: [],
    campos_resposta: [],
  };
}

function campoVazio(): CampoConector {
  return { nome: "", papel: "ia", destino: "query", valor: "", descricao: "", obrigatorio: true };
}

// Os [nomes] entre colchetes de uma URL (o padrão do Bubble): cada um vira um campo.
function colchetesDaUrl(url: string): string[] {
  const achados = url.match(/\[([^\]]+)\]/g) ?? [];
  return [...new Set(achados.map((s) => s.slice(1, -1).trim()).filter(Boolean))];
}

export function ConstrutorInstrumento({
  time,
  instrumento,
  onFechar,
  onSalvou,
}: {
  time: Time;
  instrumento: Instrumento | null; // null = criar; conector existente = editar
  onFechar: () => void;
  onSalvou?: (salvo: Instrumento) => void;
}) {
  const router = useRouter();
  const cfg = (instrumento?.configuracao ?? {}) as Partial<ConfigConector>;

  const [salvoId, setSalvoId] = useState<string | null>(instrumento?.id ?? null);
  const [secao, setSecao] = useState<Secao>("operacoes");

  const [nome, setNome] = useState(instrumento?.nome ?? "");
  const [icone, setIcone] = useState<string | null>(instrumento?.icone ?? null);
  const [descricao, setDescricao] = useState(cfg.descricao ?? "");
  const [categoria, setCategoria] = useState(cfg.categoria ?? "");

  const [authTipo, setAuthTipo] = useState<TipoAuthConector>(cfg.auth_tipo ?? "nenhuma");
  const [authNome, setAuthNome] = useState(cfg.auth_nome ?? "");
  const [authUsuario, setAuthUsuario] = useState(cfg.auth_usuario ?? "");
  const [authSegredo, setAuthSegredo] = useState(""); // vazio = manter o guardado (edição)
  const [urlToken, setUrlToken] = useState(cfg.url_token ?? "");
  const [escopo, setEscopo] = useState(cfg.escopo ?? "");

  // Certificado digital (mTLS): o arquivo vive só até salvar — o cérebro o
  // converte no par PEM guardado no cofre. `certArquivo` é o base64 do que a
  // pessoa escolheu agora; vazio = manter o certificado já guardado.
  const [certArquivo, setCertArquivo] = useState("");
  const [certNomeArquivo, setCertNomeArquivo] = useState("");
  const [certChave, setCertChave] = useState("");
  const [certNomeChave, setCertNomeChave] = useState("");
  const [certSenha, setCertSenha] = useState("");

  const [operacoes, setOperacoes] = useState<OperacaoConector[]>(
    cfg.operacoes?.length ? cfg.operacoes : [opVazia(1)],
  );
  const [opSel, setOpSel] = useState(0);

  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  // Estado do "testar e detectar", por operação.
  const [detectados, setDetectados] = useState<Record<number, CampoDetectado[]>>({});
  const [exemplos, setExemplos] = useState<Record<string, string>>({}); // "idx__campo" → valor
  const [testando, setTestando] = useState(false);
  const [testMsg, setTestMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [resultadoBruto, setResultadoBruto] = useState<string | null>(null);

  const jaGuardadoAuth = instrumento?.segredos?.auth_segredo; // 4 últimos, se já há segredo

  // ─────────────────────────── mutações ───────────────────────────

  function atualizarOp(idx: number, patch: Partial<OperacaoConector>) {
    setOperacoes((ops) => ops.map((op, i) => (i === idx ? { ...op, ...patch } : op)));
  }

  function mudarUrl(idx: number, url: string) {
    setOperacoes((ops) =>
      ops.map((op, i) => {
        if (i !== idx) return op;
        const existentes = new Set(op.campos.map((c) => c.nome));
        const novos = colchetesDaUrl(url)
          .filter((n) => !existentes.has(n))
          .map((n) => ({ ...campoVazio(), nome: n, destino: "url" as const }));
        return { ...op, url, campos: [...op.campos, ...novos] };
      }),
    );
  }

  function atualizarCampo(idx: number, ci: number, patch: Partial<CampoConector>) {
    setOperacoes((ops) =>
      ops.map((op, i) =>
        i === idx
          ? { ...op, campos: op.campos.map((c, j) => (j === ci ? { ...c, ...patch } : c)) }
          : op,
      ),
    );
  }

  function removerCampo(idx: number, ci: number) {
    setOperacoes((ops) =>
      ops.map((op, i) =>
        i === idx ? { ...op, campos: op.campos.filter((_, j) => j !== ci) } : op,
      ),
    );
  }

  function adicionarOperacao() {
    setOperacoes((ops) => [...ops, opVazia(ops.length + 1)]);
    setOpSel(operacoes.length);
  }

  function removerOperacao(idx: number) {
    if (operacoes.length === 1) return;
    setOperacoes((ops) => ops.filter((_, i) => i !== idx));
    setOpSel((s) => (s >= idx && s > 0 ? s - 1 : s));
  }

  function alternarCampoResposta(idx: number, nomeCampo: string) {
    setOperacoes((ops) =>
      ops.map((op, i) => {
        if (i !== idx) return op;
        const tem = op.campos_resposta.includes(nomeCampo);
        return {
          ...op,
          campos_resposta: tem
            ? op.campos_resposta.filter((c) => c !== nomeCampo)
            : [...op.campos_resposta, nomeCampo],
        };
      }),
    );
  }

  // ─────────────────────────── salvar / testar ───────────────────────────

  /** Lê o certificado escolhido e guarda o conteúdo em base64 até salvar. O
   *  navegador não abre um `.pfx` — quem o lê é o cérebro, ao gravar. */
  async function escolherCertificado(
    arquivo: File | undefined,
    guardarConteudo: (b64: string) => void,
    guardarNome: (nome: string) => void,
  ) {
    if (!arquivo) return;
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        const leitor = new FileReader();
        leitor.onload = () => {
          const res = String(leitor.result ?? "");
          const virgula = res.indexOf(",");
          resolve(virgula >= 0 ? res.slice(virgula + 1) : res);
        };
        leitor.onerror = () => reject(leitor.error);
        leitor.readAsDataURL(arquivo);
      });
      guardarConteudo(b64);
      guardarNome(arquivo.name);
      setErro(null);
    } catch {
      setErro("Não consegui ler o arquivo. Tente escolher de novo.");
    }
  }

  function montarConfig(): ConfigConector {
    const c: ConfigConector = {
      auth_tipo: authTipo,
      auth_nome: authNome,
      auth_usuario: authUsuario,
      url_token: urlToken,
      escopo,
      operacoes,
      descricao,
      categoria,
    };
    // Segredo e certificado seguem a regra de campo de senha: em branco PRESERVA
    // o que já está guardado (o cofre nunca reexibe nada).
    if (authSegredo.trim()) c.auth_segredo = authSegredo.trim();
    if (certArquivo) {
      c.arquivo = certArquivo;
      if (certChave) c.chave_arquivo = certChave;
      if (certSenha) c.senha_certificado = certSenha;
    }
    return c;
  }

  async function salvar(silencioso = false): Promise<Instrumento | null> {
    if (!nome.trim()) {
      setErro("Dê um nome ao instrumento.");
      setSecao("identidade");
      return null;
    }
    for (const op of operacoes) {
      if (!op.nome.trim()) {
        setErro("Toda operação precisa de um nome.");
        setSecao("operacoes");
        return null;
      }
      if (!op.url.trim()) {
        setErro(`A operação "${op.nome}" precisa de um endereço (URL).`);
        setSecao("operacoes");
        return null;
      }
    }
    const eraNovo = !salvoId;
    setSalvando(true);
    setErro(null);
    try {
      const base = { nome: nome.trim(), configuracao: montarConfig(), icone };
      const salvo = salvoId
        ? await api.put<Instrumento>(`/instrumentos/${salvoId}`, base)
        : await api.post<Instrumento>(`/times/${time.id}/instrumentos`, {
            ...base,
            tipo: "conector",
          });
      setSalvoId(salvo.id);
      // Não reter segredo nem certificado depois de gravados (ficam no cofre).
      setAuthSegredo("");
      setCertArquivo("");
      setCertChave("");
      setCertSenha("");
      if (!silencioso) toast.success(eraNovo ? "Instrumento criado" : "Instrumento salvo");
      onSalvou?.(salvo);
      router.refresh();
      return salvo;
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha ao salvar o instrumento"));
      return null;
    } finally {
      setSalvando(false);
    }
  }

  // Salva (para ter id + cofre) e roda UMA operação com valores de exemplo.
  async function testar(idx: number): Promise<RespostaTeste | null> {
    const salvo = await salvar(true); // salva em silêncio (sem toast) antes de testar
    if (!salvo) return null;
    const op = operacoes[idx];
    const valores: Record<string, string> = {};
    for (const campo of op.campos) {
      if (campo.papel !== "ia") continue;
      const v = exemplos[`${idx}__${campo.nome}`];
      if (v != null && v !== "") valores[campo.nome] = v;
    }
    setTestando(true);
    setTestMsg(null);
    try {
      const r = await api.post<RespostaTeste>(`/instrumentos/${salvo.id}/testar-operacao`, {
        operacao: op.nome,
        valores,
      });
      if (r.ok) {
        setDetectados((d) => ({ ...d, [idx]: r.campos_detectados }));
        setTestMsg({
          ok: true,
          texto: `Conexão ok — ${r.campos_detectados.length} campos na resposta. Marque os que o agente precisa.`,
        });
        setResultadoBruto(JSON.stringify(r.corpo, null, 2));
      } else {
        setTestMsg({ ok: false, texto: r.erro ?? "A chamada falhou." });
        setResultadoBruto(null);
      }
      return r;
    } catch (e) {
      setTestMsg({ ok: false, texto: mensagemDeErro(e, "Falha ao testar a operação") });
      return null;
    } finally {
      setTestando(false);
    }
  }

  const op = operacoes[opSel];
  const opEscreve = op ? !SO_LEITURA.has(op.metodo) : false;

  // ─────────────────────────── UI ───────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      {/* topbar */}
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
        <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Voltar">
          <ArrowLeft className="size-4" />
        </Button>
        <div className="hidden items-center gap-1.5 text-sm text-muted-foreground sm:flex">
          <span>Instrumentos</span>
          <ChevronRight className="size-3.5" />
          <span className="text-foreground">Construtor</span>
        </div>
        <span className="ml-1 min-w-0 truncate font-medium text-foreground">
          {nome || "Novo instrumento"}
        </span>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          {salvoId ? (
            <>
              <Check className="size-3.5 text-success" /> salvo
            </>
          ) : (
            "rascunho"
          )}
        </span>
        <Button onClick={() => salvar()} disabled={salvando}>
          <Sparkles className="size-4" />
          {salvando ? "Salvando…" : salvoId ? "Salvar" : "Criar instrumento"}
        </Button>
      </header>

      {erro && (
        <div className="shrink-0 px-4 pt-3">
          <Aviso>{erro}</Aviso>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {/* rail de seções */}
        <nav className="hidden w-56 shrink-0 overflow-y-auto border-r border-border p-3 md:block">
          {["Definição", "Antes de publicar"].map((grupo) => (
            <div key={grupo} className="mb-2">
              <div className="px-2 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
                {grupo}
              </div>
              {SECOES.filter((s) => s.grupo === grupo).map(({ id, rotulo, Icone }) => (
                <button
                  key={id}
                  onClick={() => setSecao(id)}
                  className={`mb-0.5 flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
                    secao === id
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Icone className="size-4 shrink-0" />
                  {rotulo}
                  {id === "operacoes" && (
                    <span className="ml-auto rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">
                      {operacoes.length}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
          <p className="mt-3 rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
            Este instrumento vira <strong className="font-medium text-foreground">
              {operacoes.length} {operacoes.length === 1 ? "ferramenta" : "ferramentas"}
            </strong>{" "}
            no cinto do agente — cada operação é uma ação que a IA pode acionar. Sem código.
          </p>
        </nav>

        {/* conteúdo */}
        <main className="min-w-0 flex-1 overflow-y-auto px-5 py-6 sm:px-8">
          {/* seletor de seção no mobile */}
          <div className="mb-5 md:hidden">
            <Select value={secao} onChange={(e) => setSecao(e.target.value as Secao)}>
              {SECOES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.rotulo}
                </option>
              ))}
            </Select>
          </div>

          <div className="mx-auto max-w-3xl">
            {secao === "operacoes" && op && (
              <SecaoOperacoes
                operacoes={operacoes}
                opSel={opSel}
                op={op}
                opEscreve={opEscreve}
                detectados={detectados[opSel] ?? []}
                exemplos={exemplos}
                testando={testando}
                testMsg={testMsg}
                onSelecionar={setOpSel}
                onAdicionar={adicionarOperacao}
                onRemover={removerOperacao}
                onAtualizar={(patch) => atualizarOp(opSel, patch)}
                onMudarUrl={(url) => mudarUrl(opSel, url)}
                onAtualizarCampo={(ci, patch) => atualizarCampo(opSel, ci, patch)}
                onRemoverCampo={(ci) => removerCampo(opSel, ci)}
                onAdicionarCampo={() =>
                  atualizarOp(opSel, { campos: [...op.campos, campoVazio()] })
                }
                onMudarExemplo={(nomeCampo, v) =>
                  setExemplos((e) => ({ ...e, [`${opSel}__${nomeCampo}`]: v }))
                }
                onTestar={() => testar(opSel)}
                onAlternarCampoResposta={(nomeCampo) =>
                  alternarCampoResposta(opSel, nomeCampo)
                }
              />
            )}

            {secao === "identidade" && (
              <SecaoIdentidade
                nome={nome}
                icone={icone}
                categoria={categoria}
                descricao={descricao}
                onNome={setNome}
                onIcone={setIcone}
                onCategoria={setCategoria}
                onDescricao={setDescricao}
              />
            )}

            {secao === "auth" && (
              <SecaoAuth
                authTipo={authTipo}
                authNome={authNome}
                authUsuario={authUsuario}
                authSegredo={authSegredo}
                urlToken={urlToken}
                escopo={escopo}
                jaGuardado={jaGuardadoAuth}
                certGuardado={Boolean(instrumento?.segredos?.certificado)}
                certNomeArquivo={certNomeArquivo}
                certNomeChave={certNomeChave}
                certSenha={certSenha}
                onTipo={setAuthTipo}
                onNome={setAuthNome}
                onUsuario={setAuthUsuario}
                onSegredo={setAuthSegredo}
                onUrlToken={setUrlToken}
                onEscopo={setEscopo}
                onArquivo={(a) => escolherCertificado(a, setCertArquivo, setCertNomeArquivo)}
                onChaveArquivo={(a) => escolherCertificado(a, setCertChave, setCertNomeChave)}
                onCertSenha={setCertSenha}
              />
            )}

            {secao === "testar" && (
              <SecaoTestar
                operacoes={operacoes}
                opSel={opSel}
                exemplos={exemplos}
                testando={testando}
                testMsg={testMsg}
                resultadoBruto={resultadoBruto}
                onSelecionar={setOpSel}
                onMudarExemplo={(nomeCampo, v) =>
                  setExemplos((e) => ({ ...e, [`${opSel}__${nomeCampo}`]: v }))
                }
                onTestar={() => testar(opSel)}
              />
            )}

            {secao === "publicar" && <SecaoPublicar time={time} />}
          </div>
        </main>
      </div>
    </div>
  );
}

// ─────────────────────────── Operações ───────────────────────────

function Badge({ tipo }: { tipo: "acao" | "dado" | "portao" }) {
  const cfg = {
    acao: { c: "bg-destructive/10 text-destructive", Icone: ShieldAlert, t: "Ação" },
    dado: { c: "bg-success/10 text-success", Icone: Eye, t: "Só leitura" },
    portao: { c: "bg-warning/10 text-warning", Icone: Lock, t: "Portão" },
  }[tipo];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${cfg.c}`}
    >
      <cfg.Icone className="size-3" /> {cfg.t}
    </span>
  );
}

function SecaoOperacoes({
  operacoes,
  opSel,
  op,
  opEscreve,
  detectados,
  exemplos,
  testando,
  testMsg,
  onSelecionar,
  onAdicionar,
  onRemover,
  onAtualizar,
  onMudarUrl,
  onAtualizarCampo,
  onRemoverCampo,
  onAdicionarCampo,
  onMudarExemplo,
  onTestar,
  onAlternarCampoResposta,
}: {
  operacoes: OperacaoConector[];
  opSel: number;
  op: OperacaoConector;
  opEscreve: boolean;
  detectados: CampoDetectado[];
  exemplos: Record<string, string>;
  testando: boolean;
  testMsg: { ok: boolean; texto: string } | null;
  onSelecionar: (i: number) => void;
  onAdicionar: () => void;
  onRemover: (i: number) => void;
  onAtualizar: (patch: Partial<OperacaoConector>) => void;
  onMudarUrl: (url: string) => void;
  onAtualizarCampo: (ci: number, patch: Partial<CampoConector>) => void;
  onRemoverCampo: (ci: number) => void;
  onAdicionarCampo: () => void;
  onMudarExemplo: (nomeCampo: string, v: string) => void;
  onTestar: () => void;
  onAlternarCampoResposta: (nomeCampo: string) => void;
}) {
  const camposIa = op.campos.filter((c) => c.papel === "ia");
  const [manualNome, setManualNome] = useState("");
  // Campos escolhidos que NÃO vieram na amostra detectada (adicionados pelo nome).
  const manuais = op.campos_resposta.filter(
    (c) => !detectados.some((d) => d.nome === c),
  );
  return (
    <div>
      <header className="mb-5">
        <h1 className="text-xl font-medium tracking-tight text-foreground">Operações</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Um instrumento, várias operações. Cada uma vira uma ferramenta que o agente
          pode acionar — é aqui que mora o poder: um conector só, vários endpoints.
        </p>
      </header>

      {/* lista de operações */}
      <div className="mb-3 flex flex-col gap-2">
        {operacoes.map((o, i) => {
          const escreve = !SO_LEITURA.has(o.metodo);
          return (
            <button
              key={i}
              onClick={() => onSelecionar(i)}
              className={`flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-left transition-colors ${
                i === opSel ? "border-primary ring-2 ring-primary/15" : "border-border hover:bg-muted/40"
              }`}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">
                  {o.nome || "(sem nome)"}
                </span>
                <span className="block truncate font-mono text-xs text-muted-foreground">
                  {o.metodo} · {o.url || "—"}
                </span>
              </span>
              <Badge tipo={escreve ? "acao" : "dado"} />
              {escreve && <Badge tipo="portao" />}
            </button>
          );
        })}
      </div>

      <button
        onClick={onAdicionar}
        className="mb-6 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/40 py-3 text-sm font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary"
      >
        <Plus className="size-4" /> Adicionar operação
      </button>

      {/* editor da operação selecionada */}
      <div className="overflow-hidden rounded-lg border border-primary">
        <div className="flex items-center gap-3 border-b border-border bg-muted/40 px-4 py-3">
          <span className="min-w-0 flex-1">
            <Input
              value={op.nome}
              onChange={(e) => onAtualizar({ nome: e.target.value })}
              className="h-8 font-medium"
              placeholder="Nome da operação"
            />
          </span>
          {operacoes.length > 1 && (
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={() => onRemover(opSel)}
              aria-label="Remover operação"
            >
              <Trash2 className="size-4 text-muted-foreground" />
            </Button>
          )}
        </div>

        <div className="flex flex-col gap-5 p-4">
          {/* o que a operação faz (a IA lê) */}
          <Label className="flex-col items-start gap-1">
            O que ela faz (o agente lê isto)
            <Textarea
              value={op.descricao}
              onChange={(e) => onAtualizar({ descricao: e.target.value })}
              placeholder="Ex.: publica uma foto na conta; o agente descreve a foto e a legenda."
              rows={2}
            />
          </Label>

          {/* 1. endereço */}
          <div className="border-t border-border pt-4">
            <div className="mb-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
              1 · Endereço da chamada
            </div>
            <div className="flex gap-2">
              <Select
                value={op.metodo}
                onChange={(e) => onAtualizar({ metodo: e.target.value as MetodoHttp })}
                className="w-28 shrink-0"
              >
                {METODOS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </Select>
              <Input
                value={op.url}
                onChange={(e) => onMudarUrl(e.target.value)}
                placeholder="https://api.exemplo.com/v1/[id]/itens"
                className="font-mono text-[13px]"
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Escreva <code className="rounded bg-muted px-1 font-mono">[nome]</code> no
              endereço e o campo aparece sozinho abaixo.
            </p>
          </div>

          {/* 2. campos */}
          <div className="border-t border-border pt-4">
            <div className="mb-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
              2 · Campos — quem preenche cada um?
            </div>
            <div className="flex flex-col gap-2">
              {op.campos.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Nenhum campo ainda. Adicione um, ou escreva <code className="font-mono">[nome]</code> no
                  endereço acima.
                </p>
              )}
              {op.campos.map((campo, ci) => (
                <div
                  key={ci}
                  className="grid grid-cols-1 gap-2 rounded-md border border-border p-2.5 sm:grid-cols-[1fr_auto]"
                >
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2">
                      <Input
                        value={campo.nome}
                        onChange={(e) => onAtualizarCampo(ci, { nome: e.target.value })}
                        placeholder="nome_do_campo"
                        className="h-8 font-mono text-[13px]"
                      />
                      <Select
                        value={campo.destino}
                        onChange={(e) =>
                          onAtualizarCampo(ci, {
                            destino: e.target.value as CampoConector["destino"],
                          })
                        }
                        className="h-8 w-24 shrink-0 text-xs"
                      >
                        <option value="query">na URL (query)</option>
                        <option value="corpo">no corpo</option>
                        <option value="url">no endereço</option>
                      </Select>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        onClick={() => onRemoverCampo(ci)}
                        aria-label="Remover campo"
                      >
                        <Trash2 className="size-3.5 text-muted-foreground" />
                      </Button>
                    </div>
                    {campo.papel === "ia" ? (
                      <Input
                        value={campo.descricao}
                        onChange={(e) => onAtualizarCampo(ci, { descricao: e.target.value })}
                        placeholder="Dica para a IA (o que preencher aqui)"
                        className="h-8 text-xs"
                      />
                    ) : (
                      <Input
                        value={campo.valor}
                        onChange={(e) => onAtualizarCampo(ci, { valor: e.target.value })}
                        placeholder="Valor fixo (vale para toda chamada)"
                        className="h-8 font-mono text-xs"
                      />
                    )}
                  </div>
                  <div className="flex items-start gap-1 sm:pl-1">
                    <SegPapel
                      papel={campo.papel}
                      onChange={(papel) => onAtualizarCampo(ci, { papel })}
                    />
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={onAdicionarCampo}
              className="mt-2 flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <Plus className="size-3.5" /> Adicionar campo
            </button>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-primary" /> IA preenche na hora (vira argumento)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-muted-foreground/50" /> Você fixa (vale para toda chamada)
              </span>
            </div>
          </div>

          {/* 3. comportamento (derivado — informativo nesta fatia) */}
          <div className="border-t border-border pt-4">
            <div className="mb-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
              3 · Comportamento
            </div>
            {opEscreve ? (
              <Aviso variant="atencao">
                Esta operação <strong>escreve</strong> ({op.metodo}) — não dá para desfazer. Se
                o conector tiver qualquer operação de escrita, o Batuta pede sua aprovação antes
                de agir (a parede de ativação). Detectado do método.
              </Aviso>
            ) : (
              <Aviso variant="sucesso">
                Esta operação <strong>só lê</strong> ({op.metodo}) — não muda nada no sistema
                externo e corre livre, sem portão.
              </Aviso>
            )}
          </div>

          {/* 4. testar e detectar */}
          <div className="border-t border-border pt-4">
            <div className="mb-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
              4 · Testar e detectar a resposta
            </div>
            <div className="rounded-md border border-border">
              <div className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/40 px-3 py-2.5">
                <p className="min-w-0 flex-1 text-xs text-muted-foreground">
                  Rode a chamada uma vez. O Batuta lê a resposta e mostra os campos — marque só
                  os que o agente precisa (corta custo de tokens).
                </p>
                <Button size="sm" onClick={onTestar} disabled={testando}>
                  <Play className="size-3.5" /> {testando ? "Testando…" : "Testar e detectar"}
                </Button>
              </div>

              {camposIa.length > 0 && (
                <div className="flex flex-col gap-2 border-b border-border p-3">
                  <span className="text-xs font-medium text-muted-foreground">
                    Valores de exemplo (para o teste)
                  </span>
                  {camposIa.map((campo) => (
                    <div key={campo.nome} className="flex items-center gap-2">
                      <span className="w-32 shrink-0 truncate font-mono text-xs text-muted-foreground">
                        {campo.nome || "—"}
                      </span>
                      <Input
                        value={exemplos[`${opSel}__${campo.nome}`] ?? ""}
                        onChange={(e) => onMudarExemplo(campo.nome, e.target.value)}
                        placeholder="valor de exemplo"
                        className="h-8 text-xs"
                      />
                    </div>
                  ))}
                </div>
              )}

              {testMsg && (
                <div className="p-3">
                  <Aviso variant={testMsg.ok ? "sucesso" : "erro"}>{testMsg.texto}</Aviso>
                </div>
              )}

              {(detectados.length > 0 || op.campos_resposta.length > 0) && (
                <div className="px-3 pb-3">
                  {detectados.map((c) => {
                    const marcado = op.campos_resposta.includes(c.nome);
                    return (
                      <button
                        key={c.nome}
                        type="button"
                        onClick={() => onAlternarCampoResposta(c.nome)}
                        className="flex w-full items-center gap-3 border-t border-border py-2 text-left first:border-t-0"
                      >
                        <span
                          className={`grid size-[18px] shrink-0 place-items-center rounded border ${
                            marcado
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-background"
                          }`}
                        >
                          {marcado && <Check className="size-3" />}
                        </span>
                        <span className="font-mono text-[13px] font-medium text-foreground">
                          {c.nome}
                        </span>
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                          {c.tipo}
                        </span>
                        <span className="ml-auto max-w-[40%] truncate font-mono text-xs text-muted-foreground/70">
                          {String(c.exemplo ?? "")}
                        </span>
                      </button>
                    );
                  })}

                  {/* campos escolhidos pelo nome (vieram vazios na amostra do Bubble) */}
                  {manuais.map((nomeCampo) => (
                    <button
                      key={nomeCampo}
                      type="button"
                      onClick={() => onAlternarCampoResposta(nomeCampo)}
                      className="flex w-full items-center gap-3 border-t border-border py-2 text-left first:border-t-0"
                    >
                      <span className="grid size-[18px] shrink-0 place-items-center rounded border border-primary bg-primary text-primary-foreground">
                        <Check className="size-3" />
                      </span>
                      <span className="font-mono text-[13px] font-medium text-foreground">
                        {nomeCampo}
                      </span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                        adicionado
                      </span>
                    </button>
                  ))}

                  {/* adicionar campo pelo nome — para o que veio vazio na amostra */}
                  <form
                    className="mt-2 flex items-center gap-2 border-t border-border pt-2.5"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const nomeCampo = manualNome.trim();
                      if (nomeCampo && !op.campos_resposta.includes(nomeCampo)) {
                        onAlternarCampoResposta(nomeCampo);
                      }
                      setManualNome("");
                    }}
                  >
                    <Input
                      value={manualNome}
                      onChange={(e) => setManualNome(e.target.value)}
                      placeholder="Falta um campo? adicione pelo nome (ex.: cpo.TipoProjeto)"
                      className="h-8 font-mono text-xs"
                    />
                    <Button type="submit" size="sm" variant="outline" disabled={!manualNome.trim()}>
                      <Plus className="size-3.5" /> Adicionar
                    </Button>
                  </form>

                  <p className="mt-2 text-xs text-muted-foreground">
                    {op.campos_resposta.length === 0
                      ? "Nada marcado = traz a resposta inteira."
                      : `Trazendo ${op.campos_resposta.length} ${
                          op.campos_resposta.length === 1 ? "campo" : "campos"
                        } ao agente — o resto fica de fora para economizar.`}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Controle segmentado do papel do campo (IA / Fixo).
function SegPapel({
  papel,
  onChange,
}: {
  papel: PapelCampoConector;
  onChange: (p: PapelCampoConector) => void;
}) {
  return (
    <div className="inline-flex rounded-full border border-border bg-muted/50 p-0.5">
      {(["ia", "fixo"] as const).map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
            papel === p
              ? p === "ia"
                ? "bg-primary text-primary-foreground"
                : "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {p === "ia" ? "IA" : "Fixo"}
        </button>
      ))}
    </div>
  );
}

// ─────────────────────────── Identidade ───────────────────────────

function SecaoIdentidade({
  nome,
  icone,
  categoria,
  descricao,
  onNome,
  onIcone,
  onCategoria,
  onDescricao,
}: {
  nome: string;
  icone: string | null;
  categoria: string;
  descricao: string;
  onNome: (v: string) => void;
  onIcone: (v: string | null) => void;
  onCategoria: (v: string) => void;
  onDescricao: (v: string) => void;
}) {
  return (
    <div>
      <header className="mb-5">
        <h1 className="text-xl font-medium tracking-tight text-foreground">Identidade</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Como esse instrumento aparece para você e para que ele serve.
        </p>
      </header>
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5">
        <div className="flex flex-wrap gap-4">
          <Label className="flex-1 flex-col items-start gap-1" style={{ minWidth: 190 }}>
            Nome
            <Input value={nome} onChange={(e) => onNome(e.target.value)} autoFocus />
          </Label>
          <Label className="flex-1 flex-col items-start gap-1" style={{ minWidth: 190 }}>
            Categoria
            <Input
              value={categoria}
              onChange={(e) => onCategoria(e.target.value)}
              placeholder="Ex.: Redes sociais"
            />
          </Label>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-foreground">Ícone</span>
          <SeletorIcone valor={icone} onChange={onIcone} />
        </div>
        <Label className="flex-col items-start gap-1">
          Para que serve
          <Textarea
            value={descricao}
            onChange={(e) => onDescricao(e.target.value)}
            placeholder="Escreva como explicaria a um colega. Ex.: publica fotos e lê comentários da minha conta do Instagram."
            rows={2}
          />
          <span className="text-xs font-normal text-muted-foreground">
            Referência sua. O que guia o agente em cada ação é a descrição de cada operação.
          </span>
        </Label>
      </div>
    </div>
  );
}

// ─────────────────────────── Autenticação ───────────────────────────

function SecaoAuth({
  authTipo,
  authNome,
  authUsuario,
  authSegredo,
  urlToken,
  escopo,
  jaGuardado,
  certGuardado,
  certNomeArquivo,
  certNomeChave,
  certSenha,
  onTipo,
  onNome,
  onUsuario,
  onSegredo,
  onUrlToken,
  onEscopo,
  onArquivo,
  onChaveArquivo,
  onCertSenha,
}: {
  authTipo: TipoAuthConector;
  authNome: string;
  authUsuario: string;
  authSegredo: string;
  urlToken: string;
  escopo: string;
  jaGuardado: string | undefined;
  certGuardado: boolean;
  certNomeArquivo: string;
  certNomeChave: string;
  certSenha: string;
  onTipo: (v: TipoAuthConector) => void;
  onNome: (v: string) => void;
  onUsuario: (v: string) => void;
  onSegredo: (v: string) => void;
  onUrlToken: (v: string) => void;
  onEscopo: (v: string) => void;
  onArquivo: (arquivo: File | undefined) => void;
  onChaveArquivo: (arquivo: File | undefined) => void;
  onCertSenha: (v: string) => void;
}) {
  // Rótulo da metade secreta — muda com o tipo, porque a mesma caixa guarda
  // coisas diferentes (token, chave, senha, client secret).
  const rotuloSegredo =
    authTipo === "bearer"
      ? "Token de acesso"
      : authTipo === "basic"
        ? "Senha"
        : authTipo === "oauth2"
          ? "Client Secret"
          : "Chave / segredo";
  return (
    <div>
      <header className="mb-5">
        <h1 className="text-xl font-medium tracking-tight text-foreground">Autenticação</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Como o Batuta se identifica no serviço. Escolha o tipo e preencha — sem código. O
          segredo vai para o cofre e nunca aparece em claro.
        </p>
      </header>
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5">
        <Label className="flex-col items-start gap-1">
          Tipo de autenticação
          <Select value={authTipo} onChange={(e) => onTipo(e.target.value as TipoAuthConector)}>
            {AUTHS.map((a) => (
              <option key={a.valor} value={a.valor}>
                {a.rotulo}
              </option>
            ))}
          </Select>
        </Label>

        {(authTipo === "cabecalho" || authTipo === "query") && (
          <Label className="flex-col items-start gap-1">
            {authTipo === "cabecalho" ? "Nome do cabeçalho" : "Nome do parâmetro"}
            <Input
              value={authNome}
              onChange={(e) => onNome(e.target.value)}
              placeholder={authTipo === "cabecalho" ? "X-API-Key" : "api_key"}
              className="font-mono text-[13px]"
            />
          </Label>
        )}

        {(authTipo === "basic" || authTipo === "oauth2") && (
          <Label className="flex-col items-start gap-1">
            {authTipo === "basic" ? "Usuário" : "Client ID"}
            <Input
              value={authUsuario}
              onChange={(e) => onUsuario(e.target.value)}
              placeholder={authTipo === "basic" ? "maria@empresa.com" : "o identificador que o serviço deu"}
            />
          </Label>
        )}

        {authTipo !== "nenhuma" && (
          <Label className="flex-col items-start gap-1">
            <span className="flex items-center gap-1.5">
              <Lock className="size-3 text-muted-foreground" />
              {rotuloSegredo}
            </span>
            <Input
              type="password"
              value={authSegredo}
              onChange={(e) => onSegredo(e.target.value)}
              autoComplete="new-password"
              placeholder={
                jaGuardado
                  ? `•••• ${jaGuardado} — em branco para manter`
                  : "cole aqui"
              }
            />
            <span className="text-xs font-normal text-muted-foreground">
              Guardado cifrado no cofre; nunca é reexibido.
            </span>
          </Label>
        )}

        {authTipo === "oauth2" && (
          <>
            <Label className="flex-col items-start gap-1">
              Endereço do token
              <Input
                value={urlToken}
                onChange={(e) => onUrlToken(e.target.value)}
                placeholder="https://servico.com/oauth/token"
                className="font-mono text-[13px]"
              />
              <span className="text-xs font-normal text-muted-foreground">
                O Batuta troca o Client ID e o Client Secret por um token neste endereço, e
                renova sozinho antes de vencer.
              </span>
            </Label>
            <Label className="flex-col items-start gap-1">
              Escopo
              <Input
                value={escopo}
                onChange={(e) => onEscopo(e.target.value)}
                placeholder="deixe em branco se o serviço não pedir"
                className="font-mono text-[13px]"
              />
            </Label>
          </>
        )}
      </div>

      {/* Certificado digital — não é um "tipo" de autenticação: é a conexão em si.
          Um banco costuma exigir certificado E OAuth ao mesmo tempo, por isso vive
          num bloco próprio, combinável com qualquer tipo acima. */}
      <header className="mb-5 mt-8">
        <h2 className="text-base font-medium tracking-tight text-foreground">
          Certificado digital
        </h2>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Só para serviços que exigem se identificar com um certificado — é o caso de APIs
          bancárias (Pix, boleto). A maioria das APIs não pede; pule este bloco.
        </p>
      </header>
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5">
        {certGuardado && !certNomeArquivo && (
          <Aviso variant="sucesso">
            Já há um certificado guardado neste instrumento. Envie um arquivo novo só para
            trocá-lo.
          </Aviso>
        )}

        <Label className="flex-col items-start gap-1">
          <span className="flex items-center gap-1.5">
            <Lock className="size-3 text-muted-foreground" />
            Arquivo do certificado
          </span>
          <input
            type="file"
            accept=".pfx,.p12,.pem,.crt,.cer"
            className="text-sm text-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:text-foreground hover:file:bg-muted"
            onChange={(e) => onArquivo(e.target.files?.[0])}
          />
          <span className="text-xs font-normal text-muted-foreground">
            {certNomeArquivo
              ? `Selecionado: ${certNomeArquivo}`
              : "Aceita .pfx/.p12 (com senha) ou .pem/.crt. Vai cifrado para o cofre."}
          </span>
        </Label>

        <Label className="flex-col items-start gap-1">
          Senha do certificado
          <Input
            type="password"
            value={certSenha}
            onChange={(e) => onCertSenha(e.target.value)}
            autoComplete="new-password"
            placeholder="só se o arquivo tiver senha; é usada para abrir e não fica guardada"
          />
        </Label>

        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">Minha chave está num arquivo .key separado</summary>
          <div className="mt-2 flex flex-col gap-1">
            <input
              type="file"
              accept=".key,.pem"
              className="text-sm text-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:text-foreground hover:file:bg-muted"
              onChange={(e) => onChaveArquivo(e.target.files?.[0])}
            />
            {certNomeChave && <span>Selecionado: {certNomeChave}</span>}
          </div>
        </details>
      </div>

      <Aviso variant="atencao" className="mt-4">
        Alguns tokens (ex.: Instagram) duram ~60 dias e são regerados à mão. No OAuth 2.0 acima, a
        renovação é automática.
      </Aviso>
    </div>
  );
}

// ─────────────────────────── Testar conexão ───────────────────────────

function SecaoTestar({
  operacoes,
  opSel,
  exemplos,
  testando,
  testMsg,
  resultadoBruto,
  onSelecionar,
  onMudarExemplo,
  onTestar,
}: {
  operacoes: OperacaoConector[];
  opSel: number;
  exemplos: Record<string, string>;
  testando: boolean;
  testMsg: { ok: boolean; texto: string } | null;
  resultadoBruto: string | null;
  onSelecionar: (i: number) => void;
  onMudarExemplo: (nomeCampo: string, v: string) => void;
  onTestar: () => void;
}) {
  const op = operacoes[opSel];
  const camposIa = op?.campos.filter((c) => c.papel === "ia") ?? [];
  return (
    <div>
      <header className="mb-5">
        <h1 className="text-xl font-medium tracking-tight text-foreground">Testar conexão</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Rode uma operação com valores de exemplo antes de soltar para os agentes. O Batuta
          salva o instrumento e faz a chamada real.
        </p>
      </header>
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5">
        <Label className="flex-col items-start gap-1">
          Operação a testar
          <Select value={String(opSel)} onChange={(e) => onSelecionar(Number(e.target.value))}>
            {operacoes.map((o, i) => (
              <option key={i} value={i}>
                {o.nome} ({o.metodo})
              </option>
            ))}
          </Select>
        </Label>

        {camposIa.map((campo) => (
          <Label key={campo.nome} className="flex-col items-start gap-1">
            {campo.nome} (exemplo)
            <Input
              value={exemplos[`${opSel}__${campo.nome}`] ?? ""}
              onChange={(e) => onMudarExemplo(campo.nome, e.target.value)}
              className="font-mono text-[13px]"
            />
          </Label>
        ))}

        <div>
          <Button onClick={onTestar} disabled={testando}>
            <Play className="size-4" /> {testando ? "Rodando…" : "Rodar teste"}
          </Button>
        </div>

        {testMsg && <Aviso variant={testMsg.ok ? "sucesso" : "erro"}>{testMsg.texto}</Aviso>}

        {resultadoBruto && (
          <pre className="max-h-80 overflow-auto rounded-md bg-foreground p-3 text-xs text-background">
            {resultadoBruto}
          </pre>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────── Publicar ───────────────────────────

function SecaoPublicar({ time }: { time: Time }) {
  return (
    <div>
      <header className="mb-5">
        <h1 className="text-xl font-medium tracking-tight text-foreground">Publicar</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Onde este instrumento pode ser usado.
        </p>
      </header>
      <div className="mb-4 flex flex-col gap-4 rounded-lg border border-border bg-card p-5">
        <Label className="flex-col items-start gap-1">
          Alcance
          <Select value="time" disabled>
            <option value="time">Neste time ({time.nome})</option>
          </Select>
          <span className="text-xs font-normal text-muted-foreground">
            Por ora, o conector fica no time onde foi criado. Torná-lo uma biblioteca da
            organização (disponível a todos os times) vem na próxima fatia.
          </span>
        </Label>
      </div>
      <Aviso variant="info">
        Compartilhar com outras organizações e o marketplace público vêm depois. Criar o
        instrumento para você já funciona sem nada disso.
      </Aviso>
    </div>
  );
}
