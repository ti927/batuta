"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, ExternalLink, Link2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { api, mensagemDeErro, URL_CEREBRO } from "@/lib/api";
import { quandoRelativo, type Resposta, rotaQuadros } from "@/lib/quadros";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PainelLateral } from "@/components/quadros/pecas";

type LinkLer = {
  id: string;
  nome: string;
  final: string;
  estado: "ativo" | "revogado" | "expirado";
  limite_por_minuto: number;
  expira_em: string | null;
  ultimo_uso_em: string | null;
  usos: number;
  criado_em: string;
};

type LinkNovo = { link: LinkLer; caminho: string };

async function copiar(texto: string) {
  try {
    await navigator.clipboard.writeText(texto);
    toast.success("Copiado");
  } catch {
    toast.error("Não consegui copiar. Selecione o texto e copie à mão.");
  }
}

export function AcessoDeFora({
  organizacaoId,
  quadroId,
  quadroNome,
  admin,
  colunaExemplo,
}: {
  organizacaoId: string;
  quadroId: string;
  quadroNome: string;
  admin: boolean;
  colunaExemplo: string | null;
}) {
  const base = `${rotaQuadros(organizacaoId, quadroId)}/links`;
  const [lista, setLista] = useState<LinkLer[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState<LinkNovo | null>(null);
  const [mexendo, setMexendo] = useState<LinkLer | null>(null);

  const carregar = useCallback(async () => {
    try {
      setLista(await api.get<LinkLer[]>(base));
    } catch (e) {
      setErro(mensagemDeErro(e, "Não consegui carregar os links."));
    }
  }, [base]);

  useEffect(() => {
    let vivo = true;
    api
      .get<LinkLer[]>(base)
      .then((l) => vivo && setLista(l))
      .catch((e) => vivo && setErro(mensagemDeErro(e, "Não consegui carregar os links.")));
    return () => {
      vivo = false;
    };
  }, [base]);

  return (
    <section className="mt-8 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="flex flex-1 items-center gap-2 text-base font-medium text-foreground">
          <Link2 className="size-4 text-primary" /> Acesso de fora
        </h2>
        {admin && (
          <Button variant="outline" onClick={() => setCriando(true)}>
            <Plus /> Criar link de leitura
          </Button>
        )}
      </div>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Um link de leitura deixa um painel de fora (Google Planilhas, Looker Studio, Power BI) ler este quadro
        sem login. Ele só lê, e só este quadro. Quem tem o link vê os dados: trate como uma senha.
        {!admin && " Só administradores da organização criam links."}
      </p>
      {erro && <Aviso>{erro}</Aviso>}
      {lista && lista.length === 0 && (
        <div className="rounded-lg border border-dashed border-border px-6 py-6 text-center text-sm text-muted-foreground">
          Nenhum painel lê este quadro de fora.
        </div>
      )}
      {lista && lista.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {lista.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <span className="min-w-[160px] font-medium text-foreground">{l.nome}</span>
              <span className="font-mono text-xs text-muted-foreground">…{l.final}</span>
              <Badge variant={l.estado === "ativo" ? "success" : l.estado === "expirado" ? "warning" : "neutral"}>
                {l.estado}
              </Badge>
              <span className="flex-1 text-xs text-muted-foreground">
                {l.usos.toLocaleString("pt-BR")} {l.usos === 1 ? "leitura" : "leituras"} · última {quandoRelativo(l.ultimo_uso_em)} ·
                até {l.limite_por_minuto} por minuto
                {l.expira_em ? ` · vale até ${new Date(l.expira_em).toLocaleDateString("pt-BR")}` : ""}
              </span>
              {admin && l.estado !== "revogado" && (
                <Button variant="ghost" size="sm" onClick={() => setMexendo(l)}>
                  Gerenciar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {criando && (
        <PainelCriar
          base={base}
          onFechar={() => setCriando(false)}
          aoCriar={(n) => {
            setCriando(false);
            setNovo(n);
            carregar();
          }}
        />
      )}
      {novo && (
        <PainelLinkNovo novo={novo} quadroNome={quadroNome} colunaExemplo={colunaExemplo} onFechar={() => setNovo(null)} />
      )}
      {mexendo && (
        <PainelGerenciar
          base={base}
          link={mexendo}
          onFechar={() => setMexendo(null)}
          aoMudar={carregar}
          aoTrocar={(n) => {
            setMexendo(null);
            setNovo(n);
            carregar();
          }}
        />
      )}
    </section>
  );
}

function PainelCriar({ base, onFechar, aoCriar }: { base: string; onFechar: () => void; aoCriar: (n: LinkNovo) => void }) {
  const [nome, setNome] = useState("");
  const [limite, setLimite] = useState("60");
  const [validade, setValidade] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function criar() {
    setOcupado(true);
    setErro(null);
    try {
      const r = await api.post<Resposta<LinkNovo>>(base, {
        nome: nome.trim(),
        limite_por_minuto: Number(limite) || 60,
        expira_em: validade ? `${validade}T23:59:59` : null,
      });
      if (!r.ok) return setErro(r.erro);
      aoCriar(r);
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <PainelLateral
      titulo="Criar link de leitura"
      onFechar={onFechar}
      rodape={
        <>
          <Button variant="outline" onClick={onFechar}>Cancelar</Button>
          <Button onClick={criar} disabled={ocupado || !nome.trim()}>{ocupado ? "Criando…" : "Criar link"}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {erro && <Aviso>{erro}</Aviso>}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="link-nome">Nome</Label>
          <Input id="link-nome" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Painel do Looker" />
          <span className="text-xs text-muted-foreground">Para saber quem usa este link.</span>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="link-limite">Leituras por minuto</Label>
          <Input id="link-limite" inputMode="numeric" value={limite} onChange={(e) => setLimite(e.target.value.replace(/\D/g, ""))} />
          <span className="text-xs text-muted-foreground">Acima disso, o painel recebe um aviso para esperar. Máximo 600.</span>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="link-validade">Vale até (opcional)</Label>
          <Input id="link-validade" type="date" value={validade} onChange={(e) => setValidade(e.target.value)} />
          <span className="text-xs text-muted-foreground">Sem data, vale até você revogar.</span>
        </div>
      </div>
    </PainelLateral>
  );
}

function PainelLinkNovo({
  novo,
  quadroNome,
  colunaExemplo,
  onFechar,
}: {
  novo: LinkNovo;
  quadroNome: string;
  colunaExemplo: string | null;
  onFechar: () => void;
}) {
  const url = `${URL_CEREBRO}${novo.caminho}`;
  const formula = `=IMPORTDATA("${url}?decimal=virgula")`;
  const exemploFiltro = colunaExemplo ? `${url}?formato=json&filtro=${encodeURIComponent(`${colunaExemplo}|gte|hoje-90`)}` : null;
  return (
    <PainelLateral titulo={`Link de leitura: ${novo.link.nome}`} subtitulo={quadroNome} onFechar={onFechar} largura={560}
      rodape={<Button onClick={onFechar}>Já copiei</Button>}
    >
      <div className="flex flex-col gap-5 text-sm">
        <Aviso variant="atencao">
          Copie agora. Depois desta tela o Batuta mostra só o final do link; para ter o link inteiro de novo,
          é preciso trocá-lo (e o antigo para de funcionar).
        </Aviso>
        <Bloco rotulo="O link" texto={url} />
        <Bloco rotulo="No Google Planilhas (cole numa célula; atualiza sozinho)" texto={formula} />
        <p className="text-muted-foreground">
          Para o Looker Studio, use essa planilha como fonte de dados. No Power BI ou no Excel, use “Obter dados da web” com o link.
        </p>
        <Bloco rotulo="Em formato JSON (para um painel próprio)" texto={`${url}?formato=json`} />
        {exemploFiltro && <Bloco rotulo={`Só os últimos 90 dias de “${colunaExemplo}”`} texto={exemploFiltro} />}
        <p className="text-muted-foreground">
          Outros filtros e os totais já calculados estão na ajuda: Como funciona › Cérebro › Ler um quadro de fora.
        </p>
      </div>
    </PainelLateral>
  );
}

function Bloco({ rotulo, texto }: { rotulo: string; texto: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-medium text-foreground">{rotulo}</span>
      <div className="flex items-start gap-2">
        <code className="min-w-0 flex-1 break-all rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground select-all">
          {texto}
        </code>
        <Button variant="outline" size="icon" aria-label={`Copiar: ${rotulo}`} onClick={() => copiar(texto)}>
          <Copy className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function PainelGerenciar({
  base,
  link,
  onFechar,
  aoMudar,
  aoTrocar,
}: {
  base: string;
  link: LinkLer;
  onFechar: () => void;
  aoMudar: () => void;
  aoTrocar: (n: LinkNovo) => void;
}) {
  const [limite, setLimite] = useState(String(link.limite_por_minuto));
  const [confirmar, setConfirmar] = useState<null | "trocar" | "revogar">(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function agir(fn: () => Promise<void>) {
    setOcupado(true);
    setErro(null);
    try {
      await fn();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <PainelLateral
      titulo={link.nome}
      subtitulo={`Link terminado em …${link.final}`}
      onFechar={onFechar}
      rodape={
        confirmar ? (
          <>
            <span className="mr-auto text-sm text-destructive">
              {confirmar === "revogar"
                ? "O painel que usa este link para de receber dados agora."
                : "O link atual para de funcionar agora; o painel precisa do novo."}
            </span>
            <Button variant="outline" onClick={() => setConfirmar(null)}>Voltar</Button>
            <Button
              variant="destructive"
              disabled={ocupado}
              onClick={() =>
                agir(async () => {
                  if (confirmar === "revogar") {
                    const r = await api.post<Resposta<object>>(`${base}/${link.id}/revogar`, {});
                    if (!r.ok) return setErro(r.erro);
                    toast.success("Link revogado");
                    aoMudar();
                    onFechar();
                  } else {
                    const r = await api.post<Resposta<LinkNovo>>(`${base}/${link.id}/trocar`, {});
                    if (!r.ok) return setErro(r.erro);
                    aoTrocar(r);
                  }
                })
              }
            >
              {confirmar === "revogar" ? "Revogar" : "Trocar o link"}
            </Button>
          </>
        ) : (
          <>
            <Button variant="destructive" className="mr-auto" onClick={() => setConfirmar("revogar")}>Revogar</Button>
            <Button variant="outline" onClick={() => setConfirmar("trocar")}>
              <RefreshCw /> Trocar o link
            </Button>
          </>
        )
      }
    >
      <div className="flex flex-col gap-4 text-sm">
        {erro && <Aviso>{erro}</Aviso>}
        <p className="text-muted-foreground">
          {link.usos.toLocaleString("pt-BR")} leituras · última {quandoRelativo(link.ultimo_uso_em)}
        </p>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="g-limite">Leituras por minuto</Label>
          <div className="flex gap-2">
            <Input id="g-limite" inputMode="numeric" value={limite} onChange={(e) => setLimite(e.target.value.replace(/\D/g, ""))} />
            <Button
              variant="outline"
              disabled={ocupado || !limite || Number(limite) === link.limite_por_minuto}
              onClick={() =>
                agir(async () => {
                  const r = await api.patch<Resposta<object>>(`${base}/${link.id}`, { limite_por_minuto: Number(limite) });
                  if (!r.ok) return setErro(r.erro);
                  toast.success("Limite ajustado");
                  aoMudar();
                })
              }
            >
              Salvar
            </Button>
          </div>
        </div>
        <p className="flex items-center gap-1.5 text-muted-foreground">
          <ExternalLink className="size-3.5" /> Perdeu o link? Troque: o Batuta gera um novo e mostra uma vez.
        </p>
      </div>
    </PainelLateral>
  );
}
