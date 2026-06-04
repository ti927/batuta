// Renovação de sessão para o proxy.ts (o "middleware" do Next 16).
// Padrão oficial do @supabase/ssr: ler/gravar os cookies de sessão no par
// request/response a cada requisição, e — de quebra — barrar quem não está
// logado, mandando para /login. NÃO faça busca de dados pesada aqui (proxy é
// para checagem rápida, não para autorização completa — isso é no cérebro).

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Rotas que não exigem sessão: a tela de login; o aceite de convite e a rota
// que recebe o link do e-mail de convite (é como um convidado entra antes de
// ter cadastro).
const ROTAS_PUBLICAS = ["/login", "/convite", "/auth"];

export async function renovarSessao(request: NextRequest) {
  let resposta = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesParaGravar) {
          cookiesParaGravar.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          resposta = NextResponse.next({ request });
          cookiesParaGravar.forEach(({ name, value, options }) =>
            resposta.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // IMPORTANTE: nada de lógica entre criar o cliente e o getUser() — ele é o
  // que valida e renova o token. O getUser() (e não getSession()) bate no
  // servidor do Supabase, então a checagem é confiável.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const caminho = request.nextUrl.pathname;
  const ehPublica = ROTAS_PUBLICAS.some((p) => caminho.startsWith(p));

  if (!user && !ehPublica) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return resposta;
}
