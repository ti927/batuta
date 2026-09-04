# Batuta — Definição do Produto

Este documento descreve **o que o Batuta é** e **como ele se comporta**, pela ótica de quem usa e de quem opera o negócio. Não trata de arquitetura, tecnologia nem plano de construção — esses vêm depois, em documentos próprios, e derivam deste.

É a fundação. Qualquer decisão técnica futura deve servir ao que está descrito aqui. Se algo neste documento for impossível ou caro de construir, a conversa é mudar o produto conscientemente — não ignorar o documento.

**Versão:** 1.0
**Última atualização:** maio de 2026

---

# PARTE I — O QUE É O BATUTA

## 1. Em uma frase

O Batuta é uma plataforma onde uma pessoa cria **times de agentes de IA** que executam tarefas reais de uma empresa — atender clientes, processar documentos, lançar dados em sistemas, produzir conteúdo — encadeando agentes em fluxos que vão de 3 a 15 passos, sem que quem cria precise programar.

## 2. A metáfora

O usuário é o **maestro**: ele rege, decide, conduz. Os agentes de IA são a **orquestra**: executam. O Batuta é o instrumento que faz a regência acontecer. Tagline: "Você guia. A IA executa."

## 3. O princípio que não pode ser violado

**Simples, mas que pode ser complexo.**

O Batuta precisa servir tanto a uma tarefa de 3 passos quanto a um fluxo industrial de 15 passos. A forma de conseguir isso **sem virar um instrumento de programador** é uma só, e é a decisão de design mais importante do produto:

> A flexibilidade vem de **compor peças prontas**, não de configurar tudo do zero.

O usuário nunca programa uma peça. Ele pega uma peça pronta e sólida (um tipo de agente, um instrumento), preenche o que ela pede, e encaixa com as outras. A complexidade está em **quantas peças e em que ordem** — não na dificuldade de cada peça. Um fluxo de 15 passos é só 15 peças simples encaixadas.

Toda vez que uma decisão de produto ameaçar esse princípio — exigir que o usuário "configure", "programe", "escreva código", "entenda de API" — ela está errada e precisa ser repensada. É esse princípio que separa o Batuta de ser mais um instrumento poderoso que o leigo não usa.

## 4. Quem usa

> **Atualização (MIGRACAO.md, Virada 1):** o Batuta passou a ser **ferramenta interna da consultoria Lure**, não um SaaS público. Os consultores da Lure o usam para padronizar e automatizar processos nos clientes que atendem.

O Batuta continua servindo empresas de qualquer porte e ramo — de microempresa a indústria, hospital, escola —, mas **via a consultoria**. O que muda entre elas não é o produto, é a **composição**: mais agentes, encadeados diferente.

O operador principal é o **consultor da Lure** (perfil técnico-de-domínio, não um leigo total). Do lado do cliente, as pessoas entram em **papéis restritos** — admin, operador, observador (ver §28). Ainda assim, toda a experiência é em português e sem jargão gratuito.

---

# PARTE II — A ANATOMIA: AS PEÇAS DO BATUTA

O Batuta é feito de peças que se contêm umas às outras. Esta é a estrutura.

## 5. Hierarquia geral

```
Usuário
└── Organização (a empresa)
    └── Time de agentes
        ├── Biblioteca (o "segundo cérebro" do time)
        ├── Líder (um por time)
        └── Agentes (quantos forem necessários)
```

## 6. Usuário

Uma pessoa com conta no Batuta. Um usuário pode criar organizações ou ser convidado para organizações de outras pessoas.

## 7. Organização

Representa a empresa. É o espaço onde tudo daquela empresa vive. Um usuário cria uma organização (e a administra) ou é convidado para uma. Uma organização contém times.

## 8. Time de agentes

A unidade de trabalho do Batuta. Cada time é montado para resolver um conjunto de tarefas relacionadas — "Time Administrativo", "Time de Blog", "Time de Atendimento".

Regras do time:
- O usuário cria times ou é convidado para times.
- **Isolamento por time:** quem não pertence a um time não enxerga aquele time, nem seus agentes, nem seus dados. Isso vale dentro da mesma organização — o time do RH não vê o time da Manutenção.
- Cada time tem uma biblioteca, um Líder e quantos Agentes forem necessários.
- **O time é um espaço fechado: tudo dele se gerencia dentro da área do próprio time.** Agentes, instrumentos, automações, execuções e a conversa com a IA vivem todos na área daquele time — não há telas soltas, espalhadas, mostrando dados de times por fora. Quem quer mexer num time entra no time.

## 9. Biblioteca (o segundo cérebro do time)

O lugar onde fica a documentação e o conhecimento do time. É uma via de mão dupla:
- Os agentes **consultam** a biblioteca para tomar decisões e responder com base no conhecimento da empresa.
- Os agentes podem **alimentar** a biblioteca com novos aprendizados.

A escrita automática na biblioteca por agentes é um ponto que exige controle de qualidade — ver seção 19 (decisões em aberto).

> **[Nota de implementação 2026-07-26]** A Biblioteca ainda **não foi construída**. A decisão técnica vigente (`docs/BIBLIOTECA-DECISAO.md`, `docs/ARQUITETURA.md §12`) revisou o escopo: a base é **da ORGANIZAÇÃO** (todos os times acessam), **não por time**; e a **v1 é só-leitura** (os agentes consultam — a escrita/"alimentar", a mão dupla, fica para depois, com revisão humana). Este parágrafo descreve a visão original; o escopo da v1 é o do `BIBLIOTECA-DECISAO.md`.

## 10. Líder

Cada time tem exatamente um Líder. Ele é definido por quatro documentos em markdown que o usuário preenche:
- `agent.md` — quem o agente é, o que faz, qual seu papel
- `skill.md` — as habilidades dele
- `tools.md` — os instrumentos do cinto dele
- `soul.md` — a personalidade, o tom, o jeito de se comunicar

Características do Líder:
- É o **único agente com acesso ao WhatsApp**. Cada time tem seu próprio número de WhatsApp; times diferentes, números diferentes.
- É a **ponte entre o fluxo e os humanos**. Ele conduz a conversa: pergunta, espera resposta, retoma, entrega o resultado final.
- Ele recebe a tarefa, aciona a cadeia de Agentes, e devolve a resposta para quem pediu.

> **[Nota de implementação 2026-07-26]** O canal de mensageria virou um **INSTRUMENTO** no cinto do agente (decisão revista — `docs/MENSAGERIA-PLANO.md` e a memória `feedback_canais-sao-instrumentos`), **não** um atributo exclusivo do Líder. E o canal em produção hoje é o **Telegram**; o **WhatsApp** (Fase 2) ainda não foi construído. Onde este documento diz "WhatsApp" (aqui e no gatilho da §12), leia **"canal de mensageria" (Telegram hoje)**.

## 11. Agentes

As peças versáteis e encadeáveis. Cada Agente tem uma função única, definida pelos mesmos markdowns (`agent.md`, `skill.md`, `tools.md`, `soul.md`). Exemplos de Agente: ler documento, chamar uma API, pesquisar um tema, redigir um texto, revisar um texto, lançar dados num sistema.

Cada Agente tem um **cinto de instrumentos** próprio e customizável (ver seção 13). Agentes diferentes têm cintos diferentes — um Agente que gera imagem tem o instrumento de imagem no cinto; um que integra com um ERP tem o instrumento de API no cinto.

Cada Agente pode usar uma **LLM diferente**, escolhida conforme a tarefa — o Agente que só classifica texto pode usar um modelo barato; o que redige um artigo, um modelo mais capaz; o que gera imagem, um modelo de imagem.

> **Nota de implementação (jun/2026):** a seleção de **modelo e provedor** por agente (Claude, OpenAI, Google) é entregue na **Fase 7-A** do `BUILD-PLAN.md`. Até ela, o motor opera só com Anthropic.

## 12. Gatilhos (o que inicia um fluxo)

Todo fluxo começa por um gatilho. O Batuta tem três tipos:

- **Mensagem de WhatsApp recebida** — alguém manda mensagem para o número do time; o Líder recebe.
- **CRON (agendamento)** — em um dia/horário definido, o fluxo dispara sozinho. Ex.: "todo dia 15", "toda segunda às 8h", "todo dia 1º do mês".
- **Webhook de entrada** — um sistema externo (o ERP da empresa, outro app) aciona o Batuta e dispara um fluxo. É o gatilho disparado por uma máquina, não por uma pessoa nem pelo relógio.

## 13. O cinto de instrumentos

Um **instrumento** é uma capacidade que um agente invoca quando precisa agir ou obter algo do mundo. O agente raciocina; quando precisa fazer algo concreto, usa um instrumento do cinto.

Todos os instrumentos se encaixam no mesmo lugar, da mesma forma. O usuário, ao montar um agente, escolhe quais instrumentos pendurar no cinto dele e preenche a configuração de cada um. Isso é o que dá flexibilidade infinita sem virar caos: cada integração nova é "mais um instrumento no cinto", não um sistema diferente.

Instrumentos previstas:

**De entendimento (já vêm com os modelos de IA — o Batuta só não pode bloquear):**
- Ler imagem
- Ler documento (PDF, etc.)
- Transcrever áudio (cliente manda áudio no WhatsApp → vira texto)

**De ação e dados (construídas como peças plugáveis):**
- Chamar API REST (parametrizada: endereço, autenticação, formato)
- Disparar webhook de saída (avisar outro sistema)
- Conectar com servidor MCP (padrão universal de integração de IA com sistemas)
- Banco de dados direto (ler e escrever em SQL, para sistemas sem API)
- Planilhas (ler `.xlsx`/`.csv` recebidos e gerar planilhas)
- PDFs (gerar documentos — contrato, laudo, relatório, comunicado)
- Busca na web em tempo real (informação atualizada)
- Contas Google / Microsoft / Apple — abrangendo **calendário** (agenda), **email** (enviar/ler) e **arquivos** (Drive/OneDrive)
- Gerar imagem

A forma de cada instrumento — se é um MCP, um plugin, ou uma instrução detalhada no markdown — não importa para o usuário. O que importa é que a possibilidade esteja disponível no cinto. Novos instrumentos entram com o tempo, sempre no mesmo encaixe, sem reescrever o que já existe.

## 14. Como um fluxo se comporta

Um fluxo é o caminho de uma tarefa, do gatilho até a entrega. Comportamentos que o produto precisa ter:

### Encadeamento fixo, desenhado por quem cria o time

O caminho da cadeia é **definido por quem monta o time** — não improvisado pela IA na hora. O usuário desenha: "a tarefa entra no Líder, vai pro Agente A, depois pro B, depois volta pro Líder". A documentação de cada agente diz para onde vai o resultado dele: para outro agente ou para o usuário. Isso torna o fluxo previsível e confiável — o que uma empresa exige de um processo.

> **Como se desenha (UI):** a automação é montada num **construtor visual de grafo** — nós (gatilho, agentes, roteador, fim) ligados por arestas rotuladas, com bifurcações, loops (voltar a um agente anterior), saídas de erro e saídas "se nenhuma". É a forma visual de desenhar o que o motor já executa. Vale para a criação **manual** e para a **IA criadora** (ambas produzem o mesmo fluxo). Especificação em `docs/design_handoff_automacoes_grafo/`; fase no `BUILD-PLAN.md` ("FASE — Automações como GRAFO").

### Espera por humano

Um fluxo precisa saber **pausar, fazer uma pergunta a um humano, e retomar de onde parou** quando a resposta chega — que pode ser minutos ou um dia depois. Esta é a capacidade mais delicada do produto. Ela aparece em três formas:
- **Pergunta pontual** — o agente precisa de uma informação para continuar ("qual cliente/projeto devo lançar?").
- **Pedido de aprovação** — um humano precisa autorizar antes de um passo importante ("posso publicar este artigo?").
- **Confirmação de baixa confiança** — o agente não tem certeza do que entendeu e confirma antes de agir ("li 'R$ 1.500' no recibo — está correto?"), em vez de errar silenciosamente.

> **Estado de implementação:** o motor de pausar/perguntar/retomar está pronto e validado, respondido **na tela do Batuta** e também **pelo canal** (Telegram já no ar; o WhatsApp do Líder, §10, segue na fila da Mensageria). **Quem decide esperar é o próprio agente**, chamando o instrumento *Pedir aprovação e aguardar* porque a documentação dele manda — não há interruptor de aprovação no desenho do fluxo (ver §19). Ao receber a resposta, ele **continua de onde parou**: pode perguntar de volta antes de seguir (ex.: pedir o porquê de uma reprovação) e só então escolher os caminhos. O motor executa; o agente decide.

### Espera por tempo

Um fluxo também precisa saber **esperar o relógio**: publicar o carrossel 24 h depois do story, cobrar um lead 2 dias depois do primeiro contato, reconferir um pedido meia hora depois de enviá-lo.

Isso é um **passo do desenho** ("Esperar", com quantidade e unidade), não um agendamento à parte — e a diferença importa: a execução **para e volta exatamente daquele ponto**, com a ficha inteira. Agendar outro fluxo começaria do zero, sem nada do que já se sabia, e o time teria de redescobrir o próprio trabalho. Enquanto espera, a execução não pede nada de ninguém: ela volta sozinha, e a tela diz quando.

### Bifurcação por intenção

Um fluxo pode ter ramos. Cada seta que sai de um passo carrega uma **condição escrita** ("siga por aqui quando…"), e o agente avalia todas elas — ex.: se a mensagem é sobre agenda, consulta o sistema de agendamento; se é sobre exame, envia as instruções do exame.

**O fluxo segue TODAS as condições atendidas, não uma só.** Se duas setas têm a mesma condição e destinos diferentes, os dois destinos rodam — é assim que uma capa aprovada alimenta o gerador de carrossel **e** o de story na mesma execução. Se dois ramos voltam a se encontrar no mesmo passo, ele roda **uma vez**, recebendo o trabalho dos dois (nada é publicado em dobro). Se nenhuma condição for atendida, aquele ramo termina ali e o motivo fica no rastro — o fluxo nunca escolhe um caminho no escuro.

Além das setas condicionais, um passo pode ter uma seta **"se der erro"** (percorrida quando ele falha, levando a mensagem do erro adiante em vez de derrubar a automação) e uma seta **"se nenhuma das outras"** (a rede de segurança).

### Os dados atravessam o fluxo (a ficha da execução)

Entre um passo e outro trafega o **texto** que o agente produziu. Só isso não basta: se ele resume ("aprovado, seguindo"), tudo o que não repetiu se perde, e o passo seguinte trava pedindo dados que já existiam. Por isso cada execução carrega uma **ficha** — valores com nome que chegam a **todos** os passos:

- **o que o gatilho trouxe**, que entra sozinho e nunca se perde;
- **o que os agentes guardarem** durante o trabalho (uma URL gerada, um total apurado, uma decisão), porque a documentação deles manda guardar.

A ficha destrava duas coisas que a prosa sozinha não dá: uma seta pode ter uma **regra exata** sobre um valor da ficha (`total` está entre `1` e `10`), e aí **quem confere é o sistema, não a IA** — a borda fica certa, sempre; e existe o passo **"Para cada item"**, que percorre uma lista da ficha e repete o trecho seguinte uma vez por item, somando os resultados de volta.

A ficha é deliberadamente um punhado de valores nomeados, **não** um pipeline de dados tipado com mapeamento de campos. Quem conduz o trabalho continua sendo o agente, lendo e escrevendo em linguagem natural — a ficha só impede que o dado se perca no caminho.

### Modo intermediação

Em vez de resolver a tarefa, o agente atua como **ponte de uma conversa contínua entre duas pessoas** — uma falando pelo WhatsApp (um pai, um paciente), outra do lado de dentro do Batuta (uma coordenadora, um atendente). O agente leva a mensagem de um lado a outro, podendo enriquecer ou filtrar, mas a conversa é humano-a-humano intermediada.

## 15. Oito cenários reais que o produto precisa atender

Estes cenários foram levantados de empresas reais e são o teste de validação do produto. Qualquer mudança no produto deve continuar atendendo todos eles.

1. **Reembolso (consultoria):** consultor manda foto de recibo no WhatsApp → Líder identifica o consultor pelo telefone → Agente lê o recibo → Líder devolve os dados e pergunta cliente/projeto → consultor responde → Agente de API lança no sistema → Líder confirma.

2. **Nota fiscal mensal (consultoria):** todo dia 15, o consultor envia sua nota → Líder lê, identifica que é a nota do mês, confirma → Agente de API lança no sistema.

3. **Blog SEO (marketing):** um CRON por dia da semana dispara → Agente idealizador pesquisa e cria o tema → Agente redator escreve → Agente revisor humaniza → Líder envia para aprovação por WhatsApp → recebida a aprovação → Agente de API publica no blog com as variáveis de SEO.

4. **Lembrete mensal (controladoria):** todo dia 1º, um CRON envia uma mensagem simples de lembrete a um número. Sem cadeia — o produto serve o caso trivial sem obrigar a montar agentes.

5. **Checkpoints industriais (indústria):** cadeia de checkpoints com escrita humana em papel → Agente lê os registros → na ponta, Agente de API lança no ERP. Quando a leitura é incerta (letra ilegível), o agente confirma com o humano em vez de adivinhar.

6. **Agendamento (hospital/consultório):** paciente pergunta sobre agenda no WhatsApp → Agente consulta o banco/API → Líder responde com datas e horários e grava o agendamento. Se for sobre exame, o fluxo bifurca e envia as instruções do exame.

7. **Atendimento escolar (escola):** pai/aluno tira dúvida no WhatsApp → se é dúvida respondível por consulta ao ERP, o agente consulta e responde → se é conversa de verdade, entra o modo intermediação: o agente faz a ponte entre o pai e a coordenadora.

8. **Comando externo (geral):** um sistema da empresa aciona o Batuta por webhook de entrada, ou um agente envia comando para fora via webhook/MCP — o Batuta troca comandos com outros aplicativos da empresa nos dois sentidos.

---

# PARTE III — QUANDO AS COISAS DÃO ERRADO

Esta parte é tão importante quanto a anatomia. É o que separa um software que demonstra bem de um software que aguenta um cliente real todos os dias. Estas não são funcionalidades para depois — são **decisões de design** que a arquitetura precisa respeitar desde o início, porque consertá-las depois significa reescrever.

## 16. Falha de um instrumento

Um instrumento vai falhar às vezes: a API do cliente caiu, o ERP não respondeu, a internet oscilou, a chave de API expirou. O fluxo trava no meio. O produto precisa ter uma resposta definida:
- O fluxo tenta de novo? Quantas vezes? Com qual intervalo?
- Se desistir, quem é avisado, e como?
- O fluxo nunca pode "morrer em silêncio". Uma falha sempre resulta em alguém sabendo que falhou.

**E falhar todo dia é pior que falhar uma vez.** Uma automação que dispara sozinha e falha **três vezes seguidas** é **desligada** pelo Batuta, com um recado dizendo quantas falhas houve, onde parou a última e o que fazer. Sem isso, uma chave vencida faria o fluxo disparar diariamente, queimando dinheiro e enchendo o canal de avisos iguais — ou, se ninguém abrisse os avisos, falhando em silêncio, que é justamente o que esta seção proíbe.

Duas coisas **não** contam para esse desligamento, e o motivo é o mesmo — não punir quem não errou: um disparo **manual** (quem clicou está olhando a tela e vê a falha na hora) e uma interrupção causada pelo **próprio Batuta** (uma atualização do sistema, por exemplo). Religar a automação devolve as três chances.

**Depois da falha, o trabalho bom não se joga fora.** Quando um fluxo longo morre perto do fim, dá para **rodar de novo a partir do passo que quebrou** — nasce uma execução nova começando ali, com a mesma entrada e a mesma ficha, sem repetir (nem pagar) tudo o que já tinha dado certo. E, ao ajustar um agente, dá para **testar um passo sozinho**, com um texto escrito à mão, em vez de rodar a automação inteira a cada tentativa. Nos dois casos vale a mesma ressalva, dita com todas as letras na tela: os instrumentos são **reais** — repetir um passo que publica publica de novo.

## 17. Espera e feedback de progresso

Uma cadeia de muitos passos pode levar minutos. Quem mandou a mensagem no WhatsApp não pode ficar no silêncio achando que travou. O produto precisa dar sinal de vida — confirmar o recebimento e, em fluxos longos, sinalizar progresso. Um fluxo funcionando sem feedback é indistinguível de um fluxo quebrado, aos olhos do cliente.

## 18. Volume e fila

Picos são previsíveis: dia 15 todos os consultores enviam nota ao mesmo tempo; dia 1º todos os clientes enviam dados. O produto precisa aguentar muitas tarefas simultâneas, organizá-las em fila, e processá-las sem perder nenhuma e sem travar.

## 19. Ações irreversíveis

Alguns passos mexem no mundo real de forma que não dá para desfazer: lançar um valor financeiro num ERP, publicar um artigo, enviar um email, fazer um pagamento. O produto precisa de proteção contra erro e contra repetição:
- **A aprovação é do AGENTE, e é uma peça só.** Quem segura uma ação até uma pessoa confirmar é o próprio agente, chamando o instrumento **"Pedir aprovação e aguardar"** porque a documentação dele manda. Ele apresenta o que será feito, a execução **para**, e ele continua quando a resposta chega — pela tela ou pelo canal (Telegram).
- **Não há trava automática nem interruptor no desenho.** Até 2026-08-31 havia **duas** peças que se confundiam: um "portão" (interruptor num nó da automação) e uma "parede" (chave da organização que recusava ativar). As duas foram removidas por decisão do maestro: eram invisíveis para quem usava, se sobrepunham (o mesmo atendimento pedia confirmação duas vezes) e tiravam do agente uma decisão que é dele.
- **A contrapartida, dita com todas as letras: se o agente não chamar o instrumento, o fluxo não para.** A garantia mora no instrumento, não no desenho — foi a escolha feita ao matar o portão. Então a documentação do agente precisa mandar chamá-lo **sem instrução concorrente**: em 2026-09-02, no primeiro disparo agendado depois da mudança, um agente ainda tinha no texto do cinto a ordem antiga ("mande pelo Telegram e espere o #aprovado#"), obedeceu a ela, e a execução terminou sem que ninguém aprovasse — sem publicar, mas também sem esperar. Quem converte um time precisa **apagar a instrução velha**, e o rastro do passo mostra qual instrumento foi de fato acionado.
- **O que merece aprovação** é o passo que **muda o mundo** (escrever/enviar/publicar/apagar); uma **consulta** (ler dados) não. Essa classificação continua derivada do **instrumento + configuração** (numa chamada de API, GET é leitura e dispensa; POST/PUT/DELETE escreve; banco pode ser "somente leitura") e aparece como selo no catálogo — hoje ela governa a **política de falha** (§16) e orienta quem monta o time, em vez de barrar a ativação.
- O sistema não pode executar a mesma ação duas vezes por engano (ex.: lançar o mesmo reembolso em duplicidade).
- Toda ação irreversível fica registrada, para poder ser auditada depois.

## 20. Memória e contexto

Decisão de produto a ser detalhada: até onde o agente lembra. Da conversa de hoje, certamente. Da semana passada? Do mês passado? Memória demais fica cara e confusa; de menos, o agente parece amnésico e frustra o cliente. O produto precisa de uma política clara de memória de conversa, por interlocutor.

## 21. Custo visível

Cada passo de um fluxo é uma chamada de IA paga. Uma cadeia de 15 passos custa 15 vezes. O usuário leigo não tem noção disso. O produto precisa tornar o custo visível — dar uma estimativa de quanto um fluxo custa antes de rodar, e mostrar o consumo real depois (ver seção 24).

Visível não basta quando algo dispara: um fluxo pode ter um **teto de custo por execução** (em dólares) e um **teto de tempo**, por passo e pela execução inteira. Estourou, ele **para** e diz quanto gastou, qual era o limite e o que fazer. Os três nascem **desligados**, de propósito: um limite que o usuário não pediu interromperia trabalho legítimo e lento — gerar um vídeo leva uns 25 minutos — como se fosse defeito. O teto de tempo da execução conta **tempo de trabalho**, não de relógio: uma execução que esperou dois dias por uma aprovação humana não gastou dois dias de trabalho.

## 22. Supervisão e erro do agente

O agente pode responder errado ao cliente final — informar algo incorreto a um pai, a um paciente. O produto precisa permitir que isso seja percebido e corrigido:
- A possibilidade de um humano revisar antes de uma resposta sair (o agente pede aprovação — §19).
- Um histórico de tudo que o agente respondeu, para revisão.

## 23. Dados sensíveis e LGPD

Dados de pacientes, de menores de idade, financeiros — tudo isso trafega pelo Batuta e passa por modelos de IA. Isso traz exigências legais sérias (LGPD). Não é um instrumento nem uma tela — é uma camada que precisa ser respeitada no design inteiro: o que é guardado, por quanto tempo, quem acessa, o que é enviado a terceiros (provedores de IA), e o consentimento de quem usa.

---

# PARTE IV — O LADO ADMINISTRATIVO E DO NEGÓCIO

> **Atualização (MIGRACAO.md §3.4, jun/2026):** com a virada para ferramenta interna da consultoria (não SaaS público), boa parte desta Parte IV foi **reorientada**.
> - **Já em vigor (Fase 6):** §28 (papéis admin/operador/observador) e §31 (auditoria), ambos implementados.
> - **Removidos do escopo** (a cobrança é feita pela consultoria, fora do produto): §24 (BYOK + mensalidade), §27 (planos), §29 (billing), §30 (inadimplência).
> - **Permanecem, adaptados:** §25 (medição agora separada por chave/IA), §26 (cofre de chaves por projeto + chave padrão da consultoria) e §32 (painel vira gestão interna da consultoria) — chegam na Fase 7. §33/§34 viram suporte/onboarding internos + LGPD via contrato.
>
> O texto histórico abaixo é mantido por referência; a fonte da verdade da reorientação é o `MIGRACAO.md`.

O Batuta não é só um instrumento — é um negócio. Esta parte descreve como ele se sustenta e o que precisa ser administrado.

## 24. Modelo de cobrança: BYOK + mensalidade fixa

O modelo é deliberadamente simples.

**BYOK (Bring Your Own Key) — o cliente traz as próprias chaves.** O cliente conecta no Batuta as chaves de API dos provedores de IA dele (OpenAI, Google, Anthropic, etc.) e de seus sistemas. **Sem as chaves do cliente, o Batuta não funciona — ponto.** O Batuta não revende IA, não é intermediário do consumo, não cobra pelo uso de IA. O cliente paga seu consumo de IA diretamente aos provedores.

**Mensalidade fixa de SaaS.** O Batuta cobra um valor fixo, previsível, por **operacionalizar** — prover a plataforma, o orquestrador, a infraestrutura, o suporte. É a única cobrança que o Batuta faz.

Essa decisão elimina, de propósito, toda a complexidade de créditos, recarga, pré/pago, faturamento variável, revenda e margem. O Batuta é um SaaS de mensalidade fixa, simples.

## 25. Medição de uso (informativa, não para cobrança)

Mesmo sem cobrar pelo uso, o Batuta **conta o uso** — porque o cliente precisa de transparência para se controlar e entender a própria conta com os provedores.

Cada chamada de LLM, de API e de instrumento é contabilizada: qual agente, qual modelo, quantos tokens de entrada e saída. O Batuta exibe ao cliente:
- Quanto cada LLM consumiu (por time, por agente, por período).
- Um **custo aproximado estimado** desse consumo.

Isso é uma tela de transparência. Não está ligada a nenhuma cobrança do Batuta.

## 26. Cofre de chaves e segredos

O coração do modelo BYOK. As chaves de IA do cliente, e as credenciais dos instrumentos (acesso a ERP, banco de dados, contas Google/MS/Apple), são segredos críticos. O produto precisa:
- Guardá-las criptografadas.
- Nunca reexibi-las depois de salvas.
- Nunca deixá-las aparecer em logs, telas de erro, ou qualquer lugar.
Como tudo no Batuta depende dessas chaves, esta é uma peça central de segurança.

> **Nota de implementação (jun/2026):** as **chaves de IA** entraram no cofre na **Fase 7** e as **credenciais de instrumentos** (senha de app do WordPress, chave Tavily, token de REST/webhook) na **Fase 7-B** — ambas cifradas, por organização, nunca reexibidas. O `.env` segue como fallback legado dos instrumentos já configurados.

## 27. Planos da plataforma

A mensalidade fixa tem níveis, definidos por **capacidade do Batuta** (não por consumo de IA): quantidade de organizações, times, agentes, fluxos por mês, membros. Um nível gratuito para experimentar; níveis pagos para escalar. É a receita previsível do negócio.

## 28. Membros e papéis

> **Implementado na Fase 6** (substitui a versão antiga; ver `MIGRACAO.md` §3.7).

**Três papéis, e somente três:**
- **Admin** — poderes plenos: troca chaves de API, convida e desativa usuários, cria e apaga organizações e times, apaga histórico, vê todo o uso e custos.
- **Operador** — o dia a dia: cria e edita Agentes, Instrumentos e Automações; dispara e cancela execuções; arquiva. **Não** troca chaves, **não** convida/desativa, **não** apaga projetos/times nem histórico.
- **Observador** — só vê os projetos a que pertence; **responde portões de aprovação** e perguntas do agente quando o fluxo pausa; não altera nada.

**Princípios:** acesso só por convite (ninguém se autoinscreve); isolamento absoluto entre clientes; permissões por papel, não por usuário; admin pode ser de qualquer origem (garante a autonomia do cliente se o contrato encerrar). **Regra de polegar** para ações novas: destrutiva/sistêmica = admin; operacional = operador; observar = todos. Toda ação sensível é auditada (§31).

## 29. Billing da plataforma

O cliente administra a própria assinatura: ver a fatura, trocar o cartão, mudar de plano, ver o histórico de pagamentos. Autoatendimento, porque é cobrança de valor fixo e simples.

## 30. Inadimplência

Regras claras para quando um cliente para de pagar a mensalidade: o que acontece com os agentes e fluxos dele, se há prazo de tolerância, por quanto tempo os dados são retidos antes de eventual remoção.

## 31. Auditoria

Registro de quem fez o quê e quando: quem criou ou editou um agente, quem rodou um fluxo, quem trocou uma chave de API, quem alterou permissões. Necessário para conformidade e para resolver disputas.

## 32. Painel do operador

A visão de quem é dono do Batuta — separada do painel do cliente. Permite ver todos os clientes, quem está pagando, quem está inadimplente, a saúde geral da plataforma, o uso agregado. Sem isso, o negócio é tocado às cegas.

## 33. Suporte e onboarding

Como o cliente pede ajuda quando trava, e como ele aprende a usar o Batuta. Não é acessório — define se o cliente novo supera a primeira dificuldade ou desiste. Inclui materiais de orientação e um canal de suporte.

## 34. Termos legais

O que o cliente aceita ao se cadastrar: termos de uso, contrato de serviço, política de privacidade. Especialmente sério porque dados de pacientes e de menores de idade trafegam pelo Batuta — esta camada se conecta diretamente à seção 23 (LGPD).

---

# PARTE V — O QUE AINDA PRECISA SER DECIDIDO

Pontos conscientemente em aberto, a resolver antes ou durante o detalhamento técnico:

1. **Roteamento dentro do fluxo** — confirmado que o fluxo é desenhado pelo usuário (fixo). Falta detalhar como o usuário desenha esse caminho na prática, de forma visual e simples.
2. **Escrita na biblioteca pelos agentes** — o agente alimenta o segundo cérebro. Falta decidir: escreve direto, ou um humano revisa antes de o aprendizado virar permanente? A recomendação inicial é exigir revisão, para a base de conhecimento não degradar com o tempo.
3. **Política de memória** (seção 20) — definir o horizonte de memória de conversa por interlocutor.
4. **Profundidade de papéis** (seção 28) — definir o conjunto exato de papéis e o que cada um pode fazer.
5. **Política de retenção de dados** — por quanto tempo o Batuta guarda o conteúdo dos fluxos, mensagens e documentos, ligado à LGPD.

---

# PARTE VI — O QUE NÃO É O BATUTA

Para manter o foco, é útil dizer o que o Batuta não é:

- Não é um instrumento de programador. Se exige programar, o design falhou.
- Não gera áudio (decisão explícita; pode ser reconsiderado no futuro).
- Não é um produto só para microempresa, nem só para grande empresa. Serve a ambas pela composição de peças.
- **Não é um SaaS público** vendido a empresas em geral — é ferramenta interna da consultoria Lure (MIGRACAO §1).
- **Não é um sistema de billing** nem de cobrança recorrente automatizada (a cobrança é da consultoria, fora do produto).
- **Não usa, sob nenhuma circunstância, credenciais de planos Free/Pro/Max** (Claude ou equivalentes) — somente API keys oficiais pagas por uso (MIGRACAO Virada 5).

---

Este documento é a fundação do Batuta. O `DESIGN-SYSTEM.md` descreve a identidade visual; os documentos técnicos (`CLAUDE.md`, `BUILD-PLAN.md`) descreverão como construir — e ambos devem servir ao que está definido aqui.
