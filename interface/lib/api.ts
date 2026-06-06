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

export class ErroDaApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
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

  const resposta = await fetch(`${BASE}${caminho}`, { ...opcoes, headers });

  if (!resposta.ok) {
    // O FastAPI devolve o motivo em { detail: ... }; traduzimos para mensagem.
    let mensagem = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (corpo?.detail) {
        mensagem =
          typeof corpo.detail === "string"
            ? corpo.detail
            : JSON.stringify(corpo.detail);
      }
    } catch {
      // resposta sem corpo JSON — mantém a mensagem padrão
    }
    throw new ErroDaApi(resposta.status, mensagem);
  }

  if (resposta.status === 204) return undefined as T;
  return resposta.json() as Promise<T>;
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
  criado_em: string;
  atualizado_em: string;
};

export type Time = {
  id: string;
  organizacao_id: string;
  nome: string;
  descricao: string | null;
  criado_em: string;
  atualizado_em: string;
};

export type Papel = "lider" | "agente";

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
  criado_em: string;
  atualizado_em: string;
};

export type Instrumento = {
  id: string;
  time_id: string;
  nome: string;
  tipo: string;
  configuracao: Record<string, unknown> | null;
  criado_em: string;
  atualizado_em: string;
};

export type TipoInstrumento = {
  tipo: string;
  nome_exibicao: string;
  descricao: string;
  esquema_config: Record<string, unknown>;
  esquema_args: Record<string, unknown>;
};

// ─── Automações: a cadeia é um grafo de caminhos (bifurcação) ───

export type SaidaCadeia = {
  rotulo: string;
  quando: string;
  destino: string | null; // id de outro agente, ou null = fim (entrega ao usuário)
};

export type NoCadeia = {
  saidas: SaidaCadeia[];
  pausa_humano?: boolean; // se true, pausa e pergunta ao humano após este agente
};

export type Cadeia = {
  inicio?: string;
  nos?: Record<string, NoCadeia>;
};

export type Automacao = {
  id: string;
  time_id: string;
  nome: string;
  tipo_gatilho: string;
  configuracao_gatilho: Record<string, unknown> | null;
  cadeia: Cadeia | null;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
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
};

export type PassoExecucao = {
  id: string;
  ordem: number;
  agente_id: string | null;
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

export type TipoIA = "executora" | "criadora" | "companheira";

// Uma chave do cofre como a API a devolve: NUNCA o valor, só os 4 últimos
// dígitos + metadados (PRODUTO §26). organizacao_id null = chave-mãe da consultoria.
export type ChaveApiLer = {
  id: string;
  organizacao_id: string | null;
  tipo_ia: TipoIA;
  provedor: string;
  ultimos4: string | null;
  apelido: string | null;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
};
