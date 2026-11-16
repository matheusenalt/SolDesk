# Validação do Prompt 03

Executada em 16/11/2026, Windows/PowerShell, Docker Desktop/WSL 2,
PostgreSQL 17, Node 22.23.5, Python 3.13 e Edge headless. Somente contas,
organizações, clientes e relatos fictícios. Não é aprovação de produção.

## Implementado

- Relato único com destinos finalização/chamado/conhecimento, edição humana e
  snapshots, derivação ligada ao original, `revision` e recibos de idempotência.
- Tempos separados: fato ajustável antes de confirmar, recebimento imutável,
  captura não confiável, revisão humana. Processamento/publicação reservados.
- Confirmação exclusivamente pelo autor, individual/lote atômico; histórico
  confirmado separado de provisórios, fila ordenada por idade e destaque 24 h.
- Chamado imediato, inclusive urgente, código por empresa, atribuição/transferência,
  prioridade/categoria, conversa e menções, esclarecimentos e intervalos de espera,
  resolução/encerramento e reabertura com histórico do mesmo ticket.
- Rascunho de artigo, notificações individuais/polling/leitura, interfaces reais
  responsivas e strings centralizadas. Nenhuma IA, upload ou autopublicação.
- Migração 0003 aditiva e esquema congelado, RLS FORCE, FKs por organização,
  trigger de imutabilidade e privilégios de inclusão/leitura nas trilhas.
  Nenhuma nova dependência, tecnologia ou serviço externo.

## Verificações executadas

| Verificação | Resultado observado |
| --- | --- |
| `ruff check backend scripts/tokens.py scripts/audit_licenses.py` | Aprovado |
| `ruff format --check` nos mesmos alvos | Aprovado, 23 arquivos |
| `python scripts/tokens.py --check` | Aprovado, 32 pares de contraste e ausência de deriva |
| Web: lint, formatação, build TypeScript/Vite, `npm test` | Aprovados, 6 Vitest |
| `scripts/setup.ps1`, builds Docker e inicialização dos serviços | Aprovados, migração 0003 no volume existente |
| `docker compose --profile test run --rm tests` após build | **24 pytest aprovados em 22,28 s**, nenhum ignorado |
| Playwright `playwright.identity.config.ts` com API real e Edge | **12 aprovados em 42,1 s**, desktop/emulação móvel, após o último ajuste de navegação |
| `scripts/test-compose.ps1` | Aprovado: migrações repetidas, reinício, UUID preservado, proxy, HTTP 200, usuários não root, volume PostgreSQL e ausência de porta do banco no host |
| `npm run test:e2e` contra Nginx/API/PostgreSQL | **4 aprovados em 8,7 s**, desktop/emulação móvel |
| Proxy do perfil dev | server-info acessível, mesmo UUID e capabilities de registros/chamados/notificações |
| Revalidação após estabilizar a comparação temporal do teste | 9 testes de operação aprovados em 11,72 s; Ruff e formatação aprovados |
| `npm audit --omit=dev` | Zero vulnerabilidades informadas para dependências de runtime |

Os 24 pytest incluem 5 regressões de instalação, 10 da fase 02 e 9 desta fase.
Aceites específicos: fato/envio às 14:35 e revisão às 17:50 com tempos preservados;
ajuste auditado antes/depois e futuro rejeitado; pendentes fora da contagem;
administrador impedido de confirmar outro autor; lote com conflito integralmente
desfeito; chamado normal/urgente direto; transições inválidas; quem resolve/encerra
distintos; reabertura no mesmo ticket; dois intervalos de espera e comentários
preservados; menção/transferência; UUIDs e SQL sem filtro bloqueados entre empresas;
notificações próprias também protegidas no mesmo tenant; cancelamento justificado
sem exclusão; trigger de recebimento e permissão de versão somente leitura/inclusão.

Concorrência real com duas conexões comprovou que a mesma chave cria um único
registro e duas edições sobre a mesma revisão resultam em 200/409. Reenvio pelas
rotas `/records` e `/tickets` compartilha o recibo. Derivar preserva horário e
original. Autor do chamado pode encerrá-lo resolvido, mas não aproveitar essa
permissão para transferir ou mudar seus dados operacionais.

Os seis cenários autenticados, repetidos em dois viewports, cobrem os três
fluxos novos (revisão/histórico/derivação com precisão de segundos e milissegundos;
urgente/esclarecimento/resposta/resolver/encerrar/reabrir; lote/notificações) e
três regressões de clientes/convites/senha temporária. Credenciais aleatórias
foram passadas pelo ambiente e sessões reaproveitadas em memória; sem traces
autenticados nem desativação de rate limit. Largura móvel e localStorage verificados.

## Problemas encontrados e corrigidos

- Edição de texto na UI reenviava o horário com precisão de minutos. Corrigida
  para omitir o campo quando não alterado; E2E comprovou preservação de frações.
- Seletores de teste com labels envolvendo opções/textarea preenchida não
  localizavam o campo pelo texto exato. Rótulos ARIA explícitos adicionados;
  suíte autenticada final passou integralmente.
- Encerramento por quem abriu poderia carregar mudança de responsável/prioridade
  na mesma requisição. Agora alterações operacionais exigem a permissão própria,
  com teste de regressão; UI limita controles e opções conforme o papel.
- Imports de fixtures novas exigiram ordenação Ruff. Corrigidos e revalidados.
- Navegação para o histórico de um cliente recém-criado usava uma lista já
  carregada enquanto Atendimentos estava oculto. A lista agora é atualizada ao
  abrir a área, incluindo o cliente selecionado mesmo fora da primeira página;
  navegação repetida para o mesmo cliente também foi corrigida e testada.
- Comparação do original derivado exclui somente a idade calculada, evitando
  depender de o relógio continuar no mesmo segundo; os campos persistidos são
  comparados integralmente.

## Revisão de publicação e limites

LICENSE preservado: SHA-256
`0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`.
Nenhum pacote ou lock mudou, mantendo o inventário/revisão de
[LICENCAS](LICENCAS.md). Código novo próprio, usando bibliotecas instaladas,
sem copiar fontes/dados de terceiros ou de outros projetos.

`git status` e diff revisados, sem arquivos alheios à fase. Busca de padrões de
chaves privadas/tokens não encontrou correspondências nos arquivos da fase;
essa busca não substitui auditoria de segurança completa. `.env`, `.venv`,
`.tools`, node_modules, caches e resultados de teste permanecem ignorados.
Locks necessários preservados. `origin` oficial e `main` conferidos;
`git fetch origin` mostrou 0 commits de divergência antes do commit.

Áudio/arquivos/processamento são fase 04; publicação/busca/relatórios, fase 05.
Prazo rígido de revisão continua em aberto. A UI mostra as 30 notificações
recentes; anteriores têm paginação na API. Auditoria completa de segurança e
operação produtiva permanecem pendentes gerais. Há um aviso upstream de
depreciação TestClient/httpx, sem teste ignorado ou falha.

## Publicação e validação remota

Implementação enviada à `main` oficial, sem force push:
[fd415f740a59862d00758e5b0f852f1796d84145](https://github.com/matheusenalt/SolDesk/commit/fd415f740a59862d00758e5b0f852f1796d84145).
Push concluído; SHA remoto conferido por `git ls-remote`, histórico sincronizado
e árvore local limpa depois do envio.

[GitHub Actions 43872972449](https://github.com/matheusenalt/SolDesk/actions/runs/43872972449)
concluído com sucesso nos jobs `checks` e `postgres`. Logs do job PostgreSQL
confirmam **24 pytest aprovados em 11,65 s** e **12 Playwright aprovados em
24,2 s** com Chromium desktop/emulação móvel. Setup Bash, migração desde banco
isolado, instalação Cloud, builds, Ruff, ESLint, formatação, tokens e testes
unitários também aprovados no Ubuntu do runner.

Critérios obrigatórios da fase 03 aprovados local e remotamente. As limitações
de produção e funções de fases futuras acima não foram apresentadas como prontas.
Parar nesta fase, sem iniciar o Prompt 04 automaticamente.
