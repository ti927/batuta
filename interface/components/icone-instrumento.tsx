"use client";

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { Wrench } from "lucide-react";

import { MAPA_ICONES } from "@/lib/icones-instrumento";

/**
 * Ícone de um instrumento. Se o instrumento tem um `icone` escolhido (id do
 * catálogo Font Awesome), renderiza-o; senão, cai no genérico `Wrench` (lucide),
 * que é o comportamento de sempre. `className` controla tamanho/cor (ex.: "size-4").
 */
export function IconeInstrumento({
  icone,
  className,
}: {
  icone?: string | null;
  className?: string;
}) {
  const def = icone ? MAPA_ICONES.get(icone) : undefined;
  if (def) {
    return <FontAwesomeIcon icon={def} className={className} />;
  }
  return <Wrench className={className} />;
}
