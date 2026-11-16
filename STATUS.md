# Status do SolDesk

Atualizado em 15/11/2026. **Fase 01 implementada; aceite Compose/PostgreSQL e
navegador aprovado no Windows com WSL 2. As fases 02–06 não foram implementadas.**
Não pronto para produção.

## Funciona agora

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

02: autenticação, organizações, equipe, clientes, auditoria e RLS com papel separado.
03: registros, chamados, notificações, tempos e revisões.
04: áudio, Redis/worker, storage e processamento.
05: conhecimento, busca e métricas.
06A: Expo/mobile e QR; 06B: conectores mock, ponta a ponta e privacidade.

## Próximo passo necessário

Consultar [TESTE_LOCAL.md](TESTE_LOCAL.md) para reproduzir o aceite. O prompt 02
não foi iniciado nesta entrega. Não usar dados reais: autenticação, isolamento de
organizações e RLS continuam planejados para a próxima fase.

Evidências, comandos, versões e arquivos: [relatório da fase 01](docs/VALIDACAO_PROMPT_01.md).
