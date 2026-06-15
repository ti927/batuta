"use client";

import {
  type ChaveApiLer,
  type Credencial,
  type TipoCredencial,
} from "@/lib/api";
import { CofreCredenciais } from "@/components/cofre-credenciais";
import { GestaoChaves } from "@/components/gestao-chaves";

export function ConsultoriaCliente({
  chaves,
  credenciais,
  tiposCredencial,
}: {
  chaves: ChaveApiLer[];
  credenciais: Credencial[];
  tiposCredencial: TipoCredencial[];
}) {
  return (
    <div className="flex flex-col gap-10">
      <section>
        <h2 className="mb-1 text-lg font-medium text-foreground">
          Chaves de serviço
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          As chaves de IA e busca da consultoria. Marque como compartilhável a
          que pode servir de reserva às organizações sem chave própria.
        </p>
        <GestaoChaves
          basePath="/chaves-consultoria"
          chavesIniciais={chaves}
          ehConsultoria
        />
      </section>

      <section>
        <h2 className="mb-1 text-lg font-medium text-foreground">Credenciais</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Credenciais nomeadas da consultoria (ex.: um servidor MCP próprio).
          Marque como compartilhável para que os instrumentos das organizações
          possam escolhê-la.
        </p>
        <CofreCredenciais
          credenciais={credenciais}
          tipos={tiposCredencial}
          ehConsultoria
        />
      </section>
    </div>
  );
}
