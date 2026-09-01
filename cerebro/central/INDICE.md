---
titulo: "Índice da Central de Conhecimento"
area: "meta"
slug: "indice"
tags: ["meta", "sumario", "indice"]
revisado_em: "2026-08-22"
fontes: ["PRODUTO.md", "cerebro/modelos.py"]
---

# Central de Conhecimento — índice

Manual do Batuta para **dois leitores**: a pessoa (dentro do app, em /ajuda) e a IA criadora
(consulta sob demanda). Cada capítulo é um arquivo em `cerebro/central/<area>/<slug>.md`, no formato do
[[gabarito]] (fica dentro do backend para ir ao container em produção; o front lê via API).

**Legenda:** ✅ recurso no ar · 📋 planejado · 🧩 conceito. Coluna "capítulo" = status de ESCRITA:
✍️ escrito · ⬜ a escrever.

> **Onda A + Onda B escritas (2026-07-17):** todos os capítulos abaixo estão escritos, exceto
> `mensageria/canal-whatsapp` (recurso ainda não construído — 📋). O que vale na tela e para a IA são os
> arquivos existentes; esta tabela é o plano/sumário.

> Este índice é a **Fase 1** do roadmap (arquitetura da informação). A granularidade de instrumentos
> foi decidida assim: **1 capítulo de conceito** ("O cinto e os instrumentos") **+ 1 mini-capítulo por
> instrumento**, agrupados por família.

---

## 1. Fundamentos
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| O que é o Batuta | `fundamentos/o-que-e-o-batuta` | O princípio de composição; a metáfora do maestro | 🧩 | ✍️ |
| A hierarquia | `fundamentos/hierarquia` | Usuário → Organização → Time → Agentes | ✅ | ✍️ |

## 2. Times & Agentes
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| O Time | `times-agentes/time` | Unidade de trabalho; o que vive dentro | ✅ | ✍️ |
| O Líder | `times-agentes/lider` | O agente especial (ponte com humanos) | ✅ | ✍️ |
| O Agente e os 4 markdowns | `times-agentes/agente` | agent.md / skill.md / tools.md / soul.md; modelo de IA | ✅ | ✍️ |
| Memória do agente | `times-agentes/memoria-do-agente` | Fichas por assunto; recall sempre/sob demanda | ✅ | ✍️ |
| Criar com a IA | `times-agentes/criar-com-a-ia` | A IA criadora (conversa que monta o time) | ✅ | ✍️ |
| Editar pelo dashboard | `times-agentes/editar-agente` | Drawer/popup, cinto, salvar sem perder | ✅ | ✍️ |

## 3. Automações & Fluxo
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| A Automação | `automacoes/automacao` | A definição do fluxo; ativar/desativar | ✅ | ✍️ |
| Cadeia e grafo | `automacoes/cadeia-e-grafo` | Construtor visual; nós; bifurcação; loops | ✅ | ✍️ |
| Condições e ramos | `automacoes/condicoes-e-ramos` | A condição de cada seta; o fluxo segue TODAS as atendidas; junção | ✅ | ✍️ |
| Quando um passo dá erro | `automacoes/erros-no-fluxo` | Saída de erro, saída "se nenhuma", aviso da falha | ✅ | ✍️ |
| A ficha da execução | `automacoes/ficha-da-execucao` | Os dados que atravessam o fluxo; `anotar`; regra exata na seta; "Para cada item" | ✅ | ✍️ |
| Gatilhos | `automacoes/gatilhos` | Manual, agendamento, webhook, comentário do Instagram; a "entrada" ao 1º agente | ✅ | ✍️ |
| Pedir aprovação e aguardar | `automacoes/pedir-aprovacao` | O instrumento que para o fluxo até uma pessoa responder; por tela e por canal | ✅ | ✍️ |
| Execuções e inspeção | `automacoes/execucoes-e-inspecao` | Ver o fluxo rodar; feedback ao vivo; diagnóstico | ✅ | ✍️ |

## 4. Instrumentos
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| O cinto e os instrumentos | `instrumentos/cinto` | Conceito: encaixe, config × args, ação irreversível, segredos | ✅ | ✍️ |
| **Conteúdo & mídia** | | | | |
| Gerar imagem | `instrumentos/gerar-imagem` | Texto→imagem; modelo/tamanho/qualidade; proporção | ✅ | ✍️ |
| Montar imagem | `instrumentos/montar-imagem` | Composição a partir de fotos | ✅ | ✍️ |
| Gerar vídeo (Sora) | `instrumentos/gerar-video` | Texto/imagem→vídeo | ✅ | ✍️ |
| Gerar vídeo de foto (fal.ai) | `instrumentos/gerar-video-fal` | Anima foto (rosto real); freios de movimento | ✅ | ✍️ |
| Descrever imagem | `instrumentos/descrever-imagem` | Visão (imagem→texto) | ✅ | ✍️ |
| Guardar imagem recebida | `instrumentos/arquivar-imagem` | Salva a foto do canal → URL pública (comprovantes) | ✅ | ✍️ |
| Gerar PDF | `instrumentos/gerar-pdf` | Documentos | ✅ | ✍️ |
| **Instagram** | | | | |
| Publicar no Instagram | `instrumentos/publicar-instagram` | Feed/Reels/Stories/carrossel | ✅ | ✍️ (piloto) |
| Ler post do Instagram | `instrumentos/instagram-ler-post` | Legenda + mídia do post | ✅ | ✍️ |
| Ler comentários | `instrumentos/instagram-ler-comentarios` | Comentários de um post | ✅ | ✍️ |
| Responder comentário | `instrumentos/instagram-responder-comentario` | Resposta pública | ✅ | ✍️ |
| Insights do Instagram | `instrumentos/instagram-insights` | Métricas de mídia | ✅ | ✍️ |
| **Sites & blogs** | | | | |
| Publicar no WordPress | `instrumentos/publicar-wordpress` | Post + imagem destacada | ✅ | ✍️ |
| Ler site | `instrumentos/ler-site` | Extrair texto de uma URL (Tavily) | ✅ | ✍️ |
| Ler site (JS pesado) | `instrumentos/ler-site-firecrawl` | Firecrawl (sites de JavaScript) | ✅ | ✍️ |
| **Web (busca)** | | | | |
| Busca na web | `instrumentos/busca-web` | Tavily; tópico/recência/domínios | ✅ | ✍️ |
| Busca semântica (Exa) | `instrumentos/busca-exa` | Alternativa semântica | ✅ | ✍️ |
| **Dados & integração** | | | | |
| Chamar API REST | `instrumentos/chamar-rest` | GET/POST/…; leitura × escrita | ✅ | ✍️ |
| Banco SQL | `instrumentos/banco-sql` | Ler/escrever em SQL; somente-leitura | ✅ | ✍️ |
| Conectar MCP | `instrumentos/mcp` | Ferramentas de um servidor MCP | ✅ | ✍️ |
| Webhook de saída | `instrumentos/webhook-saida` | Avisar/disparar um sistema externo | ✅ | ✍️ |
| Agendar automação | `instrumentos/agendar-automacao` | Um agente reprograma um disparo futuro (alvo manual+ativa) | ✅ | ✍️ |
| **Mensageria** | | | | |
| Enviar no Telegram | `instrumentos/enviar-telegram` | Enviar mensagem por um bot | ✅ | ✍️ |
| **Google (OAuth)** | | | | |
| Search Console | `instrumentos/search-console` | Desempenho no Google (cliques/impressões/posição) | ✅ | ✍️ |
| Gmail: ler | `instrumentos/gmail-ler` | Ler e-mails | 📋 | ⬜ |
| Gmail: enviar | `instrumentos/gmail-enviar` | Enviar e-mail | 📋 | ⬜ |
| Agenda: listar/criar | `instrumentos/agenda` | Eventos do Google Agenda | 📋 | ⬜ |
| Drive: listar/subir | `instrumentos/drive` | Arquivos do Google Drive | 📋 | ⬜ |

## 5. Segredos & Conexões
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| Chaves de IA | `segredos/chaves-de-ia` | Pool por provedor (org → consultoria) | ✅ | ✍️ |
| Credenciais nomeadas | `segredos/credenciais-nomeadas` | Caixa-forte tipada; reuso entre instrumentos | ✅ | ✍️ |
| Segredos de instrumento | `segredos/segredos-de-instrumento` | Inline × credencial × pool | ✅ | ✍️ |
| Conectar Google (OAuth) | `segredos/conectar-google` | Conta Google por OAuth (Gmail/Agenda/Drive/Search Console) | ✅ | ✍️ |
| Certificado digital (mTLS) | `segredos/certificado-digital-mtls` | Pix, boleto e APIs bancárias; upload do .pfx/.pem + token OAuth renovado sozinho | ✅ | ✍️ |

## 6. Mensageria & Conversação
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| Conversas | `mensageria/conversas` | Inbound; estados; humano assume (takeover) | ✅ | ✍️ |
| Canal Telegram | `mensageria/canal-telegram` | Conectar o bot; alcance; **um bot = um canal** | ✅ | ✍️ |
| Canal WhatsApp | `mensageria/canal-whatsapp` | Número do Líder; janela de 24h | 📋 | ⬜ |

## 7. Operação, Uso & Segurança
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| Uso e custos | `operacao/uso-e-custos` | Medição informativa por categoria/chave | ✅ | ✍️ |
| Falhas e retentativa | `operacao/falhas-e-retentativa` | Retentável × não-retentável; backoff; falha devolvida como resposta; erro de rede | ✅ | ✍️ |
| Sinais e diagnóstico | `operacao/sinais-e-diagnostico` | Nada falha em silêncio: eventos, trabalho preso, modo degradado, **página de status dos elos**, ordem de investigação | ✅ | ✍️ |
| Auditoria e LGPD | `operacao/auditoria-e-lgpd` | Registro de ações; dados sensíveis | ✅ | ✍️ |

## 8. Administração
| Capítulo | slug | O que cobre | Recurso | Escrita |
|---|---|---|---|---|
| Papéis e permissões | `admin/papeis-e-permissoes` | Admin / Operador / Observador | ✅ | ✍️ |
| Membros e convites | `admin/membros-e-convites` | Convidar por e-mail; aceitar; desativar | ✅ | ✍️ |
| Duplicar time | `admin/duplicar-time` | Cópia com remapeamento; canais nascem desconectados | ✅ | ✍️ |

---

**Total:** ~40 capítulos (8 áreas). **Onda A** (fundamentos + chave/credencial + agente + instrumentos-chave
+ automação/gatilho/aprovação) e **Onda B** (demais instrumentos + times/agentes + operação + administração +
conversas) **escritas**. Falta só `mensageria/canal-whatsapp` (recurso não construído). A **Fase 5**
(governança/manutenção) mantém os capítulos em dia quando o código muda.
