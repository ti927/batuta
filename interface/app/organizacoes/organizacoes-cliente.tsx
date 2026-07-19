"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Building2, KeyRound } from "lucide-react";

import {
  api,
  mensagemDeErro,
  type Organizacao,
  type PapelAcesso,
} from "@/lib/api";
import { podeAdmin } from "@/lib/permissoes";
import { AvatarOrg } from "@/components/avatar-org";
import { FormularioOrganizacao } from "@/components/formulario-organizacao";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";

export function OrganizacoesCliente({
  inicial,
  papeis,
  adminConsultoria,
}: {
  inicial: Organizacao[];
  papeis: Record<string, PapelAcesso>;
  adminConsultoria: boolean;
}) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  // Modal: fechado quando `aberto` é false. `editando=null` cria; com org edita.
  const [aberto, setAberto] = useState(false);
  const [editando, setEditando] = useState<Organizacao | null>(null);

  function abrirCriar() {
    setEditando(null);
    setAberto(true);
  }

  function abrirEditar(org: Organizacao) {
    setEditando(org);
    setAberto(true);
  }

  async function remover(id: string, nome: string) {
    if (!confirm(`Remover a organização "${nome}"?`)) return;
    try {
      await api.delete(`/organizacoes/${id}`);
      setErro(null);
      router.refresh();
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha ao remover"));
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-1">
        <h1 className="text-2xl font-medium text-foreground">Organizações</h1>
        {adminConsultoria && (
          <Link
            href="/chaves-consultoria"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <KeyRound className="size-3.5" />
            Chave-mãe da consultoria
          </Link>
        )}
      </div>

      {erro && <Aviso className="mb-4">{erro}</Aviso>}

      <div className="mb-6">
        <Button onClick={abrirCriar}>Criar organização</Button>
      </div>

      {inicial.length === 0 ? (
        <EstadoVazio icone={Building2} titulo="Você ainda não tem organizações.">
          Crie a primeira acima para começar.
        </EstadoVazio>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {inicial.map((org) => (
            <li key={org.id} className="flex items-center gap-3 p-3">
              <AvatarOrg nome={org.nome} logoUrl={org.logo_url} />
              <Link
                href={`/organizacoes/${org.id}`}
                className="flex-1 text-sm font-medium text-foreground hover:text-primary hover:underline"
              >
                {org.nome}
              </Link>
              {podeAdmin(papeis[org.id]) && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => abrirEditar(org)}
                  >
                    Editar
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => remover(org.id, org.nome)}
                  >
                    Remover
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {aberto && (
        <FormularioOrganizacao
          organizacao={editando}
          onSalvo={() => {
            setAberto(false);
            router.refresh();
          }}
          onCancelar={() => setAberto(false)}
        />
      )}
    </main>
  );
}
