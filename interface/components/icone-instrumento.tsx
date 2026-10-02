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
 * O ícone do serviço (`auto`, guardado pelo cérebro como data:) entra quando não há
 * escolhido — ou ANTES do escolhido, com `autoPrimeiro` (os prontos que chamam uma IA
 * ou o Telegram: o escolhido vira a reserva para quando o site não tem ícone).
 * `className` controla tamanho/cor (ex.: "size-4").
 */
export function IconeInstrumento({
  icone,
  auto,
  autoPrimeiro,
  className,
}: {
  icone?: string | null;
  /** Ícone do serviço (data:): quando não há `icone`, ou antes dele com `autoPrimeiro`. */
  auto?: string | null;
  autoPrimeiro?: boolean;
  className?: string;
}) {
  const temAuto = !!auto?.startsWith("data:image/");
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
  if (temAuto && (autoPrimeiro || !icone)) {
    // Guardado pelo cérebro como data: — não busca nada fora.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={auto!} alt="" className={`${className ?? ""} rounded-sm object-contain`} />;
  }
  if (def) {
    return <FontAwesomeIcon icon={def} className={className} />;
  }
  return <Wrench className={className} />;
}
