# Status do SolDesk

Atualizado em 16/11/2026. **Fases 01–02 implementadas e validadas localmente com
Docker/PostgreSQL e navegador. As fases 03–06 não foram implementadas.**
Não pronto para produção.

## Funciona agora

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
  resultado remoto deve ser consultado no GitHub para o commit publicado.

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

- Setup completo em um host Linux não executado; Bash teve somente a sintaxe
  conferida com `bash -n`. O aceite atual é Windows/WSL 2 com contêineres Linux.
- pip-audit/gitleaks e auditoria completa de segurança são pendentes, previstos
  para o fechamento do produto; `npm audit` e busca textual não os substituem.
- pytest emite aviso upstream de depreciação do transporte httpx no TestClient.

## Planejado

03: registros, chamados, notificações, tempos e revisões.
04: áudio, Redis/worker, storage e processamento.
05: conhecimento, busca e métricas.
06A: Expo/mobile e QR; 06B: conectores mock, ponta a ponta e privacidade.

## Próximo passo necessário

Consultar [TESTE_LOCAL.md](TESTE_LOCAL.md) para reproduzir o aceite e
[API_FASE_02.md](docs/API_FASE_02.md) / [PERMISSOES.md](docs/PERMISSOES.md) para as
regras. Aguardar instrução antes do prompt 03. Usar somente dados fictícios.

Evidências, comandos, versões e arquivos: [relatório da fase 01](docs/VALIDACAO_PROMPT_01.md).
Fase 02: [relatório](docs/VALIDACAO_PROMPT_02.md).
