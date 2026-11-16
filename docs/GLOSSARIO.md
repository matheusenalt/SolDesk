# Glossário de código

Entidades em inglês: Installation, Organization, User, OrganizationMembership,
Client, ClientExternalRef, Record, Ticket, KnowledgeArticle, Attachment,
Notification e AuditEvent. Fase 01: Installation. Fase 02: Organization, User,
OrganizationMembership, Client, ClientExternalRef, Invitation, AuditEvent e as
tabelas internas AuthSession, CsrfGrant e AuthThrottle.

Isolamento: `organization_id` obrigatório nos dados pertinentes, obtido do contexto autenticado.
Datas em UTC no banco; `ocorrido_em` é horário do fato, `enviado_em` do envio,
`revisado_em` da revisão; jamais substituí-los uns pelos outros.

Estados em português sem acento: `aguardando_revisao`, `confirmado`, `publicado`.
Fase 02: `ativo`, `inativo`; papéis `administrador`, `gestor`, `tecnico`.
Datas adicionais: `criado_em`, `expira_em`, `usado_em`, `revogado_em`,
`bloqueado_ate` e `window_em` (janela interna de limitação).
Fase 03 acrescenta RecordVersion, TicketSequence, TicketParticipant,
TicketComment, TicketEvent, TicketInterval e RequestReceipt. Prioridades:
`baixa`, `normal`, `alta`, `urgente`; estados em [ESTADOS](ESTADOS.md).
`capturado_em` é do dispositivo, não confiável; `processado_em` é preenchido pelo
worker na fase 04, `publicado_em` segue reservado; `revisado_por` identifica o autor que confirmou. `entrada_em`/
`saida_em` delimitam esperas, `resolvido_em`/`encerrado_em` são eventos distintos.
Interface e documentos em pt-BR; strings web centralizadas em
`web/src/strings.ts`, `web/src/work-strings.ts` e `web/src/media-strings.ts`.

Fase 04: Attachment (arquivo com um dono), AudioJob (tentativa histórica de
processamento), TemplateVersion (configuração imutável versionada), GlossaryTerm
(termo/variações por empresa). `criado_em`, `enfileirado_em`, `iniciado_em`,
`finalizado_em`, `proxima_tentativa_em` são tempos do job; `purgado_em` indica
remoção do objeto, preservando metadados. Job usa `aguardando`, `processando`,
`concluido`, `erro`, `descartado`; retenção `manter`, `apos_confirmacao`, `apos_dias`.
`ditado_texto` é original opcional do navegador, separado da transcrição do
servidor; `raw_text`, `normalized_text`, `organized_text` identificam estágios.
