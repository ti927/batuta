"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Wrench } from "lucide-react";

import {
  api,
  ErroDaApi,
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

// Cinto de instrumentos do agente: pendurar / tirar (ao vivo, POST/DELETE +
// router.refresh) e — quando temos o catálogo de `tipos` — clicar num instrumento
// para editar a configuração dele no DrawerInstrumento (por cima). FONTE ÚNICA:
// reusado pela read-view do drawer estreito E pela aba "Instrumentos" do popup amplo,
// para os dois se comportarem igual (evita fontes de verdade divergentes).
// `onSubDrawer` avisa o pai que abriu/fechou um drawer por cima (coordena o Esc).

export function PainelCinto({
  agente,
  cinto,
  instrumentosTime,
  time,
  meuPapel,
  tipos,
  onSubDrawer,
}: {
  agente: Agente;
  cinto: Instrumento[];
  instrumentosTime: Instrumento[];
  time: Time;
  meuPapel: PapelAcesso | null;
  tipos?: TipoInstrumento[];
  onSubDrawer?: (aberto: boolean) => void;
}) {
  const router = useRouter();
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
    if (!selecionado) return;
    setOcupado(true);
    try {
      await api.post(`/agentes/${agente.id}/instrumentos`, {
        instrumento_id: selecionado,
      });
      setSelecionado("");
      router.refresh();
    } catch (e) {
      toast.error(
        e instanceof ErroDaApi ? e.message : "Falha ao pendurar instrumento",
      );
    } finally {
      setOcupado(false);
    }
  }

  async function tirar(instrumentoId: string) {
    setOcupado(true);
    try {
      await api.delete(`/agentes/${agente.id}/instrumentos/${instrumentoId}`);
      router.refresh();
    } catch (e) {
      toast.error(
        e instanceof ErroDaApi ? e.message : "Falha ao tirar instrumento",
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
            router.refresh();
          }}
        />
      )}
    </div>
  );
}
