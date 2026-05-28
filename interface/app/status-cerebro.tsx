"use client";

import { useEffect, useState } from "react";

export function StatusCerebro() {
  const [mensagem, setMensagem] = useState("conectando ao cérebro...");

  useEffect(() => {
    fetch("http://localhost:8000/saude")
      .then((res) => res.json())
      .then((data) => setMensagem(data.mensagem))
      .catch(() => setMensagem("não foi possível falar com o cérebro"));
  }, []);

  return <p className="text-sm text-zinc-600">Cérebro diz: {mensagem}</p>;
}
