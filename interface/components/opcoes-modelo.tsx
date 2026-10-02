"use client";

// As opções de um seletor de modelo de IA, agrupadas por provedor — o mesmo nos três
// seletores (agente, IA de conversa, instrumentos de IA). O catálogo vem do cérebro
// (GET /modelos), com custo e aviso de saída; é lido uma vez por página e reaproveitado.

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import {
  modelosDoProvedor,
  rotuloModelo,
  ROTULO_PROVEDOR,
  type InfoModelo,
  type Provedor,
} from "@/lib/modelos";

let emCache: InfoModelo[] | null = null;
let pedido: Promise<InfoModelo[]> | null = null;

/** O catálogo de modelos do cérebro. Vazio enquanto carrega (ou se falhar). */
export function useCatalogoModelos(): InfoModelo[] {
  const [catalogo, setCatalogo] = useState<InfoModelo[]>(emCache ?? []);
  useEffect(() => {
    if (emCache) return;
    let vivo = true;
    pedido ??= api.get<InfoModelo[]>("/modelos").then((c) => (emCache = c));
    pedido
      .then((c) => {
        if (vivo) setCatalogo(c);
      })
      .catch(() => {
        pedido = null; // tenta de novo na próxima vez que o seletor abrir
      });
    return () => {
      vivo = false;
    };
  }, []);
  return catalogo;
}

export function OpcoesModelo({
  provedores,
  catalogo,
  atual,
}: {
  provedores: Provedor[];
  catalogo: InfoModelo[];
  atual?: string | null;
}) {
  // O valor salvo continua visível mesmo antes de o catálogo chegar (ou se ele não
  // conhecer o modelo) — o seletor nunca "esquece" o que está configurado.
  const conhecido = catalogo.some((m) => m.id === atual);
  return (
    <>
      {atual && !conhecido && <option value={atual}>{atual}</option>}
      {provedores.map((p) => {
        const lista = modelosDoProvedor(catalogo, p, atual);
        if (lista.length === 0) return null;
        return (
          <optgroup key={p} label={ROTULO_PROVEDOR[p]}>
            {lista.map((m) => (
              <option key={m.id} value={m.id}>
                {rotuloModelo(m)}
              </option>
            ))}
          </optgroup>
        );
      })}
    </>
  );
}

/** O aviso de saída do modelo escolhido (ou null), para mostrar abaixo do seletor. */
export function alertaDoModelo(catalogo: InfoModelo[], atual?: string | null): string | null {
  return catalogo.find((m) => m.id === atual)?.alerta ?? null;
}
