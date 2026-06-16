"use client";

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useState } from "react";
import { Wrench } from "lucide-react";

import { CATALOGO_ICONES } from "@/lib/icones-instrumento";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

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
 * Seletor de ícone do instrumento: busca + grade clicável (catálogo Font Awesome
 * curado). A 1ª opção, "Sem ícone", limpa para `null` (volta ao genérico Wrench).
 */
export function SeletorIcone({
  valor,
  onChange,
}: {
  valor: string | null;
  onChange: (id: string | null) => void;
}) {
  const [busca, setBusca] = useState("");
  const termo = busca.trim().toLowerCase();
  const lista = termo
    ? CATALOGO_ICONES.filter(
        (i) => i.nome.toLowerCase().includes(termo) || i.termos.includes(termo),
      )
    : CATALOGO_ICONES;

  return (
    <div className="flex flex-col gap-2">
      <Input
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        placeholder="Buscar ícone (ex.: telegram, banco, busca)…"
      />
      <div className="grid max-h-52 grid-cols-6 gap-2 overflow-y-auto rounded-lg border border-border bg-background p-2 sm:grid-cols-8">
        {/* Sem ícone → genérico */}
        <Celula
          selecionada={!valor}
          titulo="Sem ícone (padrão)"
          onClick={() => onChange(null)}
        >
          <Wrench className="size-4 text-muted-foreground" />
        </Celula>
        {lista.map((i) => (
          <Celula
            key={i.id}
            selecionada={valor === i.id}
            titulo={i.nome}
            onClick={() => onChange(i.id)}
          >
            <FontAwesomeIcon icon={i.icon} className="size-4" />
          </Celula>
        ))}
        {lista.length === 0 && (
          <p className="col-span-full py-3 text-center text-xs text-muted-foreground">
            Nenhum ícone para “{busca}”.
          </p>
        )}
      </div>
    </div>
  );
}
