// Cliente único de acesso ao cérebro (a API em Python/FastAPI).
// A interface nunca fala com o banco direto — sempre passa por aqui (CLAUDE.md §8).

const BASE =
  process.env.NEXT_PUBLIC_CEREBRO_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class ErroDaApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

async function pedir<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const resposta = await fetch(`${BASE}${caminho}`, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });

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

export const api = {
  get: <T>(caminho: string) => pedir<T>(caminho),
  post: <T>(caminho: string, corpo: unknown) =>
    pedir<T>(caminho, { method: "POST", body: JSON.stringify(corpo) }),
  put: <T>(caminho: string, corpo: unknown) =>
    pedir<T>(caminho, { method: "PUT", body: JSON.stringify(corpo) }),
  delete: (caminho: string) => pedir<void>(caminho, { method: "DELETE" }),
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
