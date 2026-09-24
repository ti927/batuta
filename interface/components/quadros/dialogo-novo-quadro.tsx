"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { KeyRound, Plus, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro } from "@/lib/api";
import {
  type QuadroResumo,
  type Resposta,
  ROTULO_TIPO,
  TIPOS_ORDEM,
  type TipoColuna,
} from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Janela, ListaRecusas, lerArquivo } from "@/components/quadros/pecas";

// A planilha escolhida viaja até a tela do quadro por aqui, para a importação abrir lá
// já com o arquivo (a prévia e a correção de problemas moram num lugar só).
export const CHAVE_CSV_PENDENTE = "batuta_quadro_csv_pendente";

export type ColunaEditavel = {
  nome: string;
  tipo: TipoColuna;
  obrigatoria: boolean;
  opcoes: string;
  descricao: string;
  identifica: boolean;
};

const PODE_IDENTIFICAR: TipoColuna[] = ["texto", "numero", "dinheiro", "data", "data_hora", "sim_nao", "opcao"];

export function colunaVazia(): ColunaEditavel {
  return { nome: "", tipo: "texto", obrigatoria: false, opcoes: "", descricao: "", identifica: false };
}

export function EditorColunas({
  colunas,
  onChange,
}: {
  colunas: ColunaEditavel[];
  onChange: (c: ColunaEditavel[]) => void;
}) {
  const mudar = (i: number, parte: Partial<ColunaEditavel>) =>
    onChange(colunas.map((c, j) => (j === i ? { ...c, ...parte } : c)));
  return (
    <div className="flex flex-col gap-3">
      {colunas.map((c, i) => (
        <div key={i} className="rounded-lg border border-border bg-background p-3">
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_190px_auto]">
            <Input
              id={`col-nome-${i}`}
              aria-label={`Nome da coluna ${i + 1}`}
              placeholder="Nome da coluna"
              value={c.nome}
              onChange={(e) => mudar(i, { nome: e.target.value })}
            />
            <Select
              id={`col-tipo-${i}`}
              aria-label={`Tipo da coluna ${i + 1}`}
              value={c.tipo}
              onChange={(e) => {
                const tipo = e.target.value as TipoColuna;
                mudar(i, { tipo, identifica: PODE_IDENTIFICAR.includes(tipo) ? c.identifica : false });
              }}
            >
              {TIPOS_ORDEM.map((t) => (
                <option key={t} value={t}>
                  {ROTULO_TIPO[t]}
                </option>
              ))}
            </Select>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Remover a coluna ${c.nome || i + 1}`}
              onClick={() => onChange(colunas.filter((_, j) => j !== i))}
              disabled={colunas.length === 1}
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
          {c.tipo === "opcao" && (
            <Input
              className="mt-2"
              id={`col-opcoes-${i}`}
              aria-label="Opções, separadas por vírgula"
              placeholder="Opções, separadas por vírgula (ex.: pendente, aprovado, pago)"
              value={c.opcoes}
              onChange={(e) => mudar(i, { opcoes: e.target.value })}
            />
          )}
          <Input
            className="mt-2"
            id={`col-desc-${i}`}
            aria-label="O que vai nesta coluna"
            placeholder="O que vai nesta coluna (o agente lê isto)"
            value={c.descricao}
            onChange={(e) => mudar(i, { descricao: e.target.value })}
          />
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={c.obrigatoria || c.identifica}
                disabled={c.identifica}
                onChange={(e) => mudar(i, { obrigatoria: e.target.checked })}
              />
              Obrigatória
            </label>
            {PODE_IDENTIFICAR.includes(c.tipo) && (
              <label className="flex items-center gap-2" title="Cada combinação destas colunas aparece uma vez só no quadro.">
                <input
                  type="checkbox"
                  checked={c.identifica}
                  onChange={(e) => mudar(i, { identifica: e.target.checked })}
                />
                <KeyRound className="size-3.5 text-primary" /> Identifica a linha
              </label>
            )}
          </div>
        </div>
      ))}
      <Button variant="outline" className="self-start" onClick={() => onChange([...colunas, colunaVazia()])}>
        <Plus /> Adicionar coluna
      </Button>
    </div>
  );
}

export function paraOServidor(c: ColunaEditavel) {
  return {
    nome: c.nome.trim(),
    tipo: c.tipo,
    obrigatoria: c.obrigatoria || c.identifica,
    descricao: c.descricao.trim() || undefined,
    ...(c.tipo === "opcao"
      ? { opcoes: c.opcoes.split(",").map((o) => o.trim()).filter(Boolean) }
      : {}),
  };
}

export function DialogoNovoQuadro({
  organizacaoId,
  comecarDePlanilha,
  quadrosExistentes,
  onFechar,
}: {
  organizacaoId: string;
  comecarDePlanilha: boolean;
  quadrosExistentes: QuadroResumo[];
  onFechar: () => void;
}) {
  const router = useRouter();
  const [csv, setCsv] = useState<string | null>(null);
  const [arquivo, setArquivo] = useState<string>("");
  const [destino, setDestino] = useState<string>("novo");
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [colunas, setColunas] = useState<ColunaEditavel[]>(comecarDePlanilha ? [] : [colunaVazia()]);
  const [erro, setErro] = useState<string | null>(null);
  const [recusas, setRecusas] = useState<{ linha: number | null; coluna: string | null; motivo: string }[]>([]);
  const [ocupado, setOcupado] = useState(false);

  const planilhaPendente = comecarDePlanilha && !csv;

  async function escolherArquivo(f: File | undefined) {
    if (!f) return;
    setErro(null);
    setOcupado(true);
    try {
      const texto = await lerArquivo(f);
      setCsv(texto);
      setArquivo(f.name);
      setNome((n) => n || f.name.replace(/\.(csv|txt)$/i, ""));
      const r = await api.post<Resposta<{ colunas: { nome: string; tipo: TipoColuna }[]; linhas_no_csv: number }>>(
        `/organizacoes/${organizacaoId}/quadros/sugerir-colunas`,
        { csv: texto },
      );
      if (!r.ok) {
        setErro(r.erro);
        setCsv(null);
        return;
      }
      setColunas(r.colunas.map((c) => ({ ...colunaVazia(), nome: c.nome, tipo: c.tipo })));
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  function levarParaQuadro(quadroId: string) {
    try {
      if (csv) sessionStorage.setItem(CHAVE_CSV_PENDENTE, JSON.stringify({ csv, arquivo }));
    } catch {
      /* sem sessionStorage: a pessoa escolhe o arquivo de novo na tela do quadro */
    }
    router.push(`/organizacoes/${organizacaoId}/cerebro/${quadroId}${csv ? "?importar=1" : ""}`);
  }

  async function criar() {
    setErro(null);
    setRecusas([]);
    if (csv && destino !== "novo") {
      levarParaQuadro(destino);
      return;
    }
    if (!nome.trim()) {
      setErro("Dê um nome ao quadro.");
      return;
    }
    if (colunas.some((c) => !c.nome.trim())) {
      setErro("Toda coluna precisa de um nome.");
      return;
    }
    setOcupado(true);
    try {
      const r = await api.post<Resposta<{ quadro_id: string }>>(`/organizacoes/${organizacaoId}/quadros`, {
        nome: nome.trim(),
        descricao: descricao.trim() || null,
        colunas: colunas.map(paraOServidor),
        chave: colunas.filter((c) => c.identifica).map((c) => c.nome.trim()),
      });
      if (!r.ok) {
        setErro(r.erro);
        setRecusas(r.detalhes ?? []);
        return;
      }
      toast.success("Quadro criado");
      levarParaQuadro(r.quadro_id);
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  const paraExistente = !!csv && destino !== "novo";

  return (
    <Janela
      titulo={comecarDePlanilha ? "Importar planilha" : "Novo quadro"}
      subtitulo={
        comecarDePlanilha
          ? "Salve a aba como CSV (no Google Planilhas: Arquivo › Fazer download › CSV) e escolha o arquivo."
          : "Uma coluna para cada informação. O agente lê o nome e a descrição de cada uma."
      }
      onFechar={onFechar}
      rodape={
        planilhaPendente ? (
          <Button variant="outline" onClick={onFechar}>
            Cancelar
          </Button>
        ) : (
          <>
            <Button variant="outline" onClick={onFechar} disabled={ocupado}>
              Cancelar
            </Button>
            <Button onClick={criar} disabled={ocupado}>
              {ocupado ? "Criando…" : paraExistente ? "Continuar para a importação" : csv ? "Criar e importar" : "Criar quadro"}
            </Button>
          </>
        )
      }
    >
      <div className="flex flex-col gap-5">
        {erro && (
          <Aviso>
            {erro}
            <ListaRecusas detalhes={recusas} />
          </Aviso>
        )}

        {comecarDePlanilha && (
          <label
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-[#D6D3E8] bg-background px-6 py-8 text-center text-sm text-muted-foreground hover:border-primary"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              escolherArquivo(e.dataTransfer.files?.[0]);
            }}
          >
            <Upload className="size-6 text-primary" />
            {arquivo ? (
              <span className="text-foreground">{arquivo} · trocar arquivo</span>
            ) : (
              <span>Solte o arquivo CSV aqui ou clique para escolher</span>
            )}
            <input
              id="arquivo-csv"
              type="file"
              accept=".csv,text/csv,.txt"
              className="sr-only"
              onChange={(e) => escolherArquivo(e.target.files?.[0])}
            />
          </label>
        )}

        {csv && quadrosExistentes.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="destino">Para onde vai</Label>
            <Select id="destino" value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="novo">Um quadro novo, com as colunas da planilha</option>
              {quadrosExistentes.map((q) => (
                <option key={q.id} value={q.id}>
                  O quadro “{q.nome}”
                </option>
              ))}
            </Select>
          </div>
        )}

        {!planilhaPendente && !paraExistente && (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="nome-quadro">Nome</Label>
              <Input id="nome-quadro" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Contas a pagar" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="desc-quadro">Para que serve</Label>
              <Textarea
                id="desc-quadro"
                value={descricao}
                onChange={(e) => setDescricao(e.target.value)}
                placeholder="Ex.: Uma linha por nota fiscal recebida, do lançamento até o pagamento."
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Colunas</span>
              {csv && (
                <span className="text-sm text-muted-foreground">
                  Sugeridas pela planilha. Confira os tipos antes de criar.
                </span>
              )}
              <EditorColunas colunas={colunas} onChange={setColunas} />
            </div>
          </>
        )}
      </div>
    </Janela>
  );
}
