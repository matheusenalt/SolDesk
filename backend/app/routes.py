import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select, text, update

from app.access import context, database, set_context
from app.models import (
    AuditEvent,
    AuthSession,
    Client,
    ClientExternalRef,
    Invitation,
    Organization,
    OrganizationMembership,
    User,
    new_id,
    now,
)
from app.schemas import (
    AcceptInvitation,
    ClientInput,
    InvitationInput,
    Login,
    MembershipChange,
    OrganizationChange,
    OrganizationSelection,
    PasswordChange,
    Signup,
    TemporaryUser,
)
from app.security import (
    check_csrf,
    digest,
    dummy_hash,
    issue_csrf,
    new_session,
    password_hash,
    password_matches,
    throttle,
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(check_csrf)])


@router.get("/auth/config", tags=["Autenticação"])
def auth_config(request: Request):
    settings = request.app.state.settings
    return {"signup_enabled": settings.soldesk_mode == "cloud" and settings.allow_org_signup}


def organization_data(item):
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "timezone": item.timezone,
        "settings": item.settings,
    }


def profile(ctx):
    organizations = ctx.db.scalars(
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(
            OrganizationMembership.user_id == ctx.user.id,
            OrganizationMembership.situation == "ativo",
        )
        .order_by(Organization.slug)
    ).all()
    return {
        "id": ctx.user.id,
        "name": ctx.user.name,
        "email": ctx.user.email,
        "organization_id": ctx.organization_id,
        "role": ctx.membership.role,
        "must_change_password": ctx.user.must_change_password,
        "organizations": [organization_data(o) for o in organizations],
    }


@router.get("/auth/csrf", tags=["Autenticação"])
def csrf(request: Request, response: Response, db=Depends(database, scope="function")):
    return {
        "csrf_token": issue_csrf(
            db, response, request.app.state.settings, request.cookies.get("soldesk_session")
        )
    }


@router.post("/auth/login", tags=["Autenticação"])
def login(
    body: Login, request: Request, response: Response, db=Depends(database, scope="function")
):
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
            OrganizationMembership.user_id == user.id, OrganizationMembership.situation == "ativo"
        )
        .order_by(OrganizationMembership.organization_id)
    )
    if member is None:
        throttle(request, "login", body.email, failed=True)
        raise HTTPException(401, "Não foi possível entrar. Confira os dados ou tente mais tarde")
    throttle(request, "login", body.email, failed=False)
    return {
        "csrf_token": new_session(
            db, response, request.app.state.settings, user.id, member.organization_id
        )
    }


@router.get("/me", tags=["Autenticação"])
def me(ctx=Depends(context, scope="function")):
    return profile(ctx)


@router.post("/auth/logout", tags=["Autenticação"])
def logout(response: Response, ctx=Depends(context, scope="function")):
    ctx.session.revogado_em = now()
    response.delete_cookie("soldesk_session", path="/")
    response.delete_cookie("soldesk_csrf", path="/")
    return {"message": "Sessão encerrada"}


@router.post("/auth/logout-all", tags=["Autenticação"])
def logout_all(response: Response, ctx=Depends(context, scope="function")):
    ctx.db.execute(
        update(AuthSession).where(AuthSession.user_id == ctx.user.id).values(revogado_em=now())
    )
    response.delete_cookie("soldesk_session", path="/")
    response.delete_cookie("soldesk_csrf", path="/")
    return {"message": "Todas as sessões foram encerradas"}


@router.post("/auth/password", tags=["Autenticação"])
def change_password(
    body: PasswordChange,
    request: Request,
    response: Response,
    ctx=Depends(context, scope="function"),
):
    if not password_matches(ctx.user.password_hash, body.current_password):
        raise HTTPException(400, "Confira a senha atual")
    ctx.user.password_hash = password_hash(body.new_password)
    ctx.user.must_change_password = False
    ctx.db.execute(
        update(AuthSession).where(AuthSession.user_id == ctx.user.id).values(revogado_em=now())
    )
    ctx.audit(request, "senha_alterada", "User", ctx.user.id)
    return {
        "csrf_token": new_session(
            ctx.db, response, request.app.state.settings, ctx.user.id, ctx.organization_id
        )
    }


@router.get("/organizations", tags=["Organizações"])
def organizations(ctx=Depends(context, scope="function")):
    return profile(ctx)["organizations"]


@router.post("/organizations/select", tags=["Organizações"])
def select_organization(
    body: OrganizationSelection, request: Request, ctx=Depends(context, scope="function")
):
    # ID do cliente é apenas seleção: a permissão é validada usando o usuário da sessão.
    member = ctx.db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == ctx.user.id,
            OrganizationMembership.organization_id == body.organization_id,
            OrganizationMembership.situation == "ativo",
        )
    )
    if member is None:
        raise HTTPException(404, "Organização não encontrada")
    ctx.session.organization_id = member.organization_id
    set_context(ctx.db, member.organization_id, ctx.user.id)
    ctx.membership = member
    return profile(ctx)


@router.patch("/organizations/current", tags=["Organizações"])
def edit_organization(
    body: OrganizationChange, request: Request, ctx=Depends(context, scope="function")
):
    ctx.require_admin()
    item = ctx.db.get(Organization, ctx.organization_id)
    before = {"name": item.name, "timezone": item.timezone, "settings": item.settings}
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    ctx.audit(request, "organizacao_alterada", "Organization", item.id, before, body.model_dump())
    return organization_data(item)


@router.post("/organizations", tags=["Organizações"], status_code=201)
def signup(
    body: Signup, request: Request, response: Response, db=Depends(database, scope="function")
):
    settings = request.app.state.settings
    if settings.soldesk_mode != "cloud" or not settings.allow_org_signup:
        raise HTTPException(403, "Cadastro público de organizações desabilitado")
    throttle(request, "signup", body.email)
    encoded = password_hash(body.password)
    organization_id, user_id = new_id(), new_id()
    set_context(db, organization_id, user_id)
    organization = Organization(
        id=organization_id, name=body.organization_name, slug=body.slug, timezone=body.timezone
    )
    user = User(id=user_id, name=body.name, email=body.email, password_hash=encoded)
    db.add_all([organization, user])
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=organization_id, user_id=user_id, role="administrador"
        )
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_id=user_id,
            action="organizacao_criada",
            entity="Organization",
            entity_id=organization_id,
            origin=request.client.host[:80],
        )
    )
    return {"csrf_token": new_session(db, response, settings, user_id, organization_id)}


@router.get("/memberships", tags=["Equipe"])
def members(ctx=Depends(context, scope="function")):
    if ctx.membership.role not in {"administrador", "gestor"}:
        raise HTTPException(403, "Acesso restrito à gestão da equipe")
    rows = ctx.db.execute(
        ctx.query(OrganizationMembership)
        .add_columns(User.name, User.email)
        .join(User, User.id == OrganizationMembership.user_id)
        .order_by(User.name)
    ).all()
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "name": name,
            "email": email,
            "role": m.role,
            "situation": m.situation,
        }
        for m, name, email in rows
    ]


@router.patch("/memberships/{identifier}", tags=["Equipe"])
def edit_member(
    identifier: str,
    body: MembershipChange,
    request: Request,
    ctx=Depends(context, scope="function"),
):
    ctx.require_admin()
    # Serializa todas as alterações administrativas da organização, inclusive concorrentes.
    ctx.db.scalar(
        select(Organization).where(Organization.id == ctx.organization_id).with_for_update()
    )
    item = ctx.get(OrganizationMembership, identifier)
    if (
        item.user_id == ctx.user.id
        and body.role == "administrador"
        and item.role != "administrador"
    ):
        raise HTTPException(403, "Não é permitido promover a si mesmo")
    if (
        item.role == "administrador"
        and item.situation == "ativo"
        and (body.role != "administrador" or body.situation != "ativo")
    ):
        count = ctx.db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == ctx.organization_id,
                OrganizationMembership.role == "administrador",
                OrganizationMembership.situation == "ativo",
            )
        )
        if count <= 1:
            raise HTTPException(409, "Mantenha pelo menos um administrador ativo")
    before = {"role": item.role, "situation": item.situation}
    item.role, item.situation = body.role, body.situation
    if body.situation == "inativo" or before["role"] != body.role:
        ctx.db.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == item.user_id,
                AuthSession.organization_id == ctx.organization_id,
            )
            .values(revogado_em=now())
        )
    ctx.audit(
        request, "integrante_alterado", "OrganizationMembership", item.id, before, body.model_dump()
    )
    return {"id": item.id, **body.model_dump()}


@router.post("/memberships", tags=["Equipe"], status_code=201)
def temporary_user(body: TemporaryUser, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    if ctx.db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "Use convite para adicionar uma conta já existente")
    temporary = secrets.token_urlsafe(18)
    user = User(
        name=body.name,
        email=body.email,
        password_hash=password_hash(temporary),
        must_change_password=True,
    )
    ctx.db.add(user)
    ctx.db.flush()
    member = OrganizationMembership(
        organization_id=ctx.organization_id, user_id=user.id, role=body.role
    )
    ctx.db.add(member)
    ctx.db.flush()
    ctx.audit(
        request, "integrante_criado", "OrganizationMembership", member.id, after={"role": body.role}
    )
    return {"id": member.id, "temporary_password": temporary}


@router.post("/memberships/{identifier}/reset-password", tags=["Equipe"])
def reset_password(identifier: str, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    item = ctx.get(OrganizationMembership, identifier)
    # Uma organização não pode tomar posse de identidade compartilhada com outra.
    if ctx.db.scalar(text("SELECT public.membership_count(:u)"), {"u": item.user_id}) != 1:
        raise HTTPException(409, "Conta compartilhada: solicite ao titular a alteração da senha")
    user = ctx.db.get(User, item.user_id)
    temporary = secrets.token_urlsafe(18)
    user.password_hash = password_hash(temporary)
    user.must_change_password = True
    ctx.db.execute(
        update(AuthSession).where(AuthSession.user_id == user.id).values(revogado_em=now())
    )
    ctx.audit(request, "senha_redefinida", "User", user.id)
    return {"temporary_password": temporary}


@router.post("/invitations", tags=["Equipe"], status_code=201)
def invite(body: InvitationInput, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    token = secrets.token_urlsafe(32)
    item = Invitation(
        organization_id=ctx.organization_id,
        email=body.email,
        role=body.role,
        token_hash=digest(token),
        expira_em=now() + timedelta(days=2),
    )
    ctx.db.add(item)
    ctx.db.flush()
    ctx.audit(request, "convite_criado", "Invitation", item.id, after={"role": body.role})
    return {"id": item.id, "invitation_path": f"/#convite={token}", "expira_em": item.expira_em}


@router.get("/invitations", tags=["Equipe"])
def invitations(ctx=Depends(context, scope="function")):
    ctx.require_admin()
    return [
        {
            "id": i.id,
            "email": i.email,
            "role": i.role,
            "expira_em": i.expira_em,
            "usado_em": i.usado_em,
        }
        for i in ctx.db.scalars(ctx.query(Invitation).order_by(Invitation.expira_em.desc()))
    ]


@router.post("/invitations/accept", tags=["Equipe"])
def accept(
    body: AcceptInvitation,
    request: Request,
    response: Response,
    db=Depends(database, scope="function"),
):
    throttle(request, "accept", body.email)
    organization_id = db.scalar(
        text("SELECT public.invitation_organization(:token)"), {"token": digest(body.token)}
    )
    if not organization_id:
        raise HTTPException(400, "Convite inválido, expirado ou já utilizado")
    set_context(db, organization_id)
    invitation = db.scalar(
        select(Invitation).where(Invitation.token_hash == digest(body.token)).with_for_update()
    )
    if (
        invitation is None
        or invitation.usado_em
        or invitation.expira_em <= now()
        or invitation.email != body.email
    ):
        raise HTTPException(400, "Convite inválido, expirado ou já utilizado")
    user = db.scalar(select(User).where(User.email == body.email))
    if user:
        if not password_matches(user.password_hash, body.password):
            raise HTTPException(400, "Confira os dados do convite e a senha da conta")
    else:
        user = User(name=body.name, email=body.email, password_hash=password_hash(body.password))
        db.add(user)
        db.flush()
    set_context(db, organization_id, user.id)
    member = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if member is not None:
        raise HTTPException(
            409, "A conta já possui vínculo; o administrador deve revisar a situação"
        )
    db.add(
        OrganizationMembership(
            organization_id=organization_id, user_id=user.id, role=invitation.role
        )
    )
    invitation.usado_em = now()
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_id=user.id,
            action="convite_aceito",
            entity="Invitation",
            entity_id=invitation.id,
            origin=request.client.host[:80],
        )
    )
    return {
        "csrf_token": new_session(
            db, response, request.app.state.settings, user.id, organization_id
        )
    }


def client_data(ctx, item):
    data = {
        key: getattr(item, key)
        for key in ("id", "name", "nickname", "phone", "email", "notes", "situation", "criado_em")
    }
    refs = ctx.db.scalars(
        ctx.query(ClientExternalRef).where(ClientExternalRef.client_id == item.id)
    ).all()
    data["external_refs"] = [
        {"provider": r.provider, "identifier": r.identifier, "label": r.label} for r in refs
    ]
    return data


def save_client(ctx, item, body, request):
    data = body.model_dump(exclude={"external_refs"})
    for key, value in data.items():
        setattr(item, key, value)
    item.name_key = ctx.db.scalar(
        text("SELECT public.search_normalize(:name)"), {"name": body.name.strip()}
    )
    ctx.db.add(item)
    ctx.db.flush()
    for old in ctx.db.scalars(
        ctx.query(ClientExternalRef).where(ClientExternalRef.client_id == item.id)
    ):
        ctx.db.delete(old)
    for ref in body.external_refs:
        ctx.db.add(
            ClientExternalRef(
                organization_id=ctx.organization_id, client_id=item.id, **ref.model_dump()
            )
        )
    ctx.audit(request, "cliente_salvo", "Client", item.id, after={"situation": item.situation})
    ctx.db.flush()
    return client_data(ctx, item)


@router.get("/clients", tags=["Clientes"])
def list_clients(
    search: str = Query(default="", max_length=160),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    query = ctx.query(Client)
    if search.strip():
        needle = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + needle + "%"
        query = query.where(
            func.search_normalize(Client.name).ilike(func.search_normalize(pattern), escape="\\")
            | func.search_normalize(Client.nickname).ilike(
                func.search_normalize(pattern), escape="\\"
            )
        )
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(
        query.order_by(Client.criado_em, Client.id).offset(offset).limit(limit)
    ).all()
    return {
        "items": [client_data(ctx, row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/clients/{identifier}", tags=["Clientes"])
def get_client(identifier: str, ctx=Depends(context, scope="function")):
    return client_data(ctx, ctx.get(Client, identifier))


@router.post("/clients", tags=["Clientes"], status_code=201)
def create_client(body: ClientInput, request: Request, ctx=Depends(context, scope="function")):
    return save_client(ctx, Client(organization_id=ctx.organization_id), body, request)


@router.patch("/clients/{identifier}", tags=["Clientes"])
def edit_client(
    identifier: str, body: ClientInput, request: Request, ctx=Depends(context, scope="function")
):
    return save_client(ctx, ctx.get(Client, identifier), body, request)


@router.get("/audit-events", tags=["Auditoria"])
def audit_events(offset: int = Query(default=0, ge=0), ctx=Depends(context, scope="function")):
    if ctx.membership.role not in {"administrador", "gestor"}:
        raise HTTPException(403, "Acesso restrito à gestão")
    rows = ctx.db.scalars(
        ctx.query(AuditEvent)
        .order_by(AuditEvent.ocorrido_em.desc(), AuditEvent.id)
        .offset(offset)
        .limit(50)
    )
    return [
        {
            key: getattr(row, key)
            for key in (
                "id",
                "actor_id",
                "action",
                "entity",
                "entity_id",
                "before",
                "after",
                "ocorrido_em",
                "origin",
            )
        }
        for row in rows
    ]
