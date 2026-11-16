"""Parte A: sessão mobile curta e refresh rotativo, sem apagar sessões web."""

from alembic import op

revision = "0006a"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE auth_session ADD client_kind varchar(16) NOT NULL DEFAULT 'web'")
    op.execute("""ALTER TABLE auth_session ADD CONSTRAINT auth_client_kind
        CHECK (client_kind IN ('web','mobile'))""")
    op.execute("""CREATE TABLE mobile_refresh_token (
        token_hash varchar(64) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        user_id varchar(36) NOT NULL REFERENCES app_user(id),
        family_id varchar(36) NOT NULL,
        session_hash varchar(64) NOT NULL UNIQUE REFERENCES auth_session(token_hash),
        criado_em timestamptz NOT NULL, expira_em timestamptz NOT NULL,
        usado_em timestamptz, revogado_em timestamptz,
        FOREIGN KEY (organization_id,user_id)
            REFERENCES organization_membership(organization_id,user_id))""")
    op.execute("CREATE INDEX mobile_refresh_family ON mobile_refresh_token(family_id)")
    op.execute("ALTER TABLE mobile_refresh_token ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mobile_refresh_token FORCE ROW LEVEL SECURITY")
    scope = (
        "organization_id=nullif(current_setting('app.organization_id',true),'') "
        "AND user_id=nullif(current_setting('app.user_id',true),'')"
    )
    op.execute(f"CREATE POLICY owner ON mobile_refresh_token USING ({scope}) WITH CHECK ({scope})")
    # Localiza somente o contexto a partir do hash de uma credencial de alta entropia.
    # A validade, uso único e vínculo são conferidos sob lock pela aplicação.
    op.execute("""CREATE FUNCTION public.mobile_refresh_context(value text)
        RETURNS TABLE(organization_id varchar,user_id varchar)
        LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        SELECT t.organization_id,t.user_id FROM public.mobile_refresh_token t
        WHERE t.token_hash=value $$""")
    op.execute("REVOKE ALL ON FUNCTION public.mobile_refresh_context(text) FROM PUBLIC")


def downgrade():
    raise RuntimeError("Reversão destrutiva desabilitada; preserve sessões e histórico")
