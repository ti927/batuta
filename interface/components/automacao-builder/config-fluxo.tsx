"use client";

// Diálogo "Configurações do fluxo": o usuário escolhe um TIPO DE FLUXO (perfil, que
// já traz regras sensatas) e, no "Avançado", afina botão a botão. Os perfis, grupos
// e opções vêm de /config/fluxo (fonte única no backend) — nada é duplicado aqui.
//
// A tela é HONESTA sobre o que o fluxo faz: (a) não finge um tipo quando nenhum foi
// escolhido (mostra "padrão geral" e avisa); (b) resume em português claro o tempo
// efetivo e o comportamento do portão; (c) no "Avançado", marca cada campo como
// "herdado do tipo" ou "ajustado" (com um "voltar ao padrão"), para um valor afinado
// não vencer o tipo em silêncio.

import { useEffect, useState } from "react";
import { AlertTriangle, Clock, RotateCcw, ShieldCheck, Sliders, X } from "lucide-react";

import {
  api,
  type CampoConfigFluxo,
  type ConfiguracaoFluxo,
  type PainelConfigFluxo,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

function semChave(
  obj: Record<string, unknown>,
  chave: string,
): Record<string, unknown> {
  const resto = { ...obj };
  delete resto[chave];
  return resto;
}

function CampoConfig({
  campo,
  valor,
  ajustado,
  podeEditar,
  onChange,
  onReset,
}: {
  campo: CampoConfigFluxo;
  valor: unknown;
  ajustado: boolean;
  podeEditar: boolean;
  onChange: (v: unknown) => void;
  onReset: () => void;
}) {
  // Marcador "herdado do tipo" / "ajustado — voltar ao padrão" (o afinado vence o
  // tipo; deixamos isso visível e reversível).
  const marcador =
    ajustado && podeEditar ? (
      <button
        type="button"
        onClick={onReset}
        className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
      >
        <RotateCcw className="size-3" /> ajustado — voltar ao padrão
      </button>
    ) : ajustado ? (
      <span className="text-[11px] text-primary">ajustado</span>
    ) : (
      <span className="text-[11px] text-muted-foreground/60">herdado do tipo</span>
    );

  if (campo.tipo === "bool") {
    return (
      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-[13px] text-foreground">
          <input
            type="checkbox"
            className="accent-primary"
            disabled={!podeEditar}
            checked={!!valor}
            onChange={(e) => onChange(e.target.checked)}
          />
          {campo.rotulo}
        </label>
        {marcador}
      </div>
    );
  }
  return (
    <Label className="flex-col items-start gap-1 text-[12px] text-muted-foreground">
      <span className="flex w-full items-center justify-between gap-2">
        <span>
          {campo.rotulo}
          {campo.sufixo ? ` (${campo.sufixo})` : ""}
        </span>
        {marcador}
      </span>
      {campo.tipo === "escolha" ? (
        <Select
          value={String(valor ?? "")}
          disabled={!podeEditar}
          onChange={(e) => onChange(e.target.value)}
          className="w-full"
        >
          {(campo.opcoes ?? []).map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.rotulo}
            </option>
          ))}
        </Select>
      ) : campo.tipo === "int" || campo.tipo === "valor" ? (
        <Input
          type="number"
          step={campo.tipo === "valor" ? "0.01" : "1"}
          disabled={!podeEditar}
          value={valor === undefined || valor === null ? "" : String(valor)}
          onChange={(e) =>
            onChange(
              campo.tipo === "valor"
                ? Number(e.target.value)
                : parseInt(e.target.value || "0", 10),
            )
          }
          className="w-full"
        />
      ) : campo.tipo === "hora" ? (
        <Input
          type="time"
          disabled={!podeEditar}
          value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
          className="w-full"
        />
      ) : (
        <Input
          type="text"
          disabled={!podeEditar}
          value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
          className="w-full"
        />
      )}
    </Label>
  );
}

export function DialogoConfigFluxo({
  valor,
  onChange,
  podeEditar,
  onClose,
}: {
  valor: ConfiguracaoFluxo;
  onChange: (v: ConfiguracaoFluxo) => void;
  podeEditar: boolean;
  onClose: () => void;
}) {
  const [painel, setPainel] = useState<PainelConfigFluxo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [avancado, setAvancado] = useState(false);

  useEffect(() => {
    api
      .get<PainelConfigFluxo>("/config/fluxo")
      .then(setPainel)
      .catch(() => setErro("Não consegui carregar as opções de configuração."));
  }, []);

  const ajustes = valor.ajustes ?? {};
  // HONESTO: só considera "tem tipo" um perfil realmente salvo e conhecido. Sem tipo
  // (automação legada) → os defaults vêm do PADRÃO GERAL, não de um perfil fingido.
  const perfilObj = painel?.perfis.find((p) => p.id === valor.perfil);
  const temPerfil = !!perfilObj;
  const defaults = perfilObj?.defaults ?? painel?.padrao_global ?? {};

  function efetivo(chave: string): unknown {
    return chave in ajustes ? ajustes[chave] : defaults[chave];
  }

  const temAjustes = Object.keys(ajustes).length > 0;
  const cutucar = Number(efetivo("timeout_min"));
  const encerrar = Number(efetivo("nudge_timeout_min"));
  const encerraPorInatividade = !!efetivo("encerrar_por_inatividade");
  const cancelaNoPortao = String(efetivo("portao_acao_abandono") ?? "") === "cancelar";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        className="absolute inset-0 bg-foreground/20"
        onClick={onClose}
        aria-label="Fechar"
      />
      <div className="relative flex max-h-[85vh] w-full max-w-lg flex-col rounded-xl border border-border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-border p-5">
          <h2 className="flex items-center gap-2 font-heading text-lg font-medium text-foreground">
            <Sliders className="size-4 text-primary" /> Configurações do fluxo
          </h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Fechar">
            <X className="size-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {erro && <p className="mb-3 text-sm text-destructive">{erro}</p>}
          {!painel ? (
            <p className="text-sm text-muted-foreground">Carregando…</p>
          ) : (
            <>
              <Label className="flex-col items-start gap-1">
                Tipo de fluxo
                <Select
                  value={temPerfil ? String(valor.perfil) : ""}
                  disabled={!podeEditar}
                  onChange={(e) =>
                    onChange({ ...valor, perfil: e.target.value || undefined })
                  }
                  className="w-full"
                >
                  {!temPerfil && (
                    <option value="">
                      — Padrão geral (nenhum tipo escolhido) —
                    </option>
                  )}
                  {painel.perfis.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.rotulo}
                    </option>
                  ))}
                </Select>
              </Label>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Cada tipo já vem com regras sensatas. Use o “Avançado” só se quiser
                afinar algo.
              </p>

              {!temPerfil && (
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[13px] text-amber-900">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                  <span>
                    Nenhum tipo escolhido: este fluxo está usando o{" "}
                    <strong>padrão geral</strong>. Escolha um tipo acima para regras
                    mais adequadas ao seu caso.
                  </span>
                </div>
              )}

              {/* Resumo em português claro do que o fluxo REALMENTE faz. */}
              <div className="mt-3 flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3 text-[13px] text-foreground">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Como este fluxo se comporta
                </div>
                <div className="flex items-start gap-2">
                  <Clock className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <span>
                    {encerraPorInatividade ? (
                      <>
                        Cutuca quem some em <strong>{cutucar} min</strong>; se
                        continuar quieto, encerra <strong>{encerrar} min</strong>{" "}
                        depois.
                      </>
                    ) : (
                      <>Não encerra por inatividade (a conversa fica aberta).</>
                    )}
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <span>
                    {cancelaNoPortao ? (
                      <>
                        Se o aprovador some no portão: o fluxo é{" "}
                        <strong>cancelado</strong>.
                      </>
                    ) : (
                      <>
                        Se o aprovador some no portão: fica{" "}
                        <strong>pendente e retomável</strong> (não cancela).
                      </>
                    )}
                  </span>
                </div>
              </div>

              <button
                type="button"
                className="mt-4 text-sm font-medium text-primary"
                onClick={() => setAvancado((v) => !v)}
              >
                {avancado ? "▾ Avançado" : "▸ Avançado"}
              </button>

              {avancado && (
                <div className="mt-3 flex flex-col gap-5">
                  {temAjustes && podeEditar && (
                    <button
                      type="button"
                      onClick={() => onChange({ ...valor, ajustes: {} })}
                      className="flex items-center gap-1.5 self-start text-xs font-medium text-primary hover:underline"
                    >
                      <RotateCcw className="size-3.5" /> Restaurar os padrões do tipo
                    </button>
                  )}
                  {painel.grupos.map((g) => (
                    <div key={g.grupo} className="flex flex-col gap-3">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                        {g.grupo}
                      </div>
                      {g.campos.map((c) => (
                        <CampoConfig
                          key={c.chave}
                          campo={c}
                          valor={efetivo(c.chave)}
                          ajustado={c.chave in ajustes}
                          podeEditar={podeEditar}
                          onChange={(v) =>
                            onChange({
                              ...valor,
                              ajustes: { ...ajustes, [c.chave]: v },
                            })
                          }
                          onReset={() =>
                            onChange({ ...valor, ajustes: semChave(ajustes, c.chave) })
                          }
                        />
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end border-t border-border p-4">
          <Button onClick={onClose}>Pronto</Button>
        </div>
      </div>
    </div>
  );
}
