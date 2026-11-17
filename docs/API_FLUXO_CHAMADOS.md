# Prazos, rastreabilidade e conclusão de chamados

Evolução do fluxo existente, sem reescrever estados/eventos antigos. A interface
gerencial completa continua pendente. O formulário legado ganhou apenas o campo
necessário para descrição/justificativa, sem substituir os painéis atuais.

## Equivalência e migração

| Estado legado preservado | workflow_state derivado no banco |
|---|---|
| aberto | novo |
| em_andamento / reaberto | em_andamento |
| aguardando_esclarecimento / aguardando_terceiros | aguardando_retorno |
| resolvido | aguardando_validacao |
| encerrado | concluido |
| cancelado (novo) | cancelado |

As migrações 0014/0014a acrescentam estado gerado, descrição de conclusão,
autoaceite, última interação e recibos. Não renomeiam estados, alteram versões
antigas ou inventam descrição para conclusão legada. Prazo opcional já existe.
A última interação legada deriva dos eventos/comentários registrados, com abertura
como fallback. Horários originais permanecem intactos. Reversão bloqueia se houver
cancelamento, conclusão nova ou recibos; extensão vazia pode reverter.

## Ações e aceite

`POST /api/v1/tickets/{id}/actions` exige sessão, CSRF, `Idempotency-Key` e corpo:
`{revision, action, description?, reason?}`. Ações: iniciar, aguardar_retorno,
retomar, concluir, aceitar, devolver, reabrir, cancelar. Transições inválidas geram
409. Revisão obsoleta também gera 409; ação idêntica com mesma chave retorna o
resultado original, sem evento extra. Chave reutilizada com outro corpo gera 409.

Conclusão exige descrição humana do que foi feito e registra autor/instante pelos
campos resolved_by/resolvido_em e eventos. Anexos continuam opcionais pelo fluxo
existente. Solicitante diferente do responsável recebe conclusão para validar:
aceita ou devolve com justificativa. Devolver mantém responsável e histórico;
retorna em andamento. Somente solicitante aceita/devolve. Gestão pode reabrir
concluído, com justificativa. Cancelamento justificado é permitido nos estados
operacionais abertos e é terminal. Notificações existentes são preservadas e
conclusão/devolução/aceite/cancelamento notificam o destinatário correspondente.

O PATCH legado usa a mesma regra: resolver exige completion_description; reabrir
exige reason. Portanto o endpoint antigo não contorna a descrição obrigatória.
Alterar responsável/prioridade/prazo mantém autorização e revisão existentes.
Aceite não concede ao solicitante permissão de transferir ou editar classificação.

## Autoaceite — decisão a confirmar

Quando solicitante = responsável, padrão `ticket_self_accept=true` na configuração
booleana de Organization.settings: conclui direto, exige descrição e registra
auto_accept=true. Gestão pode reabrir. Com flag falsa, fica aguardando validação
explícita do solicitante, inclusive quando é a mesma pessoa. Isso não é confirmação
de fidelidade do texto. Matheus ainda deve confirmar esse comportamento de produto.
Administrador configura a flag pela API de organização; GET /ticket-policy informa
o padrão efetivo. Não existe conclusão gerada por IA ou por transcrição.

## Acompanhamento descritivo

GET /api/v1/ticket-monitoring aceita `stale_hours` (por exemplo 24/48/72),
`overdue`, `due_soon`, `due_within_hours` (padrão 24), offset/limit.
Horas são corridas em UTC, sem excluir fins de semana ou horários de expediente.
Limite de ausência de atualização é inclusivo; prazo vencido é anterior a agora,
e próximo do vencimento está entre agora e o limite da janela, inclusive.
Filtros combinados fazem interseção. Prazo ausente não é inventado.

Aguardando retorno não aparece como sem atualização: retorna aguardando_desde_em
do intervalo aberto e sem_atualizacao_horas=null. A resposta traz responsável
atual, última interação relevante registrada, ator e instante. Concluídos e
cancelados não aparecem nesse monitoramento. Sem ranking, comparação de pessoas
ou interpretação de ausência de atualização como ausência de trabalho.

## Evidências e limites

- [Regras/rotas](../backend/app/ticket_workflow.py) e [regras legadas](../backend/app/work.py).
- [Testes de fluxo, permissões, bordas e concorrência](../backend/tests/test_ticket_workflow.py).
- [Migração de legado/RLS](../backend/tests/test_ticket_migration.py).
- [Resultados executados](../STATUS.md).

Validação operacional da solução é independente da fidelidade por versão da etapa
de conteúdo. Não há alterações nos registros de validação de transcrição.
Painéis técnico/gerencial completos e filtros visuais pertencem à Parte B.
