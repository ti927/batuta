// app-data-team.jsx — Dados reais do time "Conteúdo Controladoria (Teste)" (Lure Consultoria)
// Alinhado aos screenshots do app de produção.

const ORG = { nome: 'Lure Consultoria', sigla: 'LC' };
const USER = { nome: 'luregpt@lureconsult…', inicial: 'N', papel: 'admin' };

const TEAMS_SIDEBAR = [
  { nome: 'Publicação Rápida WordPr…', key: 'placeholder:Publicação Rápida WordPress' },
  { nome: 'Conteúdo Controladoria (T…', key: 'time' },
  { nome: 'Teste Webhook + REST (B…', key: 'placeholder:Teste Webhook + REST' },
  { nome: 'Time de Teste — Telegram', key: 'placeholder:Time de Teste — Telegram' },
];

const CT = {
  nome: 'Conteúdo Controladoria (Teste)',
  resumo: 'Cadeia de teste que descobre um tema sobre controladoria financeira, valida, escreve o artigo e publica no WordPress.',
  estado: 'ativo',
  agentes: [
    {
      id: 'cacador', nome: 'Caçador de Pauta', papel: 'inicial', cor: '#3DD8C3',
      modelo: 'claude-sonnet-4-6', tier: 'capaz',
      resumo: 'Propõe um tema relevante e atual de controladoria financeira para um artigo.',
      instrumentos: [{ nome: 'Busca na web', icon: 'search' }],
      docs: {
        agent: 'Você é um pauteiro de conteúdo especializado em controladoria financeira. Sua função é propor UM tema relevante e atual sobre controladoria financeira para um artigo de blog.',
        skill: 'Encontrar temas atuais e com potencial de busca.\nAvaliar relevância para o público de controladoria.\nEntregar UMA pauta clara, com ângulo definido.',
        tools: 'Busca na web — para checar o que está em alta no momento.',
        soul: 'Curioso e objetivo. Entrega uma pauta pronta, sem rodeios.',
      },
    },
    {
      id: 'validador', nome: 'Validador de Pauta', papel: 'agente', cor: '#B19CD9',
      modelo: 'claude-sonnet-4-6', tier: 'capaz',
      resumo: 'Valida se a pauta é pertinente, clara e tem fôlego antes de virar artigo.',
      instrumentos: [],
      docs: {
        agent: 'Você é um editor que valida pautas de controladoria financeira antes de virarem artigo. Julga se o tema é pertinente, claro e tem fôlego para um bom texto.',
        skill: 'Avaliar pertinência e clareza do tema.\nApontar ajustes de ângulo.\nAprovar ou recusar a pauta com justificativa curta.',
        tools: 'Nenhum instrumento — trabalha só com o texto recebido.',
        soul: 'Criterioso e direto. Prefere recusar a deixar passar algo morno.',
      },
    },
    {
      id: 'redator', nome: 'Redator', papel: 'agente', cor: '#6D4AFF',
      modelo: 'claude-opus-4-8', tier: 'avançado',
      resumo: 'Escreve o artigo a partir da pauta aprovada — claro, correto e útil.',
      instrumentos: [],
      docs: {
        agent: 'Você é um redator de blog especializado em controladoria financeira. Escreve artigos claros, corretos e úteis a partir da pauta aprovada.',
        skill: 'Redação longa e fluida.\nEstrutura com título, intertítulos e fechamento.\nLinguagem técnica acessível, sem jargão desnecessário.',
        tools: 'Nenhum instrumento.',
        soul: 'Escreve com clareza e ritmo. Português de gente real.',
      },
    },
    {
      id: 'revisor', nome: 'Revisor de SEO', papel: 'agente', cor: '#3DD8C3',
      modelo: 'claude-sonnet-4-6', tier: 'capaz',
      resumo: 'Recebe o artigo pronto e o entrega lapidado e otimizado para publicação.',
      instrumentos: [],
      gate: true,
      docs: {
        agent: 'Você é um revisor de conteúdo e SEO especializado em artigos de controladoria financeira. Recebe o artigo pronto e o entrega lapidado para publicação.',
        skill: 'Revisão fina de texto.\nSEO on-page (título, meta, intertítulos, palavra-chave).\nGarantir consistência de marca.',
        tools: 'Nenhum instrumento.',
        soul: 'Detalhista e cuidadoso. Entrega só o que está pronto pra publicar.',
      },
    },
    {
      id: 'publicador', nome: 'Publicador', papel: 'agente', cor: '#F5C44A',
      modelo: 'claude-haiku-4-5', tier: 'rápido',
      resumo: 'Publica o artigo pronto no WordPress.',
      instrumentos: [{ nome: 'Publicar no WordPress (rascunho)', icon: 'globe' }],
      docs: {
        agent: 'Você é o agente que publica o artigo pronto no WordPress.',
        skill: 'Montar o post.\nAplicar título, categoria e tags.\nPublicar como rascunho para revisão final.',
        tools: 'Publicar no WordPress (rascunho).',
        soul: 'Preciso e cuidadoso. Confere antes de publicar.',
      },
    },
  ],
  instrumentos: [
    { id: 'wp', nome: 'Publicar no WordPress (rascunho)', slug: 'publicar_wordpress', tipo: 'WordPress', icon: 'globe', exigeAprovacao: true, usadoPor: ['Publicador'], descricao: 'Cria um rascunho de post no WordPress do cliente via API REST.' },
    { id: 'web', nome: 'Busca na web', slug: 'busca_web', tipo: 'Busca', icon: 'search', exigeAprovacao: false, usadoPor: ['Caçador de Pauta'], descricao: 'Consulta a web em tempo real para checar temas e fatos.' },
  ],
  automacao: {
    nome: 'Automação de Conteúdo Controladoria (Teste)',
    gatilho: 'Manual', gatilhoDetalhe: 'Dispara apenas pelo botão de teste, na tela da automação.',
    inicial: 'Caçador de Pauta',
    saidas: [
      { agente: 'Caçador de Pauta', inicial: true, gate: false, rotulo: 'tema escolhido', destino: 'Validador de Pauta' },
      { agente: 'Validador de Pauta', gate: false, rotulo: 'pauta aprovada', destino: 'Redator' },
      { agente: 'Redator', gate: false, rotulo: 'artigo escrito', destino: 'Revisor de SEO' },
      { agente: 'Revisor de SEO', gate: true, rotulo: 'artigo revisado e aprovado por humano', destino: 'Publicador' },
      { agente: 'Publicador', gate: false, rotulo: 'publicado', destino: 'fim' },
    ],
  },
};

// Cadeia (ordem do fluxo) derivada da automação
const CT_CADEIA = [
  { tipo: 'gatilho' },
  { tipo: 'agente', ref: 'cacador' },
  { tipo: 'agente', ref: 'validador' },
  { tipo: 'agente', ref: 'redator' },
  { tipo: 'agente', ref: 'revisor' },
  { tipo: 'portao', label: 'Aprovação' },
  { tipo: 'agente', ref: 'publicador' },
  { tipo: 'fim', label: 'Fim' },
];

// Execuções
const CT_RUNS = [
  {
    id: '#b3c1d9', estado: 'concluida', quando: 'Hoje, 09:12', dur: '1min 18s', custo: '~US$ 0.31', entrada: 'execute um ciclo de testes',
    passos: [
      { ref: 'cacador', estado: 'ok', dur: '8.7s', tokens: '2.811', saida: 'Pauta: "Como o fluxo de caixa projetado revela problemas antes do balanço".' },
      { ref: 'validador', estado: 'ok', dur: '9.4s', tokens: '0.998', saida: 'Pauta aprovada — tema pertinente e com fôlego.' },
      { ref: 'redator', estado: 'ok', dur: '40.1s', tokens: '3.690', saida: 'Artigo de 1.040 palavras, com título e intertítulos.' },
      { ref: 'revisor', estado: 'ok', dur: '12.2s', tokens: '1.420', gate: { resolvido: true, decisao: 'Aprovado', por: 'luregpt' }, saida: 'Artigo revisado, meta e palavra-chave definidas.' },
      { ref: 'publicador', estado: 'ok', dur: '4.1s', tokens: '0.880', saida: 'Rascunho criado no WordPress.' },
    ],
    uso: '4.230 entrada + 3.466 saída tokens · ~US$ 0.31 · Consultoria (.env legado)',
  },
  {
    id: '#f6267b', estado: 'falhou', quando: '08 de jun., 15:09', dur: '1min 02s', custo: '~US$ 0.2411', entrada: 'execute um ciclo de testes',
    passos: [
      { ref: 'cacador', estado: 'ok', dur: '9.2s', tokens: '2.905', saida: 'Pauta proposta sobre indicadores de controladoria.' },
      { ref: 'validador', estado: 'ok', dur: '10.2s', tokens: '1.016', saida: 'Pauta aprovada.' },
      { ref: 'redator', estado: 'ok', dur: '42.5s', tokens: '3.775', saida: 'Artigo redigido.' },
      { tipo: 'falha', estado: 'falhou', titulo: 'Falhou', erro: "O instrumento 'Publicar no WordPress (rascunho)' falhou: não foi possível publicar no WordPress: Request URL is missing an 'http://' or 'https://' protocol." },
    ],
    uso: '4.230 entrada + 3.466 saída tokens · ~US$ 0.2411 · Consultoria (.env legado)',
  },
  {
    id: '#a7e0c2', estado: 'aguardando_humano', quando: '07 de jun., 11:30', dur: '— em pausa', custo: '~US$ 0.19', entrada: 'execute um ciclo de testes',
    passos: [
      { ref: 'cacador', estado: 'ok', dur: '8.9s', tokens: '2.740', saida: 'Pauta sobre conciliação contábil.' },
      { ref: 'validador', estado: 'ok', dur: '9.1s', tokens: '0.970', saida: 'Pauta aprovada.' },
      { ref: 'redator', estado: 'ok', dur: '39.8s', tokens: '3.510', saida: 'Artigo redigido.' },
      { ref: 'revisor', estado: 'aguardando', dur: '11.0s', tokens: '1.300', gate: { resolvido: false }, saida: 'Artigo revisado — aguardando sua aprovação para publicar.' },
      { ref: 'publicador', estado: 'pendente' },
    ],
    artigo: { titulo: 'Conciliação contábil sem dor de cabeça: um roteiro prático', meta: 'Passo a passo para fechar o mês sem surpresas — e o que automatizar primeiro.', palavras: 1040, categoria: 'Controladoria' },
    uso: 'parcial · ~US$ 0.19 até agora',
  },
];

// Conversas (canal do time — dados do screenshot real, Telegram)
const CT_CONVERSAS_STATS = { total: 6, andamento: 0, humano: 1, humanoPct: '16,7%', primeira: '9s', custo: '~US$ 0.10' };
const CT_CONVERSAS = [
  { id: 'c1', contato: 'Julio Franco', canal: 'Telegram', estado: 'fechada', turnos: 8, quando: '16/06/2026, 00:31:08', humano: false,
    thread: [
      { de: 'contato', txt: 'Boa noite! Vocês fazem implantação de controladoria pra empresa pequena?', hora: '00:24' },
      { de: 'ia', txt: 'Boa noite, Julio! Fazemos sim — temos um pacote de implantação pensado pra PMEs. Posso te explicar como funciona?', hora: '00:24' },
      { de: 'contato', txt: 'Pode. Quanto tempo leva?', hora: '00:26' },
      { de: 'ia', txt: 'Em média de 6 a 8 semanas, dependendo da maturidade dos controles atuais. Começamos com um diagnóstico de 1 semana. Quer que eu agende uma conversa com um consultor?', hora: '00:27' },
      { de: 'contato', txt: 'Quero sim', hora: '00:30' },
      { de: 'ia', txt: 'Perfeito! Vou te passar para o time comercial agendar. Obrigado, Julio 👋', hora: '00:31' },
    ] },
  { id: 'c2', contato: 'Julio Franco', canal: 'Telegram', estado: 'fechada', turnos: 3, quando: '14/06/2026, 14:40:21', humano: true,
    thread: [
      { de: 'contato', txt: 'Preciso falar com uma pessoa, é sobre um contrato em andamento', hora: '14:38' },
      { de: 'ia', txt: 'Claro, Julio. Esse assunto é melhor com um humano — já estou chamando alguém do time. Um instante.', hora: '14:38' },
      { de: 'sistema', txt: 'Conversa transferida para atendimento humano', hora: '14:39' },
    ] },
  { id: 'c3', contato: 'Julio Franco', canal: 'Telegram', estado: 'fechada', turnos: 5, quando: '14/06/2026, 13:41:16', humano: false, thread: [] },
  { id: 'c4', contato: 'Julio Franco', canal: 'Telegram', estado: 'fechada', turnos: 1, quando: '14/06/2026, 13:34:16', humano: false, thread: [] },
  { id: 'c5', contato: 'Julio Franco', canal: 'Telegram', estado: 'fechada', turnos: 2, quando: '14/06/2026, 13:27:48', humano: false, thread: [] },
  { id: 'c6', contato: 'Julio Franco', canal: 'Telegram', estado: 'fechada', turnos: 5, quando: '14/06/2026, 12:38:36', humano: false, thread: [] },
];

const MODELOS = ['claude-haiku-4-5', 'claude-sonnet-4-6', 'claude-opus-4-8'];

Object.assign(window, { ORG, USER, TEAMS_SIDEBAR, CT, CT_CADEIA, CT_RUNS, CT_CONVERSAS, CT_CONVERSAS_STATS, MODELOS });
