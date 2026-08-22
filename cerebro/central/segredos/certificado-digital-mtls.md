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
O caminho recomendado é montar tudo **dentro do próprio instrumento**, no Construtor — sem depender
de nenhum cadastro à parte.

1. Peça ao banco o **certificado do cliente** (tipo A1 — arquivo, não token físico). Ele costuma vir
   como `.pfx`/`.p12` (um arquivo só, com senha) ou como `.pem`/`.crt` acompanhado de um `.key`.
2. Crie o instrumento no **Construtor** e vá ao passo **Autenticação**.
3. No bloco **Certificado digital**, suba o arquivo e informe a senha, se houver.
4. Escolha o **tipo de autenticação** conforme o que o serviço pede **além** do certificado (veja o
   quadro abaixo).
5. Salve. O agente faz as chamadas normalmente.

### Qual tipo de autenticação escolher

O certificado **não é** um tipo de autenticação: ele é a identificação da conexão e vale **junto com
qualquer opção** do seletor. O que você escolhe ali é o que o serviço pede *além* dele:

| O serviço pede… | Escolha |
|---|---|
| Só o certificado | **Sem autenticação** |
| Certificado + Client ID/Secret + endereço de token | **OAuth 2.0** |
| Certificado + um token fixo que já te deram | **Token de acesso (Bearer)** |

> **"Sem autenticação" não quer dizer "sem segurança".** Quer dizer "nada além do certificado" — e
> nesse caso é o próprio certificado que identifica você. É o caso mais comum das APIs de **governo**
> (Receita Federal, SEFAZ, e-Social, notas fiscais), onde se usa um **e-CNPJ**. **Banco** é que
> normalmente pede certificado **e** OAuth 2.0.

> Também existe o caminho antigo, pela caixa-forte: criar uma credencial do tipo **Certificado
> digital (mTLS)** em Chaves e credenciais e apontar o instrumento para ela. Continua funcionando
> para quem já usa, mas para um instrumento novo prefira o Construtor — tudo o que ele precisa
> mora nele.

## Exemplos
- **Consultar um boleto no Inter:** credencial com o certificado + Client ID/Secret + o endereço de
  token do Inter e o escopo de cobrança; um instrumento REST apontando para o endpoint de consulta.
- **Só certificado, sem token:** algumas APIs (e órgãos públicos) pedem apenas o certificado. Deixe
  os campos de OAuth em branco — funciona igual.

## Limites e cuidados
- **O certificado vence** (normalmente em 1 ano). A tela mostra a data; quando renovar com o banco,
  suba o arquivo novo na mesma credencial.
- **A senha do arquivo não é guardada.** Ela serve só para abrir o `.pfx` no momento do envio. Vale
  conferir se a senha não está no **nome do arquivo** (acontece com frequência: `..._SENHA abc123.pfx`)
  — um `.pfx` sem a senha é inútil para quem o pegue; com a senha no nome, vira uma chave completa.
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
montar um agente que fala com banco: monte o conector com as operações certas e `auth_tipo: "oauth2"`
(com `auth_usuario`, `url_token` e `escopo`), deixe o segredo e o certificado **pendentes**, e diga
com todas as letras que falta a pessoa abrir o instrumento e subir o arquivo do certificado. **Não
diga que está pronto ou ligado enquanto isso não acontecer.**

Você não configura nada de token: a borda obtém e renova o `access_token` sozinha e o entrega ao
instrumento como `Authorization`. Não invente uma operação separada "para pegar o token" — isso não
funciona (o token não viaja de uma chamada para outra) e já é resolvido pela plataforma.

Ação em banco é **irreversível** por natureza: fluxo que paga, transfere ou emite cobrança precisa de
**portão de aprovação humano** antes — a parede de ativação vai exigir isso de qualquer forma.

## Relacionado
- [[segredos/credenciais-nomeadas]]
- [[segredos/segredos-de-instrumento]]
- [[instrumentos/chamar-rest]]
- [[automacoes/portao-de-aprovacao]]
