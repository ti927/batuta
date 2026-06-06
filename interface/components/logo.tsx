import { cn } from "@/lib/utils"

// Logotipo da Batuta (DESIGN-SYSTEM §3): símbolo (batuta diagonal roxa com um
// sparkle amarelo na ponta) + a palavra "Batuta" em Bricolage Grotesque
// Semibold. Símbolo SIMPLES, provisório — a arte final (mascote, kit de logo,
// favicon) ainda não foi produzida (DS §13 TODO).

function SimboloBatuta({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("size-6", className)}
    >
      {/* a batuta — linha diagonal arredondada, Roxo Batuta */}
      <path
        d="M5 19 L16 8"
        stroke="#6D4AFF"
        strokeWidth="3"
        strokeLinecap="round"
      />
      {/* o sparkle na ponta — Amarelo Aplauso */}
      <path
        d="M18 4.2c.45 1.75 1.05 2.35 2.8 2.8-1.75.45-2.35 1.05-2.8 2.8-.45-1.75-1.05-2.35-2.8-2.8 1.75-.45 2.35-1.05 2.8-2.8Z"
        fill="#F5C44A"
      />
    </svg>
  )
}

export function Logo({
  className,
  simboloClassName,
}: {
  className?: string
  simboloClassName?: string
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <SimboloBatuta className={simboloClassName} />
      <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
        Batuta
      </span>
    </span>
  )
}

export { SimboloBatuta }
