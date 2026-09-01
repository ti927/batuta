import type { Metadata } from "next";

import { CONTROLADOR, ENCARREGADO, PRODUTO } from "@/lib/legal";
import { PaginaLegal, Secao } from "@/components/pagina-legal";

export const metadata: Metadata = {
  title: "Termos de Uso — Batuta",
  description:
    "As regras de uso da plataforma Batuta: serviço, conta, integrações de " +
    "terceiros, conteúdo gerado por IA e responsabilidades.",
};

export default function TermosPage() {
  return (
    <PaginaLegal titulo="Termos de Uso">
      <p>
        Estes Termos de Uso regulam o acesso e a utilização da plataforma{" "}
        <strong>{PRODUTO}</strong> (batuta.team), fornecida pela{" "}
        {CONTROLADOR.razaoSocial}, CNPJ {CONTROLADOR.cnpj} (“nós” ou “{PRODUTO}”).
        Ao criar uma conta ou usar a plataforma, você concorda com estes Termos. Se
        não concordar, não utilize o serviço.
      </p>

      <Secao titulo="1. Definições">
        <ul>
          <li>
            <strong>Organização:</strong> a conta da empresa que utiliza o {PRODUTO}.
          </li>
          <li>
            <strong>Time:</strong> um conjunto de agentes que trabalham juntos.
          </li>
          <li>
            <strong>Agente:</strong> um trabalhador de IA configurado para uma função.
          </li>
          <li>
            <strong>Instrumento:</strong> uma capacidade ou integração que um agente
            usa (por exemplo, publicar num site, enviar mensagem, gerar imagem).
          </li>
          <li>
            <strong>Automação:</strong> o fluxo que encadeia agentes para executar
            uma tarefa.
          </li>
        </ul>
      </Secao>

      <Secao titulo="2. O serviço">
        <p>
          O {PRODUTO} permite que pessoas não técnicas criem times de agentes de
          inteligência artificial que executam tarefas reais, encadeando agentes,
          instrumentos e canais. O serviço é fornecido “no estado em que se
          encontra” e pode evoluir ao longo do tempo.
        </p>
      </Secao>

      <Secao titulo="3. Conta e cadastro">
        <p>
          Você é responsável por manter a confidencialidade das suas credenciais e
          por todas as atividades realizadas na sua conta. Comprometa-se a fornecer
          informações verdadeiras e a mantê-las atualizadas. Avise-nos imediatamente
          em caso de uso não autorizado.
        </p>
      </Secao>

      <Secao titulo="4. Contas e integrações de terceiros">
        <p>
          A plataforma permite conectar contas e serviços de terceiros (por exemplo,
          Instagram/Meta, WordPress, provedores de IA). Ao conectá-los, você declara
          que:
        </p>
        <ul>
          <li>
            possui autorização e os direitos necessários para usar essas contas e os
            dados nelas contidos;
          </li>
          <li>
            cumprirá os termos e as políticas de cada plataforma de terceiros,{" "}
            <strong>incluindo os Termos da Plataforma e Políticas de
            Desenvolvedores da Meta</strong> aplicáveis ao Instagram;
          </li>
          <li>
            é o responsável pelo conteúdo publicado e pelas interações realizadas por
            meio dessas integrações.
          </li>
        </ul>
      </Secao>

      <Secao titulo="5. Uso aceitável">
        <p>Ao usar o {PRODUTO}, você concorda em não:</p>
        <ul>
          <li>
            violar leis, direitos de terceiros (incluindo propriedade intelectual e
            privacidade) ou as regras das plataformas integradas;
          </li>
          <li>enviar spam, conteúdo enganoso, ilegal, ofensivo ou prejudicial;</li>
          <li>
            usar a plataforma para abusar de APIs de terceiros ou contornar seus
            limites e políticas;
          </li>
          <li>
            tentar burlar a segurança, fazer engenharia reversa ou interferir no
            funcionamento do serviço.
          </li>
        </ul>
      </Secao>

      <Secao titulo="6. Conteúdo gerado por inteligência artificial">
        <p>
          Os agentes produzem conteúdo por meio de modelos de IA. Esse conteúdo pode
          conter imprecisões e <strong>não constitui aconselhamento</strong>{" "}
          profissional. Você é responsável por revisar o conteúdo antes de publicá-lo
          ou utilizá-lo, especialmente em ações irreversíveis (como publicar numa
          rede social). A plataforma oferece um recurso de{" "}
          <strong>aprovação humana</strong> — o agente apresenta o que fará e aguarda
          sua autorização explícita — para que ações sensíveis dependam de você.
        </p>
      </Secao>

      <Secao titulo="7. Propriedade intelectual">
        <p>
          A plataforma {PRODUTO}, sua marca, código e materiais são de titularidade
          da {CONTROLADOR.razaoSocial} e protegidos por lei. Os dados, configurações
          e conteúdos que você fornece ou produz por meio da plataforma permanecem
          seus; você nos concede as licenças necessárias para operar o serviço em seu
          benefício.
        </p>
      </Secao>

      <Secao titulo="8. Planos, uso e pagamento">
        <p>
          O uso da plataforma pode estar sujeito a planos, limites e cobrança,
          conforme contratado. A plataforma contabiliza o uso e os custos
          associados. Condições comerciais específicas, quando aplicáveis, serão
          informadas separadamente.
        </p>
      </Secao>

      <Secao titulo="9. Disponibilidade, suspensão e rescisão">
        <p>
          Empenhamo-nos para manter o serviço disponível, mas não garantimos
          operação ininterrupta. Podemos suspender ou encerrar o acesso em caso de
          violação destes Termos ou de exigência legal. Você pode encerrar sua conta
          a qualquer momento.
        </p>
      </Secao>

      <Secao titulo="10. Limitação de responsabilidade">
        <p>
          Na máxima extensão permitida pela lei, o {PRODUTO} não se responsabiliza
          por danos indiretos, lucros cessantes ou pelo conteúdo gerado pela IA ou
          publicado por meio das integrações que você configura. O serviço é
          fornecido sem garantias além das previstas em lei.
        </p>
      </Secao>

      <Secao titulo="11. Privacidade">
        <p>
          O tratamento de dados pessoais é regido pela nossa{" "}
          <a href="/privacidade">Política de Privacidade</a>, que integra estes
          Termos.
        </p>
      </Secao>

      <Secao titulo="12. Alterações destes Termos">
        <p>
          Podemos atualizar estes Termos a qualquer momento. A data da última
          atualização consta no topo desta página; mudanças relevantes serão
          comunicadas. O uso continuado após a atualização implica concordância.
        </p>
      </Secao>

      <Secao titulo="13. Lei aplicável e foro">
        <p>
          Estes Termos são regidos pelas leis da República Federativa do Brasil.
          Fica eleito o foro da Comarca de Goiânia/GO para dirimir quaisquer
          questões, com renúncia a qualquer outro, por mais privilegiado que seja.
          Dúvidas podem ser encaminhadas para{" "}
          <a href={`mailto:${ENCARREGADO.email}`}>{ENCARREGADO.email}</a>.
        </p>
      </Secao>
    </PaginaLegal>
  );
}
