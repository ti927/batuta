import type { Metadata } from "next";

import { ENCARREGADO, PRODUTO, URL_BASE } from "@/lib/legal";
import { PaginaLegal, Secao } from "@/components/pagina-legal";

export const metadata: Metadata = {
  title: "Exclusão de Dados — Batuta",
  description:
    "Como solicitar a exclusão dos seus dados pessoais no Batuta, incluindo os " +
    "dados obtidos do Instagram/Meta.",
};

export default function ExclusaoDeDadosPage() {
  return (
    <PaginaLegal titulo="Exclusão de Dados">
      <p>
        Esta página explica como solicitar a exclusão dos seus dados pessoais
        tratados pelo <strong>{PRODUTO}</strong>, incluindo os dados obtidos por
        meio de contas conectadas, como o Instagram/Meta. Levamos a sério o seu
        direito de eliminação previsto na LGPD.
      </p>

      <Secao titulo="1. Como solicitar a exclusão">
        <p>
          Envie um e-mail para{" "}
          <a href={`mailto:${ENCARREGADO.email}`}>{ENCARREGADO.email}</a> com o
          assunto <strong>“Exclusão de dados”</strong>, informando:
        </p>
        <ul>
          <li>seu nome e o e-mail cadastrado na plataforma;</li>
          <li>
            a organização e/ou as contas conectadas envolvidas (por exemplo, a conta
            do Instagram);
          </li>
          <li>o que você deseja excluir (todos os dados ou itens específicos).</li>
        </ul>
        <p>
          Poderemos solicitar informações adicionais para confirmar a sua identidade
          antes de atender ao pedido, como medida de segurança.
        </p>
      </Secao>

      <Secao titulo="2. O que é excluído">
        <p>Mediante a solicitação, excluímos:</p>
        <ul>
          <li>sua conta e os dados pessoais associados;</li>
          <li>
            tokens e credenciais de contas conectadas (por exemplo, o token de acesso
            do Instagram);
          </li>
          <li>
            conteúdos, conversas e arquivos vinculados à sua conta/organização,
            quando aplicável.
          </li>
        </ul>
        <p>
          Alguns dados podem ser <strong>retidos pelo tempo necessário</strong> ao
          cumprimento de obrigações legais ou regulatórias (por exemplo, registros
          mínimos de auditoria e obrigações fiscais) e, depois disso, eliminados ou
          anonimizados.
        </p>
      </Secao>

      <Secao titulo="3. Dados do Instagram/Meta">
        <p>
          Para os dados obtidos do Instagram/Meta, você pode:
        </p>
        <ul>
          <li>
            <strong>Desconectar a conta</strong> na plataforma — isso remove o token
            de acesso armazenado e interrompe o acesso do {PRODUTO} à sua conta;
          </li>
          <li>
            <strong>Solicitar a remoção</strong> dos dados derivados (métricas,
            comentários e conteúdos coletados) pelo e-mail acima;
          </li>
          <li>
            <strong>Revogar o acesso pelo próprio Instagram</strong>: nas
            configurações da sua conta, em “Aplicativos e sites”, remova o aplicativo
            — isso revoga imediatamente as permissões concedidas.
          </li>
        </ul>
      </Secao>

      <Secao titulo="4. Prazo de atendimento">
        <p>
          Atendemos às solicitações de exclusão em até <strong>15 dias</strong>{" "}
          corridos, prorrogáveis quando justificado, conforme a LGPD. Confirmaremos a
          conclusão pelo e-mail informado na solicitação.
        </p>
      </Secao>

      <Secao titulo="5. Contato">
        <p>
          Solicitações e dúvidas sobre exclusão de dados devem ser enviadas ao nosso
          Encarregado, {ENCARREGADO.nome}, pelo e-mail{" "}
          <a href={`mailto:${ENCARREGADO.email}`}>{ENCARREGADO.email}</a>.
        </p>
        <p>
          Esta página está disponível publicamente em{" "}
          <a href={`${URL_BASE}/exclusao-de-dados`}>{URL_BASE}/exclusao-de-dados</a>.
        </p>
      </Secao>
    </PaginaLegal>
  );
}
