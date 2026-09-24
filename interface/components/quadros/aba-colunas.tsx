"use client";

import { useState } from "react";
import { KeyRound, Pencil, Plus } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro } from "@/lib/api";
import {
  type ColunaQuadro,
  type DetalheRecusa,
  type QuadroDetalhe,
  type Resposta,
  ROTULO_TIPO,
  rotaQuadros,
  TIPOS_ORDEM,
  type TipoColuna,
} from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ListaRecusas, PainelLateral } from "@/components/quadros/pecas";

type Previa = { feitas: string[]; linhas_afetadas: number };

// Aplica operações de estrutura com a MESMA regra do agente e do MCP: primeiro simula
// (mostra o que muda), e só então grava.
function useEstrutura(base: string, aoMudar: () => void, onFechar: () => void) {
  const [previa, setPrevia] = useState<Previa | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [recusas, setRecusas] = useState<DetalheRecusa[]>([]);
  const [ocupado, setOcupado] = useState(false);

  async function enviar(operacoes: object[], simular: boolean) {
    setOcupado(true);
    setErro(null);
    setRecusas([]);
    try {
      const r = await api.post<Resposta<Previa>>(`${base}/estrutura`, { operacoes, simular });
      if (!r.ok) {
        setErro(r.erro);
        setRecusas(r.detalhes ?? []);
        setPrevia(null);
        return;
      }
      if (simular) {
        setPrevia(r);
        return;
      }
      toast.success("Quadro atualizado");
      aoMudar();
      onFechar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }
  return { previa, setPrevia, erro, recusas, ocupado, enviar };
}

export function AbaColunas({
  organizacaoId,
  detalhe,
  opera,
  aoMudar,
}: {
  organizacaoId: string;
  detalhe: QuadroDetalhe;
  opera: boolean;
  aoMudar: () => void;
}) {
  const q = detalhe.quadro;
  const base = rotaQuadros(organizacaoId, q.id);
  const [editando, setEditando] = useState<ColunaQuadro | "nova" | null>(null);
  const [mudandoChave, setMudandoChave] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-sm text-muted-foreground">
          A descrição de cada coluna é o que o agente lê para saber o que gravar.
        </p>
        {opera && (
          <Button variant="outline" onClick={() => setEditando("nova")}>
            <Plus /> Nova coluna
          </Button>
        )}
      </div>

      <ul className="divide-y divide-border rounded-lg border border-border bg-card">
        {q.colunas.map((c) => (
          <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span className="flex min-w-[160px] items-center gap-1.5 font-medium text-foreground">
              {c.faz_parte_da_chave && <KeyRound className="size-3.5 text-primary" aria-label="identifica a linha" />}
              {c.nome}
            </span>
            <Badge variant="info">{ROTULO_TIPO[c.tipo]}</Badge>
            {c.obrigatoria && <Badge>obrigatória</Badge>}
            <span className="min-w-[180px] flex-1 text-sm text-muted-foreground">
              {c.descricao}
              {c.opcoes && (
                <span className="mt-1 flex flex-wrap gap-1">
                  {c.opcoes.map((o) => (
                    <Badge key={o}>{o}</Badge>
                  ))}
                </span>
              )}
            </span>
            {opera && (
              <Button variant="ghost" size="icon" aria-label={`Editar a coluna ${c.nome}`} onClick={() => setEditando(c)}>
                <Pencil className="size-4" />
              </Button>
            )}
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-sm">
        <KeyRound className="size-4 text-primary" />
        <span className="flex-1">
          {q.chave.length
            ? <>Cada linha é única por <span className="font-medium">{q.chave.join(" + ")}</span>. Gravar de novo a mesma combinação substitui a linha em vez de criar outra.</>
            : "Nenhuma coluna identifica a linha: cada gravação acrescenta linhas novas."}
        </span>
        {opera && (
          <Button variant="outline" size="sm" onClick={() => setMudandoChave(true)}>
            Mudar
          </Button>
        )}
      </div>

      {editando && (
        <PainelColuna
          base={base}
          coluna={editando === "nova" ? null : editando}
          onFechar={() => setEditando(null)}
          aoMudar={aoMudar}
        />
      )}
      {mudandoChave && (
        <PainelChave base={base} colunas={q.colunas} onFechar={() => setMudandoChave(false)} aoMudar={aoMudar} />
      )}
    </div>
  );
}

function PainelColuna({
  base,
  coluna,
  onFechar,
  aoMudar,
}: {
  base: string;
  coluna: ColunaQuadro | null;
  onFechar: () => void;
  aoMudar: () => void;
}) {
  const [nome, setNome] = useState(coluna?.nome ?? "");
  const [tipo, setTipo] = useState<TipoColuna>(coluna?.tipo ?? "texto");
  const [opcoes, setOpcoes] = useState((coluna?.opcoes ?? []).join(", "));
  const [descricao, setDescricao] = useState(coluna?.descricao ?? "");
  const [obrigatoria, setObrigatoria] = useState(coluna?.obrigatoria ?? false);
  const [esvaziar, setEsvaziar] = useState(false);
  const [removendo, setRemovendo] = useState(false);
  const est = useEstrutura(base, aoMudar, onFechar);
  const listaOpcoes = opcoes.split(",").map((o) => o.trim()).filter(Boolean);

  function operacoes(): object[] {
    if (!coluna) {
      return [
        {
          acao: "adicionar_coluna",
          coluna: {
            nome: nome.trim(), tipo, obrigatoria, descricao: descricao.trim() || undefined,
            ...(tipo === "opcao" ? { opcoes: listaOpcoes } : {}),
          },
        },
      ];
    }
    if (removendo) return [{ acao: "remover_coluna", coluna: coluna.id }];
    const ops: object[] = [];
    if (tipo !== coluna.tipo || (tipo === "opcao" && listaOpcoes.join("|") !== (coluna.opcoes ?? []).join("|")))
      ops.push({
        acao: tipo !== coluna.tipo ? "trocar_tipo" : "mudar_opcoes",
        coluna: coluna.id, tipo, opcoes: tipo === "opcao" ? listaOpcoes : undefined, esvaziar_invalidos: esvaziar,
      });
    if (nome.trim() !== coluna.nome) ops.push({ acao: "renomear_coluna", coluna: coluna.id, nome: nome.trim() });
    if (descricao.trim() !== (coluna.descricao ?? "")) ops.push({ acao: "descrever_coluna", coluna: coluna.id, descricao: descricao.trim() });
    if (obrigatoria !== coluna.obrigatoria) ops.push({ acao: "obrigatoria", coluna: coluna.id, valor: obrigatoria });
    return ops;
  }

  // Mudanças que mexem nos DADOS precisam da prévia antes; as outras gravam direto.
  const mexeNosDados = !coluna || removendo || tipo !== coluna.tipo ||
    (tipo === "opcao" && listaOpcoes.join("|") !== (coluna.opcoes ?? []).join("|"));

  function continuar() {
    const ops = operacoes();
    if (!ops.length) return onFechar();
    if (mexeNosDados && coluna && !est.previa) return est.enviar(ops, true);
    est.enviar(ops, false);
  }

  return (
    <PainelLateral
      titulo={coluna ? `Coluna “${coluna.nome}”` : "Nova coluna"}
      onFechar={onFechar}
      rodape={
        <>
          {coluna && !coluna.faz_parte_da_chave && !removendo && (
            <Button variant="destructive" className="mr-auto" onClick={() => { setRemovendo(true); est.setPrevia(null); }}>
              Remover coluna
            </Button>
          )}
          <Button variant="outline" onClick={removendo ? () => setRemovendo(false) : onFechar}>
            {removendo ? "Voltar" : "Cancelar"}
          </Button>
          <Button variant={removendo ? "destructive" : "default"} onClick={continuar} disabled={est.ocupado || (!coluna && !nome.trim())}>
            {est.ocupado
              ? "Conferindo…"
              : mexeNosDados && coluna && !est.previa
                ? "Ver o que muda"
                : removendo
                  ? "Remover e apagar os valores"
                  : coluna
                    ? "Salvar"
                    : "Adicionar coluna"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {est.erro && (
          <Aviso>
            {est.erro}
            <ListaRecusas detalhes={est.recusas.map((r) => ({ ...r, motivo: `${r.valor !== undefined ? `“${r.valor}”: ` : ""}${r.motivo}` }))} prefixo="" />
          </Aviso>
        )}
        {est.previa && (
          <Aviso variant="atencao">
            {est.previa.feitas.join("; ")}.{" "}
            {est.previa.linhas_afetadas > 0 && `${est.previa.linhas_afetadas} ${est.previa.linhas_afetadas === 1 ? "linha muda" : "linhas mudam"}.`}{" "}
            Confira e confirme.
          </Aviso>
        )}
        {removendo ? (
          <Aviso variant="atencao">
            Remover a coluna apaga os valores dela em todas as linhas. Os agentes que gravam nesta coluna vão
            receber recusa até o texto deles ser ajustado.
          </Aviso>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c-nome">Nome</Label>
              <Input id="c-nome" value={nome} onChange={(e) => { setNome(e.target.value); est.setPrevia(null); }} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c-tipo">Tipo</Label>
              <Select id="c-tipo" value={tipo} onChange={(e) => { setTipo(e.target.value as TipoColuna); est.setPrevia(null); }}>
                {TIPOS_ORDEM.map((t) => (
                  <option key={t} value={t}>{ROTULO_TIPO[t]}</option>
                ))}
              </Select>
              {coluna && tipo !== coluna.tipo && (
                <span className="text-xs text-muted-foreground">
                  Os valores que já existem são convertidos. Antes de salvar, você vê o que não se converte.
                </span>
              )}
            </div>
            {tipo === "opcao" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="c-opcoes">Opções</Label>
                <Input id="c-opcoes" value={opcoes} placeholder="Separadas por vírgula" onChange={(e) => { setOpcoes(e.target.value); est.setPrevia(null); }} />
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c-desc">O que vai nesta coluna</Label>
              <Textarea id="c-desc" value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="O agente lê isto para saber o que gravar." />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={obrigatoria || !!coluna?.faz_parte_da_chave} disabled={!!coluna?.faz_parte_da_chave} onChange={(e) => setObrigatoria(e.target.checked)} />
              Obrigatória
            </label>
            {est.recusas.length > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={esvaziar} onChange={(e) => { setEsvaziar(e.target.checked); est.setPrevia(null); }} />
                Deixar vazios os valores que não se convertem
              </label>
            )}
          </>
        )}
      </div>
    </PainelLateral>
  );
}

function PainelChave({
  base,
  colunas,
  onFechar,
  aoMudar,
}: {
  base: string;
  colunas: ColunaQuadro[];
  onFechar: () => void;
  aoMudar: () => void;
}) {
  const podem = colunas.filter((c) => c.tipo !== "texto_longo");
  const [marcadas, setMarcadas] = useState<string[]>(colunas.filter((c) => c.faz_parte_da_chave).map((c) => c.id));
  const est = useEstrutura(base, aoMudar, onFechar);
  const ops = [{ acao: "mudar_chave", colunas: marcadas }];
  return (
    <PainelLateral
      titulo="O que identifica cada linha"
      subtitulo="Gravar de novo a mesma combinação substitui a linha em vez de criar outra."
      onFechar={onFechar}
      rodape={
        <>
          <Button variant="outline" onClick={onFechar}>Cancelar</Button>
          <Button onClick={() => est.enviar(ops, !est.previa)} disabled={est.ocupado}>
            {est.ocupado ? "Conferindo…" : est.previa ? "Confirmar" : "Ver o que muda"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {est.erro && <Aviso>{est.erro}</Aviso>}
        {est.previa && <Aviso variant="atencao">{est.previa.feitas.join("; ")}. Confira e confirme.</Aviso>}
        {podem.map((c) => (
          <label key={c.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={marcadas.includes(c.id)}
              onChange={(e) => {
                est.setPrevia(null);
                setMarcadas(e.target.checked ? [...marcadas, c.id] : marcadas.filter((m) => m !== c.id));
              }}
            />
            {c.nome}
          </label>
        ))}
        <p className="text-xs text-muted-foreground">Sem nenhuma marcada, o quadro só acumula linhas.</p>
      </div>
    </PainelLateral>
  );
}
