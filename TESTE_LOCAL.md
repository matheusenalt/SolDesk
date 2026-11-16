# Teste local

## Pré-requisitos

Windows 10/11: Git, navegador e Docker Desktop em versão compatível com o Windows,
backend WSL 2 e virtualização habilitada no firmware. Verifique `wsl --status`
e `wsl -l -v`; se ausente, a instalação do WSL exige privilégios e pode exigir
reinicialização. Siga a documentação oficial do Docker Desktop e do WSL.

Linux: Git, Docker Engine, plugin Compose e navegador. Configure a permissão de
acesso ao daemon segundo a política da máquina. VS Code é opcional.

Verifique espaço livre e RAM para imagens e banco. Como orçamento inicial,
reserve 8 GB de RAM e 10 GB de disco livre; isso é orientação, não medição nem
garantia de desempenho. Testes básicos não precisam de GPU ou modelo de IA.

```text
git --version
docker --version
docker compose version
docker info
```

## Setup e alternativa manual

PowerShell, na raiz:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Bash, na raiz:

```bash
bash scripts/setup.sh
```

Alternativa manual em ambos os sistemas:

1. PowerShell: `Copy-Item .env.example .env`; bash: `cp .env.example .env`.
   Não sobrescreva `.env` já existente.
2. Edite `.env`: preencha `POSTGRES_PASSWORD` com um segredo aleatório próprio,
   preferencialmente hexadecimal (sem caracteres reservados de URL), e confira portas.
3. `docker compose config --quiet` (não imprima a configuração com segredos).
4. `docker compose up -d --build db`
5. `docker compose run --rm migrate`
6. `docker compose up -d --build --wait api web`
7. `docker compose ps`

API e web devem ficar saudáveis/em execução; migrate deve terminar com código 0.
O script faz a migração antes de liberar a API e a repete para conferir idempotência.

## Verificação mínima

PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
$before = (Invoke-RestMethod http://localhost:8000/api/v1/server-info).instance_id
docker compose run --rm migrate
docker compose restart db api
docker compose up -d --wait api web
$after = (Invoke-RestMethod http://localhost:8000/api/v1/server-info).instance_id
if ($before -ne $after) { throw 'Identidade da instalação mudou' }
```

Bash:

```bash
curl --fail http://localhost:8000/api/v1/health
before=$(curl --fail --silent http://localhost:8000/api/v1/server-info)
docker compose run --rm migrate
docker compose restart db api
docker compose up -d --wait api web
after=$(curl --fail --silent http://localhost:8000/api/v1/server-info)
test "$before" = "$after"
```

Health esperado: `{"status":"ok","database":"connected"}`. Server-info inclui
`product=SolDesk`, `api_version=1.0.0`, UUID, modo `community` e capabilities reais.
Abra http://localhost:8080, confira “Backend conectado”, UUID, tema claro/escuro
e largura de celular; http://localhost:8000/docs deve abrir o OpenAPI.
Pare API com `docker compose stop api`; recarregue a web e verifique erro amigável,
sem falso sucesso. Retome com `docker compose start api` e “Verificar novamente”.

## Desenvolvimento fora do Docker

Python 3.12+ e Node LTS 22.12+ são necessários apenas neste modo.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
$env:DATABASE_URL = 'sqlite:///./soldesk.db'
.\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Bash:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
export DATABASE_URL=sqlite:///./soldesk.db
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Em outro terminal: `cd web`, `npm ci`, `npm run dev`. Abra http://localhost:5173.
Para PostgreSQL local, configure `DATABASE_URL=postgresql+psycopg://...`, crie o
banco fora da aplicação e execute o mesmo Alembic. Não coloque credenciais no Git.

## Validações automatizadas

Com o ambiente virtual ativo, na raiz:

```text
python -m pytest backend/tests -q
python -m ruff check backend scripts/tokens.py
python -m ruff format --check backend scripts/tokens.py
python scripts/tokens.py --check
```

Em `web`: `npm run lint`, `npm run format:check`, `npm test`, `npm run build`.
Para navegador: `npx playwright install chromium`, depois `npm run test:e2e`.
Se usar o Edge já instalado, PowerShell: `$env:PLAYWRIGHT_CHANNEL='msedge'`
antes de `npm run test:e2e`; bash: `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e`.
O teste inicia API/Vite nas portas 18000/15173 e encerra ao terminar; usa SQLite
`web/e2e.db` ignorado pelo Git. Não sobrescreve o banco de desenvolvimento.
Para testar contra PostgreSQL use o roteiro de Compose acima; a suíte rápida
usa SQLite temporário e não substitui essa verificação.

## Falhas comuns

- Docker ausente: instale Docker Desktop/Engine e Compose. WSL ausente não é erro
  do projeto; configure-o e reinicie quando solicitado pelo instalador.
- Daemon parado: inicie Docker e repita `docker info`.
- Porta ocupada: altere `WEB_PORT`, `API_PORT` ou `DEV_PORT` e `CORS_ORIGINS`.
- 503: confira `docker compose logs migrate api db` sem divulgar segredos;
  execute migrações. Não apague volumes como solução automática.
- Senha do banco alterada depois de criar o volume: trocar `.env` não muda a
  senha já armazenada; faça manutenção explícita com backup, sem excluir dados.
- Perfil dev: `docker compose --profile dev up -d --build db migrate api-dev web-dev`.
- Microfone mobile: HTTP por IP LAN não é contexto seguro para navegador;
  gravação web móvel exigirá HTTPS. Essa função ainda não existe na fase 01.
