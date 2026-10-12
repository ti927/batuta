"use client";

// A janela de CONFIGURAÇÕES da automação (2026-10-12).
//
// Até aqui as regras moravam no painel da direita do Estúdio, quando nada estava
// selecionado: uma coluna estreita, com tudo empilhado em duas sanfonas ("Tetos deste
// fluxo" e "Padrão que os agentes herdam"). O maestro achou péssimo — não se via o que
// existia, e a separação era pelo DONO da regra, que é como o código pensa, não pelo
// ASSUNTO, que é como a pessoa procura.
//
// Agora é uma janela com as regras por assunto (as categorias vêm do cérebro, junto com
// os campos — fonte única) e um Resumo na frente com os limites em vigor.
//
// O dono da regra continua dito, campo a campo: o que é padrão dos agentes leva a marca
// "cada agente pode mudar", e quando algum agente DESTE desenho usa um valor diferente,
// o campo fica destacado e diz quem é (pedido do maestro: a diferença tem que aparecer
// dos dois lados — aqui e na aba "Ritmo e espera" do agente).
//
// Editar aqui mexe no RASCUNHO do desenho: "Aplicar" leva para o Estúdio, que fica
// "não salvo" até o Salvar de sempre — o mesmo caminho de qualquer outra mudança.

import { useEffect, useMemo, useState } from "react";
import { Info, MessageSquare, TriangleAlert, X } from "lucide-react";

import {
  api,
  type Agente,
  type Cadeia,
  type CampoConfigFluxo,
  type ConfiguracaoFluxo,
  type Instrumento,
  type LimiteDoFluxo,
  type PainelConfigFluxo,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CampoConfig } from "@/components/automacao-builder/config-fluxo";

// Instrumentos que conversam com uma pessoa — espelha `CANAIS_TIPOS` no cérebro.
const CANAIS = ["enviar_telegram"];

const RESUMO = "resumo";

function semChave(
  obj: Record<string, unknown>,
  chave: string,
): Record<string, unknown> {
  const resto = { ...obj };
  delete resto[chave];
  return resto;
}

/** O valor como a pessoa o leria ("10 min", "US$ 0.50", "sim", o nome da opção). */
export function valorLegivel(campo: CampoConfigFluxo, v: unknown): string {
  if (campo.tipo === "bool") return v ? "sim" : "não";
  if (campo.tipo === "escolha")
    return campo.opcoes?.find((o) => o.valor === v)?.rotulo ?? String(v ?? "");
  if (v === 0 && campo.ajuda?.startsWith("0 =")) return "desligado";
  if (campo.sufixo === "US$") return `US$ ${Number(v ?? 0).toFixed(2)}`;
  return campo.sufixo ? `${v} ${campo.sufixo}` : String(v ?? "");
}

type Diferente = { agente: Agente; valor: unknown };

export function ConfiguracoesAutomacao({
  aberto,
  categoriaInicial,
  onFechar,
  nomeDoFluxo,
  cadeia,
  agentes,
  cintos,
  valor,
  onAplicar,
  podeEditar,
  onEditarInstrumento,
  onEditarAgente,
  gatilhoTipo,
  configGatilho,
}: {
  aberto: boolean;
  /** Abre direto numa categoria (ex.: vindo do atalho no agente). */
  categoriaInicial?: string | null;
  onFechar: () => void;
  nomeDoFluxo: string;
  cadeia: Cadeia;
  agentes: Agente[];
  cintos: Record<string, Instrumento[]>;
  valor: ConfiguracaoFluxo;
  onAplicar: (v: ConfiguracaoFluxo) => void;
  podeEditar: boolean;
  onEditarInstrumento: (instrumentoId: string) => void;
  onEditarAgente: (agenteId: string) => void;
  /** O gatilho COMO ESTÁ NA TELA (mesmo não salvo) — alguns limites moram nele. */
  gatilhoTipo: string;
  configGatilho: Record<string, unknown>;
}) {
  const [painel, setPainel] = useState<PainelConfigFluxo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState<ConfiguracaoFluxo>(valor);
  const [categoria, setCategoria] = useState<string>(categoriaInicial || RESUMO);
  const [limites, setLimites] = useState<LimiteDoFluxo[] | null>(null);

  // Cada abertura parte do que está no desenho agora (e da categoria pedida).
  const [abertoVisto, setAbertoVisto] = useState(false);
  if (aberto !== abertoVisto) {
    setAbertoVisto(aberto);
    if (aberto) {
      setRascunho(valor);
      setCategoria(categoriaInicial || RESUMO);
    }
  }

  useEffect(() => {
    if (!aberto || painel) return;
    api
      .get<PainelConfigFluxo>("/config/fluxo")
      .then(setPainel)
      .catch(() =>
        setErro("Não consegui carregar as configurações. Feche e abra de novo."),
      );
  }, [aberto, painel]);

  useEffect(() => {
    if (!aberto) return;
    function tecla(e: KeyboardEvent) {
      if (e.key === "Escape") onFechar();
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aberto, onFechar]);

  const ajustes = useMemo(() => rascunho.ajustes ?? {}, [rascunho]);

  // A redação dos limites vive no cérebro (`limites_por_categoria`): reescrevê-la aqui
  // faria as duas versões divergirem. Junto vai o CONTEXTO do desenho — há limites que
  // não moram nos ajustes (itens do "Para cada item", agendamentos pendentes).
  const serializado = JSON.stringify({
    ajustes,
    tipo_gatilho: gatilhoTipo,
    configuracao_gatilho: configGatilho,
    tem_no_cada: (cadeia.nos ?? []).some((n) => n.tipo === "cada"),
    tem_agendar_automacao: Object.values(cintos).some((c) =>
      c.some((i) => i.tipo === "agendar_automacao"),
    ),
  });
  useEffect(() => {
    if (!aberto) return;
    let vivo = true;
    api
      .post<{ itens: LimiteDoFluxo[] }>("/config/fluxo/limites", JSON.parse(serializado))
      .then((r) => vivo && setLimites(r.itens))
      .catch(() => vivo && setLimites([]));
    return () => {
      vivo = false;
    };
  }, [aberto, serializado]);

  // Os agentes que estão NESTE desenho — só eles importam para o aviso.
  const agentesDoDesenho = useMemo(
    () => agentes.filter((a) => (cadeia.nos ?? []).some((n) => n.ref === a.id)),
    [agentes, cadeia],
  );

  const camposPorChave = useMemo(() => {
    const m = new Map<string, { campo: CampoConfigFluxo; nivel: "fluxo" | "agente" }>();
    for (const g of painel?.grupos ?? [])
      for (const c of g.campos) m.set(c.chave, { campo: c, nivel: g.nivel });
    return m;
  }, [painel]);

  function efetivo(chave: string): unknown {
    return chave in ajustes ? ajustes[chave] : painel?.padrao_global?.[chave];
  }

  /** Agentes deste desenho cujo valor próprio DIFERE do que a automação usa. */
  function diferentes(chave: string): Diferente[] {
    if (camposPorChave.get(chave)?.nivel !== "agente") return [];
    const daAutomacao = efetivo(chave);
    return agentesDoDesenho
      .filter((a) => {
        const proprio = a.configuracao ?? {};
        return chave in proprio && proprio[chave] !== daAutomacao;
      })
      .map((a) => ({ agente: a, valor: (a.configuracao ?? {})[chave] }));
  }

  const camposDa = (cat: string) =>
    [...camposPorChave.values()].filter((x) => x.campo.categoria === cat);

  const categoriasComDiferenca = new Set(
    [...camposPorChave.values()]
      .filter((x) => diferentes(x.campo.chave).length > 0)
      .map((x) => x.campo.categoria),
  );

  // Para o aviso do Resumo: quem difere, e em quê.
  const resumoDiferencas = new Map<string, { agente: Agente; campos: string[] }>();
  for (const { campo } of camposPorChave.values()) {
    for (const d of diferentes(campo.chave)) {
      const atual = resumoDiferencas.get(d.agente.id) ?? { agente: d.agente, campos: [] };
      atual.campos.push(campo.rotulo);
      resumoDiferencas.set(d.agente.id, atual);
    }
  }

  // Os canais que este desenho usa, pelos cintos dos agentes que estão nele. É para
  // onde a pessoa vai quando procura saudação/horário aqui e não acha.
  const canais: Instrumento[] = [];
  for (const no of cadeia.nos ?? []) {
    for (const i of cintos[no.ref ?? ""] ?? []) {
      if (CANAIS.includes(i.tipo) && !canais.some((c) => c.id === i.id)) canais.push(i);
    }
  }

  const naoAplicado = JSON.stringify(rascunho) !== JSON.stringify(valor);

  function abrirAgente(id: string) {
    // Leva o que já foi mexido aqui antes de sair: o agente abre por cima do Estúdio e
    // a pessoa não pode perder o que acabou de ajustar.
    if (naoAplicado) onAplicar(rascunho);
    onFechar();
    onEditarAgente(id);
  }

  if (!aberto) return null;

  const categorias = painel?.categorias ?? [];
  const atual = categorias.find((c) => c.id === categoria);

  function avisoDiferentes(chave: string, campo: CampoConfigFluxo) {
    const lista = diferentes(chave);
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-muted-foreground">Cada agente pode mudar.</span>
        {lista.length > 0 && (
          <div className="flex items-start gap-1.5 text-[11.5px] leading-snug text-amber-900">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            <span>
              Usam um valor diferente:{" "}
              {lista.map((d, i) => (
                <span key={d.agente.id}>
                  {i > 0 && " · "}
                  <button
                    type="button"
                    onClick={() => abrirAgente(d.agente.id)}
                    className="font-medium underline underline-offset-2 hover:no-underline"
                  >
                    {d.agente.nome}
                  </button>{" "}
                  ({valorLegivel(campo, d.valor)})
                </span>
              ))}
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={onFechar}
        aria-label="Fechar"
      />
      <section
        role="dialog"
        aria-label={`Configurações de ${nomeDoFluxo}`}
        className="relative flex h-full w-full flex-col overflow-hidden bg-card shadow-xl md:h-[82vh] md:max-h-[760px] md:w-[92vw] md:max-w-3xl md:rounded-xl md:border md:border-border"
      >
        <header className="flex flex-none items-center gap-3 border-b border-border px-5 py-3.5">
          <div className="min-w-0 flex-1">
            <h2 className="font-medium text-foreground">Configurações</h2>
            <p className="truncate text-xs text-muted-foreground">{nomeDoFluxo}</p>
          </div>
          <Button size="icon" variant="ghost" onClick={onFechar} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          {/* Categorias: coluna à esquerda no computador, abas no topo no celular. */}
          <nav className="flex flex-none gap-1 overflow-x-auto border-b border-border p-2 md:w-48 md:flex-col md:overflow-visible md:border-b-0 md:border-r">
            {[{ id: RESUMO, rotulo: "Resumo" }, ...categorias].map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setCategoria(c.id)}
                className={
                  "flex shrink-0 items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-[13px] " +
                  (categoria === c.id
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-foreground hover:bg-muted")
                }
              >
                {c.rotulo}
                {categoriasComDiferenca.has(c.id) && (
                  <span
                    className="size-2 rounded-full bg-amber-500"
                    title="Algum agente usa um valor diferente aqui"
                  />
                )}
              </button>
            ))}
          </nav>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {erro ? (
              <p className="text-sm text-destructive">{erro}</p>
            ) : !painel ? (
              <p className="text-sm text-muted-foreground">Carregando…</p>
            ) : categoria === RESUMO ? (
              <div className="flex flex-col gap-4">
                {resumoDiferencas.size > 0 && (
                  <div className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[12.5px] leading-relaxed text-amber-900">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                    <div>
                      <div className="font-medium">
                        Existem agentes com configurações diferentes
                      </div>
                      <ul className="mt-1 flex flex-col gap-0.5">
                        {[...resumoDiferencas.values()].map(({ agente, campos }) => (
                          <li key={agente.id}>
                            <button
                              type="button"
                              onClick={() => abrirAgente(agente.id)}
                              className="font-medium underline underline-offset-2 hover:no-underline"
                            >
                              {agente.nome}
                            </button>
                            : {campos.join(", ")}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Limites em vigor
                  </div>
                  {limites === null ? (
                    <p className="text-sm text-muted-foreground">Carregando…</p>
                  ) : (
                    categorias.map((c) => {
                      const doGrupo = limites.filter((l) => l.categoria === c.id);
                      if (!doGrupo.length) return null;
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => setCategoria(c.id)}
                          className="flex flex-col gap-0.5 rounded-lg border border-border p-3 text-left hover:bg-muted/60"
                        >
                          <span className="text-[13px] font-medium text-foreground">
                            {c.rotulo}
                          </span>
                          {doGrupo.map((l) => (
                            <span
                              key={l.texto}
                              className="text-[12.5px] leading-snug text-muted-foreground"
                            >
                              {l.texto.charAt(0).toUpperCase() + l.texto.slice(1)}
                            </span>
                          ))}
                        </button>
                      );
                    })
                  )}
                </div>

                <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
                  <div className="flex gap-1.5 text-[12px] leading-snug text-muted-foreground">
                    <Info className="mt-0.5 size-3.5 shrink-0" />
                    <span>
                      Saudação, horário de atendimento e mensagens automáticas ficam no{" "}
                      <strong className="text-foreground">bot</strong>, não aqui.
                    </span>
                  </div>
                  {canais.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => {
                        onFechar();
                        onEditarInstrumento(c.id);
                      }}
                      className="inline-flex items-center gap-1.5 self-start rounded-md border border-border px-2 py-1 text-[12px] text-primary hover:bg-primary/5"
                    >
                      <MessageSquare className="size-3" /> abrir {c.nome}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {atual?.descricao && (
                  <p className="text-[12.5px] text-muted-foreground">{atual.descricao}</p>
                )}
                {camposDa(categoria).map(({ campo, nivel }) => {
                  const ajustado = campo.chave in ajustes;
                  const lista = nivel === "agente" ? diferentes(campo.chave) : [];
                  return (
                    <CampoConfig
                      key={campo.chave}
                      campo={campo}
                      valor={efetivo(campo.chave)}
                      ajustado={ajustado}
                      podeEditar={podeEditar}
                      destacado={lista.length > 0}
                      rodape={
                        nivel === "agente" ? avisoDiferentes(campo.chave, campo) : undefined
                      }
                      onChange={(v) =>
                        setRascunho({ ...rascunho, ajustes: { ...ajustes, [campo.chave]: v } })
                      }
                      onReset={() =>
                        setRascunho({ ...rascunho, ajustes: semChave(ajustes, campo.chave) })
                      }
                    />
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <footer className="flex flex-none items-center justify-end gap-2 border-t border-border px-5 py-3">
          {podeEditar ? (
            <>
              <Button variant="outline" onClick={onFechar}>
                Cancelar
              </Button>
              <Button
                disabled={!naoAplicado}
                onClick={() => {
                  onAplicar(rascunho);
                  onFechar();
                }}
              >
                Aplicar
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={onFechar}>
              Fechar
            </Button>
          )}
        </footer>
      </section>
    </div>
  );
}
