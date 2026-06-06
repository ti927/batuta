// app-data.jsx — Cenário real: time de Blog SEO da Lure. Agentes, markdowns e roteiro da IA criadora.

const ROBOT = { ciano: '#3DD8C3', lilas: '#B19CD9', roxo: '#6D4AFF', amarelo: '#F5C44A' };

const TEAM = {
  nome: 'Time de Blog SEO',
  org: 'Clínica Aurora', // cliente exemplo da consultoria
  agentes: [
    {
      id: 'lider', nome: 'Líder do time', papel: 'lider', cor: '#F5C44A',
      modelo: 'Claude Haiku', tier: 'rápido',
      resumo: 'Conduz a cadeia e fala com você pelo WhatsApp.',
      instrumentos: [{ nome: 'WhatsApp do time', icon: 'message' }],
      docs: {
        agent: 'Sou o líder do time de Blog SEO. Recebo a largada do gatilho, conduzo a cadeia de ponta a ponta e sou a única ponte entre o time e as pessoas — falo pelo WhatsApp do time.',
        skill: 'Coordenar a sequência de agentes.\nResumir o estado do trabalho de forma curta.\nPedir aprovação de um jeito claro e objetivo.',
        tools: 'WhatsApp do time (número próprio).\nNão executo tarefas pesadas — eu delego e acompanho.',
        soul: 'Cordial, direto e tranquilo. Escrevo como gente, sem jargão. Nunca deixo o maestro no escuro.',
      },
    },
    {
      id: 'news', nome: 'news-to-insight', papel: 'agente', cor: '#3DD8C3',
      modelo: 'Claude Haiku', tier: 'rápido',
      resumo: 'Pesquisa o mercado e transforma em pautas com potencial de busca.',
      instrumentos: [{ nome: 'Busca na web', icon: 'search' }],
      docs: {
        agent: 'Pesquiso o que está acontecendo no mercado e transformo em pautas de blog com potencial de busca.',
        skill: 'Encontrar temas atuais e relevantes.\nAvaliar intenção de busca.\nPropor uma pauta vencedora com um ângulo claro.',
        tools: 'Busca na web em tempo real.',
        soul: 'Curioso e objetivo. Entrego pauta pronta, não fico em devaneio.',
      },
    },
    {
      id: 'curator', nome: 'curator-lure-fit', papel: 'agente', cor: '#B19CD9',
      modelo: 'Claude Sonnet', tier: 'capaz',
      resumo: 'Filtra a pauta pelo que combina com a marca: tom, público e posicionamento.',
      instrumentos: [{ nome: 'Biblioteca do time', icon: 'library' }],
      docs: {
        agent: 'Filtro as pautas pelo que combina com a marca do cliente: tom, público e posicionamento. O que não encaixa, eu corto.',
        skill: 'Avaliar fit editorial.\nAjustar o ângulo pro jeito da marca.\nDefinir a palavra-chave principal.',
        tools: 'Biblioteca do time — o segundo cérebro, onde fica o conhecimento da marca.',
        soul: 'Criterioso e honesto. Prefiro cortar a deixar passar algo morno.',
      },
    },
    {
      id: 'writer', nome: 'lure-writer', papel: 'agente', cor: '#6D4AFF',
      modelo: 'Claude Sonnet', tier: 'capaz',
      resumo: 'Escreve o artigo completo a partir da pauta curada, otimizado pra busca.',
      instrumentos: [{ nome: 'Busca na web', icon: 'search' }],
      docs: {
        agent: 'Escrevo o artigo completo a partir da pauta curada, no estilo da marca e otimizado pra busca.',
        skill: 'Redação longa e fluida.\nSEO on-page (título, intertítulos, meta).\nHumanizar o texto pra não soar robótico.',
        tools: 'Busca na web (pra checar fatos enquanto escrevo).',
        soul: 'Escrevo claro, com personalidade e sem encheção. Português de gente real.',
      },
    },
    {
      id: 'publisher', nome: 'Lure.publisher', papel: 'agente', cor: '#F5C44A',
      modelo: 'Claude Haiku', tier: 'rápido',
      resumo: 'Publica o artigo aprovado no WordPress, com categoria, tags e resumo.',
      instrumentos: [{ nome: 'Publicar no WordPress', icon: 'globe' }, { nome: 'Chamar API REST', icon: 'code' }],
      docs: {
        agent: 'Publico o artigo aprovado no WordPress do cliente, com categoria, tags e resumo prontos.',
        skill: 'Montar o post.\nAplicar as variáveis de SEO.\nPublicar como rascunho ou direto no ar.',
        tools: 'Publicar no WordPress.\nChamar API REST.',
        soul: 'Preciso e cuidadoso. Confiro tudo antes — publicação não se desfaz.',
      },
    },
  ],
  gatilho: { tipo: 'Agendamento', detalhe: 'Toda segunda a sexta, às 8h', icon: 'clock' },
  custo: { porExec: 'R$ 0,38', porMes: '~R$ 8,40 / mês', chamadas: 4 },
};

// Cadeia (grafo do fluxo): a ordem em que a tarefa percorre os agentes
const CADEIA = [
  { tipo: 'gatilho', ref: 'gatilho' },
  { tipo: 'agente', ref: 'lider' },
  { tipo: 'agente', ref: 'news' },
  { tipo: 'agente', ref: 'curator' },
  { tipo: 'agente', ref: 'writer' },
  { tipo: 'portao', label: 'Aprovação pelo WhatsApp' },
  { tipo: 'agente', ref: 'publisher' },
  { tipo: 'fim', label: 'Publicado' },
];

// Roteiro da conversa. Cada beat: fala da IA + efeitos que materializam o rascunho + opções do consultor.
const STEPS = [
  {
    ai: 'Oi! Eu sou a IA criadora da Batuta. Me conta, em poucas palavras, o que esse cliente precisa que aconteça sozinho — eu cuido de montar o time.',
    chips: ['Publicar um artigo de blog otimizado por dia', 'Responder clientes no WhatsApp', 'Lançar notas fiscais no sistema'],
  },
  {
    ai: 'Boa escolha pra começar. Isso é uma sequência clássica: alguém pesquisa o tema, outro cura o que combina com a marca, um escreve, e um publica. Montei um time com um líder e 4 agentes — olha aqui do lado.',
    effects: ['createTeam', 'addAgents'],
    chips: ['Faz sentido. E o gatilho?', 'Quero ver os agentes primeiro'],
  },
  {
    ai: 'O gatilho é o que dá a largada. Pra um blog, o normal é rodar sozinho num horário fixo. Quando você quer que ele publique?',
    chips: ['Toda segunda a sexta, de manhã', 'Todo dia, incluindo fim de semana', 'Eu defino isso depois'],
  },
  {
    ai: 'Fechado — toda segunda a sexta, às 8h da manhã. Adicionei o gatilho de agendamento ao time.',
    effects: ['setTrigger'],
    chips: ['E antes de publicar, tem revisão?', 'Continuar'],
  },
  {
    ai: 'Ótima pergunta — essa é importante. Publicar é uma ação que não dá pra desfazer. Quer aprovar cada artigo pelo WhatsApp antes de ele ir pro ar?',
    chips: ['Sim, quero aprovar pelo WhatsApp', 'Não, pode publicar direto'],
  },
  {
    ai: 'Perfeito. Coloquei um portão de aprovação na cadeia: o líder te manda o rascunho pronto no WhatsApp e só libera a publicação quando você responder. Aqui está a cadeia completa.',
    effects: ['addGate', 'revealCadeia'],
    chips: ['Quanto custa por artigo?', 'Ver a cadeia'],
  },
  {
    ai: 'Cada artigo passa por 4 chamadas de IA. Estimo uns R$ 0,38 por execução — cerca de R$ 8,40 no mês rodando em dia útil. Tudo isso fica medido e visível depois de rodar.',
    effects: ['showCost'],
    chips: ['Pode criar o time', 'Quero revisar os agentes antes'],
  },
  {
    ai: 'Está tudo montado, mas em rascunho — nada existe de verdade ainda. Clica em qualquer agente pra ver os documentos que escrevi pra ele. Quando estiver bom pra você, é só aprovar que eu crio tudo de uma vez.',
    final: true,
  },
];

// ===== Execução para a tela de inspeção (mostra a espera-por-humano) =====
const EXEC = {
  id: '#1284', quando: 'Hoje, 08:00', gatilho: 'Agendamento (seg–sex, 8h)', custoAteAgora: 'R$ 0,29', estado: 'aguardando_humano',
  passos: [
    { tipo: 'gatilho', titulo: 'Gatilho · agendamento', estado: 'ok', dur: '—', detalhe: 'Disparado pelo relógio às 08:00, como todo dia útil.' },
    { ref: 'lider', estado: 'ok', dur: '2s', entrada: 'Largada do agendamento do dia.', saida: 'Acionei o news-to-insight para gerar a pauta de hoje.' },
    { ref: 'news', estado: 'ok', dur: '9s', tokens: '1,2k', entrada: 'Gere a pauta do dia para o blog da Clínica Aurora.', saida: 'Pauta proposta: "Sinais de que sua tireoide pede atenção" — alta intenção de busca, ângulo de prevenção.' },
    { ref: 'curator', estado: 'ok', dur: '14s', tokens: '3,8k', pergunta: { q: 'Posso focar no público feminino de 30 a 50 anos, que é o forte da clínica?', a: 'Pode sim, foca nesse público.' }, entrada: 'Pauta vinda do news-to-insight.', saida: 'Pauta aprovada com ajuste de ângulo. Palavra-chave principal: "sintomas de tireoide".' },
    { ref: 'writer', estado: 'ok', dur: '38s', tokens: '7,1k', entrada: 'Pauta curada + palavra-chave principal.', saida: 'Artigo de 1.180 palavras, com título, intertítulos e meta description prontos.' },
    { tipo: 'portao', estado: 'aguardando', titulo: 'Portão de aprovação', detalhe: 'O líder te mandou o rascunho no WhatsApp e está esperando você liberar antes de publicar.' },
    { ref: 'publisher', estado: 'pendente', entrada: '—', saida: '—' },
    { tipo: 'fim', estado: 'pendente', titulo: 'Publicado no WordPress' },
  ],
  artigo: { titulo: 'Sinais de que sua tireoide pede atenção', meta: '5 sinais que merecem uma consulta — e quando procurar o endocrinologista.', palavras: 1180, categoria: 'Saúde da mulher' },
};

const RECENTES = [
  { id: '#1284', quando: 'Hoje, 08:00', estado: 'aguardando_humano', dur: '1min 03s', custo: 'R$ 0,29' },
  { id: '#1271', quando: 'Ontem, 08:00', estado: 'concluida', dur: '1min 21s', custo: 'R$ 0,38' },
  { id: '#1259', quando: 'Seg, 08:00', estado: 'concluida', dur: '1min 12s', custo: 'R$ 0,36' },
  { id: '#1247', quando: 'Sex, 08:00', estado: 'falhou', dur: '22s', custo: 'R$ 0,08', nota: 'WordPress fora do ar — tentou 2 vezes e avisou no WhatsApp.' },
];

// ===== Roteiro da IA companheira (Virada 3 — memória viva do projeto) =====
const COMPANION_STEPS = [
  {
    ai: 'Oi de novo! Eu acompanho o Time de Blog SEO desde que ele nasceu — sei o que cada agente faz, como foram as execuções e o que vocês decidiram pelo caminho. No que posso ajudar?',
    chips: ['Como foram as últimas execuções?', 'Quero mudar o horário pra 7h', 'Por que a execução de sexta falhou?'],
  },
  {
    ai: 'Nas últimas 5: quatro publicaram sem intercorrência e uma está agora aguardando sua aprovação. Tempo médio de ~1min 15s e custo médio de R$ 0,36 por artigo. A de sexta falhou — quer que eu explique?',
    chips: ['Sim, o que houve na sexta?', 'Quero mudar o horário pra 7h'],
  },
  {
    ai: 'Na sexta o WordPress estava fora do ar. O Lure.publisher tentou duas vezes, esperou e desistiu — e o líder te avisou na hora pelo WhatsApp. Nada foi publicado pela metade. Quando o site voltou já era tarde pra repor no mesmo dia. Posso deixar ele tentar de novo mais tarde, no mesmo dia, se quiser.',
    chips: ['Boa, configura essa nova tentativa', 'Quero mudar o horário pra 7h'],
  },
  {
    ai: 'Sobre o horário: hoje a cadeia dispara às 8h em dias úteis. Posso mudar pra 7h. Já preparei a alteração aqui — é só você confirmar que eu aplico no time.',
    effect: 'proposeChange', final: true,
  },
];

const MEMORIA = {
  estado: ['5 agentes + 1 líder', 'Gatilho: seg–sex, às 8h', 'Cadeia com portão de aprovação'],
  execucoes: ['4 publicadas sem intercorrência', '1 aguardando sua aprovação', 'Custo médio R$ 0,36 / artigo'],
  decisoes: ['Público-alvo: mulheres de 30 a 50 anos', 'Aprovação manual antes de publicar', 'Tom: acolhedor e técnico, sem jargão'],
};

Object.assign(window, { TEAM, CADEIA, STEPS, ROBOT, EXEC, RECENTES, COMPANION_STEPS, MEMORIA });
