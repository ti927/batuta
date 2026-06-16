import { AreaEmBreve } from "@/components/area-em-breve";

// Placeholder da aba Execuções (Fase 1). A lista por time (master-detail com o
// passo a passo e o portão de aprovação dentro da aba) chega na Fase 3 — por ora
// a aba existe e navega, sem link morto. As execuções seguem visíveis pela
// automação (/automacoes/[id]) e pela visão consolidada (/execucoes).
export default function ExecucoesTabPage() {
  return (
    <AreaEmBreve titulo="Execuções do time">
      Em breve as execuções de todas as automações deste time aparecem aqui — com
      o passo a passo e a aprovação dentro da própria aba.
    </AreaEmBreve>
  );
}
