# Desenvolvimento e testes

Somente dados fictícios e ambientes isolados. Nunca executar controle de worker,
bootstrap de demonstração ou teste de reinício em produção. Instalação e
pré-requisitos: [guia](docs/INSTALACAO.md). Configuração/portas: [Compose](compose.yaml).

## Backend

Python 3.12+ declarado, ambiente local testado em 3.13. Node 22.12+ para web.
Crie `.venv`, instale `backend/requirements.lock` e então `pip install --no-deps -e backend`.
Use o Python do ambiente criado, sem instalar dependências globais.
Para operação autenticada, PostgreSQL é obrigatório: DATABASE_URL runtime,
MIGRATION_DATABASE_URL migrador e RUNTIME_PASSWORD por ambiente privado.
Execute `python -m app.manage migrate` com a conexão de migração; a API nunca
deve receber essa conexão. Não imprima URLs com credenciais.

SQLite só comprova rotas de instalação na revisão 0001; não simula autenticação/RLS.
Para instalação rápida isolada, defina DATABASE_URL=sqlite:///./soldesk.db,
rode `python -m alembic -c backend/alembic.ini upgrade 0001` e inicie
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`.

Na raiz, com ambiente virtual ativo:

```text
python -m ruff check backend scripts/tokens.py scripts/audit_licenses.py
python -m ruff format --check backend scripts/tokens.py scripts/audit_licenses.py
python scripts/tokens.py --check
python -m pytest backend/tests -q
docker compose --profile test run --build --rm tests
```

Pytest sem URLs de teste pode pular PostgreSQL; não declarar RLS aprovado nesse caso.
O perfil Compose usa test-db/test-redis e exige soldesk_test no fixture; não substitua
essas URLs por banco real. Com imagem e dependências já preparadas:
`docker compose --profile test run --no-deps --rm --pull never tests`.
Teste upgrade novo a partir da revisão anterior em banco isolado, com duas
organizações fictícias, RLS direto/HTTP/busca, concorrência e idempotência pertinentes.
Não apagar volumes nem executar downgrade destrutivo para repetir testes.

## Frontend e navegador

Em `web`, instalar do lock com `npm ci` e executar:

```text
npm run lint
npm run format:check
npm test
npm run build
```

Build inclui TypeScript sem emissão e Vite. `npm run dev` abre Vite em localhost:5173.
API_PROXY_TARGET seleciona a API de desenvolvimento; não configure produção.
Tokens centralizados vêm de docs/tokens.json; `scripts/tokens.py --check` mede
contraste, sem substituir teste de foco, teclado/leitor de tela ou dispositivo físico.

```text
npx playwright install chromium
npx playwright test --config playwright.config.ts --workers=1
```

Sem PLAYWRIGHT_BASE_URL, a suíte pública inicia API SQLite/Vite nas portas
18000/15173 e usa web/e2e.db ignorado; verifica somente instalação.
Contra Docker local, definir PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080.
Edge instalado: PLAYWRIGHT_CHANNEL=msedge. Não é teste Android/iOS físico.

Para os fluxos autenticados, prepare organização e credenciais fictícias por
bootstrap/seed em instalação local Cloud. Defina E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD
no ambiente, sem gravá-los em scripts ou repositório, e execute em web:

```text
npx playwright test --config playwright.identity.config.ts
```

E2E_CONTROL_WORKER=1 só na stack fictícia local: inclui parada/retomada real do worker.
Sem essa variável, o cenário correspondente pode ser pulado; informar a cobertura.
Confirme worker saudável ao fim. Não registrar senha, token ou trace com dados privados.

## Infraestrutura, fluxos e diagnóstico

`scripts/test-compose.ps1` verifica saúde, UUID, migração repetida, reinício,
proxy, usuário não root e volume/porta do banco; reinicia db/api. Apenas ambiente local.
API `/api/v1/health` não comprova todos os subsistemas; mídia tem saúde autenticada.
S3/ClamAV/Whisper e suas limitações: [operação](docs/OPERACAO_MIDIA.md).
Smoke funcional: [uso](docs/USO.md). Recuperação ainda pendente: [backup](docs/BACKUP.md).
Porta ocupada, Docker/WSL parado e URL/origem divergentes: corrigir configuração,
não apagar dados. Arquivo grande/sem formato: conferir limites/MIME; microfone negado:
usar digitação ou arquivo, sem inventar transcrição. Modelo ausente não é baixado.
Resultados reais e não executados: [STATUS.md](STATUS.md).
