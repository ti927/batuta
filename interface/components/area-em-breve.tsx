import Image from "next/image";

// Tela de área que existe no Batuta mas ainda não foi desenhada (handoff §6.7).
// Mascote + título + nota honesta — evita link morto na sidebar.
export function AreaEmBreve({
  titulo,
  children,
}: {
  titulo: string;
  children?: React.ReactNode;
}) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-4 py-16 text-center">
      <Image
        src="/mascote.png"
        alt=""
        width={200}
        height={200}
        className="h-auto w-44 opacity-90"
      />
      <h1 className="mt-5 font-heading text-xl font-semibold text-foreground">
        {titulo}
      </h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {children ?? "Esta área existe no Batuta — o desenho dela vem em breve."}
      </p>
    </main>
  );
}
