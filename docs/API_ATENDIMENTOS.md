# API de registros e chamados

Prefixo `/api/v1`. Sessão, organização e papel vêm do servidor. Escritas exigem
CSRF, seguindo [API](API_IDENTIDADE.md). Erros usam RFC 7807
`application/problem+json`: 404 para recurso inacessível, 403 para ação sem
permissão, 409 para revisão/transição/reenvio incompatível e 422 para entrada
inválida. `organization_id`, autoria e carimbos do servidor não são aceitos no
corpo. Regras em [ESTADOS](ESTADOS.md) e [PERMISSOES](PERMISSOES.md).

| Método e rota | Operação |
| --- | --- |
| GET `/assignment-options` | IDs e nomes de integrantes ativos da organização, sem e-mails/papéis |
| POST `/records` | Registro com um destino, opcionalmente rascunho |
| GET `/records` | Meus registros por padrão; `mine=false` respeita a visibilidade do papel |
| GET `/records/reviews` | Finalizações próprias aguardando revisão, mais antigas primeiro, até 50 |
| POST `/records/reviews/confirm` | Confirmação atômica de `items: [{id, revision}]`, até 50 distintos |
| GET/PATCH `/records/{id}` | Detalhe/edição humana antes da confirmação |
| POST `/records/{id}/actions` | `revision`, `action`, motivo e campos condicionais de envio de chamado |
| GET `/records/{id}/versions` | Snapshots em ordem de revisão, ator, ação e data |
| POST `/records/{id}/derive` | `revision` do original e `type` do novo rascunho |
| GET `/clients/{id}/history` | `confirmed_total`, `total`, itens; `include_provisional=false` por padrão |
| POST `/tickets` | Atalho de envio de Record `chamado`; retorna o Ticket criado |
| GET `/tickets` | Fila acessível; filtros `status` e `mine` (responsável atual) |
| GET/PATCH `/tickets/{id}` | Conversa/eventos/intervalos; alteração com `revision` |
| POST `/tickets/{id}/comments` | Comentário imutável com `revision`, `text`, `kind`, `mentioned_user_ids` |
| GET `/notifications` | Até 30 notificações próprias, recentes primeiro, `offset` e contador `unread` |
| POST `/notifications/{id}/read` | Marca própria notificação como lida, idempotente |

Listas de registros/chamados/histórico têm `offset`, `limit` (1–100, padrão 20)
e `total`. Revisões usam página de 50. A UI de notificações consulta as 30 mais
recentes por polling de 15 s; notificações anteriores continuam consultáveis pelo
offset da API. Não há push remoto.

## Criação e revisão

`POST /records`: `client_id`, `type` (`finalizacao`, `chamado`, `conhecimento`),
`texto_original`, opcional `ocorrido_em` com timezone, `capturado_em` não confiável
e `submit` (padrão true). Somente chamado aceita `assignee_id` (padrão autor),
`priority` (padrão normal), `category` (padrão vazio). `POST /tickets` exige envio;
rascunhos de chamado são criados por `/records`.

`PATCH /records/{id}` recebe `revision`, `texto_organizado` humano e,
opcionalmente, `ocorrido_em`. O original e o recebimento são preservados também
por trigger no PostgreSQL. Cada escrita gera versão/auditoria, inclusive envio,
confirmação, devolução, derivação e cancelamento. Ações `processar` e `publicar`
não são atalhos para processamento ou publicação. O conhecimento cria artigo
rascunho vinculado; consulta/publicação usam o [contrato editorial](API_CONHECIMENTO_RELATORIOS.md).

## Repetição e concorrência

Criação e derivação aceitam `Idempotency-Key` de 8–128 caracteres. A chave é
armazenada em hash, no escopo organização/usuário/operação. `/records` e
`/tickets` compartilham o escopo de criação; a derivação tem escopo por original.
Defaults são normalizados antes do fingerprint. Repetição com mesmo payload
retorna o recurso existente (no estado atual), sem duplicar; outro payload com
a mesma chave retorna 409. Sem chave, cada criação é uma nova intenção.
A interface conserva chave e payload após falha de rede, até o formulário mudar.

Advisory lock transacional serializa reenvios da mesma chave; `FOR UPDATE` mais
comparação de `revision` serializa edições do mesmo recurso. Comentários também
incrementam revisão. O cliente deve recarregar após 409, nunca sobrescrever
silenciosamente. Não existe endpoint DELETE para esses recursos.

## Isolamento e trilhas

Migração 0003 aditiva e SQL congelado. Todas as tabelas novas têm RLS FORCE;
referências compostas impedem relacionar clientes/registros/tickets de empresas
distintas. Notificações e recibos têm leitura limitada ao destinatário/usuário,
além do tenant. Runtime só inclui/consulta versões, comentários, eventos,
participantes e recibos; não altera nem apaga essas trilhas. Somente `lida_em`
pode ser atualizado em notificações. Não foram adicionadas dependências.

## Validação humana independente de fidelidade

Exige migração `0009` e a capacidade `text_validation` em `/server-info`.
Não altera os contratos operacionais anteriores e não cria telas novas.

| Rota sob `/api/v1` | Contrato |
|---|---|
| GET `/records/{id}/text-validation` | Estado `nao_validado`/`validado`, versão material atual, conteúdo exato e histórico de validações |
| POST `/records/{id}/text-validations` | `version_id`, `content_hash` devolvidos pela consulta e `reviewed: true`; conferência individual explícita |
| GET `/records/text-validations/pending` | Pendências acessíveis ao usuário, `offset` e `limit` (1–100, padrão 20), `total` e IDs de registro/versão |

Não envie `organization_id`: a sessão fornece esse contexto. Uma versão/hash não
autoriza acesso. Ausência de acesso ao registro retorna 404; conteúdo desatualizado
ou hash divergente retorna 409 em `application/problem+json`, exigindo recarregar e
conferir novamente. Ausência de conferência explícita retorna 422. CSRF continua
obrigatório na sessão web. Outro leitor autorizado pode validar; o próprio autor
também pode, pela política inicial. Isso não concede permissão para editar o autor.

`version` contém `id`, `record_revision`, `content_hash`, `content`, `criado_em`,
`source_version_id`, `source_actor_id` e `source_change`. O cliente deve devolver
ID/hash recebidos; não escolher uma versão antiga nem recalcular o hash de uma
serialização própria. `content.record` guarda os textos original/organizado/ditado,
cliente, tipo, horário do fato, categoria e sistema. `content.transcription` guarda
os textos brutos/normalizados/organizados, segmentos, avisos e seções do último job
com texto disponível, ou null. Assim, áudio de chamado é conferível sem mudar sua
descrição. Processo automático identificado por `source_change` não é revisão humana;
a atribuição legada de ator do worker não representa uma pessoa conferindo o texto.

Cada item em `validations` possui ID, versão/hash, `validated_by` e `validado_em` UTC.
O histórico é imutável. Reenvio pela mesma pessoa/versão retorna o evento existente,
sem duplicar auditoria. Pessoas distintas podem registrar sua própria conferência.
Edição/transcrição material posterior cria versão pendente; validações antigas
permanecem históricas. Conteúdo que volte ao texto anterior também exige nova
conferência, porque o ID da versão é diferente. Simples transição operacional não
altera a versão material. A operação usa lock do registro, como edição e worker.

Validação não altera `status`, `revision`, `revisado_em`, `ocorrido_em`, confirmação
operacional ou resolução do Ticket. `Attachment.validated` continua técnico.
Legado é importado sem ContentValidation: mesmo um registro já confirmado
operacionalmente começa com fidelidade não validada e histórico vazio nesse eixo.
As triggers antigas que bloqueiam edição de conteúdo confirmado são preservadas;
nesses casos continua necessário derivar, conforme o contrato anterior.

Migração adiciona tabelas e importa snapshots, sem alterar fatos anteriores.
Reversão só é permitida com as tabelas novas vazias; com histórico, é bloqueada
antes de apagar dados. Não executar downgrade para descartar validações.
A listagem de pendências é paginada; o histórico individual não tem paginação
nesta versão. Interface específica de conferência e etiquetas permanece pendente.

## Atendimentos contínuos e atividade interna

Disponíveis na API, com migração `0010`; interface específica pendente.
`Attendance` guarda o ciclo operacional usando o ID do registro inicial.
Conteúdo reutiliza `Record`, `RecordVersion`, anexos, fila e validações por versão.
Registros legados não são convertidos automaticamente.

| Método e rota | Contrato |
|---|---|
| `POST /api/v1/attendances` | Abre; `Idempotency-Key` obrigatório, 8–128 caracteres |
| `GET /api/v1/attendances` | Filtros `mine`, `pending`, `status`; `offset` e `limit` (1–100) |
| `GET /api/v1/attendances/{id}` | Registro, atualizações e eventos; listas paginadas por `offset`/`limit` |
| `POST /api/v1/attendances/{id}/updates` | Atualiza/transfere/finaliza; revisão e chave idempotente obrigatórias |

Abertura: `client_id` ou `internal_activity=true`, categoria/sistema opcionais,
`assignee_id` de integrante ativo (padrão: próprio usuário), `texto_original` e
`ocorrido_em`. Atividade interna também funciona em `POST /api/v1/records` com
`type=finalizacao`; chamado/conhecimento sem cliente continuam rejeitados.
Banco e API exigem cliente ou marcador explícito. Nenhum cliente artificial é
criado; relatórios separam `internal_activities` da lista de clientes.

Atualização: `revision`, `texto_original`, `ocorrido_em`, `next_action`,
`retomada_em` e `action` (`atualizar`, `transferir`, `finalizar`). Transferência
exige `assignee_id`; finalização exige `result` não vazio e nenhuma retomada.
Cada atualização cria registro ligado por `origem_record_id`, com ID próprio
para áudio/revisão, preservando o ID do atendimento. Próxima ação ausente vira
vazia; retomada ausente limpa o agendamento. Valores anteriores ficam nos eventos.
Correções de texto usam versões; nunca substituem o relato original.
A ação legada Derivar é recusada no registro inicial e nas atualizações do ciclo,
evitando inserção de histórico fora do controle de revisão do atendimento.
Conversão desses registros em outros fluxos fica para evolução posterior.

Retomada deve ser futura: ciclo `aguardando_retomada`; sem ela, `em_andamento`.
Ao vencer, `pending=true` inclui o atendimento sem transição automática.
Finalizar produz `finalizado`/`finalizado_em`, preserva as datas dos fatos e não
valida texto. Novas atualizações são recusadas com 409. Lock e revisão impedem
perda de dados: envio obsoleto retorna 409. Retry com mesma chave/corpo recupera
a atualização existente mesmo com revisão antiga; resposta traz o ciclo atual.

Gestão consulta/altera na própria empresa; técnico consulta como autor ou
responsável atual e altera somente como responsável. Autor mantém leitura após
transferir, inclusive de atualizações posteriores. Antigo responsável não autor
perde leitura do ciclo completo; autoria dos próprios registros é preservada.
A regra de finalização confirmada compartilhada não libera atendimentos ou suas
atualizações a técnicos sem acesso. RLS/FKs por empresa são obrigatórios;
`organization_id` no corpo é rejeitado.

Áudio: salvar descrição vazia e enviar para a rota de áudio do registro inicial
ou da atualização. Cada registro usa as rotas de fidelidade existentes. Job ativo
anuncia `processando`; após processamento, a versão fica `nao_validado` até
conferência explícita, ou `validado` se o material atual já foi conferido.
Validações anteriores são preservadas. Worker nunca altera o ciclo operacional.
Mock não reconhece fala: fonte vazia produz erro recuperável, preservando registro
e áudio. Reconhecimento real requer o provedor local já suportado; não foi instalado
nem medido nesta implementação. Testes com provedor controlado não comprovam ASR real.

Upgrade preserva fatos/versões. Downgrade somente sem atendimentos nem registros
internos/sem cliente; caso contrário bloqueia antes de remover estrutura.
Usar o comando de migração do projeto, que também reaplica privilégios do runtime.
Evidências: [ciclo](../backend/tests/test_attendance.py),
[migração/legado/RLS](../backend/tests/test_validation_migration.py) e
[validação](../backend/tests/test_content_validation.py).

## Interface disponível

A web oferece painel paginado do ciclo, abertura/atualização por texto ou áudio,
atividade interna, próxima ação/retomada, transferência e resultado. Fila de
fidelidade e revisão individual usam as rotas acima; validar depois preserva o
registro e não altera a resolução. Etiquetas identificam o estado da fidelidade.
Testes reais de interface em [evolution.spec.ts](../web/e2e-identity/evolution.spec.ts).
As menções anteriores à interface pendente descrevem o estado da entrega de API.
## Contexto estruturado de sistema

Criação e edição de registros aceitam `system_id` opcional. Listagens de registros,
chamados e atendimentos aceitam filtro pelo mesmo campo, limitado à empresa e ao
escopo autorizado. Atualizações e derivados herdam os instantâneos históricos do
registro de origem quando não há nova seleção explícita. O texto legado permanece.
Consulte o [contrato do catálogo](API_SISTEMAS.md) para inativação e reconciliação.
