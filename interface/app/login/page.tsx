import { LoginCliente } from "./login-cliente";

// Rota pública (liberada no proxy.ts). Quem já está logado e cai aqui pode
// simplesmente navegar para dentro; a proteção das demais rotas é do proxy.
export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">Batuta</h1>
        <p className="mt-1 text-sm text-zinc-500">Você guia. A IA executa.</p>
      </div>
      <LoginCliente />
    </main>
  );
}
