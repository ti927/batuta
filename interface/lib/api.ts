// Cliente único de acesso ao cérebro (a API em Python/FastAPI).
// A interface nunca fala com o banco direto — sempre passa por aqui (CLAUDE.md §8).
//
// Desde a Fase 6, o cérebro exige autenticação: toda chamada leva o token do
// Supabase em `Authorization: Bearer <token>`. O token vem de contextos
// diferentes — no NAVEGADOR (ilhas-cliente) usa-se `api` daqui; no SERVIDOR
// (Server Components) usa-se `apiServidor` de `lib/api-servidor.ts`. Os dois
// compartilham o núcleo `requisitar()` abaixo.

import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

// Endereço do cérebro, exposto para montar URLs públicas (ex.: webhook de entrada).
export const URL_CEREBRO = BASE;

// O servidor RESPONDEU, mas com status de erro (4xx/5xx). Traz o motivo já em texto.
export class ErroDaApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

// Falha de REDE: o fetch NÃO completou uma ida-e-volta (conexão caiu, offline, servidor
// reiniciando sem responder, ou resposta ilegível). Distinta de ErroDaApi (que teve
// resposta HTTP): a ação pode nem ter chegado ao servidor. A UI mostra isto como "a
// conexão caiu, tente de novo" — nunca um "Falha ao X" genérico e mudo.
export class ErroDeRede extends Error {
  constructor(
    mensagem = "A conexão caiu antes de completar. Verifique sua internet e tente de novo.",
  ) {
    super(mensagem);
  }
}

// Frase HUMANA por status quando o corpo do erro não é JSON (ex.: página HTML de um
// proxy/gateway) — nunca deixa "Erro 502" cru vazar para o usuário.
function mensagemPorStatus(status: number): string {
  if (status === 502 || status === 503 || status === 504)
    return "O Batuta está reiniciando ou sobrecarregado. Tente de novo em instantes.";
  if (status === 401 || status === 403)
    return "Sua sessão expirou ou você não tem acesso a isto. Entre de novo, se preciso.";
  if (status === 404) return "Não encontrei o que você pediu (pode ter sido removido).";
  if (status === 429)
    return "Muitas ações em pouco tempo. Espere um instante e tente de novo.";
  if (status >= 500)
    return "Algo deu errado no Batuta. Tente de novo; se persistir, me avise.";
  return `Não consegui completar (erro ${status}).`;
}

// Texto humano de QUALQUER erro para a tela — evita "Falha ao X" genérico quando dá para
// ser específico. ErroDaApi/ErroDeRede já trazem a mensagem pronta.
export function mensagemDeErro(
  e: unknown,
  padrao = "Não consegui completar a ação. Tente de novo.",
): string {
  if (e instanceof ErroDaApi || e instanceof ErroDeRede) return e.message;
  if (e instanceof Error && e.message) return e.message;
  return padrao;
}

// Núcleo compartilhado: faz a requisição e anexa o token quando houver.
export async function requisitar<T>(
  caminho: string,
  opcoes: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}${caminho}`, { ...opcoes, headers });
  } catch {
    // fetch só lança em falha de REDE (não em status HTTP de erro): conexão caiu,
    // offline, servidor sem responder. Vira um erro tipado, com mensagem honesta.
    throw new ErroDeRede();
  }

  if (!resposta.ok) {
    // O FastAPI devolve o motivo em { detail: ... }; traduzimos para mensagem. Sem JSON
    // (HTML de proxy), caímos numa frase humana por status — nunca "Erro 502" cru.
    let mensagem: string | null = null;
    try {
      const corpo = await resposta.json();
      if (corpo?.detail) {
        mensagem =
          typeof corpo.detail === "string"
            ? corpo.detail
            : JSON.stringify(corpo.detail);
      }
    } catch {
      // resposta sem corpo JSON — usa a frase por status abaixo
    }
    throw new ErroDaApi(resposta.status, mensagem ?? mensagemPorStatus(resposta.status));
  }

  if (resposta.status === 204) return undefined as T;
  try {
    return (await resposta.json()) as T;
  } catch {
    // resposta OK mas corpo ilegível (conexão cortada no meio do download): não sobe
    // um erro cru de parse — trata como queda de rede, com mensagem honesta.
    throw new ErroDeRede("Recebi uma resposta incompleta do Batuta. Tente de novo.");
  }
}

// Token da sessão no NAVEGADOR (cookies/local storage do Supabase).
async function tokenNavegador(): Promise<string | null> {
  const { data } = await criarClienteNavegador().auth.getSession();
  return data.session?.access_token ?? null;
}

// Cliente para ILHAS-CLIENTE ("use client"): pega o token do navegador.
export const api = {
  get: async <T>(caminho: string) =>
    requisitar<T>(caminho, {}, await tokenNavegador()),
  post: async <T>(caminho: string, corpo: unknown) =>
    requisitar<T>(
      caminho,
      { method: "POST", body: JSON.stringify(corpo) },
      await tokenNavegador(),
    ),
  put: async <T>(caminho: string, corpo: unknown) =>
    requisitar<T>(
      caminho,
      { method: "PUT", body: JSON.stringify(corpo) },
      await tokenNavegador(),
    ),
  delete: async (caminho: string) =>
    requisitar<void>(caminho, { method: "DELETE" }, await tokenNavegador()),
};

// ───────────────────────── Tipos do core ─────────────────────────

export type Organizacao = {
  id: string;
  nome: string;
  dono_id: string;
  // Modelo da IA de conversa desta org; null = padrão (Opus).
  modelo_criadora: string | null;
  // Logo da organização como data URI; null = sem logo (mostra a inicial).
  logo_url: string | null;
  // Parede de aprovação ligada? Quando false, automações ativam sem exigir
  // nó-portão antes de ações irreversíveis (config global da org).
  parede_ativacao: boolean;
  criado_em: string;
  atualizado_em: string;
};

// Disponibilidade de provedores (GET /organizacoes/{id}/modelos-disponiveis).
// Um mapa único {provedor: bool}, já que a chave é por provedor (unificação
// 2026-06-15): a mesma chave serve à conversa e aos agentes.
export type ModelosDisponiveis = Record<string, boolean>;

export type Time = {
  id: string;
  organizacao_id: string;
  nome: string;
  descricao: string | null;
  criado_em: string;
  atualizado_em: string;
};

// Visão de saúde do time: contadores das coleções (pílulas das abas) + agregados
// da aba Início. Vem de GET /times/{id}/resumo.
export type TimeResumo = {
  agentes: number;
  instrumentos: number;
  automacoes: number;
  execucoes: number;
  conversas: number;
  ativo: boolean;
  gatilho: string | null;
  custo_acumulado_usd: number;
  taxa_sucesso: number | null;
  pendencias: number;
  conversas_em_andamento: number;
};

export type Papel = "lider" | "agente";

export type RecallMemoria = "sempre" | "sob_demanda";

export type Agente = {
  id: string;
  time_id: string;
  nome: string;
  papel: Papel;
  agent_md: string | null;
  skill_md: string | null;
  tools_md: string | null;
  soul_md: string | null;
  modelo_ia: string | null;
  memoria_ativa: boolean;
  memoria_recall: RecallMemoria;
  criado_em: string;
  atualizado_em: string;
};

// Uma ficha da memória do agente (aprendizado do próprio trabalho, por assunto).
export type MemoriaAgente = {
  id: string;
  agente_id: string;
  assunto: string;
  conteudo: string;
  criado_em: string;
  atualizado_em: string;
};

export type Instrumento = {
  id: string;
  time_id: string;
  nome: string;
  tipo: string;
  configuracao: Record<string, unknown> | null;
  // Ícone escolhido na UI (id do catálogo, ex.: "fab:whatsapp"). Null = genérico.
  icone: string | null;
  // Segredos já guardados (cifrados): campo → 4 últimos dígitos (Fase 7-B).
  segredos: Record<string, string>;
  // Interruptor de aprovação humana: null = automático, true = sempre, false = nunca.
  exige_aprovacao: boolean | null;
  // Resolvido (tipo+config+interruptor): se este instrumento exige portão.
  acao_irreversivel: boolean;
  // Caixa-forte: credencial nomeada da central que este instrumento usa (ou null).
  credencial_id: string | null;
  criado_em: string;
  atualizado_em: string;
};

export type TipoInstrumento = {
  tipo: string;
  nome_exibicao: string;
  // Grupo do instrumento no catálogo (a UI agrupa o dropdown por isto, ex.:
  // "Instagram", "Web (busca e leitura)"). Padrão "Outros".
  categoria?: string;
  descricao: string;
  esquema_config: Record<string, unknown>;
  esquema_args: Record<string, unknown>;
  // Campos da config que são segredos (cifrados, nunca reexibidos) — Fase 7-B.
  campos_secretos: string[];
  // Se o tipo reusa uma chave de serviço compartilhada da org: [campo, serviço]
  // (ex.: ["chave_api","openai"]). Esse campo é OPCIONAL no formulário.
  chave_compartilhada: [string, string] | null;
  // Caixa-forte: tipos de credencial nomeada que este instrumento aceita.
  tipos_credencial_aceitos: string[];
  // Baseline do tipo: este tipo PODE escrever/agir de forma irreversível? (a
  // irreversibilidade real da instância depende da config — método, somente_leitura).
  acao_irreversivel: boolean;
  // Campos com opções DEPENDENTES de outro campo (dropdown dependente): o
  // formulário filtra as opções conforme o controlador (ex.: gerar_imagem filtra
  // tamanho/qualidade pelo modelo). null/ausente = sem dependências.
  dependencias?: Record<
    string,
    { controlado_por: string; opcoes: Record<string, string[]> }
  > | null;
};

// Caixa-forte de credenciais nomeadas (docs/CAIXA-FORTE-PLANO.md).
export type CampoCredencial = {
  nome: string;
  rotulo: string;
  secreto: boolean; // segredo → mascarado; identidade → visível
};

export type TipoCredencial = {
  tipo: string;
  nome_exibicao: string;
  campos: CampoCredencial[];
};

// Resumo mascarado por campo: identidade → {secreto:false, valor}; segredo →
// {secreto:true, ultimos4}. O valor pleno de um segredo nunca volta.
export type CredencialCampoResumo = {
  secreto: boolean;
  valor?: string;
  ultimos4?: string;
};

export type Credencial = {
  id: string;
  organizacao_id: string | null; // nulo = da consultoria
  nome: string;
  tipo: string;
  resumo: Record<string, CredencialCampoResumo> | null;
  compartilhavel: boolean;
  usado_por: number;
  criado_em: string;
  atualizado_em: string;
};

// ─── Mensageria / Conversas (Fase 1) ───
// (Nota: `MensagemConversa`, mais abaixo, é da IA criadora — outro conceito.)

export type MensagemDaConversa = {
  id: string;
  papel: "contato" | "agente" | "operador" | "sistema";
  conteudo: string | null;
  midia: Record<string, unknown> | null;
  entregue: boolean;
  criado_em: string;
};

export type Conversa = {
  id: string;
  instrumento_id: string;
  canal: string;
  contato_chave: string;
  contato_nome: string | null;
  estado:
    | "aberta"
    | "bot_respondendo"
    | "aguardando_resposta"
    | "humano_assumiu"
    | "fechada";
  destino_tipo: string | null;
  destino_id: string | null;
  atribuida_a: string | null;
  turnos: number;
  aguardando_ate: string | null;
  criado_em: string;
  atualizado_em: string;
};

export type ConversaComMensagens = Conversa & {
  mensagens: MensagemDaConversa[];
};

// Métricas do atendimento de um time (GET /times/{id}/conversas/metricas).
export type MetricasAtendimento = {
  periodo_dias: number;
  total: number;
  abertas: number;
  com_humano: number;
  fechadas: number;
  percent_humano: number; // 0..100
  turnos_total: number;
  custo_total_usd: number;
  tempo_resposta_medio_s: number | null;
  por_estado: Record<string, number>;
};

// Estado do canal (GET /mensageria/{id}/canal).
export type StatusCanal = {
  conectado: boolean;
  tem_token: boolean;
  webhook: Record<string, unknown> | null;
};

// O bot alcança o destinatário configurado? (GET /mensageria/{id}/alcance).
// `aplicavel=false` quando não dá para checar (sem token ou sem destinatário fixo).
// `alcancavel=null` = não deu para consultar o Telegram (não alarma).
export type AlcanceCanal = {
  aplicavel: boolean;
  destino?: string;
  alcancavel?: boolean | null;
  bot_username?: string | null;
  motivo?: string | null;
};

// ─── Automações: a cadeia é um GRAFO de nós tipados (bifurcação, loop, portão) ───
// Forma canônica (cérebro: orquestracao/grafo.py). `tone`/`x`/`y` são cosméticos.

export type ToneSaida = "normal" | "ok" | "loop";
export type TipoNo = "gatilho" | "agente" | "roteador" | "fim";
export type TipoGatilho =
  | "manual"
  | "agendamento"
  | "webhook"
  | "comentario_instagram";

export type SaidaCadeia = {
  id?: string;
  rotulo: string; // a condição/decisão — é a CHAVE de roteamento
  quando?: string; // descrição que ajuda o roteador
  destino: string; // id de outro nó (inclui o nó "fim"; pode ser anterior = loop)
  tone?: ToneSaida; // cor da aresta (UI)
  lane?: "above" | "below"; // dica de curva p/ loops (UI)
};

// Aprovação por canal configurada no nó com portão (Fase 6).
export type AprovacaoNo = {
  instrumento_id?: string | null;
  destinatario?: string | null;
};

export type NoCadeia = {
  id: string;
  tipo: TipoNo;
  ref?: string; // id do agente (tipo 'agente'); o mesmo agente pode estar em vários nós
  nome?: string; // rótulo do roteador
  inicial?: boolean; // marca visual do nó inicial
  gate?: boolean; // portão de aprovação (pausa após este nó)
  aprovacao?: AprovacaoNo | null;
  // Ajustes de config DESTE portão (sobrepõem o Tipo de fluxo — cascata do backend
  // `no.config`). Só as chaves ajustadas ficam aqui; o resto herda do fluxo.
  config?: Record<string, unknown>;
  // Roteiro editável do portão (o "portao.md"): o que o agente faz na abertura (como
  // apresentar o pedido) e no fechamento (o que fazer após a resposta). Ambos opcionais
  // — sem eles, vale o comportamento padrão.
  instrucoes?: { abertura?: string; fechamento?: string };
  gatilho?: TipoGatilho; // tipo 'gatilho'
  x?: number;
  y?: number;
  saidas: SaidaCadeia[];
};

export type Cadeia = {
  inicial?: string; // id do nó inicial (nó-agente que recebe a entrada do gatilho)
  nos?: NoCadeia[];
};

// Tolerância na leitura (espelha o backend `grafo.normalizar`): o front pode receber
// uma cadeia no formato ANTIGO (dict-por-agente, `nos` é um objeto + `inicio`) — de
// dados legados ou de uma página renderizada antes do deploy. Estas funções aceitam
// os dois formatos para nenhuma tela quebrar.

// O id do nó inicial, no formato novo (`inicial`) ou antigo (`inicio`).
export function inicialDaCadeia(
  cadeia: Cadeia | null | undefined,
): string | null {
  const c = cadeia as (Cadeia & { inicio?: string }) | null | undefined;
  return c?.inicial ?? c?.inicio ?? null;
}

// Os nós como LISTA, convertendo o formato antigo (nos = dict) na hora.
export function nosDaCadeia(cadeia: Cadeia | null | undefined): NoCadeia[] {
  const nos = cadeia?.nos as unknown;
  if (Array.isArray(nos)) return nos as NoCadeia[];
  if (nos && typeof nos === "object") {
    // formato antigo: { "<agente_id>": { saidas, pausa_humano } }
    const inicio = inicialDaCadeia(cadeia);
    return Object.entries(nos as Record<string, Record<string, unknown>>).map(
      ([id, no]) => ({
        id,
        tipo: "agente" as const,
        ref: id,
        gate: !!(no?.pausa_humano ?? no?.gate),
        inicial: id === inicio,
        saidas: ((no?.saidas as SaidaCadeia[]) ?? []).map((s) => ({
          ...s,
          destino: s?.destino ?? "fim",
        })),
      }),
    );
  }
  return [];
}

// Índice {id: nó} para travessia rápida do grafo no front.
export function indexarCadeia(
  cadeia: Cadeia | null | undefined,
): Record<string, NoCadeia> {
  const idx: Record<string, NoCadeia> = {};
  for (const n of nosDaCadeia(cadeia)) idx[n.id] = n;
  return idx;
}

// Caminho principal (segue a 1ª saída de cada nó, do inicial ao fim/repetição),
// só com nós-agente/roteador — para as visões compactas (dashboard, criação).
export function caminhoPrincipal(
  cadeia: Cadeia | null | undefined,
): NoCadeia[] {
  const idx = indexarCadeia(cadeia);
  const ordem: NoCadeia[] = [];
  const visto = new Set<string>();
  let atual: string | null = inicialDaCadeia(cadeia);
  while (atual && idx[atual] && !visto.has(atual)) {
    const no = idx[atual];
    visto.add(atual);
    if (no.tipo === "agente" || no.tipo === "roteador") ordem.push(no);
    atual = no.saidas?.[0]?.destino ?? null;
  }
  return ordem;
}

// Comportamento do fluxo (perfil + ajustes finos). Resolvido no backend na cascata
// global < canal < perfil < ajustes < nó (mensageria/config.py).
export type ConfiguracaoFluxo = {
  perfil?: string;
  ajustes?: Record<string, unknown>;
};

export type Automacao = {
  id: string;
  time_id: string;
  nome: string;
  tipo_gatilho: string;
  configuracao_gatilho: Record<string, unknown> | null;
  cadeia: Cadeia | null;
  ativa: boolean;
  configuracao: ConfiguracaoFluxo | null;
  criado_em: string;
  atualizado_em: string;
};

// Metadados de /config/fluxo (fonte única para a UI montar as Configurações do fluxo).
export type CampoConfigFluxo = {
  chave: string;
  rotulo: string;
  tipo: "int" | "valor" | "bool" | "texto" | "hora" | "escolha";
  sufixo?: string;
  opcoes?: { valor: string; rotulo: string }[];
  padrao?: unknown;
};
export type PerfilFluxo = {
  id: string;
  rotulo: string;
  defaults: Record<string, unknown>;
};
export type PainelConfigFluxo = {
  perfis: PerfilFluxo[];
  grupos: { grupo: string; campos: CampoConfigFluxo[] }[];
  padrao_global: Record<string, unknown>;
};

export type UsoChamada = {
  modelo: string;
  tokens_entrada: number;
  tokens_saida: number;
};

export type UsoAgrupado = {
  tokens_entrada: number;
  tokens_saida: number;
  custo_usd: number;
};

export type ResumoUso = {
  tokens_entrada: number;
  tokens_saida: number;
  custo_usd: number;
  por_modelo: Record<string, UsoAgrupado>;
  // Consumo separado por origem da chave (cliente × consultoria × legado) — 7.6.
  por_origem: Record<string, UsoAgrupado>;
  // Consumo separado por FUNÇÃO em que a IA foi gasta (execução de agentes ×
  // IA de conversa × atendimento/mensageria × transcrição de áudio).
  por_categoria: Record<string, UsoAgrupado>;
};

// Painel da consultoria (GET /uso/consultoria): o que saiu da chave-mãe somado
// entre todas as organizações, com a quebra por organização.
export type UsoConsultoria = {
  total: ResumoUso;
  por_organizacao: {
    organizacao_id: string;
    organizacao_nome: string;
    tokens_entrada: number;
    tokens_saida: number;
    custo_usd: number;
    // A quebra por função nesta organização (onde a chave-mãe foi gasta).
    por_categoria: Record<string, UsoAgrupado>;
  }[];
};

export type PassoExecucao = {
  id: string;
  ordem: number;
  agente_id: string | null;
  no_id?: string | null; // id do nó do grafo onde o passo rodou
  entrada: { texto?: string } | null;
  saida: {
    texto?: string;
    instrumentos_acionados?: string[];
    saida_escolhida?: string | null;
    uso?: UsoChamada[];
  } | null;
  estado: string;
  iniciado_em: string | null;
  finalizado_em: string | null;
};

export type Execucao = {
  id: string;
  automacao_id: string;
  estado: string;
  entrada: { texto?: string } | null;
  resultado: { texto?: string; erro?: string } | null;
  iniciada_em: string | null;
  finalizada_em: string | null;
  criado_em: string;
  // Feedback ao vivo (só enquanto em_andamento): o que o agente faz agora + quando.
  atividade?: string | null;
  atividade_em?: string | null;
};

export type ExecucaoComPassos = Execucao & {
  passos: PassoExecucao[];
  uso?: ResumoUso | null;
};

// Execução na visão consolidada (gestão de execuções), com o nome da automação
// e a organização (para a UI decidir o que cada papel pode fazer por linha).
export type ExecucaoNaLista = Execucao & {
  automacao_nome: string;
  organizacao_id: string;
};

// Um agendamento do time na aba "Agendadas" das Execuções: disparo FUTURO de uma
// automação — `pendente` (no ar, vai rodar) ou `cancelado` (não disparou; `motivo`
// explica: você cancelou, ou a automação-alvo estava desativada/removida na hora).
export type AgendamentoDoTime = {
  id: string;
  automacao_id: string;
  automacao_nome: string;
  quando_executar: string;
  estado: "pendente" | "cancelado";
  motivo: string | null;
  criado_em: string;
};

// ─────────────────── Acesso: papéis, membros, convites ───────────────────

export type PapelAcesso = "admin" | "operador" | "observador";

export type MembroLer = {
  usuario_id: string;
  papel: PapelAcesso;
  nome: string;
  email: string | null;
  ativo: boolean;
};

export type ConviteLer = {
  id: string;
  email: string;
  organizacao_id: string;
  papel: string;
  status: string;
  expira_em: string | null;
  criado_em: string;
};

// O que `criar_convite` devolve: o convite + se o e-mail saiu de fato.
// email_enviado=false → a pessoa já tinha conta; verá o aviso dentro do Batuta.
export type ConviteCriado = ConviteLer & {
  email_enviado: boolean;
};

// Convite pendente para o usuário logado (com o nome da org) — banner na home.
export type ConvitePendente = {
  id: string;
  organizacao_id: string;
  organizacao_nome: string;
  papel: string;
  expira_em: string | null;
};

export type UsuarioLer = {
  id: string;
  nome: string;
  email: string | null;
  ativo: boolean;
};

// Quem sou eu + meus papéis por organização (chave = id da organização).
export type MeuAcesso = {
  id: string;
  nome: string;
  email: string | null;
  ativo: boolean;
  papeis: Record<string, PapelAcesso>;
  // Admin da consultoria (lista no .env do cérebro) — habilita a chave-mãe.
  admin_consultoria: boolean;
};

// ───────────────────── Cofre de chaves (Fase 7) ─────────────────────

// Uma chave do cofre como a API a devolve: NUNCA o valor, só os 4 últimos
// dígitos + metadados (PRODUTO §26). organizacao_id null = chave-mãe da consultoria.
// A chave é uma por provedor (unificação 2026-06-15): sem dimensão de papel.
export type ChaveApiLer = {
  id: string;
  organizacao_id: string | null;
  provedor: string;
  ultimos4: string | null;
  apelido: string | null;
  ativa: boolean;
  // Só faz efeito na chave-mãe da consultoria: serve de reserva às orgs?
  compartilhavel: boolean;
  criado_em: string;
  atualizado_em: string;
};

// ───────────────────── IA criadora ─────────────────────
// A IA opera sobre o TIME REAL (não há mais rascunho). Em cada turno — e na
// conversa — vem a FOTOGRAFIA do time para o canvas desenhar. Espelha
// criacao/ferramentas._snapshot_time. O time nasce dormindo; ativa-se à parte.

export type AgenteTime = {
  id: string;
  nome: string;
  papel: Papel;
  modelo_ia: string | null;
  agent_md: string | null;
  skill_md: string | null;
  tools_md: string | null;
  soul_md: string | null;
  cinto: string[]; // ids de instrumento
};

export type InstrumentoTime = {
  id: string;
  nome: string;
  tipo: string;
  configuracao: Record<string, unknown> | null;
  acao_irreversivel: boolean;
  segredos_pendentes: string[];
};

export type AutomacaoTime = {
  id: string;
  nome: string;
  tipo_gatilho: string;
  configuracao_gatilho: Record<string, unknown> | null;
  cadeia: Cadeia;
  ativa: boolean;
};

export type SnapshotTime = {
  time: { id: string; nome: string; descricao: string | null };
  agentes: AgenteTime[];
  instrumentos: InstrumentoTime[];
  automacao: AutomacaoTime | null;
};

export type MensagemConversa = {
  papel: "usuario" | "ia";
  conteudo: string;
  chips?: string[];
  uso?: UsoChamada & { origem?: string };
  // Estado LOCAL (só no cliente) de uma fala otimista do usuário: "pendente" enquanto o
  // turno roda, "falhou" se caiu (com botão Reenviar). Ausente = confirmada/histórico.
  estado?: "pendente" | "falhou";
};

// A resposta imediata de POST /mensagens: o turno foi enfileirado (roda em segundo plano).
export type TurnoEnfileirado = {
  turno_id: string;
  estado: string;
};

// O andamento de um turno da IA criadora (GET /conversas-criacao/{id}/turnos/{turno_id}),
// consultado ~1,5s: atividade ao vivo enquanto roda, resultado ao concluir, mensagem
// humana ao falhar. `pergunta` deixa a tela mostrar a fala pendente ao retomar após reload.
export type TurnoCriacaoLer = {
  id: string;
  estado: "aguardando" | "em_andamento" | "concluido" | "erro";
  pergunta: string;
  atividade: string | null;
  atividade_em: string | null;
  resultado: RespostaTurno | null;
  erro_mensagem: string | null;
  criado_em: string;
};

// Memória de longo prazo do projeto (Fase 10): o que a IA aprendeu e lembra entre
// conversas. Abordagem destilada — fatos/decisões/preferências curados pela IA.
export type CategoriaMemoria = "fato" | "decisao" | "preferencia";

export type MemoriaProjeto = {
  id: string;
  categoria: CategoriaMemoria;
  conteudo: string;
  criado_em: string | null;
};

export type ConversaCriacao = {
  id: string;
  organizacao_id: string;
  titulo: string | null;
  time_id: string | null;
  criado_em: string;
  atualizado_em: string;
  mensagens: MensagemConversa[];
  time: SnapshotTime | null;
  memoria: MemoriaProjeto[];
  // Turno ainda em andamento (se houver) — a tela RETOMA o acompanhamento após reload.
  turno_em_andamento?: TurnoCriacaoLer | null;
};

// Conversa na listagem (para retomar um projeto): sem o histórico, com o nome do
// time que ela mantém (nulo se ainda não criou um).
export type ConversaCriacaoResumo = {
  id: string;
  organizacao_id: string;
  titulo: string | null;
  time_id: string | null;
  time_nome: string | null;
  criado_em: string;
  atualizado_em: string;
};

export type RespostaTurno = {
  resposta: string;
  chips: string[];
  time_id: string | null;
  time: SnapshotTime | null;
  memoria: MemoriaProjeto[];
  uso: Record<string, unknown>;
};
