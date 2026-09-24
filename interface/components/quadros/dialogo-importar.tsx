"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Clock, Upload } from "lucide-react";

import { api, mensagemDeErro } from "@/lib/api";
import {
  type DetalheRecusa,
  type PreviaImportacao,
  type QuadroDescrito,
  type Resposta,
  rotaQuadros,
} from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { CHAVE_CSV_PENDENTE } from "@/components/quadros/dialogo-novo-quadro";
import { Janela, ListaRecusas, lerArquivo } from "@/components/quadros/pecas";

type Resultado = {
  criadas: number;
  atualizadas: number;
  sem_mudanca: number;
  linhas_puladas: DetalheRecusa[];
};

// A hora do relógio, lida só em eventos (o clique em importar e o tique do cronômetro).
function horaAtual(): number {
  return Date.now();
}

export function DialogoImportar({
  organizacaoId,
  quadro,
  onFechar,
  aoImportar,
}: {
  organizacaoId: string;
  quadro: QuadroDescrito;
  onFechar: () => void;
  aoImportar: () => void;
}) {
  const base = rotaQuadros(organizacaoId, quadro.id);
  const [csv, setCsv] = useState<string | null>(null);
  const [arquivo, setArquivo] = useState("");
  const [previa, setPrevia] = useState<PreviaImportacao | null>(null);
  const [mapeamento, setMapeamento] = useState<Record<string, string | null>>({});
  const [pular, setPular] = useState(false);
  const [substituir, setSubstituir] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [recusas, setRecusas] = useState<DetalheRecusa[]>([]);
  const [importando, setImportando] = useState(false);
  const [inicio, setInicio] = useState<number | null>(null);
  const [agora, setAgora] = useState(0);
  const segundos = inicio ? Math.max(0, Math.floor((agora - inicio) / 1000)) : 0;
  const [resultado, setResultado] = useState<Resultado | null>(null);

  const carregarPrevia = useCallback(
    async (texto: string, mapa?: Record<string, string | null>) => {
      setErro(null);
      try {
        const r = await api.post<Resposta<PreviaImportacao>>(`${base}/importar/previa`, {
          csv: texto,
          mapeamento: mapa && Object.keys(mapa).length ? mapa : null,
        });
        if (!r.ok) {
          setErro(r.erro);
          return;
        }
        setPrevia(r);
        if (!mapa) setMapeamento(Object.fromEntries(r.mapeamento.map((m) => [m.coluna_csv, m.vai_para])));
      } catch (e) {
        setErro(mensagemDeErro(e));
      }
    },
    [base],
  );

  // A planilha escolhida na lista do cérebro chega por aqui (uma vez só).
  useEffect(() => {
    try {
      const pendente = sessionStorage.getItem(CHAVE_CSV_PENDENTE);
      if (pendente) {
        sessionStorage.removeItem(CHAVE_CSV_PENDENTE);
        const { csv: texto, arquivo: nome } = JSON.parse(pendente);
        // Aplicado fora do corpo do efeito (numa promessa), como uma resposta externa.
        Promise.resolve().then(() => {
          setCsv(texto);
          setArquivo(nome);
          carregarPrevia(texto);
        });
      }
    } catch {
      /* sem sessionStorage: a pessoa escolhe o arquivo aqui */
    }
  }, [carregarPrevia]);

  // Cronômetro enquanto importa: a tela nunca fica parada sem sinal.
  useEffect(() => {
    if (!inicio) return;
    const t = setInterval(() => setAgora(horaAtual()), 500);
    return () => clearInterval(t);
  }, [inicio]);

  async function escolher(f: File | undefined) {
    if (!f) return;
    try {
      const texto = await lerArquivo(f);
      setCsv(texto);
      setArquivo(f.name);
      setResultado(null);
      carregarPrevia(texto);
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  function mudarDestino(colunaCsv: string, destino: string) {
    const mapa = { ...mapeamento, [colunaCsv]: destino || null };
    setMapeamento(mapa);
    if (csv) carregarPrevia(csv, mapaParaServidor(mapa));
  }

  // "não importar" vai como um nome que não casa com coluna nenhuma (vira coluna ignorada).
  function mapaParaServidor(mapa: Record<string, string | null>) {
    return Object.fromEntries(Object.entries(mapa).map(([k, v]) => [k, v ?? "__nao_importar__"]));
  }

  async function importar() {
    if (!csv) return;
    setImportando(true);
    const t0 = horaAtual();
    setInicio(t0);
    setAgora(t0);
    setErro(null);
    setRecusas([]);
    try {
      const r = await api.post<Resposta<Resultado>>(`${base}/importar`, {
        csv,
        mapeamento: mapaParaServidor(mapeamento),
        ignorar_colunas_extras: true,
        pular_linhas_com_problema: pular,
        modo: substituir ? "pela_chave" : "acrescentar",
      });
      if (!r.ok) {
        setErro(r.erro);
        setRecusas(r.detalhes ?? []);
        return;
      }
      setResultado(r);
      aoImportar();
    } catch (e) {
      setErro(mensagemDeErro(e, "A conexão caiu durante a importação. O arquivo continua aqui: confira o quadro e tente de novo."));
    } finally {
      setImportando(false);
      setInicio(null);
    }
  }

  const problemas = previa?.problemas ?? [];
  const aImportar = previa ? previa.linhas_no_csv - (pular ? new Set(problemas.map((p) => p.linha)).size : 0) : 0;
  const passo = resultado ? 3 : previa ? 2 : 1;

  return (
    <Janela
      titulo="Importar planilha"
      subtitulo={`Para o quadro “${quadro.nome}”`}
      onFechar={importando ? () => {} : onFechar}
      largura={780}
      rodape={
        resultado ? (
          <Button onClick={onFechar}>Ver o quadro</Button>
        ) : (
          <>
            <Button variant="outline" onClick={onFechar} disabled={importando}>Cancelar</Button>
            {previa && (
              <Button onClick={importar} disabled={importando || aImportar <= 0 || (problemas.length > 0 && !pular)}>
                {importando ? `Importando… ${segundos}s` : `Importar ${aImportar.toLocaleString("pt-BR")} ${aImportar === 1 ? "linha" : "linhas"}`}
              </Button>
            )}
          </>
        )
      }
    >
      <div className="flex flex-col gap-4">
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {["Escolher o arquivo", "Conferir as colunas", "Importar"].map((t, i) => (
            <li key={t} className={`flex items-center gap-2 ${passo === i + 1 ? "font-medium text-foreground" : "text-muted-foreground"}`}>
              {i > 0 && <span className="h-px w-5 bg-border" />}
              <span className={`grid size-5 place-items-center rounded-full text-xs ${passo > i + 1 ? "bg-success/15 text-success" : passo === i + 1 ? "bg-primary text-primary-foreground" : "border border-border"}`}>
                {passo > i + 1 ? "✓" : i + 1}
              </span>
              {t}
            </li>
          ))}
        </ol>

        {erro && (
          <Aviso>
            {erro}
            <ListaRecusas detalhes={recusas} />
          </Aviso>
        )}

        {resultado ? (
          <Aviso variant="sucesso">
            <span className="flex items-center gap-2 font-medium">
              <CheckCircle2 className="size-4" /> Importação concluída
            </span>
            {resultado.criadas} {resultado.criadas === 1 ? "linha criada" : "linhas criadas"}
            {resultado.atualizadas ? `, ${resultado.atualizadas} substituídas` : ""}
            {resultado.sem_mudanca ? `, ${resultado.sem_mudanca} iguais às que já existiam` : ""}
            {resultado.linhas_puladas.length ? `. ${resultado.linhas_puladas.length} puladas por problema:` : "."}
            <ListaRecusas detalhes={resultado.linhas_puladas} />
          </Aviso>
        ) : (
          <>
            <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-[#D6D3E8] bg-background px-4 py-4 text-sm text-muted-foreground hover:border-primary"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); escolher(e.dataTransfer.files?.[0]); }}
            >
              <Upload className="size-5 text-primary" />
              {arquivo ? (
                <span><span className="text-foreground">{arquivo}</span>{previa ? ` · ${previa.linhas_no_csv.toLocaleString("pt-BR")} linhas` : ""} · trocar arquivo</span>
              ) : (
                <span>Solte o arquivo CSV aqui ou clique para escolher. No Google Planilhas: Arquivo › Fazer download › CSV.</span>
              )}
              <input id="importar-arquivo" type="file" accept=".csv,text/csv,.txt" className="sr-only" onChange={(e) => escolher(e.target.files?.[0])} />
            </label>

            {previa && (
              <>
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[#FCFBFE] text-left text-xs text-muted-foreground">
                        <th className="px-3 py-2 font-medium">Coluna da planilha</th>
                        <th className="px-1 py-2" />
                        <th className="px-3 py-2 font-medium">Vai para</th>
                        <th className="px-3 py-2 font-medium">Exemplo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previa.mapeamento.map((m) => (
                        <tr key={m.coluna_csv} className="border-t border-border">
                          <td className="px-3 py-2 font-medium text-foreground">{m.coluna_csv}</td>
                          <td className="px-1 py-2 text-muted-foreground"><ArrowRight className="size-4" /></td>
                          <td className="px-3 py-2">
                            <Select
                              aria-label={`Destino da coluna ${m.coluna_csv}`}
                              className="h-9"
                              value={mapeamento[m.coluna_csv] ?? ""}
                              onChange={(e) => mudarDestino(m.coluna_csv, e.target.value)}
                            >
                              <option value="">Não importar</option>
                              {quadro.colunas.map((c) => (
                                <option key={c.id} value={c.nome}>{c.nome}</option>
                              ))}
                            </Select>
                          </td>
                          <td className="max-w-[200px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">{m.exemplo}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {problemas.length > 0 ? (
                  <Aviso variant="atencao">
                    {problemas.length} {problemas.length === 1 ? "linha tem" : "linhas têm"} problema. Nada será importado até você
                    corrigir na planilha e escolher o arquivo de novo, ou marcar para pular essas linhas.
                    <ListaRecusas detalhes={problemas} />
                  </Aviso>
                ) : (
                  <Aviso variant="sucesso">Todas as {previa.linhas_no_csv.toLocaleString("pt-BR")} linhas estão prontas para entrar.</Aviso>
                )}

                <div className="flex flex-col gap-2 text-sm">
                  {problemas.length > 0 && (
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={pular} onChange={(e) => setPular(e.target.checked)} />
                      Pular as linhas com problema e importar o resto
                    </label>
                  )}
                  {quadro.chave.length > 0 && (
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={substituir} onChange={(e) => setSubstituir(e.target.checked)} />
                      Se a linha já existe no quadro ({quadro.chave.join(" + ")}), substituir pela da planilha
                    </label>
                  )}
                </div>

                {importando && (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="size-4" /> Gravando… {segundos}s. Tudo ou nada: se algo der errado, nenhuma linha entra.
                  </p>
                )}
              </>
            )}
          </>
        )}
      </div>
    </Janela>
  );
}
