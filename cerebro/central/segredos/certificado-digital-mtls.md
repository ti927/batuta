---
titulo: "Certificado digital (mTLS) — Pix, boleto e APIs bancárias"
area: "segredos"
slug: "certificado-digital-mtls"
tags: ["certificado", "mtls", "banco", "pix", "boleto", "inter", "itau", "oauth", "pfx", "p12", "icp-brasil"]
revisado_em: "2026-08-22"
fontes: ["cerebro/tipos_credencial.py", "cerebro/certificados.py", "cerebro/oauth_mtls.py", "cerebro/instrumentos/rest.py"]
---

# Certificado digital (mTLS) — Pix, boleto e APIs bancárias

## Em uma frase
Um tipo de credencial que guarda o **certificado digital do cliente** (aquele arquivo que o banco
entrega) e, quando o banco também exige, **busca e renova sozinho o token de acesso** — é o que
destrava integrações de Pix, boleto e extrato.

## Para que serve / quando usar
APIs comuns pedem só uma chave. Banco é diferente: além da chave, ele exige que o **cliente se
identifique com um certificado** no momento da conexão — o chamado mTLS. Sem isso, a chamada nem
começa.

Use este tipo de credencial sempre que a documentação da API falar em "certificado", ".pfx", ".p12",
"mTLS" ou "certificado de cliente". Na prática: Banco Inter, Itaú, Bradesco, Sicredi e afins, e
também alguns órgãos públicos.

## Como usar (na tela)
1. Peça ao banco o **certificado do cliente** (tipo A1 — arquivo, não token físico). Ele costuma vir
   como `.pfx`/`.p12` (um arquivo só, com senha) ou como `.pem`/`.crt` acompanhado de um `.key`.
2. Em **Chaves e credenciais**, crie uma credencial do tipo **Certificado digital (mTLS)**.
3. **Suba o arquivo** e informe a senha, se houver. O Batuta lê o certificado e mostra o titular e a
   data de vencimento — confira se é a conta certa.
4. Se o banco exigir token de acesso (a maioria exige), preencha **Client ID**, **Client Secret**,
   **Endereço do token** e **Escopo**, todos conforme a documentação dele.
5. No instrumento **Chamar API REST** (ou num Conector), aponte para essa credencial em
   **Credencial da central**. Pronto — o agente faz a chamada normalmente.

## Exemplos
- **Consultar um boleto no Inter:** credencial com o certificado + Client ID/Secret + o endereço de
  token do Inter e o escopo de cobrança; um instrumento REST apontando para o endpoint de consulta.
- **Só certificado, sem token:** algumas APIs (e órgãos públicos) pedem apenas o certificado. Deixe
  os campos de OAuth em branco — funciona igual.

## Limites e cuidados
- **O certificado vence** (normalmente em 1 ano). A tela mostra a data; quando renovar com o banco,
  suba o arquivo novo na mesma credencial.
- **A senha do arquivo não é guardada.** Ela serve só para abrir o `.pfx` no momento do envio.
- **Trocar o Client ID, o segredo, o endereço ou o próprio certificado descarta o token guardado** —
  o próximo acionamento busca um novo. Isso é proposital: evita continuar operando com a conta antiga.
- **Certificado A3** (token físico/cartão) **não serve** — o Batuta precisa do arquivo (A1).
- As credenciais do token são enviadas **no corpo do formulário**, que é o formato de Inter e Itaú. Um
  banco que exija o formato alternativo (HTTP Basic) ainda não é suportado.
- **Ainda não houve teste com um banco real.** A mecânica está coberta por testes; a primeira
  integração de verdade deve ser tratada como estreia, com uma chamada de leitura antes de qualquer
  coisa que mova dinheiro.

## Para a IA
Você **nunca** recebe nem pede o certificado — ele é um arquivo que só a pessoa sobe pela tela. Ao
montar um agente que fala com banco: crie o instrumento REST/Conector apontando para o endpoint certo,
deixe a credencial **pendente** e diga com todas as letras que falta a pessoa criar a credencial do
tipo certificado digital e subir o arquivo. **Não diga que está pronto ou ligado enquanto isso não
acontecer.**

Você não precisa configurar nada de token no instrumento: se a credencial tiver o OAuth preenchido, a
borda obtém e renova o `access_token` sozinha e o entrega ao instrumento como `Authorization`. Não
invente um instrumento separado "para pegar o token" — isso não funciona (o token não viaja de uma
chamada para outra) e já é resolvido pela plataforma.

Ação em banco é **irreversível** por natureza: fluxo que paga, transfere ou emite cobrança precisa de
**portão de aprovação humano** antes — a parede de ativação vai exigir isso de qualquer forma.

## Relacionado
- [[segredos/credenciais-nomeadas]]
- [[segredos/segredos-de-instrumento]]
- [[instrumentos/chamar-rest]]
- [[automacoes/portao-de-aprovacao]]
