"use client";

import { useEffect, useState } from "react";

import { URL_CEREBRO } from "@/lib/api";

export function StatusCerebro() {
  const [mensagem, setMensagem] = useState("conectando ao cérebro...");

  useEffect(() => {
    fetch(`${URL_CEREBRO}/saude`)
      .then((res) => res.json())
      .then((data) => setMensagem(data.mensagem))
      .catch(() => setMensagem("não foi possível falar com o cérebro"));
  }, []);

  return (
    <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <span className="size-1.5 rounded-full bg-success" aria-hidden="true" />
      Cérebro: {mensagem}
    </p>
  );
}
