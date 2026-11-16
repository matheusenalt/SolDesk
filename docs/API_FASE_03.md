# API da fase 03

Prefixo `/api/v1`. Sessão, organização e papel vêm do servidor. Escritas exigem
CSRF, seguindo [API fase 02](API_FASE_02.md). Erros usam RFC 7807
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
retornam 409 nesta fase. O conhecimento cria somente artigo rascunho vinculado;
não há endpoint de consulta/publicação da base de conhecimento.

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
