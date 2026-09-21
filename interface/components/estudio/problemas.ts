// O DESENHO SE CONFERE — a leitura do grafo que a tela faz antes de o motor rodar.
//
// Sistemas profissionais de grafo (n8n, Node-RED, Blueprints) têm um "compilador" que
// lê o desenho e aponta o que está errado ANTES de rodar. O Batuta não tinha: o
// desenho só era conferido no `salvar`, pelo cérebro, e só nos erros que barram — o
// resto (fio que nunca vai ser tomado, passo inalcançável, laço sem escape) só
// aparecia como caos em produção, horas depois. Este módulo é esse compilador.
//
// Duas famílias:
//   `erro`  — o cérebro RECUSA salvar. Espelho fiel de `cadeia.py::validar_cadeia`.
//             Mudou lá? muda aqui, senão a tela promete um salvamento que não acontece.
//   `aviso` — salva e roda, mas provavelmente não faz o que a pessoa quis. É aqui que
//             mora a lição de 2026-09-21: o fluxo não quebrou, ele seguiu por um fio
//             que ninguém ia tomar.
//
// Função pura, sem React: dá para testar sozinha e para reusar em outra tela.

import type { Agente, Cadeia, Instrumento, NoCadeia, SaidaCadeia } from "@/lib/api";

export type NivelProblema = "erro" | "aviso";

export type Problema = {
  /** Estável por (nó, saída, regra) — serve de `key` e de âncora da seleção. */
  id: string;
  nivel: NivelProblema;
  /** Nó a que o problema pertence (o painel destaca e a lista centraliza nele). */
  noId?: string;
  /** Saída, quando o problema é de um fio específico. */
  saidaId?: string;
  /** Uma frase, em português, dizendo O QUE está errado. */
  titulo: string;
  /** Uma frase dizendo O QUE FAZER. Nunca um código, nunca um "verifique". */
  comoResolver: string;
};

/** O papel de uma saída, com o padrão do motor (`condicional`). */
export function papel(sa: SaidaCadeia): "condicional" | "erro" | "senao" {
  return sa.tipo === "erro" || sa.tipo === "senao" ? sa.tipo : "condicional";
}

/** Nome humano de um nó — o mesmo que aparece no cartão do canvas. */
export function nomeDoNo(no: NoCadeia | undefined, agentes: Agente[]): string {
  if (!no) return "(passo removido)";
  switch (no.tipo) {
    case "gatilho":
      return "Gatilho";
    case "fim":
      return "Fim";
    case "agente":
      return agentes.find((a) => a.id === no.ref)?.nome ?? "Agente sem dono";
    case "roteador":
      return no.nome || "Decisão";
    case "cada":
      return no.lista ? `Para cada ${no.lista}` : "Para cada item";
    case "esperar":
      return "Esperar";
    case "chamar":
      return no.nome || "Chamar automação";
    default:
      return no.id;
  }
}

/** Texto inteiro do agente (os quatro markdowns), em minúsculas, para busca. */
function textoDoAgente(ag: Agente | undefined): string {
  if (!ag) return "";
  return [ag.agent_md, ag.skill_md, ag.tools_md, ag.soul_md]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
}

/** Alcançáveis a partir de um ponto, andando pelas saídas. */
function alcancaveis(inicio: string | undefined, saidasDe: Map<string, string[]>): Set<string> {
  const vistos = new Set<string>();
  if (!inicio) return vistos;
  const fila = [inicio];
  while (fila.length) {
    const atual = fila.shift()!;
    if (vistos.has(atual)) continue;
    vistos.add(atual);
    for (const d of saidasDe.get(atual) ?? []) if (!vistos.has(d)) fila.push(d);
  }
  return vistos;
}

export type ContextoAnalise = {
  cadeia: Cadeia;
  agentes: Agente[];
  /** Cinto de cada agente, por id do agente — de onde sai "este passo espera alguém". */
  cintos: Record<string, Instrumento[]>;
  /** Automações da organização — para saber se o alvo de um `chamar` ainda existe. */
  automacoes?: { id: string; nome: string }[];
};

export function analisar({
  cadeia,
  agentes,
  cintos,
  automacoes = [],
}: ContextoAnalise): Problema[] {
  const p: Problema[] = [];
  const nos = cadeia.nos ?? [];
  if (!nos.length) return p;

  const idsNos = new Set(nos.map((n) => n.id));
  const idsAgentes = new Set(agentes.map((a) => a.id));
  const porId = new Map(nos.map((n) => [n.id, n]));
  const nome = (id: string | undefined) => nomeDoNo(id ? porId.get(id) : undefined, agentes);
  const noFim = nos.find((n) => n.tipo === "fim");

  const saidasDe = new Map<string, string[]>(
    nos.map((n) => [n.id, (n.saidas ?? []).map((s) => s.destino).filter((d) => idsNos.has(d))]),
  );

  const executaveis = nos.filter((n) => n.tipo === "agente" || n.tipo === "roteador");

  // ── 1. O início ────────────────────────────────────────────────────────────
  // Rascunho (só gatilho e fim) é legítimo: o cérebro também deixa salvar.
  if (executaveis.length) {
    const inicial = cadeia.inicial ? porId.get(cadeia.inicial) : undefined;
    if (!inicial || (inicial.tipo !== "agente" && inicial.tipo !== "roteador")) {
      p.push({
        id: "sem-inicio",
        nivel: "erro",
        noId: nos.find((n) => n.tipo === "gatilho")?.id,
        titulo: "O fluxo não tem por onde começar.",
        comoResolver:
          "Ligue o fio do Gatilho ao primeiro passo — ou abra o Gatilho e escolha em “Começa em”.",
      });
    }
  }

  // ── 2. Cada nó, por dentro ────────────────────────────────────────────────
  for (const no of nos) {
    const saidas = no.saidas ?? [];
    const quem = nome(no.id);

    if (no.tipo === "agente") {
      if (!no.ref || !idsAgentes.has(no.ref)) {
        p.push({
          id: `${no.id}:agente-fora`,
          nivel: "erro",
          noId: no.id,
          titulo: "Este passo aponta para um agente que não está mais no time.",
          comoResolver: "Escolha outro agente no painel da direita, ou apague o passo.",
        });
      }
    }

    if (no.tipo === "cada" && !(no.lista ?? "").trim()) {
      p.push({
        id: `${no.id}:cada-sem-lista`,
        nivel: "erro",
        noId: no.id,
        titulo: "“Para cada item” não diz de QUAL lista.",
        comoResolver:
          "Escreva o nome do campo da ficha que guarda a lista — o mesmo nome que um passo anterior guardou com “anotar”.",
      });
    }

    if (no.tipo === "chamar") {
      const alvo = (no.chamar?.automacao_id ?? "").trim();
      if (!alvo) {
        p.push({
          id: `${no.id}:chamar-sem-alvo`,
          nivel: "erro",
          noId: no.id,
          titulo: "“Chamar outra automação” não diz QUAL automação.",
          comoResolver: "Escolha a automação no painel da direita.",
        });
      } else if (automacoes.length && !automacoes.some((a) => a.id === alvo)) {
        p.push({
          id: `${no.id}:chamar-sumiu`,
          nivel: "erro",
          noId: no.id,
          titulo: "A automação que este passo chama não existe mais.",
          comoResolver: "Escolha outra automação — esta foi apagada ou é de outra organização.",
        });
      }
    }

    if (no.tipo === "esperar" && !(Number(no.espera?.quanto ?? 0) > 0)) {
      p.push({
        id: `${no.id}:espera-zero`,
        nivel: "aviso",
        noId: no.id,
        titulo: "Este “Esperar” não tem tempo definido — na prática ele não espera nada.",
        comoResolver: "Diga quanto tempo o fluxo fica parado aqui.",
      });
    }

    // rótulos: obrigatórios e únicos por nó (o motor identifica o caminho por eles)
    const vistos = new Set<string>();
    for (const sa of saidas) {
      const rot = (sa.rotulo ?? "").trim();
      if (!rot) {
        p.push({
          id: `${no.id}:${sa.id}:sem-rotulo`,
          nivel: "erro",
          noId: no.id,
          saidaId: sa.id,
          titulo: `Um dos caminhos de “${quem}” está sem nome.`,
          comoResolver: "Dê um nome curto ao caminho — é por ele que o agente declara por onde seguiu.",
        });
      } else if (vistos.has(rot)) {
        p.push({
          id: `${no.id}:${sa.id}:rotulo-repetido`,
          nivel: "erro",
          noId: no.id,
          saidaId: sa.id,
          titulo: `“${quem}” tem dois caminhos com o mesmo nome (“${rot}”).`,
          comoResolver:
            "Renomeie um deles. Com nomes iguais, não há como o agente dizer por qual dos dois seguiu.",
        });
      }
      if (rot) vistos.add(rot);

      if (!idsNos.has(sa.destino)) {
        p.push({
          id: `${no.id}:${sa.id}:destino-morto`,
          nivel: "erro",
          noId: no.id,
          saidaId: sa.id,
          titulo: `O caminho “${rot || "sem nome"}” de “${quem}” não chega a lugar nenhum.`,
          comoResolver: "O passo de destino foi apagado. Ligue este fio a outro passo.",
        });
      }

      if (sa.regra && !(sa.regra.campo ?? "").trim()) {
        p.push({
          id: `${no.id}:${sa.id}:regra-sem-campo`,
          nivel: "aviso",
          noId: no.id,
          saidaId: sa.id,
          titulo: `A regra exata de “${rot || "um caminho"}” não diz qual campo conferir.`,
          comoResolver: "Escreva o nome do campo da ficha, ou remova a regra.",
        });
      }
    }

    const condicionais = saidas.filter((s) => papel(s) === "condicional");
    const senoes = saidas.filter((s) => papel(s) === "senao");

    // A CONDIÇÃO é obrigatória quando o passo bifurca — é a frase que o agente lê.
    if ((no.tipo === "agente" || no.tipo === "roteador") && condicionais.length >= 2) {
      for (const sa of condicionais) {
        if (!(sa.quando ?? "").trim()) {
          p.push({
            id: `${no.id}:${sa.id}:sem-quando`,
            nivel: "erro",
            noId: no.id,
            saidaId: sa.id,
            titulo: `“${quem}” bifurca, mas o caminho “${sa.rotulo || "sem nome"}” não diz QUANDO seguir por ele.`,
            comoResolver:
              "Preencha “Siga por aqui quando…”. É essa frase — e só ela — que o agente lê para escolher.",
          });
        }
      }
    }

    if (senoes.length > 1) {
      p.push({
        id: `${no.id}:dois-senoes`,
        nivel: "aviso",
        noId: no.id,
        titulo: `“${quem}” tem dois caminhos “se nenhuma”.`,
        comoResolver: "Deixe só um — o segundo faz o fluxo abrir em dois quando nada for atendido.",
      });
    }
    if (senoes.length && !condicionais.length) {
      p.push({
        id: `${no.id}:senao-sozinho`,
        nivel: "aviso",
        noId: no.id,
        saidaId: senoes[0].id,
        titulo: `O caminho “se nenhuma” de “${quem}” é o único que existe.`,
        comoResolver:
          "Sem condições acima dele, ele é sempre percorrido. Transforme-o num caminho normal.",
      });
    }

    // Passo que não leva a lugar nenhum: o fluxo morre aqui, em silêncio.
    if (no.tipo !== "fim" && no.tipo !== "gatilho" && !saidas.length) {
      p.push({
        id: `${no.id}:beco`,
        nivel: "aviso",
        noId: no.id,
        titulo: `“${quem}” não tem saída — o fluxo termina aqui, sem passar pelo Fim.`,
        comoResolver: "Puxe um fio da direita do cartão até o próximo passo (ou até o Fim).",
      });
    }
  }

  // ── 3. O que o CINTO diz e o desenho não ──────────────────────────────────
  // Passo que espera uma pessoa é o que tem `pedir_aprovacao` no cinto (a mesma regra
  // do motor, em `agente.py::_espera_uma_pessoa`). Se ele espera e só tem UM caminho,
  // aprovar e reprovar levam ao mesmo lugar — foi exatamente o caos de 21/09.
  for (const no of nos) {
    if (no.tipo !== "agente" || !no.ref) continue;
    const ag = agentes.find((a) => a.id === no.ref);
    const cinto = cintos[no.ref] ?? [];
    const esperaPessoa = cinto.some((i) => i.tipo === "pedir_aprovacao");
    const saidas = no.saidas ?? [];
    const condicionais = saidas.filter((s) => papel(s) === "condicional");
    const quem = nome(no.id);

    if (esperaPessoa && condicionais.length < 2) {
      p.push({
        id: `${no.id}:aprova-sem-bifurcar`,
        nivel: "aviso",
        noId: no.id,
        titulo: `“${quem}” para e pergunta a uma pessoa, mas o desenho tem um caminho só.`,
        comoResolver:
          "Aprovar e reprovar vão dar no mesmo lugar. Desenhe dois caminhos: um para quando aprovarem, outro para quando pedirem ajuste.",
      });
    }

    if (!esperaPessoa) {
      // Fio que fala de aprovação num agente que não tem como perguntar a ninguém.
      const fala = saidas.find((s) =>
        /aprov|reprov|revis|ajust/i.test(`${s.rotulo ?? ""} ${s.quando ?? ""}`),
      );
      if (fala) {
        p.push({
          id: `${no.id}:${fala.id}:aprova-sem-instrumento`,
          nivel: "aviso",
          noId: no.id,
          saidaId: fala.id,
          titulo: `O caminho “${fala.rotulo}” fala de aprovação, mas “${quem}” não tem o instrumento de pedir aprovação.`,
          comoResolver:
            "Ninguém vai ser perguntado: o agente decide sozinho. Pendure “Pedir aprovação” no cinto dele, ou renomeie o caminho.",
        });
      }
    }

    // O FIO QUE NUNCA VAI SER TOMADO: o agente escolhe declarando o NOME do caminho.
    // Se o nome não aparece em lugar nenhum do texto dele, ele não tem como saber que
    // aquele caminho existe — é o `arprovado` que ficou um mês sem ninguém ver.
    if (condicionais.length >= 2 && ag) {
      const texto = textoDoAgente(ag);
      if (texto.length > 40) {
        for (const sa of condicionais) {
          const rot = (sa.rotulo ?? "").trim().toLowerCase();
          if (rot.length >= 4 && !texto.includes(rot)) {
            p.push({
              id: `${no.id}:${sa.id}:rotulo-nao-citado`,
              nivel: "aviso",
              noId: no.id,
              saidaId: sa.id,
              // Dizer "o texto do agente" não ajuda ninguém: o agente tem QUATRO
              // textos. A frase precisa dizer onde se procurou e onde escrever.
              titulo: `A palavra “${sa.rotulo}” não aparece em nenhum dos quatro textos de “${quem}”.`,
              comoResolver:
                `Para seguir por um caminho, o agente escreve o nome dele letra por letra. Abra “${quem}” (o lápis no canto do cartão) e, em “Habilidades”, diga quando ele deve declarar “${sa.rotulo}”. Se lá já houver uma palavra parecida, então é o nome do caminho que está errado — compare as duas.`,
            });
          }
        }
      }
    }
  }

  // ── 4. O grafo inteiro ────────────────────────────────────────────────────
  const gatilho = nos.find((n) => n.tipo === "gatilho");
  const vivos = alcancaveis(gatilho?.id ?? cadeia.inicial, saidasDe);
  for (const no of nos) {
    if (no.tipo === "gatilho" || vivos.has(no.id)) continue;
    // O "fim" solto não é problema enquanto ninguém aponta para ele: já é coberto
    // pelo aviso de "nenhum caminho chega ao Fim".
    if (no.tipo === "fim") continue;
    p.push({
      id: `${no.id}:ilha`,
      nivel: "aviso",
      noId: no.id,
      titulo: `“${nome(no.id)}” está solto: nenhum fio chega até ele.`,
      comoResolver: "Ligue um passo anterior a ele — ou apague-o, se sobrou de um desenho antigo.",
    });
  }

  if (noFim && executaveis.length) {
    const chegamAoFim = new Set<string>();
    // Quem alcança o Fim: caminha ao contrário, do Fim para trás.
    const entram = new Map<string, string[]>();
    for (const no of nos)
      for (const sa of no.saidas ?? [])
        entram.set(sa.destino, [...(entram.get(sa.destino) ?? []), no.id]);
    const fila = [noFim.id];
    while (fila.length) {
      const atual = fila.shift()!;
      if (chegamAoFim.has(atual)) continue;
      chegamAoFim.add(atual);
      for (const anterior of entram.get(atual) ?? []) fila.push(anterior);
    }
    for (const no of nos) {
      if (no.tipo === "gatilho" || no.tipo === "fim") continue;
      if (!vivos.has(no.id) || chegamAoFim.has(no.id)) continue;
      p.push({
        id: `${no.id}:sem-fim`,
        nivel: "aviso",
        noId: no.id,
        titulo: `De “${nome(no.id)}” não há caminho que chegue ao Fim.`,
        comoResolver:
          "O fluxo entra aqui e não sai: ou é um laço sem escape, ou falta um fio. Ligue uma saída daqui em direção ao Fim.",
      });
    }
  }

  // Erros primeiro; dentro do nível, na ordem em que foram achados.
  return [...p.filter((x) => x.nivel === "erro"), ...p.filter((x) => x.nivel === "aviso")];
}

/** Índice {noId: problemas} — o cartão do nó mostra o seu próprio selo. */
export function porNo(problemas: Problema[]): Map<string, Problema[]> {
  const m = new Map<string, Problema[]>();
  for (const pr of problemas) {
    if (!pr.noId) continue;
    m.set(pr.noId, [...(m.get(pr.noId) ?? []), pr]);
  }
  return m;
}

/** Índice {saidaId: problemas} — o fio fica vermelho quando tem um erro seu. */
export function porSaida(problemas: Problema[]): Map<string, Problema[]> {
  const m = new Map<string, Problema[]>();
  for (const pr of problemas) {
    if (!pr.saidaId) continue;
    m.set(pr.saidaId, [...(m.get(pr.saidaId) ?? []), pr]);
  }
  return m;
}
