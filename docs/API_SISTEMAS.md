# Catálogo de sistemas

Disponível na API após a migração aditiva `0011`. Gerenciamento e combobox na
interface estão reservados à próxima parte. Não existe sincronização externa.

## Cadastro e vínculos

| Método e rota | Contrato |
|---|---|
| `POST /api/v1/systems` | Cria sistema na organização autenticada |
| `GET /api/v1/systems` | Pesquisa por nome, paginada; ativos por padrão |
| `GET /api/v1/systems/{id}` | Consulta inclusive sistema inativo |
| `PATCH /api/v1/systems/{id}` | Edita ou inativa; exige revisão atual |
| `GET /api/v1/clients/{id}/systems` | Vínculos do cliente, paginados |
| `PUT /api/v1/clients/{id}/systems/{system_id}` | Cria/atualiza vínculo N:N, com versão em uso e observação |

Sistema: `name`, `description`, `manufacturer`, `category`, `notes`, `situation`
(`ativo`/`inativo`), `revision`. PATCH recebe os mesmos campos e `revision`.
Nome normalizado é calculado no PostgreSQL: sem acentos/maiúsculas, com espaços
consecutivos unificados; unicidade por organização. Nome de apresentação mantém
a grafia informada, com espaços organizados. Conflito de nome/revisão retorna 409.

GET aceita `q`, `include_inactive`, `client_id`, `offset`, `limit` (1–100).
`client_id` restringe aos sistemas vinculados; cliente sem sistema é válido.
Inativos somem das opções novas e não podem ser selecionados em novos vínculos.
Referências existentes continuam consultáveis. Não há endpoint de exclusão;
FKs impedem apagar sistema referenciado, inclusive diretamente no banco.

Vínculo: `version_in_use` e `notes` opcionais. Para alterar conteúdo de vínculo
existente, enviar `revision`; conteúdo idêntico é idempotente. Concorrência usa
lock por cliente/sistema e revisão, evitando duplicação e perda de alterações.
Mudanças são auditadas. Técnico consulta; gestor/administrador administram o
catálogo, os vínculos e a reconciliação. Todas as rotas exigem autenticação;
mutações mantêm CSRF. Organização nunca é parâmetro de entrada.

## Seleção e histórico

Registros, atendimentos contínuos, chamados e conhecimento aceitam `system_id`
opcional na API, mantendo o campo textual `system`. O registro guarda também
`system_name_snapshot` e `legacy_system_snapshot`: nome escolhido e texto livre
existente no momento do vínculo. A criação de chamado/artigo e atualizações do
atendimento herdam o contexto do registro de origem.

Editar um registro/chamado/artigo respeita as permissões e estados anteriores;
`system_id` omitido preserva o vínculo, `null` explícito remove no estado editável,
mantendo versões anteriores. Renomear/inativar o catálogo não reescreve instantâneos.
Derivações e atualizações podem carregar contexto histórico já associado a sistema
inativo; isso não o torna selecionável para outra associação explícita nova.

Listagens de registros, chamados e atendimentos, busca de conhecimento e relatórios
aceitam filtro `system_id`; filtros textuais antigos continuam disponíveis onde já
existiam. A pesquisa de conhecimento indexa também o nome do instantâneo, preservando
o contexto histórico após renomeações. Busca por nome atual no catálogo permite
obter o ID estável para filtrar os registros históricos. Versão em uso pertence ao
vínculo cliente/sistema; não é inferida do texto do relato.

## Reconciliação manual assistida

Nenhum texto é convertido automaticamente em vínculo, mesmo quando a grafia é
idêntica. Vazios e nomes ambíguos permanecem como estão até decisão explícita.

| Método e rota | Contrato |
|---|---|
| `GET /api/v1/systems/reconciliation/values` | Valores textuais distintos, contagem e até cinco sugestões ativas |
| `GET /api/v1/systems/reconciliation/records` | Objetos não vinculados com aquele texto exato |
| `POST /api/v1/systems/reconciliation` | Aceita ou rejeita uma sugestão individualmente |
| `GET /api/v1/systems/reconciliation/history` | Eventos imutáveis das decisões, por objeto |

Consultas aceitam `kind=record|ticket|article`; listas de valores/objetos usam
`offset`/`limit`. Objetos recebem `legacy_text` exato, inclusive espaços/vazio.
Histórico recebe `entity_id` e `offset`, com até 50 eventos por página.
Contagem é por tipo de objeto, sem deduplicar registro de origem e chamado/artigo.
Sugestões usam normalização e similaridade `pg_trgm`; não são confirmação técnica.

POST exige `kind`, `entity_id`, `revision`, `legacy_text`, `decision`
(`aceitar`/`rejeitar`), `reviewed=true` e `Idempotency-Key` (8–128 caracteres).
Aceitar exige `system_id`; rejeitar exige ausência dele. Chave/corpo iguais
recuperam a decisão anterior; chave com outro corpo ou revisão/texto obsoletos
retorna 409. Registro já vinculado não é reconciliado novamente por essa rota.

Aceitar acrescenta contexto estruturado e versão/auditoria sem substituir `system`,
texto, horários ou estado operacional/editorial. No Record, mudança material de
contexto torna a fidelidade atual não validada, preservando as validações anteriores.
Rejeitar registra a decisão sem alterar o objeto, que permanece não vinculado;
o histórico permite à interface identificar decisões já tomadas. Reconciliação de
objetos legados é individual por tipo: não modifica implicitamente seus derivados.

## Banco e verificação

SoftwareSystem, ClientSystem e SystemReconciliation usam RLS forçada e organização
do contexto autenticado. FKs compostas impedem referências entre empresas. Decisões
são append-only, com ator e data. Colunas novas começam nulas, sem backfill por
semelhança, sem modificar versões, fatos ou validações anteriores.
Downgrade somente com catálogo, vínculos e decisões vazios; havendo dados novos,
bloqueia antes de remover estrutura. Procedimento padrão continua sendo upgrade.

Evidências: [testes do catálogo](../backend/tests/test_systems.py),
[migração com legado e duas empresas](../backend/tests/test_systems_migration.py),
[regressão do upgrade anterior](../backend/tests/test_validation_migration.py).
Sem dependência nova ou modelo de IA; interface do catálogo ainda não implementada.
