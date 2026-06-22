"use client";

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Wrench, X } from "lucide-react";

import { buscarExterno, type IconeExterno } from "@/lib/icones-externos";
import { CATALOGO_ICONES } from "@/lib/icones-instrumento";
import { cn } from "@/lib/utils";

// Chaves (prefix:iconName) dos curados — para não repetir, na seção "Mais da
// biblioteca", um ícone que já aparece nos curados.
const CHAVES_CURADAS = new Set(
  CATALOGO_ICONES.map((c) => `${c.icon.prefix}:${c.icon.iconName}`),
);

function Celula({
  selecionada,
  titulo,
  onClick,
  children,
}: {
  selecionada: boolean;
  titulo: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={titulo}
      onClick={onClick}
      className={cn(
        "flex aspect-square items-center justify-center rounded-lg border text-foreground transition-colors",
        selecionada
          ? "border-primary bg-primary/10 text-primary"
          : "border-border bg-card hover:bg-accent/50",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Seletor de ícone do instrumento: dropdown BUSCÁVEL (catálogo Font Awesome
 * curado). Fechado, ocupa só uma linha mostrando o ícone atual; ao clicar/focar,
 * abre a grade e o que se digita filtra por nome/termos. "Sem ícone" limpa para
 * `null` (volta ao genérico Wrench). Fecha ao clicar fora ou apertar Esc.
 */
export function SeletorIcone({
  valor,
  onChange,
}: {
  valor: string | null;
  onChange: (id: string | null) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [extras, setExtras] = useState<IconeExterno[]>([]);
  const [buscandoExtras, setBuscandoExtras] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const termo = busca.trim().toLowerCase();
  const lista = termo
    ? CATALOGO_ICONES.filter(
        (i) => i.nome.toLowerCase().includes(termo) || i.termos.includes(termo),
      )
    : CATALOGO_ICONES;
  const selecionado = valor
    ? (CATALOGO_ICONES.find((i) => i.id === valor) ?? null)
    : null;

  // Busca o RESTO da biblioteca (fora dos curados) sob demanda. Roda no onChange
  // do input (handler de evento), não em efeito — a 1ª busca baixa o registro
  // completo (chunk separado); depois é em memória. O ref descarta resultados de
  // um termo já superado (digitação rápida).
  const ultimoTermo = useRef("");
  function buscarMais(texto: string) {
    const t = texto.trim().toLowerCase();
    ultimoTermo.current = t;
    if (t.length < 2) {
      setExtras([]);
      setBuscandoExtras(false);
      return;
    }
    setBuscandoExtras(true);
    buscarExterno(t).then((achados) => {
      if (ultimoTermo.current !== t) return; // termo já mudou — descarta
      setExtras(achados.filter((e) => !CHAVES_CURADAS.has(e.id)));
      setBuscandoExtras(false);
    });
  }

  // Fecha ao clicar fora ou apertar Esc (só enquanto aberto).
  useEffect(() => {
    if (!aberto) return;
    const aoClicar = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setAberto(false);
    };
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAberto(false);
    };
    document.addEventListener("mousedown", aoClicar);
    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.removeEventListener("mousedown", aoClicar);
      document.removeEventListener("keydown", aoTeclar);
    };
  }, [aberto]);

  function escolher(id: string | null) {
    onChange(id);
    setBusca("");
    setExtras([]);
    setBuscandoExtras(false);
    ultimoTermo.current = "";
    setAberto(false);
  }

  return (
    <div ref={ref} className="relative">
      {/* Gatilho: ícone atual + campo de busca. Clicar/focar abre a grade. */}
      <div
        className={cn(
          "flex items-center gap-2 rounded-md border bg-background px-2.5 transition-colors",
          aberto ? "border-primary" : "border-border",
        )}
      >
        <span className="flex size-5 flex-none items-center justify-center">
          {selecionado ? (
            <FontAwesomeIcon icon={selecionado.icon} className="size-4 text-foreground" />
          ) : (
            <Wrench className="size-4 text-muted-foreground" />
          )}
        </span>
        <input
          value={busca}
          onChange={(e) => {
            setBusca(e.target.value);
            setAberto(true);
            buscarMais(e.target.value);
          }}
          onFocus={() => {
            setAberto(true);
            if (busca) buscarMais(busca);
          }}
          placeholder={
            selecionado ? selecionado.nome : "Buscar ícone (ex.: telegram, banco, busca)…"
          }
          className="h-9 min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
        {valor && (
          <button
            type="button"
            onClick={() => escolher(null)}
            aria-label="Remover ícone"
            className="flex-none rounded p-0.5 text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        )}
        <button
          type="button"
          onClick={() => setAberto((a) => !a)}
          aria-label={aberto ? "Fechar" : "Abrir lista de ícones"}
          className="flex-none text-muted-foreground"
        >
          <ChevronDown
            className={cn("size-4 transition-transform", aberto && "rotate-180")}
          />
        </button>
      </div>

      {aberto && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-border bg-card p-2 shadow-lg">
          <div className="grid max-h-60 grid-cols-6 gap-1.5 overflow-y-auto sm:grid-cols-8">
            {/* Sem ícone → genérico */}
            <Celula
              selecionada={!valor}
              titulo="Sem ícone (padrão)"
              onClick={() => escolher(null)}
            >
              <Wrench className="size-4 text-muted-foreground" />
            </Celula>
            {lista.map((i) => (
              <Celula
                key={i.id}
                selecionada={valor === i.id}
                titulo={i.nome}
                onClick={() => escolher(i.id)}
              >
                <FontAwesomeIcon icon={i.icon} className="size-4" />
              </Celula>
            ))}

            {/* Mais da biblioteca: o resto do Font Awesome, buscado sob demanda. */}
            {termo.length >= 2 && (extras.length > 0 || buscandoExtras) && (
              <div className="col-span-full mt-1 border-t border-border pt-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Mais da biblioteca
              </div>
            )}
            {extras.map((e) => (
              <Celula
                key={e.id}
                selecionada={valor === e.id}
                titulo={e.nome}
                onClick={() => escolher(e.id)}
              >
                <FontAwesomeIcon icon={e.icon} className="size-4" />
              </Celula>
            ))}
            {buscandoExtras && extras.length === 0 && (
              <p className="col-span-full py-2 text-center text-xs text-muted-foreground">
                Procurando na biblioteca…
              </p>
            )}

            {lista.length === 0 && extras.length === 0 && !buscandoExtras && (
              <p className="col-span-full py-3 text-center text-xs text-muted-foreground">
                {termo.length < 2
                  ? `Nenhum ícone para “${busca}”.`
                  : `Nenhum ícone para “${busca}” — nem nos curados nem na biblioteca.`}
              </p>
            )}
          </div>
          <p className="mt-1.5 px-1 text-[11px] text-muted-foreground">
            {CATALOGO_ICONES.length} ícones em destaque — digite para achar mais na
            biblioteca inteira.
          </p>
        </div>
      )}
    </div>
  );
}
