import { cn } from "@/lib/utils";

// Avatar de uma organização: mostra o logo (data URI) quando há; senão um círculo
// com o gradiente de marca e a inicial do nome. Reusado na lista de organizações
// e na sidebar. Tamanho/forma ajustáveis por `className`.
export function AvatarOrg({
  nome,
  logoUrl,
  className,
}: {
  nome: string;
  logoUrl: string | null;
  className?: string;
}) {
  if (logoUrl) {
    return (
      // data URI: o next/image não se aplica; <img> é o correto aqui.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={logoUrl}
        alt=""
        className={cn("size-6 shrink-0 rounded-md object-cover", className)}
      />
    );
  }
  return (
    <span
      className={cn(
        "flex size-6 shrink-0 items-center justify-center rounded-md text-[11px] font-medium text-[#0B2B27]",
        className,
      )}
      style={{ background: "linear-gradient(135deg,#3DD8C3,#6D4AFF)" }}
    >
      {([...nome][0] ?? "?").toUpperCase()}
    </span>
  );
}
