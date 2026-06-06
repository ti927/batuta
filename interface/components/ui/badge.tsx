import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// Selo/etiqueta (DESIGN-SYSTEM §9): pill arredondado, 12px peso 500, variações
// por contexto (informativo/sucesso/atenção/erro), sempre cor + texto (nunca só
// cor — acessibilidade §11). O neutro serve a rótulos sem carga semântica.
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap [&_svg]:size-3.5",
  {
    variants: {
      variant: {
        neutral: "bg-secondary text-muted-foreground",
        info: "bg-accent text-accent-foreground",
        success: "bg-success/12 text-success",
        warning: "bg-warning/15 text-warning",
        error: "bg-destructive/12 text-destructive",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
)

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
