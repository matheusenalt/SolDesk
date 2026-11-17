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
    from app.media_routes import signing_key

    app.state.download_signing_key = signing_key(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "Idempotency-Key",
            "X-Filename",
            "Authorization",
        ],
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
            "instance_name": settings.soldesk_instance_name,
            "mobile_protocol_version": 1
            if revision in {"0006a", "0009", "0010", "0011", "0012"}
            else None,
            "mode": settings.soldesk_mode,
            "capabilities": ["health", "server_info"]
            + (
                ["auth", "organizations", "clients", "audit"]
                if revision
                in {"0002", "0003", "0004", "0005", "0006a", "0009", "0010", "0011", "0012"}
                else []
            )
            + (
                ["records", "tickets", "notifications"]
                if revision in {"0003", "0004", "0005", "0006a", "0009", "0010", "0011", "0012"}
                else []
            )
            + (
                ["attachments", "audio", "templates"]
                if revision in {"0004", "0005", "0006a", "0009", "0010", "0011", "0012"}
                else []
            )
            + (
                ["knowledge", "search", "reports"]
                if revision in {"0005", "0006a", "0009", "0010", "0011", "0012"}
                else []
            )
            + (["mobile_auth"] if revision in {"0006a", "0009", "0010", "0011", "0012"} else [])
            + (["text_validation"] if revision in {"0009", "0010", "0011", "0012"} else [])
            + (["attendances"] if revision in {"0010", "0011", "0012"} else [])
            + (["systems"] if revision in {"0011", "0012"} else [])
            + (["tasks"] if revision == "0012" else []),
        }

    from app.attendance_routes import router as attendance_router
    from app.knowledge_routes import router as knowledge_router
    from app.media_routes import router as media_router
    from app.mobile_routes import router as mobile_router
    from app.report_routes import router as report_router
    from app.routes import router
    from app.system_routes import router as system_router
    from app.task_routes import router as task_router
    from app.work_routes import router as work_router

    app.include_router(router)
    app.include_router(work_router)
    app.include_router(system_router)
    app.include_router(task_router)
    app.include_router(attendance_router)
    app.include_router(media_router)
    app.include_router(knowledge_router)
    app.include_router(report_router)
    app.include_router(mobile_router)
    return app


app = create_app()
