"use client";

// A LISTA da aba Instrumentos (2026-09-30): Personalizados (nascem no Construtor: API
// e servidor MCP) separados dos Prontos do Batuta; busca, filtros e contagem; selos no
// cartão (situação, alcance, tipo de ligação, efeito, uso, custo). Os dados de cada
// cartão vêm prontos do cérebro (`painel_instrumentos.py`), numa consulta só.

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Pencil,
  Search,
  Trash2,
  Wrench,
} from "lucide-react";

import { type Instrumento, type TipoInstrumento } from "@/lib/api";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { Badge } from "@/components/ui/badge";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

type FiltroTipo = "todos" | "personalizados" | "prontos" | "quadros";
type Filtros = {
  busca: string;
  tipo: FiltroTipo;
  alcance: "" | "time" | "organizacao";
  situacao: "" | "atencao" | "sem_agente";
  categoria: string;
  agente: string;
};

const FILTROS_INICIAIS: Filtros = {
  busca: "",
  tipo: "todos",
  alcance: "",
  situacao: "",
  categoria: "",
  agente: "",
};
const CHAVE_FILTROS = "batuta:filtros-instrumentos";

function ehQuadro(i: Instrumento) {
  return i.tipo === "quadro";
}

function categoriaDe(
  i: Instrumento,
  tipos: Map<string, TipoInstrumento>,
): string {
  if (i.ligacao === "mcp") return "Servidor MCP";
  if (i.ligacao === "api") {
    const c = (i.configuracao?.categoria as string | undefined)?.trim();
    return c || "API";
  }
  return tipos.get(i.tipo)?.categoria || "Outros";
}

/** O que o instrumento é, em poucas palavras (linha de baixo do cartão). */
function oQueE(i: Instrumento, tipos: Map<string, TipoInstrumento>): string {
  const n = i.qtd_acoes ?? 0;
  if (i.ligacao === "api")
    return `API · ${n} ${n === 1 ? "operação" : "operações"}`;
  if (i.ligacao === "mcp")
    return `MCP · ${n} ${n === 1 ? "ferramenta" : "ferramentas"}`;
  return tipos.get(i.tipo)?.nome_exibicao ?? i.tipo;
}

function quemUsa(i: Instrumento): string {
  const nomes = i.usado_por_agentes ?? [];
  const fora = i.usado_em_outros_times ?? 0;
  const partes: string[] = [];
  if (nomes.length) partes.push(`usado por ${nomes.join(", ")}`);
  if (fora)
    partes.push(
      `${nomes.length ? "e " : "usado "}em mais ${fora} ${fora === 1 ? "time" : "times"}`,
    );
  return partes.join(" ");
}

function semAgente(i: Instrumento) {
  return !(i.usado_por_agentes?.length || i.usado_em_outros_times);
}

type Selo = {
  texto: string;
  variante: "neutral" | "info" | "warning" | "success";
};

/** Até 3 selos, na ordem do que mais importa. */
function selosDe(i: Instrumento): Selo[] {
  const selos: Selo[] = [];
  if (i.situacao)
    selos.push({ texto: "precisa de atenção", variante: "warning" });
  if (semAgente(i)) selos.push({ texto: "sem agente", variante: "neutral" });
  selos.push(
    i.escopo === "organizacao"
      ? { texto: "da organização", variante: "info" }
      : { texto: "do time", variante: "neutral" },
  );
  if (i.ligacao)
    selos.push({
      texto: i.ligacao === "api" ? "API" : "MCP",
      variante: "neutral",
    });
  selos.push(
    i.acao_irreversivel
      ? { texto: "altera algo", variante: "warning" }
      : { texto: "só lê", variante: "success" },
  );
  if (i.pago) selos.push({ texto: "pago", variante: "neutral" });
  return selos.slice(0, 3);
}

function lerFiltros(): Filtros {
  try {
    const salvo = window.localStorage.getItem(CHAVE_FILTROS);
    return salvo
      ? { ...FILTROS_INICIAIS, ...JSON.parse(salvo), busca: "" }
      : FILTROS_INICIAIS;
  } catch {
    return FILTROS_INICIAIS;
  }
}

export function ListaInstrumentos({
  instrumentos,
  tipos,
  souOperador,
  onAbrir,
  onExcluir,
}: {
  instrumentos: Instrumento[];
  tipos: TipoInstrumento[];
  souOperador: boolean;
  onAbrir: (inst: Instrumento) => void;
  /** Lixeira nos personalizados (só para quem pode apagar). */
  onExcluir?: (inst: Instrumento) => void;
}) {
  const [f, setF] = useState<Filtros>(FILTROS_INICIAIS);
  // Os filtros lembrados só são lidos depois de montar (o servidor não tem o navegador).
  useEffect(() => {
    const lidos = lerFiltros();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setF(lidos);
  }, []);
  function mudar(patch: Partial<Filtros>) {
    setF((atual) => {
      const novo = { ...atual, ...patch };
      try {
        window.localStorage.setItem(
          CHAVE_FILTROS,
          JSON.stringify({ ...novo, busca: "" }),
        );
      } catch {
        /* sem armazenamento: o filtro só não é lembrado */
      }
      return novo;
    });
  }

  const porTipo = useMemo(
    () => new Map(tipos.map((t) => [t.tipo, t])),
    [tipos],
  );
  const categorias = useMemo(
    () => [...new Set(instrumentos.map((i) => categoriaDe(i, porTipo)))].sort(),
    [instrumentos, porTipo],
  );
  const agentes = useMemo(
    () =>
      [
        ...new Set(instrumentos.flatMap((i) => i.usado_por_agentes ?? [])),
      ].sort(),
    [instrumentos],
  );

  const visiveis = instrumentos.filter((i) => {
    const busca = f.busca.trim().toLowerCase();
    if (
      busca &&
      !`${i.nome} ${oQueE(i, porTipo)}`.toLowerCase().includes(busca)
    )
      return false;
    if (f.tipo === "personalizados" && !i.personalizado) return false;
    if (f.tipo === "prontos" && (i.personalizado || ehQuadro(i))) return false;
    if (f.tipo === "quadros" && !ehQuadro(i)) return false;
    if (f.alcance && (i.escopo ?? "time") !== f.alcance) return false;
    if (f.situacao === "atencao" && !i.situacao) return false;
    if (f.situacao === "sem_agente" && !semAgente(i)) return false;
    if (f.categoria && categoriaDe(i, porTipo) !== f.categoria) return false;
    if (f.agente && !(i.usado_por_agentes ?? []).includes(f.agente))
      return false;
    return true;
  });
  const personalizados = visiveis.filter((i) => i.personalizado);
  const prontos = visiveis.filter((i) => !i.personalizado && !ehQuadro(i));
  const quadros = visiveis.filter((i) => !i.personalizado && ehQuadro(i));
  const filtrando =
    f.busca.trim() !== "" ||
    JSON.stringify({ ...f, busca: "" }) !== JSON.stringify(FILTROS_INICIAIS);

  if (instrumentos.length === 0) {
    return (
      <EstadoVazio icone={Wrench} titulo="Nenhum instrumento ainda.">
        {souOperador
          ? "Crie instrumentos para os agentes usarem (APIs, banco, web…)."
          : "Os instrumentos deste time aparecerão aqui."}
      </EstadoVazio>
    );
  }

  function cartoes(lista: Instrumento[]) {
    return (
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {lista.map((inst, idx) => (
          <Cartao
            key={inst.id}
            inst={inst}
            primeiro={idx === 0}
            oQueE={oQueE(inst, porTipo)}
            souOperador={souOperador}
            onAbrir={() => onAbrir(inst)}
            onExcluir={
              onExcluir && inst.personalizado
                ? () => onExcluir(inst)
                : undefined
            }
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* busca e filtros */}
      <div className="flex flex-col gap-2.5">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={f.busca}
            onChange={(e) => mudar({ busca: e.target.value })}
            placeholder="Buscar pelo nome"
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {(
            [
              ["todos", "Todos"],
              ["personalizados", "Personalizados"],
              ["prontos", "Prontos"],
              ["quadros", "Quadros do Cérebro"],
            ] as const
          ).map(([v, rotulo]) => (
            <button
              key={v}
              type="button"
              onClick={() => mudar({ tipo: v })}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                f.tipo === v
                  ? "border-primary bg-accent font-medium text-accent-foreground"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {rotulo}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Select
            value={f.alcance}
            onChange={(e) =>
              mudar({ alcance: e.target.value as Filtros["alcance"] })
            }
            className="w-auto"
          >
            <option value="">Do time e da organização</option>
            <option value="time">Só do time</option>
            <option value="organizacao">Só da organização</option>
          </Select>
          <Select
            value={f.situacao}
            onChange={(e) =>
              mudar({ situacao: e.target.value as Filtros["situacao"] })
            }
            className="w-auto"
          >
            <option value="">Qualquer situação</option>
            <option value="atencao">Precisa de atenção</option>
            <option value="sem_agente">Sem agente</option>
          </Select>
          <Select
            value={f.categoria}
            onChange={(e) => mudar({ categoria: e.target.value })}
            className="w-auto"
          >
            <option value="">Todas as categorias</option>
            {categorias.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          {agentes.length > 0 && (
            <Select
              value={f.agente}
              onChange={(e) => mudar({ agente: e.target.value })}
              className="w-auto"
            >
              <option value="">Qualquer agente</option>
              {agentes.map((a) => (
                <option key={a} value={a}>
                  Usado por {a}
                </option>
              ))}
            </Select>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>
            {visiveis.length} de {instrumentos.length}
          </span>
          {filtrando && (
            <button
              type="button"
              className="underline hover:text-foreground"
              onClick={() => mudar(FILTROS_INICIAIS)}
            >
              Limpar filtros
            </button>
          )}
        </div>
      </div>

      {visiveis.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nenhum instrumento com esses filtros.
        </p>
      )}

      {personalizados.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-medium text-foreground">
            Personalizados{" "}
            <span className="text-muted-foreground">
              ({personalizados.length})
            </span>
          </h3>
          {cartoes(personalizados)}
        </section>
      )}

      {(prontos.length > 0 || quadros.length > 0) && (
        <section>
          <h3 className="mb-2 text-sm font-medium text-foreground">
            Prontos do Batuta{" "}
            <span className="text-muted-foreground">
              ({prontos.length + quadros.length})
            </span>
          </h3>
          <div className="flex flex-col gap-3">
            {prontos.length > 0 && cartoes(prontos)}
            {quadros.length > 0 && (
              <details open={f.tipo === "quadros"} className="group">
                <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
                  <ChevronDown className="size-4 -rotate-90 transition-transform group-open:rotate-0" />
                  Quadros do Cérebro ({quadros.length})
                </summary>
                <div className="mt-2">{cartoes(quadros)}</div>
              </details>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function Cartao({
  inst,
  primeiro,
  oQueE,
  souOperador,
  onAbrir,
  onExcluir,
}: {
  inst: Instrumento;
  primeiro: boolean;
  oQueE: string;
  souOperador: boolean;
  onAbrir: () => void;
  onExcluir?: () => void;
}) {
  const uso = quemUsa(inst);
  return (
    <div
      className={`flex items-center transition-colors ${
        souOperador ? "hover:bg-accent/50" : ""
      } ${primeiro ? "" : "border-t border-border"}`}
    >
      <button
        onClick={() => souOperador && onAbrir()}
        disabled={!souOperador}
        className={`flex min-w-0 flex-1 items-center gap-3 py-3 pl-4 text-left ${
          onExcluir ? "pr-2" : "pr-4"
        } ${souOperador ? "" : "cursor-default"}`}
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <IconeInstrumento
            icone={inst.icone}
            auto={inst.icone_auto}
            className="size-4"
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-medium text-foreground">
              {inst.nome}
            </span>
            {selosDe(inst).map((s) => (
              <Badge key={s.texto} variant={s.variante}>
                {s.texto}
              </Badge>
            ))}
          </span>
          <span className="block truncate text-xs text-muted-foreground">
            {oQueE}
            {inst.time_casa_nome && ` · vem do time ${inst.time_casa_nome}`}
            {uso && ` · ${uso}`}
          </span>
          {inst.situacao_motivo && (
            <span className="mt-0.5 flex items-center gap-1 text-xs text-warning">
              <AlertTriangle className="size-3 shrink-0" />
              <span className="truncate">{inst.situacao_motivo}</span>
            </span>
          )}
        </span>
        {souOperador && (
          <Pencil className="size-4 shrink-0 text-muted-foreground/60" />
        )}
      </button>
      {onExcluir && (
        <button
          type="button"
          onClick={onExcluir}
          title={`Excluir “${inst.nome}”`}
          aria-label={`Excluir “${inst.nome}”`}
          className="mr-3 flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="size-4" />
        </button>
      )}
    </div>
  );
}
