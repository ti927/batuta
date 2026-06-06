import { SimboloBatuta } from "@/components/logo";
import { LoginCliente } from "./login-cliente";

// Rota pública (liberada no proxy.ts). Quem já está logado e cai aqui pode
// simplesmente navegar para dentro; a proteção das demais rotas é do proxy.
export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-1 flex-col items-center justify-center gap-8 p-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <span className="inline-flex items-center gap-2.5">
          <SimboloBatuta className="size-9" />
          <span className="font-heading text-3xl font-semibold tracking-tight text-foreground">
            Batuta
          </span>
        </span>
        <p className="text-sm text-muted-foreground">Você guia. A IA executa.</p>
      </div>
      <LoginCliente />
    </main>
  );
}
