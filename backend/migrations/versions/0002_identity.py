"""Organizações, autenticação, clientes e RLS PostgreSQL."""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        raise RuntimeError("A fase 02 exige PostgreSQL; SQLite testa somente a migração 0001")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    snapshot = Path(__file__).with_name("0002_schema.sql").read_text(encoding="utf-8")
    for statement in snapshot.split(";"):
        if statement.strip():
            op.execute(statement)
    op.execute("""
        CREATE FUNCTION public.search_normalize(value text) RETURNS text
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
        SET search_path = pg_catalog, public
        AS $$ SELECT lower(public.unaccent('public.unaccent', value)) $$
    """)
    op.execute(
        "CREATE INDEX client_name_search ON client USING gin (search_normalize(name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX client_nickname_search ON client "
        "USING gin (search_normalize(nickname) gin_trgm_ops)"
    )
    tenant = "organization_id = nullif(current_setting('app.organization_id', true), '')"
    user = "user_id = nullif(current_setting('app.user_id', true), '')"
    for table in ("client", "client_external_ref", "invitation", "audit_event"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON {table} USING ({tenant}) WITH CHECK ({tenant})")
    op.execute("ALTER TABLE organization_membership ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_membership FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY member_read ON organization_membership "
        f"FOR SELECT USING ({tenant} OR {user})"
    )
    for command in ("INSERT", "UPDATE", "DELETE"):
        using = "" if command == "INSERT" else f"USING ({tenant})"
        check = "" if command == "DELETE" else f"WITH CHECK ({tenant})"
        op.execute(
            f"CREATE POLICY member_{command.lower()} ON organization_membership "
            f"FOR {command} {using} {check}"
        )
    op.execute("ALTER TABLE organization ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization FORCE ROW LEVEL SECURITY")
    org = "id = nullif(current_setting('app.organization_id', true), '')"
    op.execute(f"""CREATE POLICY org_read ON organization FOR SELECT USING ({org} OR id IN
        (SELECT organization_id FROM organization_membership
        WHERE {user} AND situation = 'ativo'))""")
    for command in ("INSERT", "UPDATE"):
        using = "" if command == "INSERT" else f"USING ({org})"
        op.execute(
            f"CREATE POLICY org_{command.lower()} ON organization "
            f"FOR {command} {using} WITH CHECK ({org})"
        )
    # Ponte mínima para resgatar uma credencial de convite antes de conhecer o tenant.
    # O dono da função é o migrador; apenas o UUID é retornado, nunca a linha inteira.
    op.execute("""CREATE FUNCTION public.invitation_organization(credential text) RETURNS text
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$ SELECT organization_id FROM public.invitation
        WHERE token_hash = credential AND usado_em IS NULL AND expira_em > now() $$""")
    op.execute("REVOKE ALL ON FUNCTION public.invitation_organization(text) FROM PUBLIC")
    op.execute("""CREATE FUNCTION public.membership_count(identifier text) RETURNS bigint
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$ SELECT count(*) FROM public.organization_membership WHERE user_id = identifier $$""")
    op.execute("REVOKE ALL ON FUNCTION public.membership_count(text) FROM PUBLIC")
    op.execute(
        "ALTER TABLE organization_membership ADD CONSTRAINT membership_role "
        "CHECK (role IN ('administrador','gestor','tecnico'))"
    )
    op.execute(
        "ALTER TABLE invitation ADD CONSTRAINT invitation_role "
        "CHECK (role IN ('administrador','gestor','tecnico'))"
    )
    for table in ("organization_membership", "client"):
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_situation "
            "CHECK (situation IN ('ativo','inativo'))"
        )
    op.create_foreign_key(
        "external_client_tenant",
        "client_external_ref",
        "client",
        ["organization_id", "client_id"],
        ["organization_id", "id"],
    )


def downgrade():
    raise RuntimeError("Reversão destrutiva desabilitada; use manutenção com backup")
