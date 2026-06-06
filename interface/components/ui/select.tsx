import { cn } from "@/lib/utils"

// Seletor nativo estilizado. Mantém o <select> nativo de propósito: preserva
// <optgroup> (usado no seletor de modelo de IA, agrupado por provedor) e a
// acessibilidade do controle do sistema. Mesma linguagem visual do Input.
function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="select"
      className={cn(
        "h-10 w-full rounded-md border border-input bg-card px-3 text-sm text-foreground",
        "transition-colors outline-none cursor-pointer",
        "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export { Select }
