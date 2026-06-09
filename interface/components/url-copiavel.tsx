"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";

// Mostra uma URL (ou qualquer texto) num bloco mono com um botão de copiar. Usado
// para a URL do webhook de uma automação, que o consultor precisa colar num curl/
// Postman/Bubble. Sem dependências novas — usa navigator.clipboard.
export function UrlCopiavel({ url, aviso }: { url: string; aviso?: string }) {
  const [copiado, setCopiado] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // Sem permissão de clipboard (raro): o usuário ainda pode selecionar e copiar.
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-stretch gap-1.5">
        <code className="flex-1 break-all rounded-md bg-secondary px-2.5 py-1.5 font-mono text-xs text-foreground">
          {url}
        </code>
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="size-8 shrink-0"
          onClick={copiar}
          aria-label="Copiar URL"
        >
          {copiado ? (
            <Check className="size-4 text-success" />
          ) : (
            <Copy className="size-4" />
          )}
        </Button>
      </div>
      {aviso && <span className="text-xs text-muted-foreground">{aviso}</span>}
    </div>
  );
}
