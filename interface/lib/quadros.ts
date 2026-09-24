// Tipos e utilitários dos QUADROS do cérebro da organização (docs/CEREBRO-PLANO.md).
// Espelham as rotas `cerebro/rotas/quadros.py`. Uma recusa do Batuta (dado que não
// serve, filtro inválido) chega com status 200 e `ok: false` + `detalhes` por linha.

import { api } from "@/lib/api";

export type TipoColuna =
  | "texto"
  | "texto_longo"
  | "numero"
  | "dinheiro"
  | "data"
  | "data_hora"
  | "sim_nao"
  | "opcao";

// Rótulos que a pessoa lê (fonte única no front — o cérebro manda o `tipo`).
export const ROTULO_TIPO: Record<TipoColuna, string> = {
  texto: "Texto curto",
  texto_longo: "Texto longo",
  numero: "Número",
  dinheiro: "Dinheiro",
  data: "Data",
  data_hora: "Data e hora",
  sim_nao: "Sim ou não",
  opcao: "Opção de uma lista",
};

export const TIPOS_ORDEM: TipoColuna[] = [
  "texto",
  "texto_longo",
  "numero",
  "dinheiro",
  "data",
  "data_hora",
  "sim_nao",
  "opcao",
];

export type UsoDoQuadro = {
  instrumento_id: string;
  instrumento: string;
  time: string;
  time_id: string;
  acesso: "ler" | "ler_e_escrever";
  agentes: string[];
};

export type QuadroResumo = {
  id: string;
  nome: string;
  descricao: string | null;
  colunas: string[];
  linhas: number;
  ultima_gravacao: string | null;
  criado_em: string;
  usado_por: UsoDoQuadro[];
};

export type ColunaQuadro = {
  nome: string;
  id: string;
  tipo: TipoColuna;
  tipo_rotulo: string;
  obrigatoria: boolean;
  faz_parte_da_chave: boolean;
  opcoes?: string[];
  descricao?: string;
};

export type LimiteQuadro = {
  chave: string;
  rotulo: string;
  valor: number;
  padrao: number;
  teto: number;
  ajustado: boolean;
  ao_estourar: string;
};

export type QuadroDescrito = {
  id: string;
  nome: string;
  descricao: string | null;
  colunas: ColunaQuadro[];
  chave: string[];
  limites: LimiteQuadro[];
  total_linhas?: number;
};

export type ExecucaoQueGravou = {
  execucao_id: string;
  linhas: number;
  quando: string;
  automacao: string | null;
};

export type QuadroDetalhe = {
  quadro: QuadroDescrito;
  usado_por: UsoDoQuadro[];
  execucoes_recentes: ExecucaoQueGravou[];
};

export type Carimbo = {
  origem: "agente" | "pessoa" | "ia_criadora" | "mcp" | "importacao";
  agente_id: string | null;
  execucao_id: string | null;
  usuario_id: string | null;
  criado_em: string | null;
  atualizado_em: string | null;
  versao: number;
  agente_nome?: string | null;
  usuario_nome?: string | null;
  automacao_nome?: string | null;
};

export type Valor = string | number | boolean | null;

export type LinhaQuadro = {
  id: string;
  valores: Record<string, Valor>;
  carimbo: Carimbo;
};

export type Filtro = { coluna: string; operador: string; valor?: Valor };

export type ResultadoConsulta = {
  quadro: string;
  total: number;
  devolvidas: number;
  deslocamento: number;
  proximo: number | null;
  colunas: string[];
  linhas: LinhaQuadro[];
  aviso?: string;
};

export type DetalheRecusa = { linha: number | null; coluna: string | null; motivo: string; valor?: Valor };

export type Recusa = { ok: false; erro: string; detalhes?: DetalheRecusa[] };
export type Resposta<T> = ({ ok: true } & T) | Recusa;

export type Alteracao = {
  acao: "criou" | "mudou" | "apagou";
  quando: string | null;
  antes: Record<string, Valor> | null;
  depois: Record<string, Valor> | null;
  origem: Carimbo["origem"];
  agente_id: string | null;
  execucao_id: string | null;
  usuario_id: string | null;
  agente_nome?: string | null;
  usuario_nome?: string | null;
  automacao_nome?: string | null;
};

export type PreviaImportacao = {
  quadro: string;
  linhas_no_csv: number;
  mapeamento: { coluna_csv: string; vai_para: string | null; exemplo: string }[];
  colunas_sem_destino: string[];
  problemas: DetalheRecusa[];
};

// Operadores do filtro, com o rótulo que a pessoa lê, por tipo de coluna.
export type OperadorFiltro = { valor: string; rotulo: string; semValor?: boolean };

const IGUAL: OperadorFiltro = { valor: "=", rotulo: "é igual a" };
const DIFERENTE: OperadorFiltro = { valor: "!=", rotulo: "é diferente de" };
const VAZIO: OperadorFiltro = { valor: "vazio", rotulo: "está vazio", semValor: true };
const PREENCHIDO: OperadorFiltro = { valor: "nao_vazio", rotulo: "está preenchido", semValor: true };
const COMPARAR: OperadorFiltro[] = [
  { valor: ">", rotulo: "é maior que" },
  { valor: ">=", rotulo: "é maior ou igual a" },
  { valor: "<", rotulo: "é menor que" },
  { valor: "<=", rotulo: "é menor ou igual a" },
];

export function operadoresPara(tipo: TipoColuna): OperadorFiltro[] {
  if (tipo === "texto" || tipo === "texto_longo")
    return [{ valor: "contem", rotulo: "contém" }, IGUAL, DIFERENTE, VAZIO, PREENCHIDO];
  if (tipo === "opcao" || tipo === "sim_nao") return [IGUAL, DIFERENTE, VAZIO, PREENCHIDO];
  return [IGUAL, DIFERENTE, ...COMPARAR, VAZIO, PREENCHIDO];
}

export function rotuloOperador(op: string): string {
  const todos = [IGUAL, DIFERENTE, VAZIO, PREENCHIDO, ...COMPARAR, { valor: "contem", rotulo: "contém" }];
  return todos.find((o) => o.valor === op)?.rotulo ?? op;
}

// Como um valor GUARDADO aparece na tela (data em DD/MM/AAAA, dinheiro em R$…).
export function mostrarValor(v: Valor | undefined, tipo?: TipoColuna): string {
  if (v === null || v === undefined || v === "") return "";
  if (tipo === "sim_nao" || typeof v === "boolean") return v ? "sim" : "não";
  if (tipo === "data" && typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const [a, m, d] = v.split("-");
    return `${d}/${m}/${a}`;
  }
  if (tipo === "data_hora" && typeof v === "string") return dataHora(v);
  if (tipo === "dinheiro" && typeof v === "number")
    return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  if (tipo === "numero" && typeof v === "number") return v.toLocaleString("pt-BR");
  return String(v);
}

// O valor como a pessoa EDITA (sem símbolo de moeda, data em DD/MM/AAAA).
export function valorParaCampo(v: Valor | undefined, tipo: TipoColuna): string {
  if (v === null || v === undefined) return "";
  if (tipo === "dinheiro" || tipo === "numero") return String(v).replace(".", ",");
  if (tipo === "sim_nao") return v ? "sim" : "não";
  // "DD/MM/AAAA HH:MM" sem vírgula — é a forma que o Batuta aceita de volta.
  if (tipo === "data_hora" && typeof v === "string") return dataHora(v).replace(",", "");
  return mostrarValor(v, tipo);
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      timeZone: "America/Sao_Paulo",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// "há 3 min", "hoje, 11:32", "ontem", "23/09"
export function quandoRelativo(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  const d = new Date(iso);
  const agora = new Date();
  const min = Math.round((agora.getTime() - d.getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const fmt = (o: Intl.DateTimeFormatOptions) =>
    d.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", ...o });
  const hoje = agora.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
  if (fmt({ day: "2-digit", month: "2-digit", year: "numeric" }) === hoje)
    return `hoje, ${fmt({ hour: "2-digit", minute: "2-digit" })}`;
  const ontem = new Date(agora.getTime() - 86400000).toLocaleDateString("pt-BR", {
    timeZone: "America/Sao_Paulo",
  });
  if (fmt({ day: "2-digit", month: "2-digit", year: "numeric" }) === ontem) return "ontem";
  return fmt({ day: "2-digit", month: "2-digit" });
}

// Quem gravou, em palavras.
export function quemGravou(c: Carimbo | Alteracao): string {
  if (c.origem === "agente") return c.agente_nome ?? "Um agente";
  if (c.origem === "ia_criadora") return "IA criadora";
  if (c.origem === "mcp") return `${c.usuario_nome ?? "Alguém"} pelo Claude`;
  if (c.origem === "importacao") return `${c.usuario_nome ?? "Alguém"} (importou)`;
  return c.usuario_nome ?? "Uma pessoa";
}

export function iniciais(nome: string | null | undefined): string {
  if (!nome) return "?";
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

// Atalho para as rotas de um quadro.
export function rotaQuadros(orgId: string, quadroId?: string): string {
  return quadroId ? `/organizacoes/${orgId}/quadros/${quadroId}` : `/organizacoes/${orgId}/quadros`;
}

export async function baixarCsv(orgId: string, quadroId: string, filtros: Filtro[], busca: string) {
  const r = await api.post<Resposta<{ csv: string; arquivo: string; total: number; exportadas: number }>>(
    `${rotaQuadros(orgId, quadroId)}/exportar`,
    { filtros, busca: busca || null },
  );
  if (!r.ok) return r;
  // O ﻿ faz o Excel reconhecer os acentos (UTF-8).
  const blob = new Blob(["﻿" + r.csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = r.arquivo;
  a.click();
  URL.revokeObjectURL(url);
  return r;
}
