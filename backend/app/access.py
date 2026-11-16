"""Transação por requisição e ponto único de acesso aos dados do tenant."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditEvent, AuthSession, OrganizationMembership, User


def set_context(db, organization_id="", user_id=""):
    db.execute(
        text(
            "SELECT set_config('app.organization_id', :o, true), "
            "set_config('app.user_id', :u, true)"
        ),
        {"o": organization_id, "u": user_id},
    )


def database(request: Request):
    with request.app.state.sessions() as db:
        if db.bind.dialect.name != "postgresql":
            raise HTTPException(503, "Esta operação exige PostgreSQL")
        role = db.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        owns = db.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
                "AND tablename='client' AND tableowner=current_user)"
            )
        )
        if role.rolsuper or role.rolbypassrls or owns:
            raise HTTPException(503, "Configure o usuário restrito de banco da API")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


@dataclass
class Context:
    db: Session
    user: User
    session: AuthSession
    membership: OrganizationMembership

    @property
    def organization_id(self):
        return self.session.organization_id

    def require_admin(self):
        if self.membership.role != "administrador":
            raise HTTPException(403, "Ação permitida somente ao administrador")

    def query(self, model):
        return select(model).where(model.organization_id == self.organization_id)

    def get(self, model, identifier):
        item = self.db.scalar(self.query(model).where(model.id == identifier))
        if item is None:
            raise HTTPException(404, "Recurso não encontrado")
        return item

    def audit(self, request, action, entity, entity_id, before=None, after=None):
        self.db.add(
            AuditEvent(
                organization_id=self.organization_id,
                actor_id=self.user.id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                before=before or {},
                after=after or {},
                origin=(request.client.host if request.client else "desconhecido")[:80],
            )
        )


def context(request: Request, db=Depends(database, scope="function")):
    from app.security import request_credential, validate_access

    credential, kind = request_credential(request)
    session = validate_access(db, credential, kind)
    set_context(db, session.organization_id, session.user_id)
    member = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == session.organization_id,
            OrganizationMembership.user_id == session.user_id,
            OrganizationMembership.situation == "ativo",
        )
    )
    user = db.get(User, session.user_id)
    if member is None or user is None:
        raise HTTPException(401, "Entre novamente para continuar")
    allowed = {
        "/api/v1/me",
        "/api/v1/auth/password",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/mobile/auth/password",
    }
    if user.must_change_password and request.url.path not in allowed:
        raise HTTPException(403, "Troque a senha temporária para continuar")
    return Context(db, user, session, member)
