import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import {
  type ChaveApiLer,
  type Credencial,
  type TipoCredencial,
} from "@/lib/api";
import { buscarCerebro, buscarMeuAcesso } from "@/lib/cerebro-servidor";
import { Aviso } from "@/components/ui/aviso";

import { ConsultoriaCliente } from "./consultoria-cliente";

async function carregar(): Promise<{
  adminConsultoria: boolean;
  chaves: ChaveApiLer[];
  credenciais: Credencial[];
  tiposCredencial: TipoCredencial[];
}> {
  const eu = await buscarMeuAcesso();
  const adminConsultoria = eu?.admin_consultoria ?? false;
  let chaves: ChaveApiLer[] = [];
  let credenciais: Credencial[] = [];
  let tiposCredencial: TipoCredencial[] = [];
  if (adminConsultoria) {
    const [respChaves, respCred, respTipos] = await Promise.all([
      buscarCerebro("/chaves-consultoria"),
      buscarCerebro("/credenciais-consultoria"),
      buscarCerebro("/credenciais/tipos"),
    ]);
    if (respChaves.ok) chaves = await respChaves.json();
    if (respCred.ok) credenciais = await respCred.json();
    if (respTipos.ok) tiposCredencial = await respTipos.json();
  }
  return { adminConsultoria, chaves, credenciais, tiposCredencial };
}

export default async function ChavesConsultoriaPage() {
  const { adminConsultoria, chaves, credenciais, tiposCredencial } =
    await carregar();
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Link
        href="/organizacoes"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Organizações
      </Link>
      <h1 className="mb-2 mt-2 text-2xl font-medium text-foreground">
        Chaves e credenciais da consultoria
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        As chaves de serviço e credenciais da consultoria. Cada uma só serve de
        reserva às organizações se você marcá-la como compartilhável.
      </p>

      {adminConsultoria ? (
        <ConsultoriaCliente
          chaves={chaves}
          credenciais={credenciais}
          tiposCredencial={tiposCredencial}
        />
      ) : (
        <Aviso variant="atencao">
          Esta área é restrita aos administradores da consultoria.
        </Aviso>
      )}
    </main>
  );
}
