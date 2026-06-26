// Constantes legais — fonte ÚNICA usada pelas páginas públicas /privacidade,
// /termos e /exclusao-de-dados (exigidas no App Review da Meta + LGPD).
// Mantenha os dados do controlador aqui; as três páginas leem deste arquivo.

export const PRODUTO = "Batuta";
export const DOMINIO = "batuta.team";
export const URL_BASE = "https://batuta.team";

// Data da última revisão das páginas legais (mostrada no topo de cada uma).
export const ATUALIZADO_EM = "26 de junho de 2026";

// Controlador dos dados pessoais (LGPD, art. 41).
export const CONTROLADOR = {
  razaoSocial: "JMF TREINAMENTOS E CONSULTORIA LTDA - ME",
  cnpj: "56.923.834/0001-23",
  endereco: "Rua 137, nº 556 — Setor Marista, Goiânia/GO, CEP 74170-120",
} as const;

// Encarregado pelo tratamento de dados (DPO) e canal de contato.
export const ENCARREGADO = {
  nome: "Julio Manfrin di Franco",
  email: "ti@lureconsultoria.com.br",
} as const;

// Caminhos das páginas legais (para os links cruzados no rodapé).
export const ROTAS_LEGAIS = [
  { href: "/privacidade", rotulo: "Política de Privacidade" },
  { href: "/termos", rotulo: "Termos de Uso" },
  { href: "/exclusao-de-dados", rotulo: "Exclusão de Dados" },
] as const;
