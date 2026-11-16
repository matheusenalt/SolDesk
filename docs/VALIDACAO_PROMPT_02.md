# Validação da fase 02

Implementação iniciada após a autorização do titular e aceite da fase 01.
Data de fechamento: 16/11/2026. Somente dados fictícios; fase 03 não iniciada.

## Implementação

- Migração aditiva 0002, snapshot SQL congelado; PostgreSQL unaccent/pg_trgm,
  índices GIN, RLS FORCE e conexão runtime distinta da migração.
- Organizações/fuso, usuários, vínculos, sessões, CSRF, limitação persistente de
  tentativas, convites, clientes/referências externas e auditoria.
- Argon2id; quatro dependências acrescentadas e fixadas no lock. Inventário de
  42 distribuições Python e 272 pacotes npm; licença própria AGPL-3.0-only mantida.
- Bootstrap explícito sem senha fixa, seed Cloud idempotente, atualização dos
  setups PowerShell/Bash sem apagar volumes, perfil de testes PostgreSQL em tmpfs.
- Interface pt-BR com strings/tokens centralizados, sem tokens em localStorage,
  datas no fuso da organização e link para o código-fonte.
- Pipeline GitHub Actions ampliado com PostgreSQL/RLS e E2E autenticado.

## Executado e aprovado

- `docker compose --profile test run --rm tests`: 15 testes aprovados em
  PostgreSQL real (13,31 s na execução ampliada). Usuário runtime não é dono,
  superusuário ou BYPASSRLS.
- Testes HTTP de leitura/listagem/alteração cruzada por UUID, seleção de empresa
  sem vínculo, SQL sem filtro, escrita cruzada rejeitada e pool sem contexto residual.
- Técnico sem autopromoção, último admin protegido inclusive em concorrência,
  desativação/revogação, logout global, expiração, CSRF/origem, cookie Secure de
  produção, rate limit por IP/conta e bloqueio progressivo.
- Convite expirado/reutilizado recusado; identidade existente exige senha atual;
  redefinição de senha compartilhada recusada; troca temporária obrigatória.
- Busca por nome/apelido e acentos/caixa, paginação, duplicidade e validação.
- Captura de logs/auditoria sem senhas ou tokens usados no teste de sessão/senha.
- `npx playwright test --config playwright.identity.config.ts`: 6 aprovados em
  25,6 s contra Nginx/API/PostgreSQL, usando Edge. Desktop e emulação móvel;
  criação/edição/busca/detalhe de cliente, convite/aceite e senha temporária.
- Credenciais fictícias de E2E foram passadas por ambiente, não gravadas em Git.
  Traces autenticados desabilitados. Criada uma organização fictícia adicional
  somente para a segunda execução E2E, sem redefinir senhas da demonstração.
- Ruff lint/formatação e tokens (32 pares de contraste) aprovados após os arquivos
  novos; build web aprovado durante as verificações e nos Dockerfiles.

## Problemas encontrados e correções

- Migração inicial da fase 02 encontrou um comentário com ponto e vírgula no
  snapshot, interferindo na separação de instruções. Corrigido, reconstruído e
  aplicado com sucesso, sem apagar o banco.
- Duas regressões SQLite herdavam Cloud/CORS do perfil de testes. As fixtures
  agora fixam a configuração que pretendem testar e usam explicitamente 0001.
- E2E primeiro encontrou seleção ambígua de cartão e seis logins sequenciais
  ultrapassando a proteção por conta. Seletores passaram a escopar o cartão e a
  suíte reutiliza uma sessão em memória por projeto, preservando o rate limit.
  A execução final dos seis cenários passou.
- Aceite de regressão encontrou falta de SELECT em `alembic_version` no runtime
  para `server-info`. Acrescentada apenas a permissão de leitura e um teste HTTP
  de regressão em PostgreSQL. Revalidação registrada na conclusão abaixo.

## Conclusão das verificações locais

- Revalidação após corrigir SELECT de `alembic_version`: **15 pytest aprovados**
  em 11,85 s. Inclui o novo assert de server-info com capabilities reais.
- `scripts/test-compose.ps1`: **aprovado** com migração 0002/runtime restrito,
  duas migrações repetidas, reinício de banco/API e UUID preservado.
- **4 Playwright de regressão aprovados** em 7,0 s contra os contêineres.
- **3 Vitest aprovados**, lint/formatação web e build TypeScript/Vite aprovados.
- Ruff lint/formatação: aprovados, 17 arquivos. YAML Compose/CI válido. Sintaxe
  PowerShell dos scripts e `bash -n` de setup/seed aprovados.
- Perfil dev reconstruído/reiniciado com runtime restrito; health e server-info
  acessíveis pelo proxy Vite, incluindo capacidades da fase 02.
- Texto AGPL original preservado (mesmo SHA-256 da revisão da fase 01).
- Revisão de arquivos e exclusões: `.env`, `.venv`, `.tools`, node_modules,
  caches e resultados locais não são incluídos no commit. Busca textual de
  credenciais é uma verificação limitada, não uma auditoria de segurança completa.

## Publicação e validação remota

Implementação enviada à `main` oficial, sem force push, após conferir sincronização:
[f9aa2e7d310333afae82f5f2710475b30027e989](https://github.com/matheusenalt/SolDesk/commit/f9aa2e7d310333afae82f5f2710475b30027e989).

[GitHub Actions 43865117672](https://github.com/matheusenalt/SolDesk/actions/runs/43865117672)
concluído com **success**. Jobs de checks e PostgreSQL concluídos sem falhas,
incluindo a suíte real PostgreSQL/RLS, `scripts/setup.sh` em host Ubuntu do runner,
build das imagens e 6 E2E autenticados com Chromium desktop/emulação móvel.
Isso acrescenta a validação Bash/Linux ao aceite local PowerShell/Windows/WSL 2.
Não há aprovação automática de outros ambientes ou implantação produtiva.

## Limites remanescentes

Sem recuperação SMTP, tokens mobile, áudio, histórico, chamados, arquivos ou
conectores nesta fase. Revisão de implantação e auditoria
de produção permanecem pendentes. O IP atrás do Nginx é conservador e pode ser
compartilhado; configuração de proxies externos exige revisão de produção.
Aviso upstream TestClient/httpx permanece. Nenhum desses limites é apresentado
como implementação de fases futuras.
