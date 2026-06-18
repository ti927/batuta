import { type LucideIcon } from "lucide-react";

/** Rótulo de seção: ícone roxo + texto + linha-régua (handoff §6.0). Compartilhado
 *  pelo canvas da criação e pelo painel "O que eu sei deste projeto". */
export function RotuloSecao({
  Icone,
  children,
}: {
  Icone: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-7 mb-3 flex items-center gap-2">
      <Icone className="size-4 text-primary" />
      <span className="text-sm font-medium text-foreground">{children}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

export function rotuloGatilho(tipo: string): string {
  const mapa: Record<string, string> = {
    manual: "Manual (você dispara quando quiser)",
    agendamento: "Por horário (agendado)",
    webhook: "Por webhook (chamada externa)",
  };
  return mapa[tipo] ?? tipo;
}
