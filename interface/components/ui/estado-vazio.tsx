import { cn } from "@/lib/utils"

// Estado vazio (DESIGN-SYSTEM §10): ícone grande + texto curto + sugestão do
// que fazer (e, quando faz sentido, um botão de ação passado via `acao`).
// Substitui os "Nenhum X ainda." crus espalhados pelas listas.
function EstadoVazio({
  icone: Icone,
  titulo,
  className,
  children,
  acao,
}: {
  icone?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>
  titulo: string
  className?: string
  children?: React.ReactNode
  acao?: React.ReactNode
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className,
      )}
    >
      {Icone && (
        <Icone className="size-8 text-muted-foreground/50" aria-hidden={true} />
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{titulo}</p>
        {children && (
          <p className="text-sm text-muted-foreground">{children}</p>
        )}
      </div>
      {acao}
    </div>
  )
}

export { EstadoVazio }
