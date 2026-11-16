-- Esquema congelado da fase 04.

CREATE TABLE glossary_term (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	term VARCHAR(80) NOT NULL,
	aliases JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, term),
	FOREIGN KEY(organization_id) REFERENCES organization (id)
);

CREATE INDEX ix_glossary_term_organization_id ON glossary_term (organization_id);

CREATE TABLE template_version (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	type VARCHAR(24) NOT NULL,
	version INTEGER NOT NULL,
	fields JSON NOT NULL,
	created_by VARCHAR(36),
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, id),
	UNIQUE (organization_id, type, version),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(created_by) REFERENCES app_user (id)
);

CREATE INDEX ix_template_version_organization_id ON template_version (organization_id);

CREATE TABLE attachment (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	owner_type VARCHAR(16) NOT NULL,
	client_id VARCHAR(36),
	ticket_id VARCHAR(36),
	record_id VARCHAR(36),
	kind VARCHAR(16) NOT NULL,
	filename VARCHAR(255) NOT NULL,
	content_type VARCHAR(80) NOT NULL,
	size INTEGER NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	object_key VARCHAR(160) NOT NULL,
	storage_backend VARCHAR(16) NOT NULL,
	uploaded_by VARCHAR(36) NOT NULL,
	enviado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	validated BOOLEAN NOT NULL,
	duration_seconds FLOAT,
	purgado_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(client_id) REFERENCES client (id),
	FOREIGN KEY(ticket_id) REFERENCES ticket (id),
	FOREIGN KEY(record_id) REFERENCES record (id),
	UNIQUE (object_key),
	FOREIGN KEY(uploaded_by) REFERENCES app_user (id)
);

CREATE INDEX ix_attachment_organization_id ON attachment (organization_id);

CREATE TABLE audio_job (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	record_id VARCHAR(36) NOT NULL,
	attachment_id VARCHAR(36) NOT NULL,
	template_id VARCHAR(36) NOT NULL,
	template_snapshot JSON NOT NULL,
	glossary_snapshot JSON NOT NULL,
	parent_id VARCHAR(36),
	status VARCHAR(24) NOT NULL,
	priority VARCHAR(16) NOT NULL,
	attempts INTEGER NOT NULL,
	lease VARCHAR(36),
	raw_text TEXT,
	normalized_text TEXT,
	organized_text TEXT,
	segments JSON NOT NULL,
	warnings JSON NOT NULL,
	sections JSON NOT NULL,
	provider_metadata JSON NOT NULL,
	error_code VARCHAR(40),
	criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	enfileirado_em TIMESTAMP WITH TIME ZONE,
	iniciado_em TIMESTAMP WITH TIME ZONE,
	finalizado_em TIMESTAMP WITH TIME ZONE,
	proxima_tentativa_em TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organization (id),
	FOREIGN KEY(record_id) REFERENCES record (id),
	FOREIGN KEY(attachment_id) REFERENCES attachment (id),
	FOREIGN KEY(template_id) REFERENCES template_version (id),
	FOREIGN KEY(parent_id) REFERENCES audio_job (id)
);

CREATE INDEX ix_audio_job_organization_id ON audio_job (organization_id);

CREATE INDEX ix_audio_job_record_id ON audio_job (record_id);
