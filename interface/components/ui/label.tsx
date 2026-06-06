import { cn } from "@/lib/utils"

// Rótulo de formulário (DESIGN-SYSTEM §5): peso 500, 14px. Acima do campo.
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-1 text-sm font-medium text-foreground select-none",
        className,
      )}
      {...props}
    />
  )
}

export { Label }
