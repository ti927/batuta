// RobotFace — o avatar de um agente (handoff de design §6.1).
// Reflete os robôs do mascote: quadrado arredondado, "visor" escuro com dois
// olhos. O líder ganha um pequeno sparkle amarelo no canto. As cores são as do
// mascote; por padrão a cor sai do índice do agente (estável por posição).

const CORES_AGENTE = ["#3DD8C3", "#B19CD9", "#6D4AFF", "#F5C44A"];
const COR_LIDER = "#F5C44A";

export function corDoAgente(indice: number): string {
  return CORES_AGENTE[indice % CORES_AGENTE.length];
}

export function RobotFace({
  size = 40,
  cor,
  indice = 0,
  lider = false,
}: {
  size?: number;
  cor?: string;
  indice?: number;
  lider?: boolean;
}) {
  const fundo = cor ?? (lider ? COR_LIDER : corDoAgente(indice));
  const visorW = size * 0.6;
  const visorH = size * 0.44;
  const olho = size * 0.12;
  const gap = size * 0.12;

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center"
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.32,
        background: fundo,
        boxShadow: "inset 0 -2px 4px rgba(20,16,40,.18)",
      }}
      aria-hidden="true"
    >
      <span
        className="flex items-center justify-center"
        style={{
          width: visorW,
          height: visorH,
          borderRadius: size * 0.16,
          background: "rgba(20,16,40,.85)",
          gap,
        }}
      >
        <span
          style={{ width: olho, height: olho, borderRadius: "50%", background: "#fff" }}
        />
        <span
          style={{ width: olho, height: olho, borderRadius: "50%", background: "#fff" }}
        />
      </span>
      {lider && (
        <svg
          viewBox="0 0 24 24"
          style={{
            position: "absolute",
            top: -size * 0.12,
            right: -size * 0.12,
            width: size * 0.4,
            height: size * 0.4,
          }}
        >
          <path
            d="M12 2l1.9 5.2L19 9l-5.1 1.8L12 16l-1.9-5.2L5 9l5.1-1.8z"
            fill="#F5C44A"
            stroke="#1A1730"
            strokeWidth="1.2"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </span>
  );
}
