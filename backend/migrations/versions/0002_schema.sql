-- Snapshot imutável da fase 02, independente de modelos futuros.

CREATE TABLE app_user (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(160) NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash TEXT NOT NULL,
	must_change_password BOOLEAN NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
);

CREATE TABLE auth_throttle (
	key VARCHAR(80) NOT NULL,
	count INTEGER NOT NULL,
	failures INTEGER NOT NULL,
	window_em TIMESTAMP WITH TIME ZONE NOT NULL,
	bloqueado_ate TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (key)
);

CREATE TABLE csrf_grant (
	token_hash VARCHAR(64) NOT NULL,
	session_hash VARCHAR(64),
	expira_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (token_hash)
);

CREATE TABLE organization (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(160) NOT NULL,
	slug VARCHAR(80) NOT NULL,
	timezone VARCHAR(80) NOT NULL,
	settings JSON NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug)
);

CREATE TABLE audit_event (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	actor_id VARCHAR(36),
	action VARCHAR(80) NOT NULL,
	entity VARCHAR(80) NOT NULL,
	entity_id VARCHAR(36) NOT NULL,
	before JSON NOT NULL,
	after JSON NOT NULL,
	ocorrido_em TIMESTAMP WITH TIME ZONE NOT NULL,
	origin VARCHAR(80) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
);

CREATE INDEX ix_audit_event_organization_id ON audit_event (organization_id);

CREATE TABLE auth_session (
	token_hash VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	expira_em TIMESTAMP WITH TIME ZONE NOT NULL,
	revogado_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES app_user (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id)
);

CREATE INDEX ix_auth_session_organization_id ON auth_session (organization_id);

CREATE INDEX ix_auth_session_user_id ON auth_session (user_id);

CREATE TABLE client (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	name VARCHAR(160) NOT NULL,
	name_key VARCHAR(200) NOT NULL,
	nickname VARCHAR(160) NOT NULL,
	phone VARCHAR(40) NOT NULL,
	email VARCHAR(254) NOT NULL,
	notes TEXT NOT NULL,
	situation VARCHAR(16) NOT NULL,
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, name_key),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES organization (id)
);

CREATE INDEX client_org_created ON client (organization_id, criado_em, id);

CREATE INDEX ix_client_organization_id ON client (organization_id);

CREATE TABLE invitation (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	email VARCHAR(254) NOT NULL,
	role VARCHAR(24) NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	expira_em TIMESTAMP WITH TIME ZONE NOT NULL,
	usado_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	UNIQUE (token_hash)
);

CREATE INDEX ix_invitation_organization_id ON invitation (organization_id);

CREATE TABLE organization_membership (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	role VARCHAR(24) NOT NULL,
	situation VARCHAR(16) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, user_id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(user_id) REFERENCES app_user (id)
);

CREATE INDEX ix_organization_membership_organization_id ON organization_membership (organization_id);

CREATE INDEX ix_organization_membership_user_id ON organization_membership (user_id);

CREATE TABLE client_external_ref (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	client_id VARCHAR(36) NOT NULL,
	provider VARCHAR(80) NOT NULL,
	identifier VARCHAR(200) NOT NULL,
	label VARCHAR(160) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(client_id) REFERENCES client (id)
);

CREATE INDEX ix_client_external_ref_client_id ON client_external_ref (client_id);

CREATE INDEX ix_client_external_ref_organization_id ON client_external_ref (organization_id);
