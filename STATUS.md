# Status do SolDesk

Atualizado em 16/11/2026. **Fases 01–05 implementadas e validadas localmente com
Docker/PostgreSQL e navegador. Fase 06 não iniciada.**
Não pronto para produção.

## Funciona agora

- Fase 05: artigos estruturados, revisão editorial humana, devolução/arquivamento,
  versões/diferenças, política de papéis e autopublicação desligada por padrão.
- Busca PostgreSQL português/unaccent/trigramas e código literal; filtro de
  cliente/categoria/sistema/publicação, trechos destacados sem HTML e origem com
  autorização própria. Publicados separados de rascunhos/fila; restritos não
  entram em sugestões de outros clientes. Consultas agregadas sem leitor.
- Relatórios factuais com calendário/fuso, comparação anterior, filtros e equipes,
  autoria de cada ação, ações/tickets únicos, mediana/P90/n e pausas. Técnico só
  recebe números próprios; CSV auditado, fórmulas prefixadas e histórico completo.
- Migração 0005 aplicada ao PostgreSQL local e de testes; **65 pytest**, **32
  cenários Playwright autenticados** (30 na suíte completa + 2 repetidos após
  corrigir uma asserção) e **4 regressões de instalação** aprovados, sem skips
  obrigatórios, Edge desktop/emulação móvel. Worker realmente parado/retomado.
- Build web/Docker, 6 Vitest, Ruff/ESLint/formatação, 32 pares de tokens, setup
  PowerShell, migrações repetidas e persistência após reinício aprovados. Saúde
  do worker ocioso corrigida com heartbeat compatível. Exemplos JSON/CSV gerados
  pela API com dados fictícios em [exemplos](docs/exemplos/README.md).
  Evidências: [VALIDACAO_PROMPT_05](docs/VALIDACAO_PROMPT_05.md).

- Fase 04: anexos privados de cliente/chamado, storage local/S3 compatível,
  validação de bytes/assinatura/tamanho/MIME, áudio real decodificado e duração
  medida no worker; download temporário autenticado por sessão e acesso auditado.
- MediaRecorder com permissão explícita, contador, prévia/regravação/cancelamento,
  upload de arquivo e digitação. Falha de microfone mantém texto. Strings pt-BR
  centralizadas e estados identificados, em desktop/emulação móvel.
- Redis/RQ e worker/dispatcher separados; upload 202 sem aguardar transcrição,
  recibo PostgreSQL durável, prioridade urgente, idempotência/lease, retry/backoff,
  timeout recuperável, reprocessamento e descarte. ffmpeg só na imagem do worker.
- Mock offline explícito reutiliza o relato digitado e **não reconhece fala**.
  Texto bruto/organizado/humano e tempos separados, incerteza/possível credencial
  destacados, notificação interna, revisão humana obrigatória. Urgente abre e
  resolve com worker parado; resultado posterior não altera o estado do Ticket.
- Templates por empresa/tipo, edição visual e versões/snapshots preservados,
  regras por marcadores, descrição livre integral, glossário sem alterar números.
  Retenção padrão manter e limpeza de políticas explícitas auditada/testada.
- Migração 0004 aditiva com RLS FORCE, FKs compostas, isolamento áudio/anexos A/B,
  URLs expiradas/outra sessão recusadas e conteúdo original preservado.
- **43 pytest com PostgreSQL/Redis/ffmpeg**, **6 Vitest** e **24 Playwright
  autenticados** aprovados (sem skips, Edge desktop/emulação móvel, worker realmente
  parado/retomado). ESLint/Ruff, formatação, TypeScript/Vite e 32 pares de tokens
  aprovados. Setup PowerShell e persistência/migrações/reinício aprovados sem
  apagar dados; 4 regressões Playwright de instalação aprovadas. Perfil dev
  reconstruído/iniciado. Evidências: [VALIDACAO_PROMPT_04](docs/VALIDACAO_PROMPT_04.md).
- S3 compatível RustFS: escrita/leitura/remoção de objeto fictício real aprovadas.
  Imagem opcional faster-whisper construída, SDK/CPU e erro de modelo ausente
  verificados sem rede/download. Inventários: 52 pacotes Python base, 16 opcionais
  e 272 npm; texto AGPL oficial preservado. Não houve nova dependência npm.
- Fase 04 publicada na main: `23b276a`. [Actions da implementação](https://github.com/matheusenalt/SolDesk/actions/runs/43889397697):
  lint/formatação/testes/build, PostgreSQL (43 aprovados), setup Bash e E2E
  Chromium Ubuntu (24 aprovados, incluindo worker parado/retomado) concluídos
  com sucesso. Limitações opcionais permanecem explícitas abaixo.

- Fase 03: registro textual com três destinos, original preservado, edição humana
  versionada, fato/recebimento/revisão separados, retroativo auditado e futuro rejeitado.
- Revisão individual ou lote atômico, exclusivamente pelo autor; histórico conta
  somente finalizações confirmadas. Fila mostra idade e destaque acima de 24 h.
- Chamados normais/urgentes abrem diretamente; sequência por organização, estados
  explícitos, responsável/prioridade/categoria, comentários e menções, intervalos
  de espera, resolução/encerramento distintos e reabertura no mesmo ticket.
- Derivação cria rascunho ligado ao original e preserva o fato; conhecimento fica
  somente como rascunho. Notificações internas próprias, polling e leitura.
- Migração 0003 aditiva, RLS FORCE/FKs por empresa, trilhas sem alteração/exclusão
  pelo runtime, trigger para fatos originais e conteúdo confirmado, revisão 409 e
  idempotência para criação/derivação, inclusive concorrente.
- **24 pytest aprovados** com PostgreSQL isolado (5 instalação, 10 identidade,
  9 fase 03); **6 Vitest**, **12 Playwright autenticados** desktop/emulação móvel
  e **4 regressões de instalação** aprovados contra Nginx/API/PostgreSQL.
- Ruff e ESLint, formatação, TypeScript/Vite e builds Docker aprovados; 32 pares
  de contraste/tokens aprovados. Migrações repetidas e reinício novamente
  aprovados com UUID preservado e volume existente, sem apagar dados.
- Sem novas dependências na fase 03; locks, inventários e texto AGPL preservados.
- Fase 03 publicada na main: `fd415f7`. [GitHub Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/43872972449),
  com 24 pytest PostgreSQL e 12 E2E autenticados Chromium no Ubuntu, além dos
  linters, tokens, testes unitários, build e setup Bash.

- Fase 02: organizações, identidades e vínculos, sessões opacas, Argon2id, CSRF,
  revogação/logout global, bloqueio progressivo e rate limit persistente por IP/conta.
- Equipe: papéis, convites de uso único, senha temporária e troca obrigatória,
  proteção do último administrador inclusive concorrência, auditoria sem segredos.
- Clientes por organização: cadastro/edição, consulta, apelido, referências externas,
  busca com/sem acento/caixa, paginação offset e duplicidade por nome normalizado.
- API com papel runtime separado, tenant por transação e RLS FORCE. Testes SQL
  sem filtro da aplicação e reutilização de conexão do pool aprovados.
- Interface responsiva de login/equipe/clientes/configurações; fuso IANA na
  exibição de datas; dados reais da API, sem token em localStorage.
- 15 testes pytest aprovados no perfil Docker com PostgreSQL isolado, incluindo
  5 regressões da instalação e 10 testes de segurança/operação da fase 02.
- 6 testes Playwright autenticados aprovados com Edge: desktop e emulação móvel,
  cadastro/busca/edição, convite/aceite e troca obrigatória de senha temporária.
- Migração 0002 aplicada ao volume existente, preservando a instalação; seed
  Cloud de duas empresas fictícias executado com senhas aleatórias e idempotência.
- Aceite de migrações repetidas/reinício e UUID novamente aprovado com o runtime
  restrito. Quatro regressões Playwright de instalação aprovadas na fase 02.
- CI ampliada para testar PostgreSQL/RLS, setup Bash e interface autenticada;
  [execução da fase 02 aprovada](https://github.com/matheusenalt/SolDesk/actions/runs/43865117672),
  incluindo setup em Ubuntu e E2E autenticado Chromium desktop/móvel.

- API FastAPI com saúde real do banco, identidade persistente, modo Community/Cloud,
  OpenAPI, CORS estrito, erros padronizados e logs JSON sem corpo/query.
- Migração inicial apenas com instalação; migração repetida e persistência do UUID
  entre instâncias da aplicação comprovadas em SQLite temporário.
- Web React/TypeScript em pt-BR, responsiva, temas claro/escuro, tokens oficiais e
  conexão real com a API, timeout, erro e nova tentativa.
- Teste de contraste de 32 pares, tokens gerados para web/mobile e detecção de deriva.
- Build web, lint Python/web e formatação aprovados localmente.
- 5 testes pytest, 3 testes Vitest e 4 testes Playwright aprovados. O Playwright
  executou Edge headless, desktop e emulação de largura/dispositivo móvel, com API real.
- `npm audit`: zero vulnerabilidades após corrigir Vitest e minimatch transitivo.
- Setup PowerShell executado com Docker Desktop 4.99.0, Engine 29.9.3 e Compose
  5.7.0: imagens construídas e serviços iniciados; PostgreSQL 17 saudável.
- Migrações repetidas e UUID preservado após reinício; volume persistente
  conferido. API/web sem root e PostgreSQL sem porta publicada no host.
- 4 testes Playwright adicionais aprovados contra Nginx/API/PostgreSQL reais:
  desktop e emulação móvel, temas, UUID, erro e nova tentativa.
- Perfil dev construído/iniciado e outros 4 testes Playwright aprovados contra
  Vite/API em contêineres e PostgreSQL. UUID preservado após recriar contêineres;
  banco parado produz 503 e recupera após restabelecer a conexão.
- Swagger aberto no navegador; frontend, health, server-info e OpenAPI acessíveis.
- Primeiro push `e6f5cb9` concluído na `main`; GitHub Actions aprovado.
- AGPL v3 somente aplicada com texto oficial inalterado; dependências revisadas
  em [LICENCAS.md](docs/LICENCAS.md).

## Parcial / não validado

- faster-whisper: sem modelo instalado/baixado e sem inferência real. Precisão,
  velocidade e consumo com pesos dependem de benchmark ainda pendente, conforme
  o Prompt 04 e [DECISOES](docs/DECISOES.md). Mock não substitui reconhecimento.
- Web Speech é protótipo opt-in/desabilitável com aviso prévio de privacidade;
  serviço real do fabricante não foi ativado/testado. Não promete simultaneidade.
- Safari/iOS/Firefox e microfone em aparelho físico não foram testados. Formatos
  desses clientes foram exercitados por arquivos reais gerados por ffmpeg; isso
  não comprova compatibilidade do navegador/dispositivo. HTTP por IP da LAN não
  habilita microfone; HTTPS de desenvolvimento não foi provisionado pelo setup.
- Hook ClamAV testado em TCP controlado; daemon/assinaturas reais não validados.
  MinIO não subiu (imagem 401); perfil local usa RustFS. S3 público/AWS em produção,
  versionamento/replicação/backups e remoção nesses sistemas externos não validados.

- Setup PowerShell validado localmente em Windows/WSL 2; setup Bash validado em
  runner Ubuntu do GitHub Actions. Distribuições/instalações diferentes desse
  ambiente e implantação de produção ainda não foram validadas.
- pip-audit/gitleaks e auditoria completa de segurança são pendentes, previstos
  para o fechamento do produto; `npm audit` e busca textual não os substituem.
- pytest emite aviso upstream de depreciação do transporte httpx no TestClient.

## Planejado

06A: Expo/mobile e QR; 06B: conectores mock, ponta a ponta e privacidade.

## Próximo passo necessário

Consultar [TESTE_LOCAL.md](TESTE_LOCAL.md) para reproduzir o aceite e
[API_FASE_02.md](docs/API_FASE_02.md) / [PERMISSOES.md](docs/PERMISSOES.md) para as
regras. Fase 05: [API](docs/API_FASE_05.md), [métricas](docs/METRICAS.md),
[estados](docs/ESTADOS.md) e [relatório](docs/VALIDACAO_PROMPT_05.md).
Publicar o aceite da Fase 05 e aguardar instrução antes do Prompt 06.
Usar somente dados fictícios.

Evidências, comandos, versões e arquivos: [relatório da fase 01](docs/VALIDACAO_PROMPT_01.md).
Fase 02: [relatório](docs/VALIDACAO_PROMPT_02.md).
