import { AjudaCliente, type CapituloResumo } from "@/components/ajuda-cliente";
import { buscarCerebro } from "@/lib/cerebro-servidor";

// Central de Conhecimento (manual do humano). O índice vem do cérebro (que lê os
// capítulos de `cerebro/central/`); o conteúdo de cada capítulo é buscado no cliente.
export default async function AjudaPage() {
  const resp = await buscarCerebro("/ajuda/indice");
  const capitulos: CapituloResumo[] = resp.ok
    ? ((await resp.json()).capitulos ?? [])
    : [];
  return <AjudaCliente capitulos={capitulos} />;
}
