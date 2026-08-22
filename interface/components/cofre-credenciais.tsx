"use client";

// Caixa-forte de credenciais nomeadas (FASE Caixa-forte, Passo 6). Substitui o
// antigo "inventário por-instrumento". O usuário cria credenciais nomeadas
// ("WordPress Blog" = usuario+senha_app); os instrumentos as referenciam. Trocar
// num lugar só vale para todos. Valores secretos nunca voltam (só os 4 últimos).
//
// Serve a duas telas pela diferença de caminho:
// - organização: lista = /organizacoes/{id}/credenciais (POST); item = /credenciais/{id}
// - consultoria: lista = /credenciais-consultoria (POST/item) + toggle "compartilhável"
//
// Na tela da organização a lista inclui as credenciais da consultoria marcadas
// como compartilháveis — exibidas como somente-leitura (geridas na consultoria).

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { KeyRound } from "lucide-react";

import {
  ErroDaApi,
  api,
  mensagemDeErro,
  type Credencial,
  type TipoCredencial,
} from "@/lib/api";
import { Aviso } from "@/components/ui/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EstadoVazio } from "@/components/ui/estado-vazio";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

type Edicao = { modo: "criar" } | { modo: "editar"; cred: Credencial } | null;

// Lê um arquivo do disco e devolve seu conteúdo em base64 (sem o prefixo
// "data:...;base64,"). Usado no tipo certificado_mtls: o navegador não abre o
// .pfx — manda os bytes; quem lê o certificado é o cérebro (`certificados.py`).
function lerArquivoBase64(arquivo: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const leitor = new FileReader();
    leitor.onload = () => {
      const res = String(leitor.result ?? "");
      const virgula = res.indexOf(",");
      resolve(virgula >= 0 ? res.slice(virgula + 1) : res);
    };
    leitor.onerror = () => reject(leitor.error);
    leitor.readAsDataURL(arquivo);
  });
}

export function CofreCredenciais({
  credenciais,
  tipos,
  organizacaoId,
  ehConsultoria = false,
}: {
  credenciais: Credencial[];
  tipos: TipoCredencial[];
  organizacaoId?: string;
  ehConsultoria?: boolean;
}) {
  const router = useRouter();
  const [edicao, setEdicao] = useState<Edicao>(null);
  const [erro, setErro] = useState<string | null>(null);

  // Retorno do fluxo "Conectar Instagram" (OAuth): a Meta devolve o navegador
  // para esta página com ?instagram=ok|erro. useSearchParams não exige Suspense
  // aqui (página dinâmica, atrás de login).
  const params = useSearchParams();
  const igRetorno = params.get("instagram");
  const googleRetorno = params.get("google");
  const igConta = params.get("conta");
  const igMotivo = params.get("motivo");

  const caminhoCriar = ehConsultoria
    ? "/credenciais-consultoria"
    : `/organizacoes/${organizacaoId}/credenciais`;
  const caminhoItem = (id: string) =>
    ehConsultoria ? `/credenciais-consultoria/${id}` : `/credenciais/${id}`;

  // Uma credencial é gerível nesta tela se for do mesmo escopo (org vs consultoria).
  const gerivel = (c: Credencial) =>
    ehConsultoria ? c.organizacao_id === null : c.organizacao_id !== null;

  function rotuloTipo(tipo: string) {
    return tipos.find((t) => t.tipo === tipo)?.nome_exibicao ?? tipo;
  }

  async function apagar(c: Credencial) {
    if (!confirm(`Apagar a credencial "${c.nome}"?`)) return;
    try {
      await api.delete(caminhoItem(c.id));
      setErro(null);
      router.refresh();
    } catch (e) {
      setErro(mensagemDeErro(e, "Falha ao apagar a credencial"));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {erro && <Aviso>{erro}</Aviso>}

      {igRetorno === "ok" && (
        <Aviso variant="sucesso">
          Conta {igConta ? `@${igConta}` : "do Instagram"} conectada. Ela já
          aparece na lista abaixo.
        </Aviso>
      )}
      {igRetorno === "erro" && (
        <Aviso variant="atencao">
          Não foi possível conectar o Instagram
          {igMotivo ? `: ${igMotivo}` : "."}
        </Aviso>
      )}

      {googleRetorno === "ok" && (
        <Aviso variant="sucesso">
          Conta {igConta ? igConta : "do Google"} conectada. Ela já aparece na
          lista abaixo.
        </Aviso>
      )}
      {googleRetorno === "erro" && (
        <Aviso variant="atencao">
          Não foi possível conectar o Google
          {igMotivo ? `: ${igMotivo}` : "."}
        </Aviso>
      )}

      {credenciais.length === 0 ? (
        <EstadoVazio icone={KeyRound} titulo="Nenhuma credencial">
          Crie credenciais nomeadas (senha do WordPress, banco, bot…) e os
          instrumentos passam a apontar para elas — você troca num lugar só.
        </EstadoVazio>
      ) : (
        <ul className="flex flex-col gap-2">
          {credenciais.map((c) => {
            const resumo = c.resumo ?? {};
            return (
              <li
                key={c.id}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-sm font-medium text-foreground">
                    {c.nome}
                  </span>
                  <Badge>{rotuloTipo(c.tipo)}</Badge>
                  {!ehConsultoria && c.organizacao_id === null && (
                    <Badge>da consultoria</Badge>
                  )}
                  {ehConsultoria && (
                    <Badge variant={c.compartilhavel ? "success" : "neutral"}>
                      {c.compartilhavel ? "compartilhável" : "privada"}
                    </Badge>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">
                    usado por {c.usado_por}{" "}
                    {c.usado_por === 1 ? "instrumento" : "instrumentos"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {Object.entries(resumo).map(([campo, r], i) => (
                    <span key={campo}>
                      {i > 0 && " · "}
                      {campo}:{" "}
                      {r.secreto ? `••••${r.ultimos4 || "—"}` : r.valor || "—"}
                    </span>
                  ))}
                </p>
                {gerivel(c) && (
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEdicao({ modo: "editar", cred: c });
                        setErro(null);
                      }}
                    >
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => apagar(c)}
                    >
                      Apagar
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {edicao ? (
        <FormularioCredencial
          key={edicao.modo === "editar" ? edicao.cred.id : "criar"}
          tipos={tipos}
          ehConsultoria={ehConsultoria}
          organizacaoId={organizacaoId}
          credencial={edicao.modo === "editar" ? edicao.cred : null}
          caminhoCriar={caminhoCriar}
          caminhoItem={caminhoItem}
          onPronto={() => {
            setEdicao(null);
            router.refresh();
          }}
          onCancelar={() => setEdicao(null)}
          onErro={setErro}
        />
      ) : (
        <Button
          className="self-start"
          variant="outline"
          onClick={() => {
            setEdicao({ modo: "criar" });
            setErro(null);
          }}
        >
          Nova credencial
        </Button>
      )}
    </div>
  );
}

function FormularioCredencial({
  tipos,
  ehConsultoria,
  organizacaoId,
  credencial,
  caminhoCriar,
  caminhoItem,
  onPronto,
  onCancelar,
  onErro,
}: {
  tipos: TipoCredencial[];
  ehConsultoria: boolean;
  organizacaoId?: string;
  credencial: Credencial | null; // null = criar
  caminhoCriar: string;
  caminhoItem: (id: string) => string;
  onPronto: () => void;
  onCancelar: () => void;
  onErro: (m: string | null) => void;
}) {
  const editando = credencial !== null;
  const [conectando, setConectando] = useState(false);

  // Conectar Instagram por OAuth: pede ao cérebro a URL de consentimento da Meta
  // e manda o navegador para lá. No retorno, a credencial já vem preenchida (o
  // colar token manual abaixo continua como alternativa). Só na org (não na
  // consultoria), pois o fluxo grava uma credencial DA organização.
  async function conectarInstagram() {
    if (!organizacaoId) return;
    setConectando(true);
    try {
      const { url } = await api.post<{ url: string }>(
        `/organizacoes/${organizacaoId}/instagram/iniciar`,
        {},
      );
      window.location.href = url;
    } catch (e) {
      onErro(
        e instanceof ErroDaApi
          ? e.message
          : "Não foi possível iniciar a conexão com o Instagram.",
      );
      setConectando(false);
    }
  }

  // Conectar Google por OAuth (Gmail/Agenda/Drive/Search Console): pede a URL de
  // consentimento e manda o navegador para lá. No retorno, a credencial vem
  // preenchida. Não há colar token à mão (o token do Google vence em ~1h e precisa
  // do refresh token, que só o fluxo OAuth entrega). Só na org, não na consultoria.
  async function conectarGoogle() {
    if (!organizacaoId) return;
    setConectando(true);
    try {
      const { url } = await api.post<{ url: string }>(
        `/organizacoes/${organizacaoId}/google/iniciar`,
        {},
      );
      window.location.href = url;
    } catch (e) {
      onErro(
        e instanceof ErroDaApi
          ? e.message
          : "Não foi possível iniciar a conexão com o Google.",
      );
      setConectando(false);
    }
  }
  const [tipoSel, setTipoSel] = useState(credencial?.tipo ?? tipos[0]?.tipo ?? "");
  const [nome, setNome] = useState(credencial?.nome ?? "");
  const [compartilhavel, setCompartilhavel] = useState(
    credencial?.compartilhavel ?? false,
  );
  // Valor por campo. Na edição, identidade vem pré-preenchida do resumo; segredo
  // fica em branco (em branco = manter o atual).
  const [valores, setValores] = useState<Record<string, string>>(() => {
    const inicial: Record<string, string> = {};
    if (credencial?.resumo) {
      for (const [campo, r] of Object.entries(credencial.resumo)) {
        if (!r.secreto && r.valor) inicial[campo] = r.valor;
      }
    }
    return inicial;
  });
  const [salvando, setSalvando] = useState(false);
  // Nome dos arquivos escolhidos (só para exibir; o conteúdo vai em `valores`).
  const [nomeArquivo, setNomeArquivo] = useState("");
  const [nomeChave, setNomeChave] = useState("");

  const tipo = tipos.find((t) => t.tipo === tipoSel);
  const ehCertificado = tipoSel === "certificado_mtls";

  async function selecionarArquivo(
    arquivo: File | undefined,
    campo: "arquivo" | "chave_arquivo",
    setNome: (n: string) => void,
  ) {
    if (!arquivo) return;
    try {
      const b64 = await lerArquivoBase64(arquivo);
      setValores((v) => ({ ...v, [campo]: b64 }));
      setNome(arquivo.name);
      onErro(null);
    } catch {
      onErro("Não consegui ler o arquivo. Tente escolher de novo.");
    }
  }

  async function salvar() {
    if (!nome.trim()) {
      onErro("Dê um nome à credencial.");
      return;
    }
    setSalvando(true);
    try {
      const dados: Record<string, string> = {};
      if (ehCertificado) {
        // Campos transitórios do upload (o cérebro os normaliza e não os guarda
        // em claro): arquivo/chave em base64 + senha; mais o OAuth opcional.
        for (const c of [
          "arquivo",
          "chave_arquivo",
          "senha_certificado",
          "client_id",
          "client_secret",
        ]) {
          const v = (valores[c] ?? "").trim();
          if (v) dados[c] = v;
        }
        if (!editando && !dados.arquivo) {
          onErro("Envie o arquivo do certificado (.pfx/.p12 ou .pem/.crt).");
          setSalvando(false);
          return;
        }
      } else {
        for (const c of tipo?.campos ?? []) {
          const v = (valores[c.nome] ?? "").trim();
          if (v) dados[c.nome] = v;
        }
      }
      if (editando) {
        await api.put(caminhoItem(credencial!.id), {
          nome: nome.trim(),
          dados,
          compartilhavel,
        });
      } else {
        await api.post(caminhoCriar, {
          nome: nome.trim(),
          tipo: tipoSel,
          dados,
          compartilhavel,
        });
      }
      onErro(null);
      onPronto();
    } catch (e) {
      onErro(mensagemDeErro(e, "Falha ao salvar a credencial"));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-foreground">
        {editando ? "Editar credencial" : "Nova credencial"}
      </h3>

      <div className="flex flex-col gap-1">
        <Label htmlFor="cred-tipo">Tipo</Label>
        <Select
          id="cred-tipo"
          value={tipoSel}
          disabled={editando}
          onChange={(e) => {
            setTipoSel(e.target.value);
            setValores({});
          }}
        >
          {tipos.map((t) => (
            <option key={t.tipo} value={t.tipo}>
              {t.nome_exibicao}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="cred-nome">Nome</Label>
        <Input
          id="cred-nome"
          placeholder="Ex.: WordPress do Blog"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
      </div>

      {tipoSel === "instagram" && !ehConsultoria && organizacaoId && (
        <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3">
          <Button
            type="button"
            className="self-start"
            disabled={conectando}
            onClick={conectarInstagram}
          >
            {conectando ? "Abrindo o Instagram…" : "Conectar Instagram"}
          </Button>
          <p className="text-xs text-muted-foreground">
            Recomendado: você faz login na conta na própria Meta e o Batuta
            guarda o acesso sozinho — sem colar token, e ele se renova
            automaticamente.
          </p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            ou cole o token manualmente
            <span className="h-px flex-1 bg-border" />
          </div>
        </div>
      )}

      {tipoSel === "google" && !ehConsultoria && organizacaoId && (
        <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3">
          <Button
            type="button"
            className="self-start"
            disabled={conectando}
            onClick={conectarGoogle}
          >
            {conectando ? "Abrindo o Google…" : "Conectar Google"}
          </Button>
          <p className="text-xs text-muted-foreground">
            Você faz login na conta na própria tela do Google e autoriza os serviços
            (Gmail, Agenda, Drive, Search Console). O Batuta guarda o acesso e o
            renova sozinho — sem colar token.
          </p>
        </div>
      )}

      {/* Certificado digital (mTLS): o consultor SOBE o arquivo — o certificado e
          a chave não são digitados. A IA nunca recebe o segredo (fica no cofre). */}
      {ehCertificado && (
        <div className="flex flex-col gap-3 rounded-md border border-border bg-muted/40 p-3">
          <p className="text-xs text-muted-foreground">
            Suba o certificado digital do cliente (tipo A1 — arquivo). Aceita{" "}
            <strong>.pfx</strong>/<strong>.p12</strong> (com senha) ou{" "}
            <strong>.pem</strong>/<strong>.crt</strong>. O certificado fica guardado
            no cofre, cifrado — a IA nunca o vê.
          </p>

          {editando && credencial?.resumo?.titular?.valor && (
            <p className="text-xs text-foreground">
              Certificado atual: <strong>{credencial.resumo.titular.valor}</strong>
              {credencial.resumo.validade?.valor
                ? ` · vence em ${credencial.resumo.validade.valor}`
                : ""}
              . Envie um arquivo novo só para trocá-lo.
            </p>
          )}

          <div className="flex flex-col gap-1">
            <Label htmlFor="cred-cert-arquivo">
              Arquivo do certificado (.pfx/.p12 ou .pem/.crt)
            </Label>
            <input
              id="cred-cert-arquivo"
              type="file"
              accept=".pfx,.p12,.pem,.crt,.cer"
              className="text-sm text-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:text-foreground hover:file:bg-muted"
              onChange={(e) =>
                selecionarArquivo(e.target.files?.[0], "arquivo", setNomeArquivo)
              }
            />
            {nomeArquivo && (
              <span className="text-xs text-muted-foreground">
                Selecionado: {nomeArquivo}
              </span>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="cred-cert-senha">Senha do certificado (se houver)</Label>
            <Input
              id="cred-cert-senha"
              type="password"
              autoComplete="new-password"
              placeholder="Senha do arquivo .pfx (usada só para abrir; não é guardada)"
              value={valores.senha_certificado ?? ""}
              onChange={(e) =>
                setValores((v) => ({ ...v, senha_certificado: e.target.value }))
              }
            />
          </div>

          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">
              Minha chave está num arquivo .key separado
            </summary>
            <div className="mt-2 flex flex-col gap-1">
              <Label htmlFor="cred-cert-chave">Arquivo da chave (.key)</Label>
              <input
                id="cred-cert-chave"
                type="file"
                accept=".key,.pem"
                className="text-sm text-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:text-foreground hover:file:bg-muted"
                onChange={(e) =>
                  selecionarArquivo(
                    e.target.files?.[0],
                    "chave_arquivo",
                    setNomeChave,
                  )
                }
              />
              {nomeChave && <span>Selecionado: {nomeChave}</span>}
            </div>
          </details>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            OAuth do banco (opcional)
            <span className="h-px flex-1 bg-border" />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="cred-cert-clientid">Client ID</Label>
            <Input
              id="cred-cert-clientid"
              type="text"
              autoComplete="off"
              placeholder="Client ID fornecido pelo banco"
              value={valores.client_id ?? ""}
              onChange={(e) =>
                setValores((v) => ({ ...v, client_id: e.target.value }))
              }
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="cred-cert-clientsecret">Client Secret</Label>
            <Input
              id="cred-cert-clientsecret"
              type="password"
              autoComplete="new-password"
              placeholder={
                editando ? "Deixe em branco para manter" : "Client Secret do banco"
              }
              value={valores.client_secret ?? ""}
              onChange={(e) =>
                setValores((v) => ({ ...v, client_secret: e.target.value }))
              }
            />
          </div>
        </div>
      )}

      {/* Google é OAuth-only: os campos (tokens/e-mail/escopos) vêm do fluxo de
          conexão, não são digitados. Certificado tem bloco próprio (upload). */}
      {tipoSel !== "google" &&
        !ehCertificado &&
        tipo?.campos.map((campo) => (
        <div key={campo.nome} className="flex flex-col gap-1">
          <Label htmlFor={`cred-${campo.nome}`}>{campo.rotulo}</Label>
          <Input
            id={`cred-${campo.nome}`}
            type={campo.secreto ? "password" : "text"}
            autoComplete={campo.secreto ? "new-password" : "off"}
            placeholder={
              campo.secreto && editando
                ? "Deixe em branco para manter"
                : campo.rotulo
            }
            value={valores[campo.nome] ?? ""}
            onChange={(e) =>
              setValores((v) => ({ ...v, [campo.nome]: e.target.value }))
            }
          />
        </div>
      ))}

      {ehConsultoria && (
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="size-4 rounded border-border"
            checked={compartilhavel}
            onChange={(e) => setCompartilhavel(e.target.checked)}
          />
          Pode ser compartilhada com as organizações
        </label>
      )}

      <div className="flex gap-2">
        {/* Google novo é criado pelo fluxo "Conectar Google" (não há o que salvar).
            Ao editar (renomear) uma credencial Google, o Salvar volta a valer. */}
        {!(tipoSel === "google" && !editando) && (
          <Button disabled={salvando} onClick={salvar}>
            {salvando ? "Salvando…" : "Salvar"}
          </Button>
        )}
        <Button variant="ghost" disabled={salvando} onClick={onCancelar}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
