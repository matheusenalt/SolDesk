import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request
from sqlalchemy import text

from app.models import AuthSession, AuthThrottle, CsrfGrant, now

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(value):
    if not 12 <= len(value) <= 128 or value.isspace():
        raise HTTPException(422, "Use uma senha de 12 a 128 caracteres")
    return hasher.hash(value)


def password_matches(encoded, value):
    try:
        return hasher.verify(encoded, value)
    except VerificationError:
        return False


def cookie(response, name, value, settings, max_age):
    response.set_cookie(
        name,
        value,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=max_age,
        path="/",
    )


def issue_csrf(db, response, settings, session_token=None):
    token = secrets.token_urlsafe(32)
    db.add(
        CsrfGrant(
            token_hash=digest(token),
            session_hash=digest(session_token) if session_token else None,
            expira_em=now() + timedelta(hours=1),
        )
    )
    cookie(response, "soldesk_csrf", token, settings, 3600)
    return token


def check_csrf(request: Request):
    if request.method not in {"POST", "PATCH", "PUT", "DELETE"}:
        return
    credential, kind = request_credential(request)
    if kind == "mobile":
        if request.url.path in {
            "/api/v1/auth/login",
            "/api/v1/auth/password",
            "/api/v1/organizations",
            "/api/v1/invitations/accept",
            "/api/v1/organizations/select",
        }:
            raise HTTPException(403, "Use o fluxo de autenticação do aplicativo")
        with request.app.state.sessions() as db:
            validate_access(db, credential, kind)
        return
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        raise HTTPException(403, "Origem não permitida")
    header = request.headers.get("x-csrf-token", "")
    token = request.cookies.get("soldesk_csrf", "")
    if not header or not secrets.compare_digest(header, token):
        raise HTTPException(403, "Atualize a página e tente novamente (CSRF)")
    with request.app.state.sessions() as db:
        grant = db.get(CsrfGrant, digest(token))
        session_token = request.cookies.get("soldesk_session")
        binding = digest(session_token) if session_token else None
        if grant is None or grant.expira_em <= now() or grant.session_hash != binding:
            raise HTTPException(403, "Atualize a página e tente novamente (CSRF)")


def request_credential(request):
    authorization = request.headers.get("authorization")
    if authorization is not None:
        if request.cookies.get("soldesk_session") or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Envie somente a sessão do aplicativo")
        token = authorization[7:]
        if not 40 <= len(token) <= 128 or not token.isascii() or any(c.isspace() for c in token):
            raise HTTPException(401, "Entre novamente para continuar")
        return token, "mobile"
    return request.cookies.get("soldesk_session", ""), "web"


def validate_access(db, token, kind):
    item = db.get(AuthSession, digest(token)) if token else None
    if item is None or item.client_kind != kind or item.revogado_em or item.expira_em <= now():
        raise HTTPException(401, "Entre novamente para continuar")
    return item


def new_session(db, response, settings, user_id, organization_id):
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user_id,
            organization_id=organization_id,
            expira_em=now() + timedelta(hours=settings.session_hours),
        )
    )
    cookie(response, "soldesk_session", token, settings, settings.session_hours * 3600)
    return issue_csrf(db, response, settings, token)


def throttle(request, purpose, account="", failed=None):
    """Estado persistente, protegido por lock transacional e compartilhado entre workers."""
    ip = request.client.host if request.client else "desconhecido"
    keys = [(f"{purpose}:ip:{digest(ip)}", 30)]
    if account:
        keys.append((f"{purpose}:user:{digest(account)}", 5))
    blocked = False
    with request.app.state.sessions.begin() as db:
        for key, limit in sorted(keys):
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
            )
            item = db.get(AuthThrottle, key)
            if item is None:
                item = AuthThrottle(key=key, count=0, failures=0, window_em=now())
                db.add(item)
            if failed is None:
                if item.window_em + timedelta(minutes=1) <= now():
                    item.count = 0
                    item.window_em = now()
                item.count += 1
                blocked |= item.count > limit or bool(
                    item.bloqueado_ate and item.bloqueado_ate > now()
                )
            elif failed:
                item.failures += 1
                if item.failures >= 5:
                    item.bloqueado_ate = now() + timedelta(
                        seconds=min(900, 30 * 2 ** min(item.failures - 5, 5))
                    )
            else:
                item.failures = 0
                item.bloqueado_ate = None
    if blocked:
        raise HTTPException(429, "Muitas tentativas. Aguarde e tente novamente")
