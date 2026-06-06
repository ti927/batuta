"use client";

import { type ChaveApiLer } from "@/lib/api";
import { GestaoChaves } from "@/components/gestao-chaves";

export function ConsultoriaCliente({ chaves }: { chaves: ChaveApiLer[] }) {
  return <GestaoChaves basePath="/chaves-consultoria" chavesIniciais={chaves} />;
}
