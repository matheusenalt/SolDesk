# Glossário de código

Entidades em inglês: Installation, Organization, User, OrganizationMembership,
Client, ClientExternalRef, Record, Ticket, KnowledgeArticle, Attachment,
Notification, AuditEvent, Invitation e as tabelas internas AuthSession, CsrfGrant e AuthThrottle.

Isolamento: `organization_id` obrigatório nos dados pertinentes, obtido do contexto autenticado.
Datas em UTC no banco; `ocorrido_em` é horário do fato, `enviado_em` do envio,
`revisado_em` da revisão; jamais substituí-los uns pelos outros.

Estados em português sem acento: `aguardando_revisao`, `confirmado`, `publicado`.
Fidelidade independente: RecordContentVersion e ContentValidation;
`nao_validado`/`validado` são estados derivados por versão exata. `validado_em`
é a data UTC da conferência humana; `validated_by` identifica quem a realizou.
`source_version_id` vincula à trilha RecordVersion; `content_hash` é SHA-256 do
`canonical_snapshot`, sem misturar status operacional aos campos materiais.
Vínculos: `ativo`, `inativo`; papéis `administrador`, `gestor`, `tecnico`.
Datas adicionais: `criado_em`, `expira_em`, `usado_em`, `revogado_em`,
`bloqueado_ate` e `window_em` (janela interna de limitação).
Operação inclui RecordVersion, TicketSequence, TicketParticipant,
TicketComment, TicketEvent, TicketInterval e RequestReceipt. Prioridades:
`baixa`, `normal`, `alta`, `urgente`; estados em [ESTADOS](ESTADOS.md).
`capturado_em` é do dispositivo, não confiável; `processado_em` é preenchido pelo
worker; `publicado_em` é editorial; `revisado_por` identifica o autor que confirmou. `entrada_em`/
`saida_em` delimitam esperas, `resolvido_em`/`encerrado_em` são eventos distintos.
Interface e documentos em pt-BR; strings web centralizadas em
`web/src/strings.ts`, `web/src/work-strings.ts`, `web/src/media-strings.ts` e
`web/src/insight-strings.ts`.

Mídia: Attachment (arquivo com um dono), AudioJob (tentativa histórica de
processamento), TemplateVersion (configuração imutável versionada), GlossaryTerm
(termo/variações por empresa). `criado_em`, `enfileirado_em`, `iniciado_em`,
`finalizado_em`, `proxima_tentativa_em` são tempos do job; `purgado_em` indica
remoção do objeto, preservando metadados. Job usa `aguardando`, `processando`,
`concluido`, `erro`, `descartado`; retenção `manter`, `apos_confirmacao`, `apos_dias`.
`ditado_texto` é original opcional do navegador, separado da transcrição do
servidor; `raw_text`, `normalized_text`, `organized_text` identificam estágios.

Conhecimento/relatórios: ArticleVersion (snapshot/diferenças), ArticleConsultation (consulta
sem leitor), Team (equipe atual de relatórios). Campos editoriais em inglês:
title, problem, context, confirmed_cause, procedure, result, keywords, category,
system; ausência de causa exibida como "Não informada". Datas editoriais:
`enviado_revisao_em`, `publicado_em`, `arquivado_em`, `atualizado_em`.
Estados adicionais: `devolvido`, `arquivado`. Filtros de período:
`dia`, `semana`, `mes`, `inicio`, `livre`; granularity `dia`, `semana`, `mes`.
Métricas/ações e atribuição estão definidas em [METRICAS](METRICAS.md).
Sessão legada: MobileRefreshToken, family_id (família de rotação), client_kind
(`web`/`mobile`). Campos de resposta temporal `acesso_expira_em` e
`renovacao_expira_em`; persistência usa expira_em/usado_em/revogado_em.
instance_name é nome público da instalação; instance_id continua identidade,
nunca credencial. Cliente nativo e painel QR descontinuados; termos da sessão legada preservados na API.

## Atendimentos contínuos

Attendance: ciclo operacional, com o ID do Record inicial. internal_activity é o
marcador explícito e imutável de atividade interna; next_action é a próxima ação;
retomada_em é o agendamento UTC e finalizado_em é a conclusão operacional, distintos
de ocorrido_em. result é o resultado humano; assignee_id é o responsável atual.
pending é calculado, sem alterar o estado gravado no vencimento.
## Catálogo de sistemas

- `SoftwareSystem`: sistema cadastrado no catálogo da organização.
- `ClientSystem`: vínculo cliente/sistema, com versão em uso e observação opcionais.
- `SystemReconciliation`: decisão humana imutável sobre classificação do legado.
- `system_id`: referência opcional ao catálogo, sempre limitada à empresa autenticada.
- `system_name_snapshot`: nome do catálogo preservado no momento da seleção.
- `legacy_system_snapshot`: texto original preservado no momento da classificação.
