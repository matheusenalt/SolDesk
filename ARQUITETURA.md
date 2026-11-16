# Arquitetura

## Interface web e compatibilidade da API

SolDesk usa uma única interface React responsiva para computador e navegador
móvel. Android/iOS nativos foram descontinuados. Não há pipeline nativo nem
painel de conexão por deep link; gravação e anexos continuam no navegador.

A migração aplicada `0006a` é preservada: `client_kind`, MobileRefreshToken,
RLS por usuário/empresa e hashes de tokens não foram removidos nem alterados.
O contrato legado bearer mantém acesso curto, refresh rotativo/antirreplay e
testes de segurança, independente de SDK nativo. Cookie/CSRF continuam sendo
a autenticação da web. Nenhum modelo de negócio ou horário foi alterado.
Contrato: [sessão por token](docs/API_FASE_06A.md).

## Fase 05: conhecimento e relatórios

Migração aditiva 0005 amplia KnowledgeArticle e acrescenta ArticleVersion,
ArticleConsultation e Team, com RLS FORCE. FKs compostas protegem cliente/template
e autor/revisor na empresa. Versões/consultas são append-only para o runtime;
triggers protegem origem/autoria/conteúdo publicado e classificação de Record revisado.
Artigos anteriores recebem snapshot de importação sem inventar ator/template histórico.

`knowledge.py` / `knowledge_routes.py`: fluxo editorial humano, revisão otimista
409 e locks Record → artigo, compatíveis com worker. Conteúdo editorial editado
não é sobrescrito pelo processamento. Busca combina tsvector português/GIN,
unaccent/trigramas/GIN e trecho literal de códigos; trigger atualiza índices.
Destaques são offsets de texto renderizados pelo React, sem HTML do banco.
Publicados gerais são o padrão; filtro de cliente acrescenta os restritos daquele
cliente. Origem mantém permissão própria. Consultas guardam artigo/empresa/data,
sem identidade do leitor. Strings em `insight-strings`; UI KnowledgeArea/ReportArea
integrada a WorkArea e cadastro de clientes, com links navegáveis por hash.

`reports.py` / `report_routes.py`: métricas definidas antes do código em
[METRICAS](docs/METRICAS.md), por autoria de Record e ator de TicketEvent.
Calendários no fuso IANA viram limites UTC independentes; mediana/P90/n e pausas
unificadas/recortadas, sem duração presumida. Técnico tem escopo próprio, gestão
consulta a empresa, inclusive no CSV. Equipe/classificação atuais não simulam
histórico passado. Pessoas em ordem alfabética; gráfico tem tabela equivalente.

Agregação inicial em memória limitada a 10 mil registros, 10 mil tickets, 50 mil
eventos, 20 mil intervalos e 50 mil consultas; excesso retorna 422 sem truncar.
Períodos até 3661 dias. Tela pagina histórico em 100; CSV exporta histórico completo
dentro dos limites. Carga de produção exige medição futura. Não há dependência
nova, busca vetorial ou serviço externo. Nome/fuso da organização preservam as
políticas aninhadas de mídia/conhecimento; alterações usam rotas e locks próprios.
Contrato: [API Fase 05](docs/API_FASE_05.md).

Monorepo: API Python/FastAPI + Pydantic, SQLAlchemy 2 e Alembic; web React,
TypeScript, Vite e Tailwind CSS v4; PostgreSQL 17 no Compose. Sem microserviços
de negócio nesta fase. Contrato OpenAPI disponível em `/docs` e `/openapi.json`.

```mermaid
flowchart LR
  N[Navegador] --> W[Web / Nginx]
  W --> A[API FastAPI]
  A --> P[(PostgreSQL)]
  A --> K[Conhecimento: revisão humana / versões]
  K --> P
  A --> F[Relatórios: fatos / eventos / fuso]
  F --> P
  A --> S[StorageBackend privado: local / S3 compatível]
  D[Dispatcher] --> P
  D --> R[(Redis / RQ)]
  R --> T[Worker: ffmpeg + mock / faster-whisper opcional]
  T --> P
  T --> S
```

## Implementado

- `GET /api/v1/health`: testa conexão e presença da instalação; retorna 503
  quando o banco está inacessível ou ainda não migrado.
- `GET /api/v1/server-info`: produto, versão API, UUID persistente, modo,
  capabilities efetivamente disponíveis. Não expõe credenciais ou clientes.
- Migração 0001 cria apenas `installation` (além da tabela técnica do Alembic),
  com restrição singleton e UUID gerado uma vez. API nunca cria tabelas ao subir.
- Erros em `application/problem+json`, CORS com origens explícitas, request ID
  e logs JSON sem corpo, query ou mensagens internas de exceção.
- Web usa proxy de mesma origem, consulta duas rotas reais, possui timeout,
  erro e nova tentativa; nenhum sucesso simulado ou login fictício.
- Fonte de tokens JSON gera CSS web e verifica contraste WCAG.

## Infraestrutura e fronteiras

Compose espera banco saudável, aplica migrações e só então libera API e web.
Banco sem porta no host; API/web vinculadas a 127.0.0.1. Imagens de API e Nginx
usam usuário não root. O perfil dev monta fontes para hot reload.
Scripts não apagam banco ou volumes; preservam o UUID em migrações repetidas.

Na fase 01, setup PowerShell, builds de imagens, Compose/PostgreSQL, migrações
repetidas e reinício com preservação de UUID foram executados em Windows/WSL 2.
O navegador foi testado contra Nginx/API/PostgreSQL, além da suíte SQLite local.
O aceite reproduzível está em `scripts/test-compose.ps1`; o Playwright aceita
`PLAYWRIGHT_BASE_URL` para usar serviços externos sem iniciar API/Vite locais.

SQLite é exclusivamente alternativa de desenvolvimento/testes rápidos. Testes
SQLite não comprovam PostgreSQL, RLS ou persistência entre contêineres.
Na fase 02, a API usa `soldesk_runtime`, sem superusuário/BYPASSRLS e sem ser dona
das tabelas. Migração/bootstrap usam conexão separada, nunca entregue à API.
`Context.query/get` aplica o tenant da sessão e `set_config(..., true)` define
o contexto por transação. Políticas RLS com FORCE reforçam a separação. Testes
com SQL sem filtro e conexão reutilizada demonstram a barreira no PostgreSQL.

Na Fase 04, Redis/RQ, dispatcher, worker e `StorageBackend` local/S3 compatível
estão implementados. A API grava recibo durável no PostgreSQL e responde 202 sem
esperar Redis ou transcrição; o dispatcher entrega o trabalho ao RQ. Não há
conectores externos de negócio.

VPS/produção, TLS, backup/restauração e revisão de segurança ainda não validados.
Use apenas dados fictícios até a revisão de produção e segurança do produto.

## Fase 02: identidade e organização

`Organization`, `User`, `OrganizationMembership`, `Client`, `ClientExternalRef`,
`Invitation` e `AuditEvent` adicionados em migração aditiva 0002. O esquema SQL
é um snapshot congelado, independente dos modelos de futuras fases. Datas
TIMESTAMPTZ em UTC; fuso IANA por organização, aplicado na interface.

Sessões opacas (12 h), hashes Argon2id, CSRF sincronizado no servidor, revogação,
convites de uso único e rate limit persistente. Usuário global pode ter vários
vínculos; o ID selecionado não autoriza acesso sem vínculo ativo. Tabelas internas
de autenticação global não têm CRUD público. Redefinição de senha de identidade
compartilhada é limitada para impedir tomada de acesso entre organizações.

Clientes usam unaccent/pg_trgm, índices GIN, nome normalizado único por empresa e
paginação offset. Referências externas são apenas armazenadas, com FK composta
por empresa/cliente. Auditoria administrativa não armazena segredos e o runtime
não recebe permissão para alterar/apagar auditoria.

Papéis e regras: [PERMISSOES](docs/PERMISSOES.md). Contratos e fronteiras:
[API fase 02](docs/API_FASE_02.md). Mobile, Redis, áudio, SMTP e arquivos continuam
fora desta fase.

## Fase 03: relato, revisão e operação

Migração 0003 aditiva: Record/RecordVersion, Ticket/TicketSequence,
TicketParticipant/TicketComment/TicketEvent/TicketInterval, KnowledgeArticle
(somente rascunho), Notification e RequestReceipt. SQL congelado, FKs por tenant,
RLS FORCE em todas as tabelas novas, leitura de notificações por destinatário.
`work_schemas`, `work`, `work_routes` separam entrada, regras transacionais e HTTP.
Não houve novas dependências nem serviços; worker/Redis permanecem na fase 04.

Bloqueio da linha e revisão otimista evitam sobrescrita; recibo com hash e
advisory lock transacional evitam criações duplicadas. Comentários, versões e
eventos são apenas incluídos/consultados pelo runtime. O banco protege fatos
originais e conteúdo confirmado com trigger; não há DELETE desses recursos.
Lotes de revisão são atômicos. Somente o autor confirma finalizações.

UI em `WorkArea`, textos em `work-strings`; API real, polling de 15 s, páginas
de registros/revisões/histórico/chamados e três destinos. Conversão de horário
IANA preserva o fato e exige offset em ambiguidades de horário de verão.
Na fase 03, processamento/publicação não tinham caminhos ativos. Contratos:
[API fase 03](docs/API_FASE_03.md), [estados](docs/ESTADOS.md).

## Fase 04: arquivos e processamento assíncrono

Migração 0004: Attachment, AudioJob, TemplateVersion e GlossaryTerm, tenant e FKs
compostas/RLS FORCE. Armazenamento privado local por padrão; adaptador boto3 para
S3 compatível. Perfil S3 usa RustFS fixado por digest (a tentativa da imagem MinIO
retornou 401); endpoint MinIO existente também pode usar o adaptador S3.
URLs HMAC curtas continuam exigindo autorização e a mesma sessão; acesso auditado.

Upload verifica tamanho/assinatura/MIME e salva arquivo + job durável. Dispatcher
reconcilia PostgreSQL com RQ/Redis; worker separado normaliza ffmpeg mono 16 kHz,
verifica duração e chama o provedor. API não contém ffmpeg nem carrega Whisper.
Prioridade urgente, retries com backoff, deadline e lease idempotente; perda da
fila ou worker não bloqueia trabalho textual nem a operação de tickets.

Mock determinístico utiliza só texto humano informado, com identificação de
simulação; não reconhece fala. faster-whisper opcional CPU/int8, modelo local
explícito e downloads desativados na imagem. Contrato futuro de organizador LLM
valida evidência literal; somente regras de marcadores estão ativas.
Templates são versões imutáveis e glossário só normaliza palavras conhecidas.

UI MediaRecorder com consentimento, contador/prévia/cancelamento; upload e
digitação são alternativas. Web Speech é opt-in, desabilitável por empresa,
com aviso de possível envio ao fabricante e sem captura simultânea prometida.
Strings centralizadas em `media-strings.ts`. Conclusão exige conferência humana;
Ticket recebe comentário posterior sem mudar estado. Horários originais imutáveis.
Retenção padrão manter; políticas explícitas removem áudio elegível com auditoria.
Detalhes, limites e contratos: [API fase 04](docs/API_FASE_04.md).

## Licenciamento do código

Código próprio sob GNU AGPL v3 somente (`AGPL-3.0-only`). Componentes terceiros
mantêm suas licenças; inventário, condições de redistribuição e limites da revisão
em [docs/LICENCAS.md](docs/LICENCAS.md). A arquitetura permite instalações próprias
e hospedagem comercial, sujeitas à licença e às obrigações de fonte correspondente.
