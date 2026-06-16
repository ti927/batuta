// Catálogo curado de ícones para instrumentos (Font Awesome free).
//
// Exceção pontual ao DESIGN-SYSTEM §8 (lucide-only): aqui o usuário escolhe um
// ícone para o instrumento, e a Font Awesome traz os LOGOS DE MARCA (WhatsApp,
// Telegram, Google, WordPress…) que o lucide não tem. Toda a iconografia de UI
// segue lucide; isto vale só para o ícone do instrumento.
//
// Cada ícone é importado EXPLICITAMENTE (tree-shaking: só o que está aqui entra
// no bundle — não embarcamos as ~1500 figuras da FA). Para ampliar, basta
// adicionar uma linha ao catálogo.

import { config, type IconDefinition } from "@fortawesome/fontawesome-svg-core";
import {
  faAmazon,
  faApple,
  faDiscord,
  faDropbox,
  faFacebook,
  faFacebookMessenger,
  faGithub,
  faGitlab,
  faGoogle,
  faGoogleDrive,
  faInstagram,
  faLinkedin,
  faMailchimp,
  faMeta,
  faMicrosoft,
  faPaypal,
  faPinterest,
  faReddit,
  faShopify,
  faSlack,
  faSpotify,
  faStripe,
  faTelegram,
  faTiktok,
  faTrello,
  faWhatsapp,
  faWordpress,
  faXTwitter,
  faYoutube,
} from "@fortawesome/free-brands-svg-icons";
import {
  faBell,
  faBolt,
  faBullhorn,
  faCalendarDays,
  faCartShopping,
  faChartLine,
  faCloud,
  faCode,
  faComments,
  faCreditCard,
  faDatabase,
  faEnvelope,
  faFileLines,
  faFilePdf,
  faGear,
  faGlobe,
  faHeadset,
  faImage,
  faKey,
  faLink,
  faLocationDot,
  faMagnifyingGlass,
  faMicrophone,
  faMoneyBillTransfer,
  faNewspaper,
  faPaperPlane,
  faPenToSquare,
  faPhone,
  faPlug,
  faRobot,
  faServer,
  faTable,
  faTruck,
  faVideo,
} from "@fortawesome/free-solid-svg-icons";

// O componente React injeta o <svg> inline; desligamos a inserção automática de
// CSS global da FA (evita flicker/conflito no Next App Router).
config.autoAddCss = false;

export type IconeCatalogo = {
  id: string; // ex.: "fab:whatsapp", "fas:database"
  nome: string;
  icon: IconDefinition;
  termos: string; // palavras de busca (pt-br + en), minúsculas
};

// Marcas (logos) — o motivo de usar Font Awesome aqui.
const MARCAS: IconeCatalogo[] = [
  { id: "fab:whatsapp", nome: "WhatsApp", icon: faWhatsapp, termos: "whatsapp zap mensagem chat" },
  { id: "fab:telegram", nome: "Telegram", icon: faTelegram, termos: "telegram bot mensagem chat" },
  { id: "fab:google", nome: "Google", icon: faGoogle, termos: "google busca pesquisa" },
  { id: "fab:google-drive", nome: "Google Drive", icon: faGoogleDrive, termos: "google drive arquivo nuvem" },
  { id: "fab:wordpress", nome: "WordPress", icon: faWordpress, termos: "wordpress blog site publicar cms" },
  { id: "fab:slack", nome: "Slack", icon: faSlack, termos: "slack mensagem time" },
  { id: "fab:discord", nome: "Discord", icon: faDiscord, termos: "discord mensagem comunidade" },
  { id: "fab:instagram", nome: "Instagram", icon: faInstagram, termos: "instagram insta rede social foto" },
  { id: "fab:facebook", nome: "Facebook", icon: faFacebook, termos: "facebook rede social meta" },
  { id: "fab:messenger", nome: "Messenger", icon: faFacebookMessenger, termos: "messenger facebook mensagem chat" },
  { id: "fab:meta", nome: "Meta", icon: faMeta, termos: "meta facebook" },
  { id: "fab:linkedin", nome: "LinkedIn", icon: faLinkedin, termos: "linkedin rede profissional" },
  { id: "fab:youtube", nome: "YouTube", icon: faYoutube, termos: "youtube video" },
  { id: "fab:tiktok", nome: "TikTok", icon: faTiktok, termos: "tiktok video rede social" },
  { id: "fab:x-twitter", nome: "X (Twitter)", icon: faXTwitter, termos: "x twitter tuite rede social" },
  { id: "fab:pinterest", nome: "Pinterest", icon: faPinterest, termos: "pinterest imagem" },
  { id: "fab:reddit", nome: "Reddit", icon: faReddit, termos: "reddit forum" },
  { id: "fab:spotify", nome: "Spotify", icon: faSpotify, termos: "spotify audio musica" },
  { id: "fab:github", nome: "GitHub", icon: faGithub, termos: "github git codigo repositorio" },
  { id: "fab:gitlab", nome: "GitLab", icon: faGitlab, termos: "gitlab git codigo repositorio" },
  { id: "fab:stripe", nome: "Stripe", icon: faStripe, termos: "stripe pagamento cobranca" },
  { id: "fab:paypal", nome: "PayPal", icon: faPaypal, termos: "paypal pagamento" },
  { id: "fab:shopify", nome: "Shopify", icon: faShopify, termos: "shopify loja ecommerce" },
  { id: "fab:mailchimp", nome: "Mailchimp", icon: faMailchimp, termos: "mailchimp email marketing" },
  { id: "fab:dropbox", nome: "Dropbox", icon: faDropbox, termos: "dropbox arquivo nuvem" },
  { id: "fab:microsoft", nome: "Microsoft", icon: faMicrosoft, termos: "microsoft office" },
  { id: "fab:apple", nome: "Apple", icon: faApple, termos: "apple ios" },
  { id: "fab:amazon", nome: "Amazon", icon: faAmazon, termos: "amazon aws loja" },
  { id: "fab:trello", nome: "Trello", icon: faTrello, termos: "trello quadro tarefa" },
];

// Conceitos (genéricos) — para instrumentos que não são de uma marca.
const CONCEITOS: IconeCatalogo[] = [
  { id: "fas:globe", nome: "Web", icon: faGlobe, termos: "web internet site globo mundo" },
  { id: "fas:magnifying-glass", nome: "Busca", icon: faMagnifyingGlass, termos: "busca pesquisa lupa procurar" },
  { id: "fas:database", nome: "Banco de dados", icon: faDatabase, termos: "banco dados sql database" },
  { id: "fas:table", nome: "Tabela", icon: faTable, termos: "tabela planilha dados" },
  { id: "fas:server", nome: "Servidor", icon: faServer, termos: "servidor server api host" },
  { id: "fas:plug", nome: "Conexão", icon: faPlug, termos: "conexao plug integracao api mcp" },
  { id: "fas:code", nome: "Código", icon: faCode, termos: "codigo code api rest json" },
  { id: "fas:paper-plane", nome: "Enviar", icon: faPaperPlane, termos: "enviar mensagem envio" },
  { id: "fas:comments", nome: "Conversa", icon: faComments, termos: "conversa chat mensagem atendimento" },
  { id: "fas:headset", nome: "Atendimento", icon: faHeadset, termos: "atendimento suporte sac" },
  { id: "fas:envelope", nome: "E-mail", icon: faEnvelope, termos: "email correio mensagem" },
  { id: "fas:phone", nome: "Telefone", icon: faPhone, termos: "telefone ligacao voz" },
  { id: "fas:robot", nome: "Robô / IA", icon: faRobot, termos: "robo ia bot agente" },
  { id: "fas:image", nome: "Imagem", icon: faImage, termos: "imagem foto figura gerar" },
  { id: "fas:video", nome: "Vídeo", icon: faVideo, termos: "video filme" },
  { id: "fas:microphone", nome: "Áudio", icon: faMicrophone, termos: "audio microfone voz transcricao" },
  { id: "fas:file-pdf", nome: "PDF", icon: faFilePdf, termos: "pdf documento arquivo" },
  { id: "fas:file-lines", nome: "Documento", icon: faFileLines, termos: "documento arquivo texto" },
  { id: "fas:newspaper", nome: "Notícia / Conteúdo", icon: faNewspaper, termos: "noticia conteudo artigo jornal" },
  { id: "fas:pen-to-square", nome: "Editar / Escrever", icon: faPenToSquare, termos: "editar escrever redacao" },
  { id: "fas:bullhorn", nome: "Marketing", icon: faBullhorn, termos: "marketing anuncio divulgacao" },
  { id: "fas:bell", nome: "Notificação", icon: faBell, termos: "notificacao alerta sino aviso" },
  { id: "fas:calendar", nome: "Agenda", icon: faCalendarDays, termos: "agenda calendario data evento" },
  { id: "fas:chart-line", nome: "Relatório", icon: faChartLine, termos: "relatorio grafico metrica analise" },
  { id: "fas:cart-shopping", nome: "Carrinho", icon: faCartShopping, termos: "carrinho compra loja ecommerce" },
  { id: "fas:credit-card", nome: "Pagamento", icon: faCreditCard, termos: "pagamento cartao cobranca" },
  { id: "fas:money-bill-transfer", nome: "Financeiro", icon: faMoneyBillTransfer, termos: "financeiro dinheiro transferencia pagamento" },
  { id: "fas:truck", nome: "Logística", icon: faTruck, termos: "logistica entrega frete transporte" },
  { id: "fas:location-dot", nome: "Localização", icon: faLocationDot, termos: "localizacao mapa endereco gps" },
  { id: "fas:cloud", nome: "Nuvem", icon: faCloud, termos: "nuvem cloud armazenamento" },
  { id: "fas:link", nome: "Link / Webhook", icon: faLink, termos: "link url webhook conexao" },
  { id: "fas:bolt", nome: "Automação", icon: faBolt, termos: "automacao raio gatilho disparo" },
  { id: "fas:key", nome: "Chave / Credencial", icon: faKey, termos: "chave credencial senha api" },
  { id: "fas:gear", nome: "Configuração", icon: faGear, termos: "config engrenagem ajuste ferramenta" },
];

export const CATALOGO_ICONES: IconeCatalogo[] = [...MARCAS, ...CONCEITOS];

// Lookup O(1): id → IconDefinition (usado pelo <IconeInstrumento>).
export const MAPA_ICONES: Map<string, IconDefinition> = new Map(
  CATALOGO_ICONES.map((i) => [i.id, i.icon]),
);
