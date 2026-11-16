# Definições de métricas — Fase 05

Contrato escrito antes da implementação dos relatórios. Os números descrevem
somente atendimentos registrados; não medem conhecimento, complexidade,
competência, produtividade, necessidade de treinamento ou contratação.

## Escopo, períodos e filtros

- Tenant sempre da sessão. Gestão/admin consultam a empresa; técnico consulta
  exclusivamente sua autoria/ações/responsabilidade, inclusive no CSV. Não basta
  ser participante para consultar números de outra pessoa.
- Dia, semana (segunda a domingo) e mês são calendários no fuso IANA atual da
  organização. Período livre usa datas locais inclusivas; internamente intervalo
  UTC semiaberto `[início, fim)`. Desde o início parte do primeiro fato disponível.
  Limites são convertidos separadamente, respeitando dias de duração variável.
- Comparação: janela imediatamente anterior com a mesma quantidade de dias
  locais. Sem porcentagem quando o denominador é zero; mostrar totais lado a lado.
- Filtros: cliente atendido, pessoa/responsável, equipe, categoria e sistema.
  Equipe significa integrantes cadastrados **atualmente**, não composição histórica.
  Categoria/sistema são classificação informada, nunca inferida da narrativa;
  dados antigos sem classificação aparecem como "Não informado".
- Ocorrências de registros usam `ocorrido_em`. Ações de tickets usam
  `TicketEvent.ocorrido_em`; abertura usa `aberto_em`. Não trocar pelo processamento
  ou revisão posterior. Fila atual é fotografia no instante da consulta, identificada
  separadamente dos totais do período. Histórico de classificações/equipes anterior
  à Fase 05 não é reconstruído por suposição.

## Indicadores e fontes

| Indicador | Fórmula / fonte / exclusões |
| --- | --- |
| Registros no período | Quantidade de Record por fato e autor; separa finalização, chamado e conhecimento; cancelados excluídos e informados separadamente |
| Finalizações confirmadas | Finalizações no período do fato com status atual confirmado; revisão pode ser posterior; não soma provisórios |
| Finalizações aguardando revisão | Finalizações no período do fato com status atual aguardando_revisao; rascunho/processamento/erro aparecem separados |
| Chamados abertos | Tickets distintos com aberto_em na janela, atribuídos ao opened_by; reabrir não é nova abertura |
| Atribuições / assumiu | Atribuição inicial ou mudança real de assignee; conta ações e tickets únicos por destinatário, diferente de quem executou o encaminhamento |
| Encaminhou | Mudança de assignee em evento humano; atribuída ao actor_id, exclui atribuição inicial |
| Comentou | Eventos chamado_comentario/esclarecimento/resposta, por actor_id; transcrição automática e eventos do worker excluídos |
| Movimentou | Alteração humana efetiva de estado, responsável, prioridade, categoria ou sistema; não conta PATCH sem mudança nem comentário isolado |
| Resolveu / encerrou / reabriu | Transição efetiva para resolvido/encerrado/reaberto, por actor_id; ações e tickets distintos separados; um ticket reaberto não vira novo ticket |
| Aguardando terceiros | Entradas efetivas nesse estado na janela; fotografia da fila atual mostrada à parte |
| Distribuição temporal | Ações por pessoa agrupadas por dia/semana/mês locais, sem atribuir resolução ao autor da abertura |
| Assuntos/sistemas | Registros por categoria/sistema declarados e pessoa/equipe; sem interpretar causa ou extrair diagnóstico do texto |
| Clientes com atendimentos | Registros não cancelados por cliente; contagem, período e filtros visíveis; provisórios identificados |
| Recorrência | Frequência de categoria/sistema informados; não classificar automaticamente textos livres como o mesmo problema |
| Categoria/sistema/prioridade de chamados | Tickets únicos com ao menos uma ação no período por pessoa/escopo selecionados, agrupados pela classificação atual; reaberturas não duplicam ticket; não reconstrói prioridade passada |
| Artigos consultados | Eventos ArticleConsultation por artigo/data, sem identidade do leitor; somente visão agregada da organização para gestão, sem ranking por pessoa |
| Fila atual | Tickets fora de resolvido/encerrado, por responsável/prioridade/estado, idade desde abertura e pedido de esclarecimento vigente |
| Carga no tempo | Registros por dia do fato e tickets simultaneamente abertos em cada fim de dia, reconstruídos de eventos de estado/atribuição; pendências de revisão atuais agrupadas pelo dia do fato, explicitamente não fotografia histórica da revisão |

## Tempos: bruto e descontando pausas

- Primeira ação: primeiro evento **humano e efetivo** após a abertura (alteração
  real ou comentário/resposta/esclarecimento); criação/atribuição inicial,
  transcrição automática e PATCH sem mudança não são primeira resposta. Intervalo
  abertura → evento. Não equivale a início de atendimento presencial nem SLA.
- Resolução: para cada transição a resolvido na janela, intervalo abertura →
  primeira resolução, ou reabertura imediatamente anterior → próxima resolução.
  Cada ciclo concluído é uma amostra; exibir também tickets distintos.
  Encerramento não é resolução e não gera segunda amostra automaticamente.
- Tempo líquido = bruto menos união dos intervalos aguardando_esclarecimento e
  aguardando_terceiros, recortados ao intervalo medido. Sobreposições não são
  descontadas duas vezes. Nunca descontar além da duração bruta.
- Tempos sem abertura/eventos/intervalos coerentes não geram amostra; informar
  quantidade de ciclos excluídos. Não inventar duração usando apenas envio.
- Mediana e P90 por interpolação linear (`percentile_cont` equivalente), em
  segundos, lado a lado para bruto/líquido, com **n**. `n < 5`: aviso de amostra
  pequena. `n = 0`: valores nulos e estado vazio, nunca zero como duração medida.
- Técnico recebe apenas amostras de primeira ação/resolução **executadas por ele**;
  a abertura por outra pessoa não dá acesso aos números dela. Filtro pessoa/equipe
  seleciona ator para ações e autor para registros; fila/carga usam responsável.

## Apresentação, exportação e limites

Pessoas ordenadas alfabeticamente por padrão, sem posição/medalha/avaliação.
Reordenação manual de coluna é opção de consulta, sem pontuação automática.
Texto fixo contextualiza demanda, especialização, distribuição, escalonamento,
complexidade não medida e classificação. Não há metas, semáforo por pessoa nem
conclusões geradas. Gráficos possuem rótulos e tabela equivalente.

CSV usa o mesmo relatório/escopo/filtros da tela; BOM UTF-8, ponto e vírgula e
todas as células entre aspas. Texto começando (também depois de espaços/controles)
com =, +, -, @ ou equivalentes de largura cheia recebe apóstrofo. Isso protege
a exportação inicial; não certifica regravações/conversões por qualquer planilha.
Exportação auditada com
período/filtros/escopo e sem conteúdo sensível de relatos. Histórico por cliente
e por pessoa respeita o mesmo escopo. Paginação e limite explícito evitam resposta
silenciosamente incompleta; relatórios muito grandes são recusados com orientação
para reduzir período/filtros, nunca truncados como se fossem completos.

Limites iniciais: 3661 dias, 10 mil registros, 10 mil tickets, 50 mil eventos,
20 mil intervalos e 50 mil consultas. A carga de fatos preserva histórico necessário
às pausas/carga; reduzir apenas o período pode não bastar: filtre cliente/categoria/
sistema quando receber 422. Tela pagina histórico em 100, CSV inclui todas as
linhas dentro dos limites. Nenhum limite silencioso é apresentado como total.

Sem duração de serviço presumida, sem busca semântica externa, sem métricas de
leitura individual, sem uso de tempo do worker como tempo de atendimento.
