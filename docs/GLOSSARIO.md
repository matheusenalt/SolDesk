# Glossário de código

Entidades em inglês: Installation, Organization, User, OrganizationMembership,
Client, ClientExternalRef, Record, Ticket, KnowledgeArticle, Attachment,
Notification e AuditEvent. Apenas Installation existe na fase 01.

Isolamento futuro: `organization_id` obrigatório, obtido do contexto autenticado.
Datas em UTC no banco; `ocorrido_em` é horário do fato, `enviado_em` do envio,
`revisado_em` da revisão; jamais substituí-los uns pelos outros.

Estados em português sem acento: `aguardando_revisao`, `confirmado`, `publicado`.
As transições serão definidas nas fases correspondentes. Interface e documentos
em pt-BR; strings web centralizadas em `web/src/strings.ts`.
