"""Autenticação nativa: sem cookies, acesso curto e refresh de uso único."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import select, text, update

from app.access import context, database, set_context
from app.mobile_models import MobileRefreshToken
from app.models import AuthSession, OrganizationMembership, User, new_id, now
from app.schemas import Input, Login, PasswordChange
from app.security import digest, dummy_hash, password_hash, password_matches, throttle

router = APIRouter(prefix="/api/v1/mobile/auth", tags=["Sessão mobile"])
ACCESS_SECONDS = 900
REFRESH_DAYS = 30


class RefreshInput(Input):
    refresh_token: str = Field(min_length=40, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


def issue(db, user_id, organization_id, *, family_id=None, deadline=None):
    set_context(db, organization_id, user_id)
    access, refresh, instant = secrets.token_urlsafe(48), secrets.token_urlsafe(48), now()
    deadline = deadline or instant + timedelta(days=REFRESH_DAYS)
    session = AuthSession(
        token_hash=digest(access),
        user_id=user_id,
        organization_id=organization_id,
        expira_em=instant + timedelta(seconds=ACCESS_SECONDS),
        client_kind="mobile",
    )
    db.add(session)
    db.flush()
    db.add(
        MobileRefreshToken(
            token_hash=digest(refresh),
            user_id=user_id,
            organization_id=organization_id,
            family_id=family_id or new_id(),
            session_hash=session.token_hash,
            expira_em=deadline,
        )
    )
    db.flush()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "acesso_expira_em": session.expira_em,
        "renovacao_expira_em": deadline,
    }


def find_refresh(db, token):
    token_hash = digest(token)
    found = db.execute(
        text("SELECT * FROM public.mobile_refresh_context(:hash)"), {"hash": token_hash}
    ).first()
    if found is None:
        raise HTTPException(401, "Entre novamente para continuar")
    set_context(db, found.organization_id, found.user_id)
    item = db.get(MobileRefreshToken, token_hash)
    # Mesmo lock para qualquer geração da família; replay e rotação não se cruzam.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:family,0))"),
        {"family": "mobile:" + item.family_id},
    )
    return db.scalar(
        select(MobileRefreshToken)
        .where(MobileRefreshToken.token_hash == token_hash)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def revoke_family(db, item):
    sessions = select(MobileRefreshToken.session_hash).where(
        MobileRefreshToken.family_id == item.family_id
    )
    instant = now()
    db.execute(
        update(AuthSession).where(AuthSession.token_hash.in_(sessions)).values(revogado_em=instant)
    )
    db.execute(
        update(MobileRefreshToken)
        .where(MobileRefreshToken.family_id == item.family_id)
        .values(revogado_em=instant)
    )


@router.post("/login")
def login(body: Login, request: Request, db=Depends(database, scope="function")):
    throttle(request, "login", body.email)
    user = db.scalar(select(User).where(User.email == body.email))
    valid = password_matches(user.password_hash if user else dummy_hash, body.password)
    if not valid or user is None:
        throttle(request, "login", body.email, failed=True)
        raise HTTPException(401, "Não foi possível entrar. Confira os dados ou tente mais tarde")
    set_context(db, user_id=user.id)
    member = db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.situation == "ativo",
        )
        .order_by(OrganizationMembership.organization_id)
    )
    if member is None:
        throttle(request, "login", body.email, failed=True)
        raise HTTPException(401, "Não foi possível entrar. Confira os dados ou tente mais tarde")
    throttle(request, "login", body.email, failed=False)
    return issue(db, user.id, member.organization_id)


@router.post("/refresh")
def refresh(body: RefreshInput, request: Request, db=Depends(database, scope="function")):
    throttle(request, "refresh")
    item = find_refresh(db, body.refresh_token)
    if item.revogado_em or item.expira_em <= now():
        raise HTTPException(401, "Entre novamente para continuar")
    if item.usado_em:
        revoke_family(db, item)
        # A recusa não pode desfazer a revogação, mesmo com rollback da dependência.
        db.commit()
        raise HTTPException(401, "Sessão de renovação reutilizada. Entre novamente")
    old = db.get(AuthSession, item.session_hash)
    member = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == item.organization_id,
            OrganizationMembership.user_id == item.user_id,
            OrganizationMembership.situation == "ativo",
        )
    )
    if old is None or old.revogado_em or old.client_kind != "mobile" or member is None:
        raise HTTPException(401, "Entre novamente para continuar")
    item.usado_em, old.revogado_em = now(), now()
    return issue(
        db, item.user_id, item.organization_id, family_id=item.family_id, deadline=item.expira_em
    )


@router.post("/logout", status_code=204)
def logout(body: RefreshInput, db=Depends(database, scope="function")):
    item = find_refresh(db, body.refresh_token)
    revoke_family(db, item)
    return Response(status_code=204)


@router.post("/password")
def change_password(body: PasswordChange, request: Request, ctx=Depends(context, scope="function")):
    if ctx.session.client_kind != "mobile":
        raise HTTPException(403, "Use uma sessão do aplicativo")
    if not password_matches(ctx.user.password_hash, body.current_password):
        raise HTTPException(400, "Confira a senha atual")
    ctx.user.password_hash = password_hash(body.new_password)
    ctx.user.must_change_password = False
    ctx.db.execute(
        update(AuthSession).where(AuthSession.user_id == ctx.user.id).values(revogado_em=now())
    )
    ctx.audit(request, "senha_alterada", "User", ctx.user.id)
    return issue(ctx.db, ctx.user.id, ctx.organization_id)
