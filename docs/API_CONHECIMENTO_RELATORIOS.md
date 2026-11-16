# API de conhecimento, relatórios e equipes

Prefixo `/api/v1`, sessão opaca/vínculo ativo, tenant exclusivo do servidor.
Mutações exigem `X-CSRF-Token` obtido em `/auth/csrf` com os mesmos cookies.
Erros RFC 7807; sem detalhes internos. IDs nunca autorizam acesso.
`revision` inteiro obrigatório para alterar artigo/equipe; conflito 409.

## Conhecimento

| Método e rota | Entrada e comportamento |
| --- | --- |
| GET `/knowledge/policy` | publisher_roles, allow_self_publish e capacidade do solicitante |
| PATCH `/knowledge/policy` | Admin; papéis administrador/gestor/tecnico, lista não vazia; allow_self_publish false por padrão |
| GET `/knowledge/search` | q até 200, category/system até 80, client_id, status publicado ou arquivado, start_date/end_date locais de publicação, offset, limit 1–100 |
| GET `/knowledge/drafts` | Próprios; queue=true exige revisor e mostra aguardando_revisao; páginas de 20 |
| POST `/knowledge/articles` | record_id acessível; um artigo por origem; retorna existente acessível ou novo rascunho |
| GET `/knowledge/articles/{id}` | Campos, nomes, permissões da fonte, avisos e conteúdo acessível da origem; publicado/arquivado gera consulta agregável |
| PATCH `/knowledge/articles/{id}` | Autor em rascunho/devolvido; revision e campos estruturados completos |
| POST `/knowledge/articles/{id}/actions` | revision, action enviar/publicar/devolver/arquivar/reabrir; comment, human_reviewed e warnings_reviewed quando necessários |
| GET `/knowledge/articles/{id}/versions` | Snapshots, revision, ator/data, diferenças de conteúdo/estado/comentário |
| GET `/tickets/{id}/suggestions` | Autoriza Ticket, usa cliente real do Ticket; coincidência de termos/categoria, até 5; sugestão, não diagnóstico |

Campos editoriais: title (200), problem/context/result (10 mil), confirmed_cause
(5 mil, vazio significa não informada), procedure (15 mil), text (20 mil), keywords
(até 30 de 1–80), category/system (80) e client_id opcional. Não se infere conteúdo
da narrativa; estrutura é preenchida por pessoa. Template fixado pela origem.
Busca combina FTS português/unaccent, substring literal escapada e trigramas;
destaque em `snippet` + `highlights[{start,end}]`, sem HTML. Não retorna estados
editoriais não publicados. Sem client_id só gerais; com cliente, gerais + restritos
daquele cliente. Arquivados só com status explícito. Filtragem de período refere-se
à publicação, não ao fato da origem.

Publicar requer papel autorizado, política de autopublicação e **ambos** os flags
de conferência; avisos são heurísticos, não verificação fiscal/credencial automática.
Devolução/arquivamento exigem motivo. Origem cancelada impede publicar; job ativo
impede envio à revisão. Fonte exige autorização própria, mesmo que artigo seja visível.

## Relatórios e equipes

| Método e rota | Contrato |
| --- | --- |
| GET `/reports/options` | Pessoas/equipes/classificações disponíveis; técnico só tem opção da própria pessoa e equipes das quais participa |
| GET `/reports` | Query com filtros abaixo; números reais, comparação anterior, pessoas/series/classificações/ticket_distribution/clientes/consultas/tempos/fila/carga/histórico |
| POST `/reports/export` | **Corpo JSON** com os mesmos filtros, não query; CSV UTF-8 BOM, ponto e vírgula, aspas e neutralização de fórmulas; auditado; Cache-Control private, no-store |
| GET `/teams` | Gestão consulta nomes, integrantes, revision e atualização |
| POST `/teams` | Admin; name, member_ids da organização; revision inicial 1 |
| PATCH `/teams/{id}` | Admin; name, member_ids, revision atual |

Filtros: preset dia/semana/mes/inicio/livre (padrão dia), start_date/end_date para
livre, client_id/responsible_id/team_id, category/system, granularity dia/semana/mes,
history_offset. Query/body extras como organization_id são recusados.
Dia/semana/mês são calendários no fuso IANA atual; livre inclusivo nas datas vira
UTC semiaberto. Comparação usa a mesma quantidade anterior de dias locais.
Técnico consulta só números próprios: outra pessoa recebe 403 também no CSV.
Equipe significa composição atual, intersectada com permissões do solicitante.

`times` separa first_action/resolution, cada qual gross/net com median_seconds,
p90_seconds, n e warning; n=0 retorna duração null. resolution_unique_tickets e
excluded_samples explicitam qualidade. `ticket_distribution` agrupa tickets
únicos com ações no período pela categoria/sistema/prioridade atuais.
`queue` é fotografia atual; `workload` reconstrói simultaneidade e identifica
pendências atuais agrupadas pelo fato. Consultas de artigos não armazenam leitor,
por isso não são atribuídas a pessoa/equipe nem fornecidas ao técnico.

Limites e definições exatas: [METRICAS](METRICAS.md). Excesso retorna 422, sem
total truncado; CSV inclui histórico completo, tela pagina em 100. Histórico não
exporta texto de relato. Não há pontuação, ranking de pessoas, diagnóstico,
inferência de complexidade, prazo/SLA presumido ou avaliação profissional.

Record agora aceita category/system também nos destinos finalização/conhecimento;
Ticket aceita system. Classificação revisada fica protegida no banco. Alterar
nome/fuso preserva políticas existentes da organização; mídia/conhecimento usam
suas rotas próprias. Capacidades knowledge/search/reports anunciadas a partir de 0005,
incluindo a revisão atual 0006a.
