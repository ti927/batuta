"use client";

import { type IconDefinition } from "@fortawesome/fontawesome-svg-core";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useEffect, useState } from "react";
import { Wrench } from "lucide-react";

import { resolverExterno } from "@/lib/icones-externos";
import { MAPA_ICONES } from "@/lib/icones-instrumento";

/**
 * Ícone de um instrumento. Resolve o `icone` escolhido (id do Font Awesome):
 * - se está no catálogo CURADO, renderiza na hora (já está no bundle);
 * - senão, carrega o registro completo SOB DEMANDA e renderiza (mostra o genérico
 *   Wrench enquanto carrega — acontece só para ícones fora dos curados);
 * - sem `icone`, fica no genérico Wrench (comportamento de sempre).
 * `className` controla tamanho/cor (ex.: "size-4").
 */
export function IconeInstrumento({
  icone,
  className,
}: {
  icone?: string | null;
  className?: string;
}) {
  const curado = icone ? MAPA_ICONES.get(icone) : undefined;
  // Guarda o id junto: um resultado de outro `icone` (troca rápida) é ignorado,
  // sem precisar de um setState de reset no corpo do efeito.
  const [resolvido, setResolvido] = useState<{ id: string; def: IconDefinition } | null>(
    null,
  );

  // Resolve no efeito (pós-hidratação) para o 1º render do cliente bater com o
  // do servidor — evita "hydration mismatch". Para ícones curados não roda.
  useEffect(() => {
    if (!icone || curado) return;
    let ativo = true;
    resolverExterno(icone).then((def) => {
      if (ativo && def) setResolvido({ id: icone, def });
    });
    return () => {
      ativo = false;
    };
  }, [icone, curado]);

  const externo =
    !curado && icone && resolvido?.id === icone ? resolvido.def : undefined;
  const def = curado ?? externo;
  if (def) {
    return <FontAwesomeIcon icon={def} className={className} />;
  }
  return <Wrench className={className} />;
}
