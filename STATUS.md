# Status do SolDesk

Atualizado em 15/11/2026. **Fase 01 implementada, com aceite de infraestrutura
pendente. As fases 02–06 não foram implementadas.** Não pronto para produção.

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

## Parcial / não validado

- Dockerfiles, Compose padrão/dev, PostgreSQL e setup criados, mas **não executados**
  em contêineres: Docker não encontrado e WSL não instalado nesta máquina.
- YAML e invariantes de exposição de portas conferidos por Python; isso **não é**
  `docker compose config`, build de imagens ou teste do daemon.
- PowerShell: sintaxe válida e interrupção clara sem Docker comprovadas. Bash:
  sintaxe conferida com `bash -n`; setup completo Linux não executado.
- Reinício de contêineres e persistência do volume PostgreSQL ainda pendentes.
- CI criada, não executada no GitHub. pip-audit/gitleaks e auditoria completa de
  segurança são pendentes, previstos para o fechamento; `npm audit` não os substitui.
- pytest emite aviso upstream de depreciação do transporte httpx no TestClient.

## Planejado

02: autenticação, organizações, equipe, clientes, auditoria e RLS com papel separado.
03: registros, chamados, notificações, tempos e revisões.
04: áudio, Redis/worker, storage e processamento.
05: conhecimento, busca e métricas.
06A: Expo/mobile e QR; 06B: conectores mock, ponta a ponta e privacidade.

## Próximo passo necessário

Verificação para publicação: 5 testes pytest, 3 Vitest e 4 Playwright novamente
aprovados, assim como lint, formatação, build web e tokens. Licença AGPL v3 somente
aprovada pelo titular e aplicada; revisão de dependências em [LICENCAS.md](docs/LICENCAS.md).
Publicação autorizada com as pendências documentadas. WSL 2 e Docker Desktop
localizados e daemon consultado com sucesso; o aceite Compose ainda será executado.
Isso não encerra o aceite de infraestrutura nem aprova as pendências abaixo.

Configurar WSL 2 e Docker Desktop (pode exigir administrador/reinicialização),
iniciar Docker e seguir [TESTE_LOCAL.md](TESTE_LOCAL.md). Executar o aceite da
fase 01 com PostgreSQL antes de avançar. Por determinação mais recente do titular,
o prompt 02 só começa quando os critérios obrigatórios da fase 01 estiverem aprovados.

Evidências, comandos, versões e arquivos: [relatório da fase 01](docs/VALIDACAO_PROMPT_01.md).
