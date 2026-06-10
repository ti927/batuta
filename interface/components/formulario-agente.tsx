"use client";

import { useEffect, useState } from "react";

import {
  api,
  ErroDaApi,
  type Agente,
  type ModelosDisponiveis,
  type Papel,
  type Time,
} from "@/lib/api";
import {
  MODELOS_POR_PROVEDOR,
  provedorDoModelo,
  provedoresParaSeletor,
  ROTULO_PROVEDOR,
  type ProvedoresDisponiveis,
} from "@/lib/modelos";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// Formulário de agente, compartilhado entre a tela "Gerenciar agentes"
// (/times/[id]/agentes) e o drawer editável do dashboard. `agente=null` cria;
// com `agente` edita. Salva pela mesma porta de sempre (POST/PUT) e devolve o
// agente salvo em `onSalvo` — o pai decide o que fazer (fechar, router.refresh).

type Campos = {
  nome: string;
  papel: Papel;
  modelo_ia: string;
  agent_md: string;
  skill_md: string;
  tools_md: string;
  soul_md: string;
};

const VAZIO: Campos = {
  nome: "",
  papel: "agente",
  modelo_ia: "",
  agent_md: "",
  skill_md: "",
  tools_md: "",
  soul_md: "",
};

function deAgente(a: Agente): Campos {
  return {
    nome: a.nome,
    papel: a.papel,
    modelo_ia: a.modelo_ia ?? "",
    agent_md: a.agent_md ?? "",
    skill_md: a.skill_md ?? "",
    tools_md: a.tools_md ?? "",
    soul_md: a.soul_md ?? "",
  };
}

const MARKDOWNS: [keyof Campos, string][] = [
  ["agent_md", "agent.md — quem o agente é, o que faz"],
  ["skill_md", "skill.md — as habilidades dele"],
  ["tools_md", "tools.md — os instrumentos do cinto"],
  ["soul_md", "soul.md — personalidade, tom, jeito de falar"],
];

export function FormularioAgente({
  time,
  agente,
  onSalvo,
  onCancelar,
}: {
  time: Time;
  agente: Agente | null;
  onSalvo: (salvo: Agente) => void;
  onCancelar: () => void;
}) {
  const [form, setForm] = useState<Campos>(agente ? deAgente(agente) : VAZIO);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  // Disponibilidade de provedores (executora) por chave: só oferecemos modelos
  // cujo provedor tem chave — escolher um sem chave quebraria na execução.
  const [disponiveis, setDisponiveis] = useState<ProvedoresDisponiveis>();

  useEffect(() => {
    let vivo = true;
    api
      .get<ModelosDisponiveis>(
        `/organizacoes/${time.organizacao_id}/modelos-disponiveis`,
      )
      .then((d) => {
        if (vivo) setDisponiveis(d.executora);
      })
      .catch(() => {
        /* sem disponibilidade: o seletor mostra todos (fallback seguro) */
      });
    return () => {
      vivo = false;
    };
  }, [time.organizacao_id]);

  // Provedores a exibir: os com chave, mais o do modelo já escolhido (para não
  // sumir um valor existente cujo provedor perdeu a chave).
  const provedoresVisiveis = provedoresParaSeletor(
    disponiveis,
    form.modelo_ia ? provedorDoModelo(form.modelo_ia) : null,
  );

  function campo<K extends keyof Campos>(chave: K, valor: Campos[K]) {
    setForm((f) => ({ ...f, [chave]: valor }));
  }

  function corpo() {
    return {
      nome: form.nome.trim(),
      papel: form.papel,
      modelo_ia: form.modelo_ia || null,
      agent_md: form.agent_md || null,
      skill_md: form.skill_md || null,
      tools_md: form.tools_md || null,
      soul_md: form.soul_md || null,
    };
  }

  async function salvar() {
    if (!form.nome.trim()) {
      setErro("O nome é obrigatório.");
      return;
    }
    setSalvando(true);
    try {
      const salvo = agente
        ? await api.put<Agente>(`/agentes/${agente.id}`, corpo())
        : await api.post<Agente>(`/times/${time.id}/agentes`, corpo());
      setErro(null);
      onSalvo(salvo);
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Falha ao salvar agente");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {erro && <Aviso>{erro}</Aviso>}

      <div className="flex flex-wrap gap-3">
        <Label className="min-w-40 flex-1 flex-col items-start gap-1">
          Nome
          <Input
            value={form.nome}
            onChange={(e) => campo("nome", e.target.value)}
            autoFocus
          />
        </Label>
        <Label className="flex-col items-start gap-1">
          Papel
          <Select
            value={form.papel}
            onChange={(e) => campo("papel", e.target.value as Papel)}
          >
            <option value="agente">Agente</option>
            <option value="lider">Líder</option>
          </Select>
        </Label>
        <Label className="flex-col items-start gap-1">
          Modelo de IA
          <Select
            value={form.modelo_ia}
            onChange={(e) => campo("modelo_ia", e.target.value)}
          >
            <option value="">(não definido)</option>
            {provedoresVisiveis.map((p) => (
              <optgroup key={p} label={ROTULO_PROVEDOR[p]}>
                {MODELOS_POR_PROVEDOR[p].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </Label>
      </div>

      {MARKDOWNS.map(([chave, rotulo]) => (
        <Label key={chave} className="flex-col items-start gap-1">
          {rotulo}
          <Textarea
            className="min-h-24 font-mono"
            value={form[chave]}
            onChange={(e) => campo(chave, e.target.value)}
          />
        </Label>
      ))}

      <div className="flex gap-2">
        <Button onClick={salvar} disabled={salvando}>
          {salvando ? "Salvando…" : "Salvar"}
        </Button>
        <Button variant="ghost" onClick={onCancelar} disabled={salvando}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
