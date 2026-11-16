import json
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from app.config import Settings
from app.database import Installation, session_factory

logger = logging.getLogger("soldesk")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def problem(status: int, title: str, request_id: str | None = None):
    body = {"type": "about:blank", "title": title, "status": status}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine, sessions = session_factory(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    app = FastAPI(title="SolDesk API", version="1.0.0", lifespan=lifespan)
    app.state.sessions = sessions
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = perf_counter()
        request_id = str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            # Não registrar URL, query, corpo, credenciais ou detalhes internos.
            logger.error(json.dumps({"event": "request_error", "request_id": request_id}))
            response = problem(500, "Não foi possível concluir a solicitação", request_id)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        titles = {404: "Recurso não encontrado", 405: "Método não permitido"}
        return problem(
            exc.status_code,
            titles.get(exc.status_code, str(exc.detail)),
            request.state.request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc):
        return problem(422, "Confira os dados informados", request.state.request_id)

    @app.exception_handler(IntegrityError)
    async def conflict_error(request: Request, _exc):
        return problem(
            409, "Cadastro já existente ou referência inválida", request.state.request_id
        )

    @app.get("/api/v1/health", tags=["Instalação"])
    def health():
        try:
            with sessions() as session:
                session.execute(text("SELECT 1"))
                if session.get(Installation, 1) is None:
                    return problem(503, "Instalação não inicializada; execute as migrações")
        except SQLAlchemyError:
            return problem(503, "Banco de dados indisponível; confira as migrações")
        return {"status": "ok", "database": "connected"}

    @app.get("/api/v1/server-info", tags=["Instalação"])
    def server_info():
        try:
            with sessions() as session:
                installation = session.get(Installation, 1)
                if installation is None:
                    return problem(503, "Instalação não inicializada; execute as migrações")
                instance_id = installation.instance_id
                revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        except SQLAlchemyError:
            return problem(503, "Banco de dados indisponível; confira as migrações")
        return {
            "product": "SolDesk",
            "api_version": "1.0.0",
            "instance_id": instance_id,
            "mode": settings.soldesk_mode,
            "capabilities": ["health", "server_info"]
            + (["auth", "organizations", "clients", "audit"] if revision == "0002" else []),
        }

    from app.routes import router

    app.include_router(router)
    return app


app = create_app()
