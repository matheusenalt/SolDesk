# Validação do Prompt 05 — conhecimento, busca e gestão

Data: 16/11/2026. Escopo exclusivo da Fase 05. [METRICAS](METRICAS.md) foi escrito
antes do código. Fase 06 não iniciada. Sem dados/fontes de empregadores ou de
outros projetos, sem serviço de IA externo e sem nova dependência.

## Funcionalidades implementadas

- Artigo estruturado por organização, categoria/sistema, geral/restrito a cliente,
  causa ausente identificada, versão do template e origem navegável autorizada.
- Rascunho → revisão → publicado, devolução comentada, arquivamento e reabertura;
  versões/snapshots/diferenças com ator/data. Política por organização, admin/gestor
  revisam por padrão, autopublicação desligada; duas conferências humanas antes de
  publicar, incluindo incerteza/código fiscal/possível credencial. Worker não publica.
- Busca PostgreSQL português/unaccent + trigramas + substring exata escapada de
  código/mensagem. GIN/índices de filtro, trechos destacados sem HTML, páginas e
  filtros de publicação/categoria/sistema/cliente. Rascunhos/fila separados.
- Restritos no contexto do cliente, excluídos das sugestões de outros clientes;
  sugestões identificadas como não diagnóstico. Consultas agregadas sem leitor.
- Relatórios diários/semanais/mensais/acumulados/livres no fuso, comparação anterior
  e filtros cliente/pessoa/equipe/categoria/sistema. Separação confirmado/pendente,
  abriu/assumiu/comentou/encaminhou/movimentou/resolveu/encerrou/reabriu/terceiros,
  ações/tickets únicos, mediana/P90/n bruto/líquido e pausas sem dupla subtração.
- Classificações declaradas/recorrência, prioridade dos tickets, clientes e consultas,
  fila atual/idade/esclarecimento, carga temporal, histórico paginado e equipes atuais.
  Pessoas alfabeticamente por padrão, sem avaliação, pontuação ou ranking automático.
- UI real responsiva, gráfico rotulado com tabela equivalente, vazio explícito e
  aviso de que estatísticas refletem somente registros. Técnico só recebe números
  próprios, inclusive CSV auditado, BOM/aspas/apóstrofo e histórico completo limitado.
- Migração 0005 aditiva, RLS FORCE, FKs tenant, triggers de preservação, concessões
  mínimas; configurações de nome/fuso preservam políticas existentes.

## Testes e resultados observados

| Validação | Resultado |
| --- | --- |
| PostgreSQL real `docker compose --profile test run --rm tests` | 65 aprovados; repetição final após heartbeat: 133,69 s, sem skips |
| Ruff check/format backend | Aprovados, 36 arquivos |
| ESLint / Prettier / TypeScript / Vite | Aprovados; build local e imagem Docker |
| Vitest | 6 aprovados |
| Tokens/contraste | 32 pares aprovados, sem deriva |
| Diagnósticos do editor | Nenhum erro nos diretórios de API e web consultados |
| Licenças | Auditoria repetida: 52 Python e 272 npm; locks preservados, sem dependência nova |
| AGPL oficial | SHA-256 `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`, inalterado |
| Setup PowerShell / test-compose | Build/saúde, migrações repetidas, UUID preservado após restart, proxy/OpenAPI, não root e volume PostgreSQL sem porta aprovados |
| E2E autenticado Edge | 32 cenários aprovados: 30 na suíte completa em 3,6 min + 2 repetições focadas em 25,9 s após corrigir falso positivo da asserção; sem skips obrigatórios |
| E2E instalação Edge | 4 aprovados em 32,7 s contra Nginx/API/PostgreSQL |
| Bash setup | Sintaxe bash -n aprovada; execução Ubuntu será conferida no Actions |
| Exemplos | JSON e CSV obtidos da API real, contagens conferidas, somente dados fictícios em [exemplos](exemplos/README.md) |
| GitHub Actions implementação | completed/success: jobs checks e postgres; 65 pytest PostgreSQL em 45,14 s e 32 E2E Chromium Ubuntu em 2,2 min, sem skips nessas suítes |

22 casos parametrizados novos cobrem estados editoriais/versões/triggers,
autopublicação padrão/configurada, comentário obrigatório, código/acento/cliente,
índices PostgreSQL, HTTP/RLS entre empresas, consultas sem leitor, São Paulo/Tóquio,
limites de dia/semana/mês e DST, autoria A/B, resolução/encerramento/reabertura,
mediana/P90/n/pausas, escopo técnico/filtros/equipes/CSV/auditoria, fórmulas com
controles/largura cheia, nomes maliciosos fictícios, estado vazio/carga e exportação
de 101 registros sem truncar na página de 100. 43 regressões anteriores preservadas.

Navegador acrescenta 4 cenários × desktop/emulação móvel: devolução/edição/reenvio/
conferência/publicação/busca/destaque/versões/origem; cliente restrito e arquivamento;
relatórios reais/CSV/fatos separados/tabela alternativa; técnico próprio/equipe.
Regressões anteriores incluem identidade, chamados, mídia e parada real do worker.
Sem traces autenticados; credenciais aleatórias somente em ambiente/memória.

## Problemas identificados e corrigidos

- Busca: bind `folded` era incluído no ORDER BY depois de aplicar parâmetros;
  produzia 500. Corrigida ordem e repetidas consultas reais de código/acento.
- Equipes: import de select ausente após inclusão de lock; teste PostgreSQL
  reproduziu 500, import corrigido e suíte completa passou.
- Nome/fuso sobrescreviam configurações aninhadas de mídia/conhecimento. Regressão
  reproduzida; PATCH preserva/mescla parâmetros fornecidos, rotas próprias protegem políticas.
- Mudança apenas de hash no mesmo documento não abria artigo; hashchange/popstate
  passam a atualizar a navegação, mantendo autorização do servidor.
- Primeiro CSV escapava apenas alguns controles; ampliado para espaços/controles/
  BOM e caracteres de largura cheia, com aspas em todas as células. Histórico da
  exportação separado da paginação visual, testado com 101 registros.
- RQ ocioso podia ultrapassar 120 s sem heartbeat e setup recusava a saúde.
  API instalada conferida: dequeue_timeout = worker_ttl - 15. Worker usa TTL 90 s,
  limite bloqueante 75 s; saúde continua exigindo heartbeat recente, sem desabilitar teste.
- Seletores novos de teste usavam texto completo de label contendo opções/textarea;
  ajustados para papéis/nomes acessíveis. Asserções respeitam prefixo do relato e
  abrem o detalhe da distribuição em vez de clicar no caption da tabela alternativa.
- A checagem de ausência de avaliação confundia "posição" com "composição" na
  explicação das equipes. Limites de palavra corrigidos; ambos os cenários de
  relatório repetidos e aprovados, incluindo download CSV real e auditoria.

## Limites e pendências

- Agregação inicial em memória com limites explícitos/422, sem benchmark de carga
  produtiva. Categoria/prioridade/equipe atuais não reconstroem histórico ausente.
  Pendência atual por dia do fato não é fotografia histórica da revisão.
- Restrição editorial por cliente é contexto de busca/sugestão, não ACL entre
  membros com acesso a todos os clientes da empresa. Origem mantém autorização própria.
- Avisos fiscais/credenciais são heurísticos, não certificação; revisão humana
  obrigatória. CSV inicial neutraliza fórmulas; conversões/regravações por qualquer
  aplicativo de planilha não são certificadas universalmente.
- Opcionais da Fase 04 continuam explícitos: benchmark/modelo Whisper real,
  microfone físico/Safari/iOS/Firefox, antivírus real, S3 de produção. Não são
  declarados aprovados por testes mock/emulação. Auditoria externa/produção pendentes.
- Aviso upstream de depreciação TestClient/httpx permanece, sem falha de teste.

## Publicação

Aceites obrigatórios locais aprovados. Revisão de fontes/diff/status e busca por
padrões de chaves privadas/tokens sem ocorrência nos arquivos publicáveis. `.env`,
`.venv`, `.tools`, node_modules/resultados/cache/mídia permanecem ignorados;
locks e texto AGPL preservados, inventários repetidos sem diferenças. Nenhuma
fonte/dado de outro projeto/empregador foi acessado ou copiado.
Busca textual não substitui auditoria independente. Origin oficial conferido,
main sincronizada com origin/main (0/0) antes do commit; identidade Git configurada.
Implementação publicada: [`160297a4b61c1b21389833b553a09c2122da423f`](https://github.com/matheusenalt/SolDesk/commit/160297a4b61c1b21389833b553a09c2122da423f),
`feat: implementa fase 05 do SolDesk`. Push normal para main oficial concluído,
avanço de `75a9018` para `160297a`, sem force; main/origin main sincronizadas (0/0).
[Actions da implementação](https://github.com/matheusenalt/SolDesk/actions/runs/43928535399)
concluído com **completed/success**, jobs checks e postgres aprovados. Logs
conferidos: **65 pytest PostgreSQL aprovados em 45,14 s** e **32 Playwright
Chromium Ubuntu aprovados em 2,2 min**, incluindo parada/retomada real do worker,
CSV e revisão editorial; sem skip nessas suítes. Lint/formatação, tokens, testes
web, build e setup Bash aprovados. O job rápido pode pular testes que dependem de
PostgreSQL; eles foram executados integralmente no job próprio, não contados por skip.
Nenhum aceite obrigatório local pendente; limites opcionais acima continuam
explícitos. Não avançar para o Prompt 06.

Arquivos principais: [conhecimento](../backend/app/knowledge.py),
[relatórios](../backend/app/reports.py), [migração](../backend/migrations/versions/0005_knowledge_reports.py),
[testes PostgreSQL](../backend/tests/test_knowledge_reports.py),
[UI de conhecimento](../web/src/KnowledgeArea.tsx),
[UI de relatórios](../web/src/ReportArea.tsx),
[E2E](../web/e2e-identity/insights.spec.ts), [métricas](METRICAS.md) e
[exemplos](exemplos/README.md), além de README/STATUS/arquitetura/permissões/estados.
**Fase 05 completamente aprovada no escopo obrigatório padrão**, localmente e no CI.
