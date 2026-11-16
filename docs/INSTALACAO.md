# Instalação local

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
2. Edite `.env`: preencha `POSTGRES_PASSWORD`, `RUNTIME_PASSWORD` e
   `DOWNLOAD_SIGNING_KEY` com segredos aleatórios próprios distintos (32 bytes),
   preferencialmente hexadecimal (sem caracteres reservados de URL), e confira portas.
3. `docker compose config --quiet` (não imprima a configuração com segredos).
4. `docker compose up -d --build db`
5. `docker compose run --rm migrate`
6. `docker compose up -d --build --wait api web redis worker dispatcher`
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



## Primeiro acesso e dados fictícios

Community é o padrão e aceita uma organização criada explicitamente:

```text
docker compose run --rm migrate python -m app.manage bootstrap --organization "Empresa fictícia" --slug empresa-ficticia --name "Administrador fictício" --email admin@example.test
```

A senha é solicitada no terminal; não existe senha fixa. Para duas organizações
fictícias, use uma instalação local Cloud, com `SOLDESK_MODE=cloud`, e siga
[seed de demonstração](../scripts/seed-demo/README.md). O seed não redefine senhas
existentes; mantenha credenciais somente no ambiente. Cadastro público permanece
desligado por padrão (`ALLOW_ORG_SIGNUP=false`).

Web: http://localhost:8080; API/OpenAPI: http://localhost:8000/docs;
Vite opcional: http://localhost:5173. Portas: WEB_PORT/API_PORT/DEV_PORT.
API_BIND_HOST mantém loopback; mudar CORS_ORIGINS ao alterar origens.
PostgreSQL/Redis não têm porta publicada no host. Nome público: SOLDESK_INSTANCE_NAME.

O setup não instala Docker, não configura HTTPS nem cria backup automático.
Antes de atualização, faça cópia recuperável de banco, mídia e configuração;
execute migrações por um único executor. Nunca remova volumes para atualizar.
Rollback de aplicação só é seguro com esquema compatível; restaure cópia validada
em volumes novos quando necessário, sem downgrade destrutivo improvisado.
Operação real depende de [segurança](SEGURANCA.md) e [recuperação homologada](BACKUP.md).
