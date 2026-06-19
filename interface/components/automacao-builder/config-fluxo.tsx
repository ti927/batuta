"use client";

// Diálogo "Configurações do fluxo": o usuário escolhe um TIPO DE FLUXO (perfil, que
// já traz regras sensatas) e, no "Avançado", afina botão a botão. Os perfis, grupos
// e opções vêm de /config/fluxo (fonte única no backend) — nada é duplicado aqui.

import { useEffect, useState } from "react";
import { Sliders, X } from "lucide-react";

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

function CampoConfig({
  campo,
  valor,
  podeEditar,
  onChange,
}: {
  campo: CampoConfigFluxo;
  valor: unknown;
  podeEditar: boolean;
  onChange: (v: unknown) => void;
}) {
  if (campo.tipo === "bool") {
    return (
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
    );
  }
  return (
    <Label className="flex-col items-start gap-1 text-[12px] text-muted-foreground">
      {campo.rotulo}
      {campo.sufixo ? ` (${campo.sufixo})` : ""}
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
  const perfilId = valor.perfil ?? "atendimento";
  const perfil = painel?.perfis.find((p) => p.id === perfilId);
  const defaults = perfil?.defaults ?? painel?.padrao_global ?? {};

  function efetivo(chave: string): unknown {
    return chave in ajustes ? ajustes[chave] : defaults[chave];
  }

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
                  value={perfilId}
                  disabled={!podeEditar}
                  onChange={(e) => onChange({ ...valor, perfil: e.target.value })}
                  className="w-full"
                >
                  {painel.perfis.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.rotulo}
                    </option>
                  ))}
                </Select>
              </Label>
              <p className="mt-1.5 text-xs text-muted-foreground">
                O tipo de fluxo já vem com regras sensatas. Use o “Avançado” só se
                quiser afinar algo.
              </p>

              <button
                type="button"
                className="mt-4 text-sm font-medium text-primary"
                onClick={() => setAvancado((v) => !v)}
              >
                {avancado ? "▾ Avançado" : "▸ Avançado"}
              </button>

              {avancado && (
                <div className="mt-3 flex flex-col gap-5">
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
                          podeEditar={podeEditar}
                          onChange={(v) =>
                            onChange({
                              ...valor,
                              ajustes: { ...ajustes, [c.chave]: v },
                            })
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
