// ORGANIZAR SOZINHO — o "auto-layout" que todo editor de grafo profissional tem.
//
// Camadas da esquerda para a direita (Sugiyama enxuto), que é como um fluxo se lê:
//   1. quebra os fios de VOLTA (laços) — senão não existe "esquerda" nem "direita";
//   2. cada passo vai para a coluna do seu antecessor MAIS PROFUNDO (caminho longo),
//      para nenhum fio apontar para trás sem ser um laço de verdade;
//   3. dentro da coluna, ordena pelo centro de massa dos antecessores — é o que
//      desembaraça os cruzamentos sem nenhuma física complicada;
//   4. empilha com a ALTURA MEDIDA de cada cartão (aqui os cartões têm alturas bem
//      diferentes: um agente com seis saídas é o triplo de um "Fim").
//
// Puro: recebe o desenho e as alturas, devolve posições. Não toca em estado nenhum.

import type { Cadeia } from "@/lib/api";

export const LARGURA_NO = 268;
const VAO_X = 110; // espaço entre colunas — cabe a pílula da condição no fio
const VAO_Y = 34; // espaço entre cartões da mesma coluna
const ALTURA_PADRAO = 104; // usado enquanto o cartão ainda não foi medido
const MARGEM_X = 48;
const MARGEM_Y = 40;

export type Posicoes = Record<string, { x: number; y: number }>;

export function arrumar(cadeia: Cadeia, alturas: Record<string, number> = {}): Posicoes {
  const nos = cadeia.nos ?? [];
  if (!nos.length) return {};
  const ids = new Set(nos.map((n) => n.id));
  const destinos = new Map<string, string[]>(
    nos.map((n) => [
      n.id,
      // sem repetição: dois fios para o mesmo passo não devem pesar em dobro
      [...new Set((n.saidas ?? []).map((s) => s.destino).filter((d) => ids.has(d)))],
    ]),
  );

  const raiz =
    nos.find((n) => n.tipo === "gatilho")?.id ??
    (cadeia.inicial && ids.has(cadeia.inicial) ? cadeia.inicial : nos[0].id);

  // ── 1. fios de volta (back edges), achados por DFS com pilha ──
  const volta = new Set<string>(); // "origem>destino"
  const cor = new Map<string, 0 | 1 | 2>(); // 0 não visto · 1 na pilha · 2 fechado
  const visitar = (id: string) => {
    cor.set(id, 1);
    for (const d of destinos.get(id) ?? []) {
      const c = cor.get(d) ?? 0;
      if (c === 1) volta.add(`${id}>${d}`);
      else if (c === 0) visitar(d);
    }
    cor.set(id, 2);
  };
  visitar(raiz);
  for (const n of nos) if (!cor.get(n.id)) visitar(n.id); // ilhas soltas também

  const paraFrente = (id: string) =>
    (destinos.get(id) ?? []).filter((d) => !volta.has(`${id}>${d}`));

  // ── 2. coluna de cada nó: caminho mais LONGO a partir da raiz ──
  const coluna = new Map<string, number>();
  const ordemDescoberta: string[] = [];
  // Kahn: só fixa a coluna de um nó depois que todos os antecessores tiverem a sua.
  const entrada = new Map<string, number>(nos.map((n) => [n.id, 0]));
  for (const n of nos) for (const d of paraFrente(n.id)) entrada.set(d, (entrada.get(d) ?? 0) + 1);

  const semEntrada = nos.filter((n) => (entrada.get(n.id) ?? 0) === 0).map((n) => n.id);
  // a raiz primeiro, sempre — é a coluna zero visual
  const fila = semEntrada.includes(raiz)
    ? [raiz, ...semEntrada.filter((id) => id !== raiz)]
    : semEntrada;
  for (const id of fila) coluna.set(id, 0);
  const pendentes = [...fila];
  while (pendentes.length) {
    const id = pendentes.shift()!;
    ordemDescoberta.push(id);
    const c = coluna.get(id) ?? 0;
    for (const d of paraFrente(id)) {
      coluna.set(d, Math.max(coluna.get(d) ?? 0, c + 1));
      const resta = (entrada.get(d) ?? 1) - 1;
      entrada.set(d, resta);
      if (resta === 0) pendentes.push(d);
    }
  }
  // Ciclo não quebrado por completo (grafo estranho): o que sobrou vai para o fim.
  const maxCol = Math.max(0, ...[...coluna.values()]);
  for (const n of nos)
    if (!coluna.has(n.id)) {
      coluna.set(n.id, maxCol);
      ordemDescoberta.push(n.id);
    }
  // O "Fim" fica sempre na última coluna, mesmo que algum ramo curto chegue antes.
  const idFim = nos.find((n) => n.tipo === "fim")?.id;
  if (idFim) coluna.set(idFim, Math.max(...[...coluna.values()]));

  // ── 3. ordem dentro da coluna: centro de massa dos antecessores ──
  const colunas = new Map<number, string[]>();
  for (const id of ordemDescoberta) {
    const c = coluna.get(id) ?? 0;
    colunas.set(c, [...(colunas.get(c) ?? []), id]);
  }
  const anteriores = new Map<string, string[]>();
  for (const n of nos)
    for (const d of paraFrente(n.id))
      anteriores.set(d, [...(anteriores.get(d) ?? []), n.id]);

  const indice = new Map<string, number>();
  const cs = [...colunas.keys()].sort((a, b) => a - b);
  for (const c of cs) (colunas.get(c) ?? []).forEach((id, i) => indice.set(id, i));
  // duas passadas bastam para desembaraçar os desenhos do tamanho que temos
  for (let passada = 0; passada < 2; passada += 1) {
    for (const c of cs) {
      if (c === cs[0]) continue;
      const lista = [...(colunas.get(c) ?? [])];
      const peso = (id: string) => {
        const ant = (anteriores.get(id) ?? []).map((a) => indice.get(a) ?? 0);
        return ant.length ? ant.reduce((s, v) => s + v, 0) / ant.length : indice.get(id) ?? 0;
      };
      lista.sort((a, b) => peso(a) - peso(b));
      colunas.set(c, lista);
      lista.forEach((id, i) => indice.set(id, i));
    }
  }

  // ── 4. coordenadas, com a altura real de cada cartão ──
  const pos: Posicoes = {};
  const alturaDaColuna = (ids: string[]) =>
    ids.reduce((s, id) => s + (alturas[id] ?? ALTURA_PADRAO) + VAO_Y, -VAO_Y);
  const maiorColuna = Math.max(
    ...cs.map((c) => alturaDaColuna(colunas.get(c) ?? [])),
    0,
  );
  for (const c of cs) {
    const lista = colunas.get(c) ?? [];
    // centraliza a coluna em relação à mais alta: o fluxo fica no eixo, como num
    // organograma, em vez de tudo grudado no topo.
    let y = MARGEM_Y + (maiorColuna - alturaDaColuna(lista)) / 2;
    for (const id of lista) {
      pos[id] = { x: MARGEM_X + c * (LARGURA_NO + VAO_X), y: Math.round(y) };
      y += (alturas[id] ?? ALTURA_PADRAO) + VAO_Y;
    }
  }
  return pos;
}
