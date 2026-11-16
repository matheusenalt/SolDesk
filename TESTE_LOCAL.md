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
.\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade 0001
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Bash:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
export DATABASE_URL=sqlite:///./soldesk.db
.venv/bin/alembic -c backend/alembic.ini upgrade 0001
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Em outro terminal: `cd web`, `npm ci`, `npm run dev`. Abra http://localhost:5173.
SQLite executa somente as rotas de instalação da fase 01 e a migração 0001.
Operações da fase 02 exigem PostgreSQL; não existe autenticação simulada SQLite.
Para PostgreSQL local, configure `DATABASE_URL` para o usuário runtime,
`MIGRATION_DATABASE_URL` para o migrador e `RUNTIME_PASSWORD` por ambiente.
Execute `python -m app.manage migrate` com o ambiente backend instalado. A API
nunca recebe a conexão do migrador. Não coloque credenciais no Git.

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

### Aceite automatizado dos contêineres

Com os serviços iniciados pelo setup, na raiz (PowerShell):

```powershell
./scripts/test-compose.ps1
```

O script verifica saúde, UUID, migrações repetidas, reinício, proxy, páginas,
usuários não root e volume PostgreSQL sem porta no host. Ele reinicia `db` e `api`;
execute somente no ambiente local de teste. Não apaga volumes. Para portas
personalizadas, informe `-ApiUrl` e `-WebUrl`. No Bash use o roteiro manual acima.

Para executar os mesmos testes de navegador contra Nginx/API/PostgreSQL, em `web`:

```powershell
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:8080'
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm run test:e2e
Remove-Item Env:PLAYWRIGHT_BASE_URL
Remove-Item Env:PLAYWRIGHT_CHANNEL
```

Bash: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080 npm run test:e2e`.
Com `PLAYWRIGHT_BASE_URL` definido, o Playwright usa o ambiente existente e não
inicia API/Vite locais. Para o perfil dev, use `http://127.0.0.1:5173` após subir
os serviços de desenvolvimento. Sem a variável, permanece o fluxo SQLite isolado.

## Falhas comuns

- Fase 02 com banco da fase 01: repita o setup, que gera `RUNTIME_PASSWORD`, cria
  o papel restrito e aplica 0002. A migração é aditiva, sem apagar a instalação.
- Login sem administrador: execute o bootstrap explícito do README. Community
  recusa bootstrap de uma segunda empresa; Cloud permite empresas distintas.
- Cookie Secure em produção exige HTTPS. Não use `ENVIRONMENT=production` com
  localhost HTTP como teste de login.
- 403 CSRF: atualize o token em `/api/v1/auth/csrf`, confira cookies e Origin/CORS.
- 429 de login: aguarde a janela/bloqueio progressivo. Não desative a proteção
  para automatizar testes; reutilize uma sessão por projeto de navegador.

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

## Aceite da fase 02

Com Docker disponível, na raiz, PowerShell e Bash:

```text
docker compose --profile test run --build --rm tests
```

O perfil usa banco isolado `soldesk_test`, em tmpfs e sem porta no host. Não limpa
o banco da aplicação. Os testes criam identificadores próprios, não dependem de
senhas fixas e recusam executar a suíte de negócio em outro nome de banco.
Sem esse perfil, os testes PostgreSQL ficam explicitamente como ignorados;
uma execução SQLite não aprova o aceite de isolamento.

Roteiro manual com dados inventados:

1. No Community, faça bootstrap; ou no Cloud, execute o seed idempotente.
2. Entre como administrador, cadastre cliente e uma referência externa fictícia.
3. Pesquise nome/apelido com e sem acento, consulte e edite, marque inativo.
4. Em Equipe, crie um convite e copie o link. Aceite em outro perfil de navegador;
   repita o aceite para observar a recusa por uso único.
5. Crie integrante com senha temporária, copie uma vez e entre em outro perfil:
   acesso aos clientes só deve ocorrer após alterar a senha.
6. Entre como técnico: equipe administrativa não aparece e promoção direta é
   recusada. Desative esse membro como admin; a sessão perde acesso imediato.
7. Não é possível rebaixar/desativar o último admin. Tente mudar o fuso IANA da
   organização e confira o horário de cadastro no detalhe do cliente.
8. Na outra empresa, UUID/nomes de clientes da primeira não são acessíveis.
9. Use "Sair de todos os dispositivos" e confira o encerramento em outro perfil.

E2E autenticado: defina `E2E_ADMIN_EMAIL` e `E2E_ADMIN_PASSWORD` **somente no
ambiente**, com uma conta fictícia, e `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080`.
No PowerShell defina também `PLAYWRIGHT_CHANNEL=msedge` para o Edge instalado.
Em `web`, execute `npx playwright test --config playwright.identity.config.ts`.
No Bash use as mesmas variáveis com `export`; Chromium precisa ser instalado
com `npx playwright install chromium`. O teste não grava traces autenticados.
As credenciais não são argumentos de linha de comando nem arquivos versionados.

## Aceite da fase 03

Repita o setup para construir os fontes atuais e aplicar 0003 no volume
existente. Não apague volumes. A migração preserva instalação, organizações,
equipe e clientes. Os comandos de backend e E2E autenticado acima agora incluem
a fase 03: 24 pytest (5 de instalação, 10 de identidade e 9 de operação), 12
Playwright autenticados (6 cenários em desktop/emulação móvel). A suíte
`npm run test:e2e` mantém 4 regressões da instalação. `npm test` executa 6 Vitest.
Execute também lint/formatação/build e `python scripts/tokens.py --check`.

Use exclusivamente organização, contas e relatos fictícios:

1. Em **Atendimentos → Novo registro**, escolha cliente e finalização. Informe
   texto e fato retroativo. Antes de confirmar, o histórico padrão deve contar
   zero; a opção de provisórios mostra o item identificado como não confirmado.
2. Confira/edite o texto e confirme como autor. O horário do fato e recebimento
   devem permanecer, com revisão separada. Outro administrador não pode confirmar.
3. Crie duas finalizações e confirme pela fila **Minhas revisões**, em lote.
4. Derive uma finalização para conhecimento/chamado: deve surgir outro rascunho
   com o mesmo fato. Conhecimento enviado continua artigo rascunho, sem publicar.
5. Abra chamado normal/urgente: encaminhamento imediato. Solicite esclarecimento,
   responda, mencione integrante, transfira e mude prioridade. Os textos anteriores
   e intervalos de entrada/saída em espera devem continuar consultáveis.
6. Resolva, depois encerre e reabra. Mesmo código/ID, contador incrementado;
   não deve encerrar automaticamente ao resolver.
7. Consulte notificações e marque leitura. Outra pessoa/empresa não acessa o UUID.
8. Duas abas editando a mesma revisão devem produzir 409 na segunda escrita.
   Repetir criação com a mesma Idempotency-Key e corpo não duplica; corpo distinto
   com a mesma chave produz 409. Esses casos também são automatizados no pytest.
9. Em horário local ambíguo/inexistente por horário de verão, informe o ISO com
   offset explícito. Editar só texto não pode truncar os segundos do fato.

Regressão de persistência: `scripts/test-compose.ps1` executa migrações duas
vezes e reinicia banco/API sem apagar dados. Transições:
[docs/ESTADOS.md](docs/ESTADOS.md); contratos e limites:
[docs/API_FASE_03.md](docs/API_FASE_03.md). Resultado executado:
[docs/VALIDACAO_PROMPT_03.md](docs/VALIDACAO_PROMPT_03.md).
