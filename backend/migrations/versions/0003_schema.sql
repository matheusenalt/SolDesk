-- Esquema congelado da fase 03.

CREATE TABLE notification (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	type VARCHAR(40) NOT NULL,
	reference_type VARCHAR(24) NOT NULL,
	reference_id VARCHAR(36) NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	lida_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(user_id) REFERENCES app_user (id)
);

CREATE INDEX ix_notification_organization_id ON notification (organization_id);

CREATE INDEX ix_notification_user_id ON notification (user_id);

CREATE TABLE ticket_sequence (
	organization_id VARCHAR(36) NOT NULL,
	value INTEGER NOT NULL,
	PRIMARY KEY (organization_id),
	FOREIGN KEY(organization_id) REFERENCES organization (id)
);

CREATE TABLE record (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	client_id VARCHAR(36) NOT NULL,
	author_id VARCHAR(36) NOT NULL,
	type VARCHAR(24) NOT NULL,
	texto_original TEXT NOT NULL,
	texto_organizado TEXT,
	status VARCHAR(32) NOT NULL,
	revision INTEGER NOT NULL,
	origem_record_id VARCHAR(36),
	ticket_id VARCHAR(36),
	article_id VARCHAR(36),
	ocorrido_em TIMESTAMP WITH TIME ZONE NOT NULL,
	enviado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	capturado_em TIMESTAMP WITH TIME ZONE,
	processado_em TIMESTAMP WITH TIME ZONE,
	revisado_em TIMESTAMP WITH TIME ZONE,
	revisado_por VARCHAR(36),
	publicado_em TIMESTAMP WITH TIME ZONE,
	cancellation_reason TEXT,
	PRIMARY KEY (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(client_id) REFERENCES client (id),
	FOREIGN KEY(author_id) REFERENCES app_user (id),
	FOREIGN KEY(origem_record_id) REFERENCES record (id),
	FOREIGN KEY(revisado_por) REFERENCES app_user (id)
);

CREATE INDEX ix_record_author_id ON record (author_id);

CREATE INDEX ix_record_client_id ON record (client_id);

CREATE INDEX ix_record_organization_id ON record (organization_id);

CREATE INDEX ix_record_status ON record (status);

CREATE TABLE knowledge_article (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	record_id VARCHAR(36) NOT NULL,
	author_id VARCHAR(36) NOT NULL,
	status VARCHAR(24) NOT NULL,
	text TEXT NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	UNIQUE (record_id),
	FOREIGN KEY(record_id) REFERENCES record (id),
	FOREIGN KEY(author_id) REFERENCES app_user (id)
);

CREATE INDEX ix_knowledge_article_organization_id ON knowledge_article (organization_id);

CREATE TABLE record_version (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	record_id VARCHAR(36) NOT NULL,
	revision INTEGER NOT NULL,
	actor_id VARCHAR(36) NOT NULL,
	change VARCHAR(40) NOT NULL,
	snapshot JSON NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (record_id, revision),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(record_id) REFERENCES record (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
);

CREATE INDEX ix_record_version_organization_id ON record_version (organization_id);

CREATE INDEX ix_record_version_record_id ON record_version (record_id);

CREATE TABLE request_receipt (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	scope VARCHAR(80) NOT NULL,
	key_hash VARCHAR(64) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	record_id VARCHAR(36) NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, user_id, scope, key_hash),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(user_id) REFERENCES app_user (id),
	FOREIGN KEY(record_id) REFERENCES record (id)
);

CREATE INDEX ix_request_receipt_organization_id ON request_receipt (organization_id);

CREATE TABLE ticket (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	record_id VARCHAR(36) NOT NULL,
	client_id VARCHAR(36) NOT NULL,
	code VARCHAR(24) NOT NULL,
	description TEXT NOT NULL,
	opened_by VARCHAR(36) NOT NULL,
	assignee_id VARCHAR(36) NOT NULL,
	resolved_by VARCHAR(36),
	closed_by VARCHAR(36),
	priority VARCHAR(16) NOT NULL,
	category VARCHAR(80) NOT NULL,
	status VARCHAR(32) NOT NULL,
	revision INTEGER NOT NULL,
	reopen_count INTEGER NOT NULL,
	aberto_em TIMESTAMP WITH TIME ZONE NOT NULL,
	resolvido_em TIMESTAMP WITH TIME ZONE,
	encerrado_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (organization_id, id),
	UNIQUE (organization_id, code),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	UNIQUE (record_id),
	FOREIGN KEY(record_id) REFERENCES record (id),
	FOREIGN KEY(client_id) REFERENCES client (id),
	FOREIGN KEY(opened_by) REFERENCES app_user (id),
	FOREIGN KEY(assignee_id) REFERENCES app_user (id),
	FOREIGN KEY(resolved_by) REFERENCES app_user (id),
	FOREIGN KEY(closed_by) REFERENCES app_user (id)
);

CREATE INDEX ix_ticket_assignee_id ON ticket (assignee_id);

CREATE INDEX ix_ticket_client_id ON ticket (client_id);

CREATE INDEX ix_ticket_organization_id ON ticket (organization_id);

CREATE INDEX ix_ticket_status ON ticket (status);

CREATE TABLE ticket_comment (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	ticket_id VARCHAR(36) NOT NULL,
	author_id VARCHAR(36) NOT NULL,
	text TEXT NOT NULL,
	kind VARCHAR(24) NOT NULL,
	mentioned_user_ids JSON NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(ticket_id) REFERENCES ticket (id),
	FOREIGN KEY(author_id) REFERENCES app_user (id)
);

CREATE INDEX ix_ticket_comment_organization_id ON ticket_comment (organization_id);

CREATE INDEX ix_ticket_comment_ticket_id ON ticket_comment (ticket_id);

CREATE TABLE ticket_event (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	ticket_id VARCHAR(36) NOT NULL,
	actor_id VARCHAR(36) NOT NULL,
	change VARCHAR(40) NOT NULL,
	before JSON NOT NULL,
	after JSON NOT NULL,
	ocorrido_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(ticket_id) REFERENCES ticket (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
);

CREATE INDEX ix_ticket_event_organization_id ON ticket_event (organization_id);

CREATE INDEX ix_ticket_event_ticket_id ON ticket_event (ticket_id);

CREATE TABLE ticket_interval (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	ticket_id VARCHAR(36) NOT NULL,
	status VARCHAR(32) NOT NULL,
	entrada_em TIMESTAMP WITH TIME ZONE NOT NULL,
	saida_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(ticket_id) REFERENCES ticket (id)
);

CREATE INDEX ix_ticket_interval_organization_id ON ticket_interval (organization_id);

CREATE INDEX ix_ticket_interval_ticket_id ON ticket_interval (ticket_id);

CREATE TABLE ticket_participant (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	ticket_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (ticket_id, user_id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(ticket_id) REFERENCES ticket (id),
	FOREIGN KEY(user_id) REFERENCES app_user (id)
);

CREATE INDEX ix_ticket_participant_organization_id ON ticket_participant (organization_id);

CREATE INDEX ix_ticket_participant_ticket_id ON ticket_participant (ticket_id);

CREATE INDEX ix_ticket_participant_user_id ON ticket_participant (user_id);
