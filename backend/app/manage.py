"""Comandos explícitos, sem senha fixa e sem apagar bancos/volumes."""

import argparse
import getpass
import json
import os
import secrets
from pathlib import Path

from alembic import command
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.access import set_context
from app.config import Settings
from app.models import AuditEvent, Client, Organization, OrganizationMembership, User
from app.schemas import Signup
from app.security import password_hash


def migrate(settings):
    url = make_url(settings.migration_database_url or settings.database_url)
    if url.drivername != "postgresql+psycopg" or not settings.runtime_password:
        raise RuntimeError("Configure MIGRATION_DATABASE_URL e RUNTIME_PASSWORD")
    with connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(728102)")
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname='soldesk_runtime'"
        ).fetchone()
        if not exists:
            connection.execute(
                "CREATE ROLE soldesk_runtime LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        connection.execute(
            sql.SQL("ALTER ROLE soldesk_runtime PASSWORD {}").format(
                sql.Literal(settings.runtime_password)
            )
        )
        connection.execute("REVOKE CREATE ON SCHEMA public FROM soldesk_runtime")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    with connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute("GRANT USAGE ON SCHEMA public TO soldesk_runtime")
        connection.execute("GRANT SELECT ON installation, alembic_version TO soldesk_runtime")
        for table in (
            "organization",
            "app_user",
            "organization_membership",
            "auth_session",
            "csrf_grant",
            "auth_throttle",
            "invitation",
            "client",
            "client_external_ref",
        ):
            connection.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON {} TO soldesk_runtime").format(
                    sql.Identifier(table)
                )
            )
        connection.execute("GRANT SELECT, INSERT ON audit_event TO soldesk_runtime")
        connection.execute(
            "GRANT EXECUTE ON FUNCTION public.invitation_organization(text), "
            "public.membership_count(text) TO soldesk_runtime"
        )


def create_organization(db, name, slug, email, user_name, password, timezone="America/Sao_Paulo"):
    item = db.scalar(select(Organization).where(Organization.slug == slug))
    if item:
        return item, False
    item = Organization(name=name, slug=slug, timezone=timezone)
    db.add(item)
    db.flush()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        raise RuntimeError(
            "Bootstrap exige uma nova identidade; use convites para contas existentes"
        )
    user = User(name=user_name, email=email, password_hash=password_hash(password))
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(organization_id=item.id, user_id=user.id, role="administrador"))
    db.add(
        AuditEvent(
            organization_id=item.id,
            actor_id=user.id,
            action="bootstrap",
            entity="Organization",
            entity_id=item.id,
            origin="cli",
        )
    )
    return item, True


def bootstrap(settings, args):
    supplied = os.environ.get("BOOTSTRAP_PASSWORD")
    password = supplied or getpass.getpass("Senha inicial (12–128 caracteres): ")
    body = Signup(
        name=args.name,
        email=args.email,
        password=password,
        organization_name=args.organization,
        slug=args.slug,
    )
    engine = create_engine(settings.migration_database_url or settings.database_url)
    with Session(engine) as db, db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(728103)"))
        if settings.soldesk_mode == "community" and db.scalar(select(Organization.id).limit(1)):
            raise RuntimeError("Community já possui uma organização; bootstrap não alterou dados")
        _, created = create_organization(
            db, body.organization_name, body.slug, body.email, body.name, body.password
        )
        if not created:
            raise RuntimeError("Organização já existe; bootstrap não altera sua senha")
    print("Organização e administrador criados. Nenhuma senha foi registrada no log.")


def seed(settings, json_output=False):
    if settings.soldesk_mode != "cloud" or settings.environment == "production":
        raise RuntimeError(
            "Demonstração com duas organizações exige modo cloud e ambiente não produtivo"
        )
    engine = create_engine(settings.migration_database_url or settings.database_url)
    credentials = []
    with Session(engine) as db, db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(728103)"))
        for label in ("aurora", "horizonte"):
            admin_password = secrets.token_urlsafe(18)
            org, created = create_organization(
                db,
                f"Empresa fictícia {label.title()}",
                f"demo-{label}",
                f"admin.{label}@example.test",
                f"Admin {label.title()}",
                admin_password,
            )
            if not created:
                continue
            technician_password = secrets.token_urlsafe(18)
            technician = User(
                name=f"Técnico {label.title()}",
                email=f"tecnico.{label}@example.test",
                password_hash=password_hash(technician_password),
            )
            db.add(technician)
            db.flush()
            db.add(
                OrganizationMembership(
                    organization_id=org.id, user_id=technician.id, role="tecnico"
                )
            )
            set_context(db, org.id)
            name = f"Merceária {label.title()}"
            normalized = db.scalar(text("SELECT public.search_normalize(:name)"), {"name": name})
            db.add(
                Client(
                    organization_id=org.id,
                    name=name,
                    name_key=normalized,
                    nickname=f"Mercadinho {label.title()}",
                )
            )
            credentials.extend(
                [
                    (f"admin.{label}@example.test", admin_password),
                    (technician.email, technician_password),
                ]
            )
    if json_output:
        print(
            json.dumps([{"email": email, "password": password} for email, password in credentials])
        )
        return
    print("Demonstração idempotente concluída. Credenciais novas, exibidas somente nesta execução:")
    for email, password in credentials:
        print(f"{email}  {password}")


def main():
    parser = argparse.ArgumentParser(description="Administração explícita do SolDesk")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    demo = commands.add_parser("seed-demo")
    demo.add_argument("--json", action="store_true", help="Credenciais novas como JSON em stdout")
    first = commands.add_parser("bootstrap")
    first.add_argument("--organization", required=True)
    first.add_argument("--slug", required=True)
    first.add_argument("--name", required=True)
    first.add_argument("--email", required=True)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "migrate":
        migrate(settings)
    elif args.command == "seed-demo":
        seed(settings, args.json)
    else:
        bootstrap(settings, args)


if __name__ == "__main__":
    main()
