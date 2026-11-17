# Calendário interno — API

O calendário é uma projeção consultada diretamente em Task, Ticket e Attendance,
mais CalendarEvent para eventos criados na agenda. Não há cópia de tarefa, chamado
ou atendimento para tabela de calendário. Não depende de Nextcloud ou outro serviço.
Interface mensal/semanal/diária e navegação acessível ainda pendentes da Parte B.

## Consulta unificada

`GET /api/v1/calendar?date_from=2026-11-01&date_until=2026-12-01`

Intervalo civil no fuso IANA de `Organization.timezone`, com início inclusivo e
fim exclusivo. Aceita 1–93 dias; `offset` >= 0 e `limit` 1–1000 (padrão 100).
Filtros opcionais: `assignee_id`, `team_id`, `include_cancelled` (padrão falso).
Responsável e equipe são filtros adicionais; nunca ampliam permissões de origem.
Equipe inclui tarefas ainda da equipe e itens de seus responsáveis atuais.
Técnico só pode filtrar equipe da qual participa.

Retorna `total`, `timezone`, intervalo e `items`, ordenados por data, início e ID
estável. Cada item contém `id` com namespace, `type`, `origin_id`, `title`,
`description`, `data`, `inicio_em`, `fim_em`, `client_id`, `assignee_id`, `team_id`,
`status` e `revision`. Ausência de início significa dia inteiro; fim é opcional.
O frontend deve abrir a origem por `type`/`origin_id`, mantendo sua autorização.

| Fonte | Data projetada | Permissão reutilizada |
|---|---|---|
| task | Data civil ou agendado_em | Autor, responsável, equipes atuais ou gestão |
| ticket | prazo_em opcional | Solicitante, responsável, participantes ou gestão |
| attendance | retomada_em | Autor do registro inicial, responsável ou gestão |
| event | Data civil ou intervalo inicio_em/fim_em | Autor, responsável, participantes ativos ou gestão |

Sem prazo/retomada, não há item correspondente. Cada fonte gera no máximo um item
por objeto, sem juntar versões ou participantes às linhas projetadas. `task:ID`
é diferente de `ticket:ID`: uma tarefa vinculada e um prazo de chamado são dois
fatos diferentes, sem duplicar qualquer um deles. Mudar a origem reflete na próxima
consulta, sem job de sincronização. Cancelados ficam ocultos por padrão; tarefas
concluídas e chamados resolvidos/encerrados preservam seu status para consulta.

Instantes são UTC no banco e convertidos para a data local na apresentação.
Predicados temporais comparam os instantes aos limites do intervalo convertidos
com o fuso da empresa, sem transformar a coluna filtrada em data. Datas civis
permanecem datas. Evento que atravessa meia-noite aparece uma vez quando sobrepõe
o intervalo; fim é exclusivo. Evento sem fim é um ponto no início informado.

## Eventos próprios

| Método e rota | Ação |
|---|---|
| POST /api/v1/calendar/events | Criar, resposta 201 |
| GET /api/v1/calendar/events/{id} | Consultar evento autorizado |
| PUT /api/v1/calendar/events/{id} | Substituir conteúdo com revisão atual |
| POST /api/v1/calendar/events/{id}/cancel | Cancelar com justificativa e revisão |
| GET /api/v1/calendar/events/{id}/history | Histórico paginado por revisão |

Mutações exigem CSRF e `Idempotency-Key` (8–128). Autenticação e organização vêm
do contexto no servidor. Erros seguem `application/problem+json`.

Conteúdo: `title` (1–200), `description` (até 20.000), `data`, `inicio_em`, `fim_em`,
`assignee_id`, `participant_ids` (até 200, únicos após normalização), `client_id`.
Cliente é opcional. Responsável e participantes precisam ser membros ativos da
empresa. Sem responsável, criação usa o autor; edição preserva o responsável atual.
PUT é substituição completa: campos opcionais de conteúdo omitidos são removidos,
inclusive participantes e cliente. Enviar `revision` atual no PUT.

Dia inteiro exige `data` sem instantes. Evento com horário exige offset explícito
em `inicio_em`; a data, se enviada, deve coincidir no fuso da organização. `fim_em`
sem início ou anterior/igual ao início é rejeitado. Não inventa duração automática.

Autor, responsável e gestão editam/cancelam; participante tem consulta. Remover
participante revoga sua consulta futura, salvo se for autor/responsável/gestão.
Remoção desativa o vínculo sem apagar versões anteriores. Cancelamento exige
`{revision, reason}` e impede novas edições; histórico permanece acessível ao
escopo atual. Cada mudança preserva ator, instante UTC, antes/depois e revisão.

Chave repetida pelo mesmo ator/empresa, operação e corpo devolve a resposta original,
sem novo evento ou versão. Outra operação/conteúdo com a chave retorna 409.
Revisão obsoleta também retorna 409; usuários sem escopo recebem 404.

## Prazo de chamado

O código anterior não tinha prazo persistido. A migração acrescenta somente
`Ticket.prazo_em` opcional, sem backfill. `PATCH /api/v1/tickets/{id}` aceita
`{revision, prazo_em}` com instante/offset ou null para remover. Responsável ou
gestão podem alterar; mesma regra de revisão, evento e auditoria já existente.
O novo prazo não muda abertura, resolução ou encerramento, nem implementa o fluxo
futuro de aprovação de chamados. Não há notificação automática adicional.

## Índices e EXPLAIN executado

Teste seguro em PostgreSQL isolado com 4.000 tarefas, 2.000 eventos próprios,
1.000 chamados e 1.000 retomadas fictícias distribuídos por 1.000 dias. Após ANALYZE,
consulta de 02/01/2030 a 04/01/2030 retornou 16 itens únicos; páginas de cinco não
se sobrepuseram. Execução como usuário restrito, com contexto de empresa e RLS.

Comando aplicado a cada SELECT real de [sources](../backend/app/calendar.py):

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT ...;
```

Resumo dos planos observados no ensaio focado de 17/11/2026:

```text
task:       Result → Bitmap Heap Scan → BitmapOr
              Bitmap Index Scan task_calendar_day (4 linhas)
              Bitmap Index Scan task_calendar_instant (4 linhas)
ticket:     Result → Bitmap Heap Scan
              Bitmap Index Scan ticket_calendar_instant (2 linhas)
attendance: Result → Nested Loop
              Index Scan attendance_calendar_instant (2 linhas)
              Index Scan record_organization_id_id_key
event:      Result → Bitmap Heap Scan → BitmapOr
              Bitmap Index Scan calendar_event_calendar_day (2 linhas)
              Bitmap Index Scan calendar_event_calendar_start (4 candidatas)
```

Saídas finais: task 8, ticket 2, attendance 2, event 4. Tempos locais observados
na rodada focada: 0,266 / 0,058 / 0,097 / 0,110 ms, respectivamente. São medições
desses SELECTs nesse teste, sem custo HTTP, contagem unificada ou garantia de
produção. Cache, distribuição de dados, tamanho da empresa e escopo técnico mudam
o plano. Não é benchmark de capacidade nem previsão de RAM/CPU. O teste imprime
resumo reproduzível; não força índice nem falha por um tempo de execução específico.

## Migração, segurança e evidências

[0013](../backend/migrations/versions/0013_calendar.py) acrescenta eventos,
participantes, versões e recibos; RLS forçada e FKs compostas impedem referência
entre empresas. Versões e recibos são append-only. Não altera fontes nem horários
anteriores; prazo novo começa nulo. Downgrade só com tabelas novas vazias e nenhum
prazo preenchido, bloqueando antes de remover qualquer estrutura se houver dados.

- [Modelos](../backend/app/calendar_models.py), [projeção](../backend/app/calendar.py)
  e [rotas](../backend/app/calendar_routes.py).
- [Testes, volume e EXPLAIN](../backend/tests/test_calendar.py).
- [Migração isolada com duas empresas](../backend/tests/test_calendar_migration.py).
- [Resultados executados e pendências](../STATUS.md).

## Integração futura — fora do escopo

CalDAV/Nextcloud se encaixariam em um adaptador opcional por organização sobre IDs e revisões das fontes.
ICS seria uma exportação autorizada da projeção, sem cópia obrigatória ou URL pública tratada como credencial.
Notificações usariam alterações das origens/eventos, com idempotência; nenhuma dessas integrações foi implementada.
