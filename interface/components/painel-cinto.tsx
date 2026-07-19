"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Wrench } from "lucide-react";

import {
  api,
  mensagemDeErro,
  type Agente,
  type Instrumento,
  type PapelAcesso,
  type Time,
  type TipoInstrumento,
} from "@/lib/api";
import { podeOperar } from "@/lib/permissoes";
import { DrawerInstrumento } from "@/components/drawer-instrumento";
import { IconeInstrumento } from "@/components/icone-instrumento";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

// Cinto de instrumentos do agente: pendurar / tirar (ao vivo, POST/DELETE) e — quando
// temos o catálogo de `tipos` — clicar num instrumento para editar a configuração dele
// no DrawerInstrumento (por cima). FONTE ÚNICA: reusado pela read-view do drawer estreito
// E pela aba "Instrumentos" do popup, para os dois se comportarem igual.
//
// IMPORTANTE: o cinto é ESTADO LOCAL e as mutações são OTIMISTAS, SEM `router.refresh()`.
// Um refresh remontaria a página (a `key={versao}` do pai inclui o cinto) e mataria o
// popup + o rascunho não salvo dos markdowns. Aqui, pendurar/tirar/editar mexe SÓ nos
// instrumentos; o pai é sincronizado uma vez quando o drawer fecha.
// `onSubDrawer` avisa o pai que abriu/fechou um drawer por cima (coordena o Esc).

export function PainelCinto({
  agente,
  cinto,
  onCintoChange,
  instrumentosTime,
  time,
  meuPapel,
  tipos,
  onSubDrawer,
}: {
  agente: Agente;
  // CONTROLADO: o cinto vive no pai (DrawerAgente), que sobrevive à troca de abas.
  // Aqui só mutamos otimista via onCintoChange + API, sem `router.refresh()`.
  cinto: Instrumento[];
  onCintoChange: (novo: Instrumento[]) => void;
  instrumentosTime: Instrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
  tipos?: TipoInstrumento[];
  onSubDrawer?: (aberto: boolean) => void;
}) {
  const souOperador = podeOperar(meuPapel);
  const [selecionado, setSelecionado] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [editando, setEditando] = useState<Instrumento | null>(null);

  const disponiveis = instrumentosTime.filter(
    (i) => !cinto.some((c) => c.id === i.id),
  );
  // Editar a config do instrumento só quando temos o catálogo de tipos (senão o
  // DrawerInstrumento não sabe montar o formulário) e o usuário pode operar.
  const podeEditar = souOperador && !!tipos;

  function abrirEditor(inst: Instrumento) {
    if (!podeEditar) return;
    setEditando(inst);
    onSubDrawer?.(true);
  }
  function fecharEditor() {
    setEditando(null);
    onSubDrawer?.(false);
  }

  async function pendurar() {
    const inst = instrumentosTime.find((i) => i.id === selecionado);
    if (!inst) return;
    const anterior = cinto;
    setOcupado(true);
    onCintoChange([...cinto, inst]); // otimista
    setSelecionado("");
    try {
      await api.post(`/agentes/${agente.id}/instrumentos`, {
        instrumento_id: inst.id,
      });
    } catch (e) {
      onCintoChange(anterior); // reverte
      toast.error(
        mensagemDeErro(e, "Falha ao pendurar instrumento"),
      );
    } finally {
      setOcupado(false);
    }
  }

  async function tirar(instrumentoId: string) {
    const anterior = cinto;
    setOcupado(true);
    onCintoChange(cinto.filter((x) => x.id !== instrumentoId)); // otimista
    try {
      await api.delete(`/agentes/${agente.id}/instrumentos/${instrumentoId}`);
    } catch (e) {
      onCintoChange(anterior); // reverte
      toast.error(
        mensagemDeErro(e, "Falha ao tirar instrumento"),
      );
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <Wrench className="size-4 text-primary" />
        <span className="text-sm font-medium text-foreground">
          Cinto de instrumentos
        </span>
      </div>

      {cinto.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhum instrumento pendurado.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {cinto.map((i) => (
            <li
              key={i.id}
              className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <IconeInstrumento
                icone={i.icone}
                className="size-3.5 text-muted-foreground"
              />
              {podeEditar ? (
                <button
                  type="button"
                  onClick={() => abrirEditor(i)}
                  className="min-w-0 flex-1 truncate text-left text-foreground hover:text-primary hover:underline"
                  title="Editar a configuração deste instrumento"
                >
                  {i.nome}
                </button>
              ) : (
                <span className="min-w-0 flex-1 truncate text-foreground">
                  {i.nome}
                </span>
              )}
              <span className="text-xs text-muted-foreground">{i.tipo}</span>
              {souOperador && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => tirar(i.id)}
                  disabled={ocupado}
                >
                  Tirar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {souOperador && disponiveis.length > 0 && (
        <div className="mt-2 flex gap-2">
          <Select
            value={selecionado}
            onChange={(e) => setSelecionado(e.target.value)}
            className="flex-1"
          >
            <option value="">Pendurar um instrumento…</option>
            {disponiveis.map((i) => (
              <option key={i.id} value={i.id}>
                {i.nome} ({i.tipo})
              </option>
            ))}
          </Select>
          <Button
            variant="outline"
            onClick={pendurar}
            disabled={!selecionado || ocupado}
          >
            Pendurar
          </Button>
        </div>
      )}

      {podeEditar && cinto.length > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Clique num instrumento para editar a configuração dele — vale para todos os
          agentes que o usam.
        </p>
      )}

      {editando && tipos && (
        <DrawerInstrumento
          key={editando.id}
          instrumento={editando}
          tipos={tipos}
          time={time}
          meuPapel={meuPapel}
          onFechar={fecharEditor}
          onSalvou={(salvo) => {
            setEditando(salvo);
            // Atualiza o item no cinto (nome/config), sem refresh.
            onCintoChange(cinto.map((x) => (x.id === salvo.id ? salvo : x)));
          }}
        />
      )}
    </div>
  );
}
