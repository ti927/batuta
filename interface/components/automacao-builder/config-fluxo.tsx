"use client";

// Diálogo das REGRAS DO FLUXO. Os grupos, rótulos e opções vêm de /config/fluxo
// (fonte única no cérebro) — nada é duplicado aqui.
//
// O "Tipo de fluxo" morreu em 2026-09-22. Ele era um dropdown que trocava seis números
// de uma vez, em silêncio, e cujos valores moravam no CÓDIGO, não no dado da automação
// — era por isso que este botão mostrava números que não estavam em lugar nenhum, e
// nunca conseguiu se explicar ("até hoje não entendi pra que serve"). Sobrou o que ele
// tinha de útil: partir de um modelo, uma vez, à vista.
//
// A tela continua HONESTA sobre o que o fluxo faz: resume em português o tempo efetivo
// e o comportamento da aprovação, e marca cada campo como "padrão do Batuta" ou
// "ajustado" (com um "voltar ao padrão"), para um valor afinado não vencer em silêncio.
//
// O que NÃO está aqui, e por quê: saudação, horário e mensagens automáticas são do
// CANAL (a voz de quem fala); o tempo de espera de cada aprovação é do AGENTE que
// espera (aba "Ritmo e espera" no popup dele), com estes valores como padrão.

import { useEffect, useState } from "react";
import {
  Clock,
  Gauge,
  RotateCcw,
  ShieldCheck,
  Sliders,
  X,
} from "lucide-react";

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

// A base de tudo é o PADRÃO DO BATUTA. O "Tipo de fluxo" era uma camada acima disto e
// morreu em 2026-09-22: ele guardava uma etiqueta cujos números moravam no cérebro, e
// era por isso que a tela mostrava valores que não estavam no dado da automação. Um
// modelo agora só CARIMBA os números nos ajustes e sai de cena.
export function defaultsDoBatuta(
  painel: PainelConfigFluxo,
): Record<string, unknown> {
  return painel.padrao_global ?? {};
}

// O valor EFETIVO de uma chave no nível do fluxo: o ajuste da automação, ou o padrão do
// Batuta. É o "herdado" que o agente sobrepõe na aba "Ritmo e espera" dele.
export function efetivoDoFluxo(
  painel: PainelConfigFluxo,
  configFluxo: ConfiguracaoFluxo,
  chave: string,
): unknown {
  const ajustes = configFluxo.ajustes ?? {};
  if (chave in ajustes) return ajustes[chave];
  return defaultsDoBatuta(painel)[chave];
}

export function CampoConfig({
  campo,
  valor,
  ajustado,
  podeEditar,
  onChange,
  onReset,
  rotuloHerdado = "padrão do Batuta",
}: {
  campo: CampoConfigFluxo;
  valor: unknown;
  ajustado: boolean;
  podeEditar: boolean;
  onChange: (v: unknown) => void;
  onReset: () => void;
  rotuloHerdado?: string;
}) {
  // Marcador "herdado" / "ajustado — voltar ao padrão" (o afinado vence o herdado;
  // deixamos isso visível e reversível).
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
      <span className="text-[11px] text-muted-foreground/60">{rotuloHerdado}</span>
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
  // Os limites EFETIVOS (perfil + ajustes) em português. A redação vive no backend
  // (`config.resumo_dos_limites`) — se ela fosse reescrita aqui, as duas versões
  // divergiriam com o tempo, que é a origem clássica de bug recorrente neste projeto.
  const [limites, setLimites] = useState<string[]>([]);
  const [ondeMudar, setOndeMudar] = useState<string>("");

  useEffect(() => {
    api
      .get<PainelConfigFluxo>("/config/fluxo")
      .then(setPainel)
      .catch(() => setErro("Não consegui carregar as opções de configuração."));
  }, []);

  // Só os ajustes: o `perfil` não é mais camada, então mandá-lo faria o cérebro
  // calcular um efetivo que a tela não pratica.
  const configSerializada = JSON.stringify({ ajustes: valor.ajustes ?? {} });
  useEffect(() => {
    let vivo = true;
    api
      .post<{ limites: string[]; onde_mudar: string }>(
        "/config/fluxo/limites",
        JSON.parse(configSerializada),
      )
      .then((r) => {
        if (!vivo) return;
        setLimites(r.limites);
        setOndeMudar(r.onde_mudar);
      })
      .catch(() => {
        if (vivo) setLimites([]);
      });
    return () => {
      vivo = false;
    };
  }, [configSerializada]);

  const ajustes = valor.ajustes ?? {};
  const defaults = painel?.padrao_global ?? {};

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
              {/* O "Tipo de fluxo" morreu aqui. Ele era um dropdown que trocava seis
                  números de uma vez, em silêncio, e cujos valores não estavam no dado
                  da automação — daí o "até hoje não entendi pra que serve". Sobrou o
                  que ele tinha de útil: partir de um modelo, uma vez, à vista. */}
              {podeEditar && painel.presets.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>Partir de um modelo:</span>
                  {painel.presets.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() =>
                        onChange({
                          ...valor,
                          perfil: undefined,
                          ajustes: { ...ajustes, ...p.ajustes },
                        })
                      }
                      className="rounded-md border border-border px-2 py-1 font-medium text-foreground hover:bg-muted"
                    >
                      {p.rotulo}
                    </button>
                  ))}
                  <span className="basis-full text-[11px]">
                    Isto copia os números do modelo para cá. Depois eles são seus — o
                    modelo não fica mandando por trás.
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

              {/* Os LIMITES, à vista. Antes viviam só dentro do "Avançado", como
                  números soltos: um teto de custo de US$ 0,50 derrubou uma aprovação
                  em 14/09/2026 e ninguém sabia que ele existia. */}
              {limites.length > 0 && (
                <div className="mt-3 flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3 text-[13px] text-foreground">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    <Gauge className="size-3.5" /> Limites deste fluxo
                  </div>
                  <ul className="flex list-disc flex-col gap-1 pl-4">
                    {limites.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                  <p className="text-[11px] text-muted-foreground">
                    Quase todos são ajustáveis no “Avançado” abaixo
                    {ondeMudar ? ` (${ondeMudar})` : ""} — os que não forem dizem isso
                    na própria linha. Quando um deles é atingido, o agente avisa quem
                    está esperando e o fluxo segue: nada fica parado em silêncio.
                  </p>
                </div>
              )}

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
                      <RotateCcw className="size-3.5" /> Limpar todos os ajustes
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
