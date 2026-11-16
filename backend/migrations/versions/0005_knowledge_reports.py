"""Conhecimento editorial, busca PostgreSQL e fatos para relatórios."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("record", "ticket"):
        if table == "record":
            op.execute("ALTER TABLE record ADD category varchar(80) NOT NULL DEFAULT ''")
        op.execute(f"ALTER TABLE {table} ADD system varchar(80) NOT NULL DEFAULT ''")
    op.execute("UPDATE record r SET category=t.category FROM ticket t WHERE t.record_id=r.id")
    for name, kind in {
        "title": "varchar(200) NOT NULL DEFAULT ''",
        "problem": "text NOT NULL DEFAULT ''",
        "context": "text NOT NULL DEFAULT ''",
        "confirmed_cause": "text NOT NULL DEFAULT ''",
        "procedure": "text NOT NULL DEFAULT ''",
        "result": "text NOT NULL DEFAULT ''",
        "keywords": "json NOT NULL DEFAULT '[]'",
        "category": "varchar(80) NOT NULL DEFAULT ''",
        "system": "varchar(80) NOT NULL DEFAULT ''",
        "client_id": "varchar(36)",
        "template_version_id": "varchar(36)",
        "revision": "integer NOT NULL DEFAULT 1 CHECK (revision > 0)",
        "reviewer_id": "varchar(36) REFERENCES app_user(id)",
        "atualizado_em": "timestamptz NOT NULL DEFAULT now()",
        "enviado_revisao_em": "timestamptz",
        "publicado_em": "timestamptz",
        "arquivado_em": "timestamptz",
        "review_comment": "text NOT NULL DEFAULT ''",
        "search_text": "text NOT NULL DEFAULT ''",
        "search_vector": "tsvector",
    }.items():
        op.execute(f'ALTER TABLE knowledge_article ADD "{name}" {kind}')
    for field, table in (("client_id", "client"), ("template_version_id", "template_version")):
        op.create_foreign_key(
            f"article_{field}_tenant",
            "knowledge_article",
            table,
            ["organization_id", field],
            ["organization_id", "id"],
        )
    op.execute("""ALTER TABLE knowledge_article ADD CONSTRAINT article_status CHECK
        (status IN ('rascunho','aguardando_revisao','publicado','devolvido','arquivado'))""")
    op.execute("""CREATE TABLE article_version (
        id varchar(36) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        article_id varchar(36) NOT NULL, revision integer NOT NULL,
        actor_id varchar(36) REFERENCES app_user(id),
        change varchar(40) NOT NULL, snapshot json NOT NULL, criado_em timestamptz NOT NULL,
        UNIQUE(article_id,revision), FOREIGN KEY (organization_id,article_id)
        REFERENCES knowledge_article(organization_id,id))""")
    op.execute("""CREATE TABLE article_consultation (
        id varchar(36) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        article_id varchar(36) NOT NULL, ocorrido_em timestamptz NOT NULL,
        FOREIGN KEY (organization_id,article_id)
        REFERENCES knowledge_article(organization_id,id))""")
    op.execute("""CREATE TABLE team (
        id varchar(36) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        name varchar(120) NOT NULL, member_ids json NOT NULL DEFAULT '[]',
        revision integer NOT NULL DEFAULT 1, atualizado_em timestamptz NOT NULL,
        UNIQUE(organization_id,name))""")
    tenant = "organization_id = nullif(current_setting('app.organization_id',true),'')"
    for table in ("article_version", "article_consultation", "team"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON {table} USING ({tenant}) WITH CHECK ({tenant})")
        op.execute(f"CREATE INDEX {table}_organization ON {table}(organization_id)")
    op.execute("""CREATE FUNCTION public.refresh_article_search() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
          NEW.search_text := public.unaccent(lower(concat_ws(' ',NEW.title,NEW.problem,
            NEW.context,NEW.confirmed_cause,NEW.procedure,NEW.result,NEW.text,
            NEW.keywords::text,NEW.category,NEW.system)));
          NEW.search_vector := to_tsvector('portuguese',NEW.search_text);
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER article_search BEFORE INSERT OR UPDATE ON knowledge_article
        FOR EACH ROW EXECUTE FUNCTION public.refresh_article_search()""")
    op.execute("UPDATE knowledge_article SET search_text='' ")
    op.execute("CREATE INDEX article_fulltext ON knowledge_article USING gin(search_vector)")
    op.execute(
        "CREATE INDEX article_trigram ON knowledge_article USING gin(search_text gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX article_filter ON "
        "knowledge_article(organization_id,status,client_id,publicado_em)"
    )
    op.execute(
        "CREATE INDEX article_views_period ON "
        "article_consultation(organization_id,ocorrido_em,article_id)"
    )
    op.execute(
        "CREATE INDEX ticket_event_period ON ticket_event(organization_id,ocorrido_em,actor_id)"
    )
    op.execute("CREATE INDEX record_report_period ON record(organization_id,ocorrido_em,author_id)")
    # Um retrato no momento da migração, sem fingir conhecer alterações anteriores.
    op.execute("""INSERT INTO article_version
        (id,organization_id,article_id,revision,actor_id,change,snapshot,criado_em)
        SELECT gen_random_uuid()::text,organization_id,id,1,NULL,'importado_fase05',
        json_build_object('text',text,'status',status,'title',title,'problem',problem,
          'context',context,'confirmed_cause',confirmed_cause,'procedure',procedure,'result',result,
          'keywords',keywords,'category',category,'system',system,'client_id',client_id,
          'template_version_id',template_version_id,'review_comment',review_comment),now()
        FROM knowledge_article""")
    for field in ("author_id", "reviewer_id"):
        op.create_foreign_key(
            f"article_{field}_member",
            "knowledge_article",
            "organization_membership",
            ["organization_id", field],
            ["organization_id", "user_id"],
        )
    op.execute("""CREATE FUNCTION public.preserve_article_publication() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
          IF (NEW.organization_id,NEW.author_id,NEW.record_id) IS DISTINCT FROM
             (OLD.organization_id,OLD.author_id,OLD.record_id) THEN
            RAISE EXCEPTION 'Origem e autoria editorial são imutáveis';
          END IF;
          IF OLD.status IN ('publicado','arquivado') AND
             (NEW.title,NEW.problem,NEW.context,NEW.confirmed_cause,NEW.procedure,
              NEW.result,NEW.text,NEW.keywords::text,NEW.category,NEW.system,NEW.client_id)
             IS DISTINCT FROM
             (OLD.title,OLD.problem,OLD.context,OLD.confirmed_cause,OLD.procedure,
              OLD.result,OLD.text,OLD.keywords::text,OLD.category,OLD.system,OLD.client_id) THEN
            RAISE EXCEPTION 'Reabra o artigo antes de alterar seu conteúdo';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER article_publication BEFORE UPDATE ON knowledge_article
        FOR EACH ROW EXECUTE FUNCTION public.preserve_article_publication()""")
    op.execute("""CREATE FUNCTION public.preserve_record_classification() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
          IF OLD.status IN ('confirmado','publicado','cancelado') AND
            (NEW.category,NEW.system) IS DISTINCT FROM (OLD.category,OLD.system) THEN
            RAISE EXCEPTION 'Classificação de registro revisado é imutável';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER record_classification BEFORE UPDATE ON record
        FOR EACH ROW EXECUTE FUNCTION public.preserve_record_classification()""")


def downgrade():
    raise RuntimeError("Reversão destrutiva desabilitada; preserve artigos e histórico")
