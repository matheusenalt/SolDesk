# API de tarefas

Tarefa é uma ação futura simples, independente do ciclo de chamados, atendimentos,
áudio e fidelidade do texto. Concluir uma tarefa não conclui sua origem nem valida
conteúdo. Esta entrega oferece dados, API e testes; interface web específica pendente.

## Rotas e campos

Todas as rotas exigem autenticação; mutações usam CSRF e `Idempotency-Key` de 8 a
128 caracteres. A organização vem da sessão no servidor, nunca do corpo enviado.

| Método e rota | Uso |
|---|---|
| POST /api/v1/tasks | Criar tarefa, resposta 201 |
| POST /api/v1/tasks/quick | Criar retorno a partir de atendimento ou chamado, resposta 201 |
| GET /api/v1/tasks | Listar com paginação e filtros |
| GET /api/v1/tasks/options | Pessoas ativas, equipes permitidas e fuso atual |
| GET /api/v1/tasks/{id} | Consultar tarefa autorizada |
| GET /api/v1/tasks/{id}/history | Histórico paginado, ordenado por revisão |
| POST /api/v1/tasks/{id}/actions | Editar, iniciar, assumir, transferir, concluir ou cancelar |

Criação aceita `title` (1–200), `description` (até 20.000), `priority`
(`baixa`, `normal`, `alta`, `urgente`), `assignee_id` **ou** `team_id`,
`prevista_para`, `agendado_em`, `client_id`, `system_id`, `attendance_id` ou
`ticket_id`. IDs opcionais devem pertencer à empresa autenticada. Sem responsável
ou equipe explícitos, atribui ao criador. Cliente é opcional, inclusive em tarefa
interna. Sem cliente ou sistema de origem, não inventa cadastro nem classificação.

O vínculo de origem é opcional e exclusivo: atendimento ou chamado. Na criação,
o usuário precisa poder consultar essa origem. Cliente/sistema são herdados;
contexto explícito divergente é rejeitado. Origem histórica pode preservar sistema
inativo; uma seleção independente exige sistema ativo. Criar uma tarefa não concede
acesso à origem a outro usuário e não altera suas permissões.

## Equipes e permissões

O projeto já possui [Team](../backend/app/insight_models.py), administração e membros
em [report_routes](../backend/app/report_routes.py). A implementação reutiliza essa
estrutura; não cria outra arquitetura de equipes. Somente integrantes ativos da
organização podem ser responsáveis. Técnicos podem atribuir a pessoas ativas e às
equipes das quais participam; gestão pode atribuir a qualquer equipe da empresa.

Administrador/gestor consultam e operam todas as tarefas da organização. Técnico
consulta tarefas que criou, que lhe foram atribuídas ou que pertencem às suas
equipes atuais. Para operar tarefa individual precisa ser responsável. O criador
mantém consulta após transferir, mas não pode operar só por ter criado. Tarefa da
equipe deve ser assumida por um membro para operação individual; gestão também
pode operar/transferir. Assumir troca equipe por responsável, preservando de/para
no histórico. Alterações de composição de equipes afetam o acesso a tarefas ainda
da equipe; não desfazem tarefas já assumidas.

## Estados, versões e reenvio

`pendente` → `em_andamento` → `concluida`. Conclusão direta de pendente é permitida:
uma única ação com revisão atual, sem aprovação editorial ou validação de solução.
`pendente` e `em_andamento` podem virar `cancelada`, sempre com justificativa.
Terminais não aceitam nova edição, transferência ou reabertura nesta versão.

Corpo de ação: `revision` atual, `action` e `reason` opcional (obrigatória no
cancelamento). `transferir` aceita exclusivamente responsável/equipe; `editar`
aceita título, descrição, prioridade e datas. Demais ações não aceitam esses campos.
Para trocar horário marcado por dia inteiro, editar `agendado_em: null`, com data
opcional. Para trocar o instante, enviar offset explícito; a data local é calculada.

Cada mudança incrementa revisão e grava ator, instante UTC, antes/depois e razão
em TaskEvent e auditoria. Eventos e recibos são imutáveis, inclusive no banco.
Atualização concorrente gera 409; se outro membro assumir e o usuário perder o
escopo de leitura, a resposta é 404. Apenas uma ação vence a mesma revisão.

Chave repetida pelo mesmo ator/empresa com operação e corpo idênticos devolve o
instantâneo da resposta original, sem nova tarefa/evento. Chave com corpo ou ação
divergentes gera 409. O recibo pode conter indicadores temporais da primeira
resposta: consultar GET para situação atual. Novas chaves representam novas ações
explícitas; não existe geração automática de uma tarefa por atendimento.

## Datas e fuso

O fuso IANA fica em `Organization.timezone`, configurado na organização pela
[API de identidade](API_IDENTIDADE.md). Horários persistidos são UTC.

- Dia inteiro: `prevista_para` é uma data civil; `agendado_em` ausente/nulo. Não
  converter a data em meia-noite UTC. Torna-se atrasada no dia seguinte da empresa.
- Horário marcado: `agendado_em` exige offset. `prevista_para`, se enviada, deve
  coincidir com a data desse instante no fuso da empresa. Atraso começa após o instante.
- Mudança do fuso mantém a data civil de tarefa de dia inteiro; um instante marcado
  é exibido no fuso atual. GET expõe `timezone`, `data_local`, `dia_inteiro`,
  `atrasada` e `periodo` (`passada`, `hoje`, `futura`). Terminais nunca são atrasadas.

Criação rápida recebe exatamente `attendance_id` ou `ticket_id`, `shortcut`
(`hoje`, `amanha`, `proxima_semana`: +0/+1/+7 dias civis), `horario` local opcional,
prioridade e atribuição opcionais. Título padrão: “Retornar ao cliente”. Sem horário
gera dia inteiro. Horário local inexistente/ambíguo por transição de fuso é rejeitado;
usar criação normal com instante e offset explícitos nesses casos.

Listagem: `mine`, `team_id`, `assignee_id`, `priority`, `status`, `date_from`,
`date_until`, `offset` e `limit` (1–100). Filtro `period=hoje|atrasadas|futuras`
seleciona tarefas abertas. Hoje considera a data local; atrasadas inclui horários
vencidos do próprio dia; futuras são datas posteriores a hoje. Portanto hoje e
atrasadas podem se sobrepor. Período por datas usa o fuso atual da organização.

## Persistência e evidências

[Migração 0012](../backend/migrations/versions/0012_tasks.py) acrescenta três tabelas,
índices e chaves compostas, sem alterar dados de negócio anteriores. RLS forçada
isola empresas; FKs impedem referências cruzadas. Unicidade composta acrescentada
a Team e Attendance permite as novas FKs. Reversão só se as três tabelas estiverem
vazias; existindo dados, bloqueia antes de remover estrutura.

- [Modelos](../backend/app/task_models.py) e [rotas/regras](../backend/app/task_routes.py).
- [Testes funcionais, permissões, fusos e concorrência](../backend/tests/test_tasks.py).
- [Migração isolada e RLS em duas empresas](../backend/tests/test_tasks_migration.py).
- [Resultados executados e pendências](../STATUS.md).

Fora deste escopo: recorrência, notificações novas, calendário e interface específica.
