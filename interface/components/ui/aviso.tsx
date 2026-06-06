import { AlertCircle, CheckCircle2, Info, XCircle } from "lucide-react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// Faixa de aviso/erro (DESIGN-SYSTEM §11): sempre cor + ícone + texto, nunca só
// cor. Padroniza as mensagens inline que antes eram <p> vermelho cru espalhados
// pelas telas. Tom acolhedor: a mensagem em si vem de quem usa o componente.
const avisoVariants = cva(
  "flex items-start gap-2 rounded-md border px-3 py-2 text-sm [&_svg]:mt-0.5 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        erro: "border-destructive/30 bg-destructive/8 text-destructive",
        atencao: "border-warning/30 bg-warning/10 text-warning",
        sucesso: "border-success/30 bg-success/10 text-success",
        info: "border-accent-foreground/20 bg-accent text-accent-foreground",
      },
    },
    defaultVariants: { variant: "erro" },
  },
)

const icones = {
  erro: XCircle,
  atencao: AlertCircle,
  sucesso: CheckCircle2,
  info: Info,
} as const

function Aviso({
  className,
  variant = "erro",
  children,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof avisoVariants>) {
  const Icone = icones[variant ?? "erro"]
  return (
    <div
      role="alert"
      className={cn(avisoVariants({ variant }), className)}
      {...props}
    >
      <Icone aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export { Aviso }
