import type { Metadata } from "next";

import { CONTROLADOR, ENCARREGADO, PRODUTO } from "@/lib/legal";
import { PaginaLegal, Secao } from "@/components/pagina-legal";

export const metadata: Metadata = {
  title: "Política de Privacidade — Batuta",
  description:
    "Como o Batuta coleta, usa, compartilha e protege seus dados pessoais, " +
    "conforme a LGPD e as políticas da Meta.",
};

export default function PrivacidadePage() {
  return (
    <PaginaLegal titulo="Política de Privacidade">
      <p>
        Esta Política de Privacidade explica como o <strong>{PRODUTO}</strong>{" "}
        (plataforma disponível em batuta.team) coleta, utiliza, compartilha e
        protege dados pessoais, em conformidade com a Lei nº 13.709/2018 (Lei
        Geral de Proteção de Dados — LGPD) e com as políticas das plataformas de
        terceiros que integramos, incluindo a Meta (Instagram).
      </p>

      <Secao titulo="1. Quem é o controlador dos seus dados">
        <p>
          O controlador dos dados pessoais tratados no {PRODUTO} é a{" "}
          <strong>{CONTROLADOR.razaoSocial}</strong>, inscrita no CNPJ sob o nº{" "}
          {CONTROLADOR.cnpj}, com sede em {CONTROLADOR.endereco}.
        </p>
        <p>
          <strong>Encarregado pelo Tratamento de Dados (DPO):</strong>{" "}
          {ENCARREGADO.nome} — contato pelo e-mail{" "}
          <a href={`mailto:${ENCARREGADO.email}`}>{ENCARREGADO.email}</a>.
        </p>
      </Secao>

      <Secao titulo="2. O que é o Batuta e a quem esta política se aplica">
        <p>
          O {PRODUTO} é uma plataforma na qual organizações criam times de
          agentes de inteligência artificial que executam tarefas reais —
          encadeando agentes em automações, conectando instrumentos e canais. Esta
          política se aplica a:
        </p>
        <ul>
          <li>
            <strong>Usuários da plataforma</strong> (administradores, operadores e
            observadores das organizações que usam o {PRODUTO});
          </li>
          <li>
            <strong>Contatos finais</strong> que interagem com os agentes por
            canais de mensagens (por exemplo, Telegram);
          </li>
          <li>
            <strong>Dados de contas de terceiros conectadas</strong> pelo cliente
            (por exemplo, Instagram/Meta e WordPress), processados a pedido e sob
            responsabilidade desse cliente.
          </li>
        </ul>
      </Secao>

      <Secao titulo="3. Quais dados coletamos">
        <p>
          Coletamos apenas os dados necessários ao funcionamento da plataforma,
          conforme a categoria e a origem:
        </p>
        <ul>
          <li>
            <strong>Dados de conta:</strong> nome, e-mail e papel do usuário,
            geridos por meio do nosso provedor de autenticação (Supabase Auth),
            além do registro de ações realizadas na plataforma (auditoria).
          </li>
          <li>
            <strong>Dados de uso da plataforma:</strong> organizações, times,
            agentes, automações, execuções, conversas mantidas com a IA de criação,
            memórias de projeto e métricas de uso e custo.
          </li>
          <li>
            <strong>Dados de mensageria</strong> (Telegram e, futuramente,
            WhatsApp): identificador do contato (chat_id), nome do contato e o
            conteúdo das mensagens trocadas com os agentes. Mensagens de voz são
            transcritas em texto por meio do serviço OpenAI Whisper —{" "}
            <strong>o áudio original não é armazenado</strong>, apenas a
            transcrição.
          </li>
          <li>
            <strong>Dados do Instagram/Meta</strong> (quando o cliente conecta uma
            conta): o token de acesso (armazenado de forma cifrada), o
            identificador da conta (ig_user_id), métricas e estatísticas dos posts,
            o conteúdo publicado por meio da plataforma e os{" "}
            <strong>comentários de terceiros</strong> (nome de usuário e texto) que
            o cliente opta por ler, responder ou moderar.
          </li>
          <li>
            <strong>Conteúdo gerado e arquivos:</strong> textos, imagens e
            documentos (PDF) produzidos pelos agentes. Imagens e PDFs são guardados
            em armazenamento de arquivos (Supabase Storage) em{" "}
            <strong>bucket público</strong>; as URLs desses arquivos são públicas e
            podem ser acessadas por quem tiver o endereço (necessário, por exemplo,
            para que a Meta baixe uma imagem ao publicá-la).
          </li>
        </ul>
        <p>
          Não coletamos intencionalmente dados pessoais sensíveis. Pedimos que você
          não insira esse tipo de dado nos conteúdos processados pelos agentes,
          salvo quando estritamente necessário e com a devida base legal.
        </p>
      </Secao>

      <Secao titulo="4. Para que usamos os dados e com qual base legal">
        <p>Tratamos os dados pessoais para as seguintes finalidades:</p>
        <ul>
          <li>operar, manter e disponibilizar a plataforma e suas funcionalidades;</li>
          <li>
            executar as automações, publicações e interações que o cliente
            configura e aciona;
          </li>
          <li>autenticar usuários e controlar acessos e permissões;</li>
          <li>medir uso e custos, dar suporte e prevenir abusos e fraudes;</li>
          <li>cumprir obrigações legais e regulatórias.</li>
        </ul>
        <p>
          As bases legais aplicáveis (LGPD, arts. 7º e 11) incluem: execução de
          contrato e de procedimentos preliminares; legítimo interesse para operar e
          aprimorar o serviço; cumprimento de obrigação legal; e consentimento,
          quando aplicável.
        </p>
      </Secao>

      <Secao titulo="5. Uso dos dados do Instagram/Meta">
        <p>
          Quando uma conta do Instagram é conectada, usamos os dados obtidos por
          meio das APIs da Meta <strong>exclusivamente</strong> para executar as
          funções que o cliente aciona — publicar conteúdo, ler métricas e ler,
          responder ou moderar comentários. Especificamente:
        </p>
        <ul>
          <li>
            <strong>não vendemos</strong> nem alugamos dados obtidos da Meta;
          </li>
          <li>
            <strong>não usamos</strong> esses dados para criar perfis de
            publicidade próprios nem os transferimos para corretores de dados;
          </li>
          <li>
            mantemos esses dados apenas enquanto a conta estiver conectada e pelo
            tempo necessário às finalidades acima;
          </li>
          <li>
            o token de acesso é guardado cifrado e usado somente para chamar as
            APIs da Meta em nome do cliente.
          </li>
        </ul>
      </Secao>

      <Secao titulo="6. Com quem compartilhamos dados (operadores e sub-processadores)">
        <p>
          Não vendemos dados pessoais. Para operar a plataforma, compartilhamos
          dados, na medida do necessário, com prestadores de serviço que atuam como
          operadores:
        </p>
        <ul>
          <li>
            <strong>Supabase</strong> — banco de dados, autenticação e armazenamento
            de arquivos;
          </li>
          <li>
            <strong>Railway</strong> — hospedagem da aplicação;
          </li>
          <li>
            <strong>Provedores de IA</strong> (Anthropic, OpenAI e Google) — para
            processar os textos e conteúdos das automações e conversas;
          </li>
          <li>
            <strong>Serviços de busca e leitura na web</strong> (Tavily, Exa e
            Firecrawl) — quando o agente pesquisa ou lê páginas;
          </li>
          <li>
            <strong>Resend</strong> — envio de e-mails transacionais (por exemplo,
            convites);
          </li>
          <li>
            <strong>Telegram</strong> e <strong>Meta/Instagram</strong> — para
            enviar e receber mensagens e para publicar e interagir, conforme o
            cliente configura.
          </li>
        </ul>
        <p>
          Alguns desses provedores estão sediados fora do Brasil. Nesses casos, há{" "}
          <strong>transferência internacional de dados</strong>, realizada com base
          nas hipóteses da LGPD (art. 33) e com salvaguardas adequadas. Também
          poderemos compartilhar dados para cumprir ordem legal ou determinação de
          autoridade competente.
        </p>
      </Secao>

      <Secao titulo="7. Como protegemos os dados">
        <p>
          Adotamos medidas técnicas e administrativas para proteger os dados (LGPD,
          art. 46), entre elas:
        </p>
        <ul>
          <li>
            segredos e credenciais (tokens, senhas) armazenados de forma{" "}
            <strong>cifrada</strong> (criptografia simétrica), com a chave-mestra
            mantida fora do banco de dados;
          </li>
          <li>comunicação por canais protegidos (TLS/HTTPS);</li>
          <li>controle de acesso por papéis dentro de cada organização;</li>
          <li>
            segredos nunca reexibidos na interface (mostramos apenas os últimos
            dígitos para conferência).
          </li>
        </ul>
        <p>
          Nenhum sistema é totalmente imune a riscos; comprometemo-nos a tratar
          incidentes com diligência e a comunicar quando exigido por lei.
        </p>
      </Secao>

      <Secao titulo="8. Por quanto tempo guardamos e como eliminamos">
        <p>
          Mantemos os dados pessoais enquanto a conta/organização existir e pelo
          tempo necessário às finalidades desta política e ao cumprimento de
          obrigações legais. Você pode solicitar a exclusão dos seus dados a
          qualquer momento — veja a página de{" "}
          <a href="/exclusao-de-dados">Exclusão de Dados</a>.
        </p>
      </Secao>

      <Secao titulo="9. Seus direitos como titular">
        <p>
          Nos termos da LGPD (art. 18), você pode, a qualquer tempo, solicitar:
          confirmação da existência de tratamento; acesso aos dados; correção de
          dados incompletos, inexatos ou desatualizados; anonimização, bloqueio ou
          eliminação de dados desnecessários ou tratados em desconformidade;
          portabilidade; informação sobre o compartilhamento; e revogação do
          consentimento.
        </p>
        <p>
          Para exercer seus direitos, escreva para{" "}
          <a href={`mailto:${ENCARREGADO.email}`}>{ENCARREGADO.email}</a>. Você
          também tem o direito de apresentar reclamação à Autoridade Nacional de
          Proteção de Dados (ANPD).
        </p>
      </Secao>

      <Secao titulo="10. Cookies e sessão">
        <p>
          Utilizamos apenas cookies estritamente necessários para autenticar sua
          sessão e manter você conectado (provisionados pelo Supabase). Não usamos
          cookies de rastreamento publicitário.
        </p>
      </Secao>

      <Secao titulo="11. Crianças e adolescentes">
        <p>
          A plataforma é destinada a uso profissional por organizações e não se
          dirige a crianças ou adolescentes. Não coletamos intencionalmente dados de
          menores.
        </p>
      </Secao>

      <Secao titulo="12. Alterações desta política">
        <p>
          Podemos atualizar esta Política de Privacidade para refletir mudanças na
          plataforma ou na legislação. A data da última atualização está indicada no
          topo desta página. Mudanças relevantes serão comunicadas pelos canais
          apropriados.
        </p>
      </Secao>

      <Secao titulo="13. Contato">
        <p>
          Em caso de dúvidas sobre esta política ou sobre o tratamento dos seus
          dados, fale com o nosso Encarregado, {ENCARREGADO.nome}, pelo e-mail{" "}
          <a href={`mailto:${ENCARREGADO.email}`}>{ENCARREGADO.email}</a>.
        </p>
      </Secao>
    </PaginaLegal>
  );
}
