# Estados e horários das fases 03–05

As transições são validadas no servidor. `revision` é obrigatório nas edições,
ações e comentários; uma versão desatualizada retorna 409. Não há confirmação
automática nem exclusão física pela API/runtime. Processamento da Fase 04
prepara conteúdo para revisão; nunca confirma/publica sozinho.

## Registro

| Origem | Ação | Destino | Quem pode executar |
| --- | --- | --- | --- |
| Criação | Salvar rascunho | `rascunho` | Membro ativo, como autor |
| Criação ou `rascunho` | Enviar finalização/conhecimento | `aguardando_revisao` | Autor |
| Criação ou `rascunho` | Enviar chamado | `enviado`, com Ticket `aberto` | Autor |
| `aguardando_revisao` | Conferir e confirmar finalização | `confirmado` | Somente autor |
| `aguardando_revisao` | Devolver para correção | `rascunho` | Somente autor |
| `rascunho` ou `aguardando_revisao` | Editar texto conferido/horário | Mesmo estado, nova versão | Somente autor |
| `rascunho`, `aguardando_revisao` ou `confirmado` | Cancelar com motivo | `cancelado` | Autor ou gestão |

O envio de finalização/conhecimento passa diretamente à revisão nesta fase;
`enviado` é uma etapa transitória conceitual. `processando`, `erro` e os campos de
processamento são usados na Fase 04. Na Fase 05 o artigo vinculado começa como
rascunho e segue o ciclo editorial independente abaixo.
Um chamado enviado usa exclusivamente as transições do Ticket e não pode ser
cancelado pelo ciclo do Record. Um rascunho de chamado pode ser cancelado.

Gestores e administradores **não confirmam finalizações de outras pessoas**.
O lote confirma até 50 finalizações próprias, atomicamente: qualquer conflito ou
falta de permissão desfaz o lote inteiro. A fila ordena os mais antigos primeiro,
mostra idade e destaca pendências acima de 24 h; isso não é prazo obrigatório.

`Derivar` cria outro registro `rascunho`, de qualquer um dos três destinos,
vinculado ao original, com o mesmo `ocorrido_em`. O original não é alterado.
Depois de confirmado, o conteúdo fica bloqueado; correções exigem derivação ou
cancelamento justificado, preservando versões e auditoria.

## Ticket

| Estado atual | Próximos estados permitidos |
| --- | --- |
| `aberto` | `em_andamento`, `aguardando_esclarecimento`, `aguardando_terceiros`, `resolvido` |
| `em_andamento` | `aguardando_esclarecimento`, `aguardando_terceiros`, `resolvido` |
| `aguardando_esclarecimento` | `em_andamento`, `aguardando_terceiros`, `resolvido` |
| `aguardando_terceiros` | `em_andamento`, `aguardando_esclarecimento`, `resolvido` |
| `resolvido` | `encerrado`, `reaberto` |
| `encerrado` | `reaberto` |
| `reaberto` | `em_andamento`, `aguardando_esclarecimento`, `aguardando_terceiros`, `resolvido` |

Responsável atual ou gestão altera o chamado, incluindo transferência e
prioridade. Encerramento cabe a quem abriu ou à gestão. Solicitar esclarecimento
cria comentário e entra em espera; responder durante essa espera adiciona outro
comentário e retorna a `em_andamento`. Nenhum texto anterior é substituído.
Comentários comuns não alteram o estado. Participantes acessíveis podem comentar.

Cada entrada em espera abre um intervalo com `entrada_em`; a saída preenche
`saida_em`. Só há um intervalo aberto por ticket. Eventos preservam cada mudança,
atores e valores anteriores/posteriores. Resolver grava `resolved_by` e
`resolvido_em`; encerrar grava campos distintos. Reabrir mantém ID/código,
incrementa `reopen_count` e conserva os dados da última resolução/encerramento
até o próximo evento correspondente; o histórico guarda todos os ciclos.

Prioridades `baixa`, `normal`, `alta` e `urgente` abrem imediatamente, sem revisão
formal ou espera por IA. O código `SD-000001` usa sequência transacional por
organização. O Record enviado não acompanha as mudanças de estado do Ticket.

## Tempos e contagem

| Campo | Fonte e regra |
| --- | --- |
| `ocorrido_em` | Fato, sugerido agora; aceita retroativo, rejeita futuro; ajuste auditado com antes/depois |
| `enviado_em` | Recebimento inicial no servidor, inclusive rascunho; imutável |
| `capturado_em` | Horário informado pelo dispositivo, não confiável; não substitui recebimento/fato |
| `processado_em` | Fim do processamento do áudio na fase 04; não substitui fato/recebimento |
| `revisado_em` / `revisado_por` | Confirmação humana da finalização, preservados após cancelamento |
| `publicado_em` | Publicação humana do conhecimento; não substitui fato/envio/revisão |

PostgreSQL armazena TIMESTAMPTZ, respostas incluem offset e a interface usa o
fuso IANA da organização. Editar somente texto preserva a precisão do fato.
Em horários inexistentes/ambíguos por mudança de fuso, a interface pede ISO 8601
com offset explícito em vez de adivinhar.

O histórico padrão contém somente finalizações `confirmado`. Provisórios são
opcionais e sinalizados; cancelados não entram na contagem confirmada. O horário
de revisão nunca substitui o horário do fato ou o recebimento.

## Áudio e jobs (fase 04)

AudioJob: `aguardando` → `processando` → `concluido` ou `erro`; falha transitória
retorna a `aguardando` com backoff limitado, descarte explícito → `descartado`.
Reprocessar cria outro job, não reinicia nem apaga a evidência anterior.
Resultado tardio após descarte/confirmado é ignorado pelo lease/estado.

Finalização/conhecimento: upload → `enviado`, worker → `processando`, conclusão
→ `aguardando_revisao`; erro definitivo → `erro`. Descarte permite digitar e
revisar. Finalização somente entra no histórico após autor confirmar o texto e a
conferência explícita do áudio, individual ou por item do lote. Conhecimento
permanece rascunho e não publica nesta fase.

Chamado: Record continua enviado; o ciclo de Ticket é independente do job. Pode
abrir, atribuir e resolver com a fila parada. Conclusão acrescenta comentário
`transcricao`/`transcricao_mock`, preserva estado resolvido e horários anteriores.
Notificação interna informa preparo do texto, sem equivaler a aprovação humana.

## Artigo — Fase 05

| Origem | Ação | Destino |
| --- | --- | --- |
| Registro acessível | Preparar artigo | `rascunho`, autoria do solicitante |
| `rascunho` ou `devolvido` | Autor envia título/problema/procedimento preenchidos | `aguardando_revisao` |
| `aguardando_revisao` | Revisor devolve com comentário | `devolvido` |
| `aguardando_revisao` | Revisor confirma conteúdo e avisos | `publicado` |
| `publicado` | Revisor arquiva com motivo | `arquivado` |
| `arquivado` | Autor reabre para edição | `rascunho` |

Padrão: gestor/admin publicam; autor não publica a si mesmo. Admin configura
papéis/autopublicação. Editar somente em rascunho/devolvido e pelo autor; toda
mudança inclui versão com ator/data/diferenças. Arquivado some da busca padrão;
reabrir também retira da busca até nova aprovação. Artigo publicado não recebe
atualização automática de conteúdo do worker. Origem cancelada impede publicar;
origem com job ativo impede enviar à revisão.

`enviado_revisao_em`, `publicado_em`, `arquivado_em` e `atualizado_em` são tempos
editoriais, separados de `Record.ocorrido_em`/`enviado_em`. Publicar artigo de
Record conhecimento marca Record como publicado sem trocar o fato; registro de
outro tipo mantém seu ciclo próprio. Cancelar origem de artigo publicado é
recusado: arquive primeiro o artigo. Histórico anterior à migração não é inventado.
## Parte A da fase 06

O app reutiliza estes estados e os apresenta com ícone e texto. Não cria estado
de sucesso local antes da resposta da API. Finalização exige confirmação do autor;
conhecimento continua editorial no painel. Captura e envio não trocam o horário
do fato por revisão/publicação. Falha de rede permite reenvio manual idempotente
na mesma tela; não é uma fila offline persistente.
