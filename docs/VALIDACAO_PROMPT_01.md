# Validação do prompt 01

## Verificação para publicação em 15/11/2026

- Backend: `pytest backend/tests -q`, 5 testes aprovados com SQLite temporário.
- Ruff: lint e formatação aprovados em `backend` e `scripts/tokens.py`.
- Tokens: `scripts/tokens.py --check` aprovado, 32 pares de contraste verificados.
- Web: lint e formatação aprovados; Vitest com 3 testes aprovados; build
  TypeScript/Vite aprovado.
- Playwright com Edge: 4 testes aprovados, desktop e emulação móvel, com API real.
- As execuções Python e esbuild bloqueadas pelo sandbox foram repetidas com
  permissão ampliada; os resultados acima são das execuções concluídas.
- Busca textual por padrões comuns de chaves privadas e tokens sem ocorrências
  nos arquivos do projeto examinados; não equivale a gitleaks ou auditoria completa.
- Cache local `Microsoft/` e relatórios Playwright excluídos do versionamento.
- `origin` configurado para `https://github.com/matheusenalt/SolDesk.git`.

## Situação no primeiro commit (histórico)

Docker não encontrado: Compose, PostgreSQL, build de imagens, reinício e
persistência do volume não foram validados. Permanece o aviso upstream do
TestClient/httpx. pip-audit e gitleaks não foram executados nesta verificação.

O titular solicitou publicar a implementação atual e, após a publicação, iniciar
o prompt 02. Em seguida escolheu GNU AGPL v3 somente e condicionou o início do
prompt 02 ao aceite obrigatório da fase 01. Texto oficial baixado sem alterações,
metadados e documentação atualizados. Revisão de 38 distribuições Python e 272
entradas npm documentada em [LICENCAS.md](LICENCAS.md).

Docker Desktop 4.99.0/Engine 29.9.3 localizado na instalação do usuário; daemon
respondeu e WSL usa versão 2. Os testes Compose serão executados após o primeiro
push, conforme a ordem solicitada. Não há aprovação de infraestrutura nesta etapa.

## Aceite executado após o primeiro push

- Primeiro commit: `e6f5cb9b407d71de1c3a2d338523c046b1ab162d`, enviado à `main`
  oficial sem force push. [Commit](https://github.com/matheusenalt/SolDesk/commit/e6f5cb9b407d71de1c3a2d338523c046b1ab162d).
- [GitHub Actions do primeiro commit](https://github.com/matheusenalt/SolDesk/actions/runs/43791339875):
  concluído com sucesso (lint, pytest, tokens, npm, testes e build).
- `scripts/setup.ps1` executado até o fim com Docker Desktop 4.99.0, Engine
  29.9.3, Compose 5.7.0 e contêiner PostgreSQL 17 em Windows/WSL 2.
- Build das imagens API/migração/web concluído; serviços saudáveis e migração
  encerrada com código zero. Nenhum volume apagado.
- `scripts/test-compose.ps1` executado até o fim: saúde real, UUID válido,
  migração executada duas vezes, reinício de banco/API, mesmo UUID, proxy Nginx,
  páginas HTTP 200, API/web sem root, volume PostgreSQL e ausência de porta do
  banco publicada no host. Sintaxe PowerShell conferida sem erros.
- Teste adicional: banco interrompido, `health` retornou 503; banco restaurado em
  bloco `finally`. Contêineres `db`, `api` e `web` recriados com
  `docker compose up -d --force-recreate --wait db api web`; UUID preservado.
- Swagger aberto no navegador em `http://localhost:8000/docs`, com as duas rotas
  de instalação exibidas. Frontend em `http://localhost:8080`.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080`, canal Edge: 4 testes aprovados em
  14,2 s contra Nginx/API/PostgreSQL. Desktop e emulação móvel; identidade real,
  temas, responsividade, erro simulado de transporte e recuperação. O cenário
  de falha usa interceptação explícita no teste, sem simular sucesso do produto.
- `npm run build` aprovado após a alteração da configuração Playwright.
- Perfil dev construído/iniciado com
  `docker compose --profile dev up -d --build --wait db migrate api-dev web-dev`.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173`, canal Edge: os mesmos 4 testes
  aprovados em 12,0 s contra o perfil dev e PostgreSQL real.

## Limites remanescentes

O aceite acima não comprova setup completo em um host Linux independente,
produção/TLS, backup/restauração, auditoria completa ou fases posteriores.
pip-audit/gitleaks permanecem pendentes do fechamento do produto. O aviso upstream
TestClient/httpx permanece. Nenhuma entidade de negócio/autenticação foi adicionada.
O prompt 02 não foi iniciado nesta entrega.
