"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Activity,
  ChevronDown,
  Coins,
  Gauge,
  Home,
  Key,
  Library,
  LogOut,
  Menu,
  Settings,
  Shield,
  Sparkles,
  Users,
  X,
} from "lucide-react";

import { AvatarOrg } from "@/components/avatar-org";
import { SimboloBatuta } from "@/components/logo";
import { criarClienteNavegador } from "@/lib/supabase/cliente-navegador";
import { podeAdmin } from "@/lib/permissoes";
import {
  type Organizacao,
  type PapelAcesso,
  type Time,
} from "@/lib/api";

// O shell de navegação definitivo (handoff §5): sidebar escura à esquerda. As
// cores são as do DESIGN-SYSTEM (#1A1730 fundo, #6D4AFF item ativo). Todos os dados
// vêm do servidor (layout); a interatividade (item ativo, expandir Times, trocar
// organização, sair) é client-side. A organização ativa vive em estado de sessão (o
// layout não desmonta entre navegações); persistir entre refreshes fica para depois.

function iniciais(email: string): string {
  const base = email.split("@")[0] ?? email;
  const partes = base.split(/[.\-_]+/).filter(Boolean);
  const txt = partes.length >= 2 ? partes[0][0] + partes[1][0] : base.slice(0, 2);
  return txt.toUpperCase();
}

export function Sidebar({
  email,
  organizacoes,
  timesPorOrg,
  papeis,
  adminConsultoria,
}: {
  email: string;
  organizacoes: Organizacao[];
  timesPorOrg: Record<string, Time[]>;
  papeis: Record<string, PapelAcesso>;
  adminConsultoria: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [orgAtiva, setOrgAtiva] = useState(organizacoes[0]?.id ?? "");
  const [seletorAberto, setSeletorAberto] = useState(false);
  const [timesAberto, setTimesAberto] = useState(true);
  const [saindo, setSaindo] = useState(false);
  const [menuMobile, setMenuMobile] = useState(false);

  function trocarOrg(id: string) {
    setOrgAtiva(id);
    setSeletorAberto(false);
  }

  async function sair() {
    setSaindo(true);
    await criarClienteNavegador().auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const org = organizacoes.find((o) => o.id === orgAtiva);
  const times = timesPorOrg[orgAtiva] ?? [];
  const ehAdminOrg = podeAdmin(papeis[orgAtiva]);
  const ativo = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  const corpo = (
    <>
      {/* Branding */}
      <Link href="/" className="mb-1 flex items-center gap-2 px-1.5 pt-1">
        <SimboloBatuta className="size-6" />
        <span className="font-heading text-lg font-semibold text-white">Batuta</span>
      </Link>

      {/* Criar com a IA */}
      <Link
        href="/criar"
        className={`mt-3 mb-2 flex h-10 items-center justify-center gap-2 rounded-md bg-[#6D4AFF] text-sm font-medium text-white transition-colors hover:bg-[#5A3FE0] ${
          ativo("/criar") ? "ring-3 ring-[#6D4AFF]/35" : ""
        }`}
      >
        <Sparkles className="size-4" />
        Criar com a IA
      </Link>

      {/* Nav primária */}
      <nav className="flex flex-col gap-0.5">
        <ItemNav href="/" Icone={Home} ativo={pathname === "/"}>
          Início
        </ItemNav>

        <button
          type="button"
          onClick={() => setTimesAberto((v) => !v)}
          className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-[#C9C6DE] transition-colors hover:bg-white/[0.07]"
        >
          <Users className="size-4.5 shrink-0" />
          <span className="flex-1 text-left">Times</span>
          <ChevronDown
            className={`size-4 transition-transform ${timesAberto ? "" : "-rotate-90"}`}
          />
        </button>
        {timesAberto && (
          <div className="ml-3.5 flex flex-col gap-0.5 border-l border-white/10 pl-2.5">
            {times.length === 0 ? (
              <span className="px-2.5 py-1.5 text-xs text-[#8A86A6]">
                Nenhum time ainda
              </span>
            ) : (
              times.map((t) => (
                <Link
                  key={t.id}
                  href={`/times/${t.id}`}
                  className={`truncate rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                    pathname === `/times/${t.id}`
                      ? "bg-[#6D4AFF] text-white"
                      : "text-[#C9C6DE] hover:bg-white/[0.07]"
                  }`}
                >
                  {t.nome}
                </Link>
              ))
            )}
          </div>
        )}

        <ItemNav href="/execucoes" Icone={Activity} ativo={ativo("/execucoes")}>
          Execuções
        </ItemNav>
        <ItemNav href="/biblioteca" Icone={Library} ativo={ativo("/biblioteca")}>
          Biblioteca
        </ItemNav>
        <ItemNav href="/uso" Icone={Gauge} ativo={ativo("/uso")}>
          Uso e custos
        </ItemNav>
      </nav>

      <div className="my-3.5 h-px bg-white/[0.08]" />

      {/* Nav da organização */}
      <nav className="flex flex-col gap-0.5">
        {ehAdminOrg && org && (
          <>
            <ItemNav
              href={`/organizacoes/${org.id}/acesso`}
              Icone={Shield}
              ativo={ativo(`/organizacoes/${org.id}/acesso`)}
            >
              Acesso e papéis
            </ItemNav>
            <ItemNav
              href={`/organizacoes/${org.id}/chaves`}
              Icone={Key}
              ativo={ativo(`/organizacoes/${org.id}/chaves`)}
            >
              Chaves e credenciais
            </ItemNav>
          </>
        )}
        {adminConsultoria && (
          <>
            <ItemNav
              href="/chaves-consultoria"
              Icone={Key}
              ativo={ativo("/chaves-consultoria")}
            >
              Chaves da consultoria
            </ItemNav>
            <ItemNav
              href="/uso-consultoria"
              Icone={Coins}
              ativo={ativo("/uso-consultoria")}
            >
              Uso da consultoria
            </ItemNav>
          </>
        )}
        <ItemNav href="/configuracoes" Icone={Settings} ativo={ativo("/configuracoes")}>
          Configurações
        </ItemNav>
      </nav>

      {/* Rodapé: seletor de organização + usuário */}
      <div className="mt-auto flex flex-col gap-2 pt-3">
        {org && (
          <div className="relative">
            <button
              type="button"
              onClick={() => organizacoes.length > 1 && setSeletorAberto((v) => !v)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left transition-colors hover:bg-white/[0.07]"
            >
              <AvatarOrg nome={org.nome} logoUrl={org.logo_url} />
              <span className="min-w-0 flex-1 truncate text-[13px] text-[#C9C6DE]">
                {org.nome}
              </span>
              {organizacoes.length > 1 && (
                <ChevronDown className="size-3.5 text-[#8A86A6]" />
              )}
            </button>
            {seletorAberto && (
              <div className="absolute bottom-full left-0 mb-1 w-full overflow-hidden rounded-md border border-white/10 bg-[#241F3D] py-1 shadow-lg">
                {organizacoes.map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    onClick={() => trocarOrg(o.id)}
                    className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] transition-colors hover:bg-white/[0.07] ${
                      o.id === orgAtiva ? "text-white" : "text-[#C9C6DE]"
                    }`}
                  >
                    <AvatarOrg
                      nome={o.nome}
                      logoUrl={o.logo_url}
                      className="size-5 text-[10px]"
                    />
                    <span className="min-w-0 flex-1 truncate">{o.nome}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 rounded-md px-2 py-1.5">
          <span
            className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
            style={{ background: "linear-gradient(135deg,#6D4AFF,#B19CD9)" }}
          >
            {iniciais(email)}
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-[#C9C6DE]" title={email}>
            {email}
          </span>
          <button
            type="button"
            onClick={sair}
            disabled={saindo}
            aria-label="Sair"
            className="rounded-md p-1.5 text-[#8A86A6] transition-colors hover:bg-white/[0.07] hover:text-white"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Barra superior (só mobile): logo + menu */}
      <div className="flex items-center justify-between border-b border-border bg-[#1A1730] px-4 py-2.5 md:hidden">
        <Link href="/" className="flex items-center gap-2">
          <SimboloBatuta className="size-5" />
          <span className="font-heading font-semibold text-white">Batuta</span>
        </Link>
        <button
          type="button"
          onClick={() => setMenuMobile(true)}
          aria-label="Abrir menu"
          className="rounded-md p-1.5 text-[#C9C6DE] hover:bg-white/[0.07]"
        >
          <Menu className="size-5" />
        </button>
      </div>

      {/* Overlay mobile */}
      {menuMobile && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <button
            className="absolute inset-0 bg-black/50"
            aria-label="Fechar menu"
            onClick={() => setMenuMobile(false)}
          />
          <aside className="relative flex w-[246px] flex-col overflow-y-auto bg-[#1A1730] p-3">
            <button
              type="button"
              onClick={() => setMenuMobile(false)}
              aria-label="Fechar menu"
              className="absolute right-2 top-2 rounded-md p-1.5 text-[#8A86A6] hover:bg-white/[0.07] hover:text-white"
            >
              <X className="size-4" />
            </button>
            {/* Fecha o menu só quando um LINK é clicado (não os botões de
                expandir Times / trocar organização). `contents` preserva o flex. */}
            <div
              className="contents"
              onClick={(e) => {
                if ((e.target as HTMLElement).closest("a")) setMenuMobile(false);
              }}
            >
              {corpo}
            </div>
          </aside>
        </div>
      )}

      {/* Sidebar desktop */}
      <aside className="hidden w-[246px] shrink-0 flex-col overflow-y-auto bg-[#1A1730] p-3 md:flex">
        {corpo}
      </aside>
    </>
  );
}

function ItemNav({
  href,
  Icone,
  ativo,
  children,
}: {
  href: string;
  Icone: typeof Home;
  ativo: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
        ativo
          ? "bg-[#6D4AFF] text-white"
          : "text-[#C9C6DE] hover:bg-white/[0.07]"
      }`}
    >
      <Icone className="size-4.5 shrink-0" />
      {children}
    </Link>
  );
}
