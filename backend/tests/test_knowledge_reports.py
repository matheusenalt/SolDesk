import csv
import io
import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
import test_identity as identity
import test_work as work_tests
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import reports
from app.access import Context, set_context
from app.insight_models import ArticleConsultation, ArticleVersion, Team
from app.knowledge import search_articles
from app.knowledge_routes import ArticleSearch
from app.models import AuditEvent, Organization, OrganizationMembership, User
from app.reports import ReportFilters, date_bounds, elapsed, period, safe_cell, sample
from app.work_models import KnowledgeArticle, Record, Ticket, TicketEvent, TicketInterval

pg_settings = identity.pg_settings
world = identity.world
login = identity.login
mutate = identity.mutate


def article(world, source_client_id=None, **fields):
    if source_client_id is None:
        source_client_id = work_tests.prepare(world)
    login(world.client, world.technician, world.password)
    source = work_tests.create(
        world, source_client_id, "conhecimento", category="fiscal", system="SGBR"
    )
    item = world.client.get(f"/api/v1/knowledge/articles/{source['article_id']}").json()
    body = {
        "revision": item["revision"],
        "title": "Impressão fictícia: erro 0x80070005",
        "problem": "Falha fictícia na impressão. CFOP 5102 relatado, não verificado.",
        "context": "Exemplo fictício informado para teste.",
        "confirmed_cause": "",
        "procedure": "Procedimento fictício informado pelo autor.",
        "result": "Resultado informado no relato.",
        "text": source["texto_original"],
        "keywords": ["impressão", "fiscal"],
        "category": "fiscal",
        "system": "SGBR",
        "client_id": None,
        **fields,
    }
    edited = mutate(world.client, f"/knowledge/articles/{item['id']}", body, "PATCH")
    assert edited.status_code == 200, edited.text
    return edited.json(), source


def action(client, item, name, **values):
    return mutate(
        client,
        f"/knowledge/articles/{item['id']}/actions",
        {"revision": item["revision"], "action": name, **values},
    )


def publish(world, item):
    submitted = action(world.client, item, "enviar")
    assert submitted.status_code == 200, submitted.text
    login(world.client, world.admin_a, world.password)
    response = action(
        world.client, submitted.json(), "publicar", human_reviewed=True, warnings_reviewed=True
    )
    assert response.status_code == 200, response.text
    return response.json()


def dashboard(client, **params):
    response = client.get("/api/v1/reports", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_editorial_review_states_versions_and_immutable_publication(world):
    item, source = article(world)
    client = world.client
    assert item["confirmed_cause"] == ""
    assert {w["kind"] for w in item["warnings"]} >= {
        "causa_nao_informada",
        "codigo_fiscal_nao_verificado",
    }
    assert client.get("/api/v1/knowledge/search?q=0x80070005").json()["total"] == 0
    submitted = action(client, item, "enviar").json()
    assert submitted["status"] == "aguardando_revisao"
    assert client.get("/api/v1/knowledge/search?q=0x80070005").json()["total"] == 0
    assert (
        action(
            client, submitted, "publicar", human_reviewed=True, warnings_reviewed=True
        ).status_code
        == 403
    )
    login(client, world.admin_a, world.password)
    assert action(client, submitted, "publicar").status_code == 409
    published = action(client, submitted, "publicar", human_reviewed=True, warnings_reviewed=True)
    assert published.status_code == 200, published.text
    item = published.json()
    assert item["status"] == "publicado" and item["reviewer_id"] != item["author_id"]
    assert item["template_version_id"] == source["template_version_id"]
    origin = client.get(f"/api/v1/records/{source['id']}").json()
    assert (
        origin["ocorrido_em"] == source["ocorrido_em"]
        and origin["enviado_em"] == source["enviado_em"]
    )
    assert origin["status"] == origin["article_status"] == "publicado"
    versions = client.get(f"/api/v1/knowledge/articles/{item['id']}/versions").json()
    assert [v["revision"] for v in versions] == [1, 2, 3, 4]
    assert versions[0]["snapshot"]["text"] == source["texto_original"]
    assert versions[1]["actor_name"] == "Técnico fictício"
    assert any(diff["field"] == "title" for diff in versions[1]["diff"])
    with Session(world.runtime_engine) as db:
        set_context(db, world.a)
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE knowledge_article SET title='mudança indevida' WHERE id=:id"),
                {"id": item["id"]},
            )
        db.rollback()
        set_context(db, world.a)
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE article_version SET change='apagar histórico' WHERE article_id=:id"),
                {"id": item["id"]},
            )
    archived = action(client, item, "arquivar", comment="Exemplo fictício obsoleto.")
    assert archived.status_code == 200, archived.text
    assert client.get("/api/v1/knowledge/search?q=0x80070005").json()["total"] == 0
    assert client.get("/api/v1/knowledge/search?q=0x80070005&status=arquivado").json()["total"] == 1
    login(client, world.technician, world.password)
    reopened = action(client, archived.json(), "reabrir")
    assert reopened.status_code == 200 and reopened.json()["status"] == "rascunho"


def test_return_comment_and_configurable_self_publication(world):
    item, _ = article(world)
    submitted = action(world.client, item, "enviar").json()
    login(world.client, world.admin_a, world.password)
    assert action(world.client, submitted, "devolver").status_code == 422
    returned = action(
        world.client, submitted, "devolver", comment="Confira o procedimento fictício."
    ).json()
    assert returned["status"] == "devolvido" and returned["review_comment"]
    assert world.client.get("/api/v1/knowledge/search").json()["total"] == 0
    assert (
        mutate(
            world.client,
            "/knowledge/policy",
            {"publisher_roles": ["administrador", "tecnico"], "allow_self_publish": True},
            "PATCH",
        ).status_code
        == 200
    )
    login(world.client, world.technician, world.password)
    sent = action(world.client, returned, "enviar").json()
    done = action(world.client, sent, "publicar", human_reviewed=True, warnings_reviewed=True)
    assert done.status_code == 200 and done.json()["reviewer_id"] == item["author_id"]
    assert (
        mutate(
            world.client, "/knowledge/policy", {"publisher_roles": ["tecnico"]}, "PATCH"
        ).status_code
        == 403
    )
    with Session(world.admin_engine) as db:
        assert db.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == world.a,
                AuditEvent.action == "politica_conhecimento_alterada",
            )
        )


def test_search_exact_code_accents_snippets_and_client_restriction(world):
    client_id = work_tests.prepare(world)
    second = mutate(world.client, "/clients", {"name": "Outro cliente fictício"}).json()["id"]
    item, _ = article(world, client_id, client_id=client_id)
    item = publish(world, item)
    with Session(world.runtime_engine) as db:
        set_context(db, world.a)
        user = db.scalar(select(User).where(User.email == world.admin_a))
        member = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == world.a,
                OrganizationMembership.user_id == user.id,
            )
        )
        ctx = Context(db, user, SimpleNamespace(organization_id=world.a), member)
        assert (
            search_articles(ctx, ArticleSearch(q="0x80070005", client_id=client_id))["total"] == 1
        )
    client = world.client
    assert client.get("/api/v1/knowledge/search?q=0x80070005").json()["total"] == 0
    for query in ("0x80070005", "CFOP 5102", "impressao", "impressão"):
        found = client.get(
            "/api/v1/knowledge/search", params={"q": query, "client_id": client_id}
        ).json()
        assert found["total"] == 1, found
        assert found["items"][0]["id"] == item["id"]
        assert found["items"][0]["source_accessible"]
        assert found["items"][0]["highlights"]
    assert (
        client.get(
            "/api/v1/knowledge/search", params={"q": "0x80070005", "client_id": second}
        ).json()["total"]
        == 0
    )
    ticket = work_tests.create(
        world,
        second,
        "chamado",
        texto_original="Erro 0x80070005 na impressão fictícia.",
        category="fiscal",
    )
    assert client.get(f"/api/v1/tickets/{ticket['ticket_id']}/suggestions").json()["items"] == []
    correct = work_tests.create(
        world,
        client_id,
        "chamado",
        texto_original="Erro 0x80070005 na impressão fictícia.",
        category="fiscal",
    )
    suggestions = client.get(f"/api/v1/tickets/{correct['ticket_id']}/suggestions").json()
    assert suggestions["label"] == "Sugestão, não diagnóstico"
    assert any(a["id"] == item["id"] for a in suggestions["items"])
    with Session(world.admin_engine) as db:
        indexes = list(
            db.scalars(text("SELECT indexdef FROM pg_indexes WHERE tablename='knowledge_article'"))
        )
        assert any("search_vector" in sql and "gin" in sql for sql in indexes)
        assert any("gin_trgm_ops" in sql for sql in indexes)


def test_article_http_and_database_tenant_isolation(world):
    item, _ = article(world)
    item = publish(world, item)
    login(world.client, world.admin_b, world.password)
    other_client = mutate(world.client, "/clients", {"name": "Cliente da outra empresa"}).json()[
        "id"
    ]
    assert world.client.get(f"/api/v1/knowledge/articles/{item['id']}").status_code == 404
    assert world.client.get(f"/api/v1/knowledge/articles/{item['id']}/versions").status_code == 404
    assert world.client.get("/api/v1/knowledge/search?q=0x80070005").json()["total"] == 0
    assert (
        world.client.get(
            "/api/v1/reports", params={"client_id": item["client_id"] or "a" * 36}
        ).status_code
        == 404
    )
    assert mutate(world.client, "/reports/export", {"client_id": "a" * 36}).status_code == 404
    with Session(world.runtime_engine) as db:
        set_context(db, world.b)
        for model in (KnowledgeArticle, ArticleVersion, ArticleConsultation, Team):
            assert all(row.organization_id == world.b for row in db.scalars(select(model)))
        assert db.get(KnowledgeArticle, item["id"]) is None
        db.rollback()
        set_context(db, world.a)
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE knowledge_article SET client_id=:client WHERE id=:id"),
                {"client": other_client, "id": item["id"]},
            )


def test_consultations_are_aggregate_without_reader(world):
    item, _ = article(world)
    item = publish(world, item)
    for _ in range(3):
        assert world.client.get(f"/api/v1/knowledge/articles/{item['id']}").status_code == 200
    result = dashboard(world.client)
    assert result["article_consultations"] == [
        {"article_id": item["id"], "title": item["title"], "consultations": 3}
    ]
    assert "reader" not in ArticleConsultation.__table__.columns
    assert "user_id" not in ArticleConsultation.__table__.columns
    login(world.client, world.technician, world.password)
    assert dashboard(world.client)["article_consultations"] == []


def test_reports_fact_period_pending_confirmed_and_timezone(world):
    client_id = work_tests.prepare(world)
    first = work_tests.create(
        world, client_id, ocorrido_em="2026-10-31T23:30:00-03:00", category="fiscal", system="SGBR"
    )
    work_tests.create(
        world, client_id, ocorrido_em="2026-11-01T00:15:00-03:00", category="fiscal", system="SGBR"
    )
    assert work_tests.action(world.client, first, "confirmar").status_code == 200
    before = dashboard(world.client, preset="livre", start_date="2026-10-31", end_date="2026-10-31")
    assert (
        before["totals"]["registered_records"] == before["totals"]["confirmed_finalizations"] == 1
    )
    assert before["totals"]["awaiting_review"] == 0
    assert datetime.fromisoformat(before["period"]["start_utc"]) == datetime(
        2026, 10, 31, 3, tzinfo=UTC
    )
    next_day = dashboard(
        world.client, preset="livre", start_date="2026-11-01", end_date="2026-11-01"
    )
    assert next_day["totals"]["confirmed_finalizations"] == 0
    assert next_day["totals"]["awaiting_review"] == 1
    assert next_day["comparison"]["totals"]["confirmed_finalizations"] == 1
    with Session(world.admin_engine) as db, db.begin():
        db.get(Organization, world.a).timezone = "Asia/Tokyo"
    tokyo = dashboard(world.client, preset="livre", start_date="2026-11-01", end_date="2026-11-01")
    assert tokyo["totals"]["registered_records"] == 2
    assert datetime.fromisoformat(tokyo["period"]["start_utc"]) == datetime(
        2026, 10, 31, 15, tzinfo=UTC
    )


def scenario(world):
    client_id = work_tests.prepare(world)
    record = work_tests.create(
        world,
        client_id,
        "chamado",
        assignee_id=world.technician_id,
        category="fiscal",
        system="SGBR",
    )
    identifier = record["ticket_id"]

    def detail():
        return world.client.get(f"/api/v1/tickets/{identifier}").json()

    login(world.client, world.technician, world.password)
    for kind in ("comentario", "esclarecimento"):
        result = mutate(
            world.client,
            f"/tickets/{identifier}/comments",
            {"revision": detail()["revision"], "text": "Conteúdo fictício.", "kind": kind},
        )
        assert result.status_code == 201, result.text
    login(world.client, world.admin_a, world.password)
    assert (
        mutate(
            world.client,
            f"/tickets/{identifier}/comments",
            {"revision": detail()["revision"], "text": "Resposta fictícia.", "kind": "resposta"},
        ).status_code
        == 201
    )
    login(world.client, world.technician, world.password)
    assert (
        mutate(
            world.client,
            f"/tickets/{identifier}",
            {
                "revision": detail()["revision"],
                "status": "resolvido",
                "completion_description": "Procedimento fictício executado",
            },
            "PATCH",
        ).status_code
        == 200
    )
    login(world.client, world.admin_a, world.password)
    assert (
        mutate(
            world.client,
            f"/tickets/{identifier}",
            {"revision": detail()["revision"], "status": "encerrado"},
            "PATCH",
        ).status_code
        == 200
    )
    for state in ("reaberto", "resolvido"):
        login(
            world.client, world.admin_a if state == "reaberto" else world.technician, world.password
        )
        assert (
            mutate(
                world.client,
                f"/tickets/{identifier}",
                {
                    "revision": detail()["revision"],
                    "status": state,
                    "reason": "Gestão solicita nova análise fictícia",
                    "completion_description": "Procedimento fictício executado",
                },
                "PATCH",
            ).status_code
            == 200
        )
    start = datetime(2026, 10, 31, 2, 30, tzinfo=UTC)  # 23:30 do dia 30 em São Paulo.
    with Session(world.admin_engine) as db, db.begin():
        ticket = db.get(Ticket, identifier)
        ticket.aberto_em = start
        events = list(
            db.scalars(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == identifier)
                .order_by(TicketEvent.ocorrido_em)
            )
        )
        assert len(events) == 8
        for event, minute in zip(events, (0, 10, 20, 50, 80, 90, 100, 110), strict=True):
            event.ocorrido_em = start + timedelta(minutes=minute)
        interval = db.scalar(select(TicketInterval).where(TicketInterval.ticket_id == identifier))
        interval.entrada_em, interval.saida_em = (
            start + timedelta(minutes=20),
            start + timedelta(minutes=50),
        )
        ticket.resolvido_em, ticket.encerrado_em = (
            start + timedelta(minutes=110),
            start + timedelta(minutes=90),
        )
    return identifier


def test_event_authorship_unique_reopen_and_pause_adjusted_times(world):
    identifier = scenario(world)
    login(world.client, world.admin_a, world.password)
    result = dashboard(world.client, preset="livre", start_date="2026-10-30", end_date="2026-10-31")
    totals = result["totals"]
    assert totals["abriu"] == {"actions": 1, "unique_tickets": 1}
    assert totals["resolveu"] == {"actions": 2, "unique_tickets": 1}
    assert result["ticket_distribution"] == [
        {
            "category": "fiscal",
            "system": "SGBR",
            "priority": "normal",
            "unique_tickets": 1,
        }
    ]
    assert totals["encerrou"] == totals["reabriu"] == {"actions": 1, "unique_tickets": 1}
    by_name = {row["name"]: row for row in result["people"]}
    assert by_name["Admin Aurora"]["abriu"]["actions"] == 1
    assert by_name["Admin Aurora"]["resolveu"]["actions"] == 0
    assert by_name["Técnico fictício"]["resolveu"]["actions"] == 2
    assert by_name["Técnico fictício"]["assumiu"]["actions"] == 1
    assert result["times"]["resolution"]["gross"] == {
        "median_seconds": 2700,
        "p90_seconds": 4380,
        "n": 2,
        "warning": reports.SMALL_SAMPLE,
    }
    assert result["times"]["resolution"]["net"]["median_seconds"] == 1800
    assert result["times"]["resolution"]["net"]["p90_seconds"] == 2760
    assert result["times"]["resolution_unique_tickets"] == 1
    assert result["times"]["first_action"]["gross"]["median_seconds"] == 600
    assert result["queue"] == []
    assert [row["name"] for row in result["people"]] == sorted(by_name, key=str.casefold)
    assert len(world.client.get(f"/api/v1/tickets/{identifier}").json()["events"]) == 8


def test_personal_scope_filters_csv_and_no_evaluation(world):
    scenario(world)
    # Atendimentos próprios de A não podem entrar nos números do técnico.
    login(world.client, world.admin_a, world.password)
    admin_id = world.client.get("/api/v1/me").json()["id"]
    client_id = world.client.get("/api/v1/clients").json()["items"][0]["id"]
    work_tests.create(world, client_id, category="fiscal", system="SGBR")
    login(world.client, world.technician, world.password)
    work_tests.create(world, client_id, category="fiscal", system="SGBR")
    result = dashboard(world.client, preset="inicio")
    assert result["scope"] == "proprio" and len(result["people"]) == 1
    assert result["people"][0]["id"] == world.technician_id
    assert result["totals"]["abriu"]["actions"] == 0
    assert result["totals"]["resolveu"]["actions"] == 2
    assert result["totals"]["registered_records"] == 1
    assert "Admin Aurora" not in json.dumps(result, ensure_ascii=False)
    assert (
        world.client.get("/api/v1/reports", params={"responsible_id": admin_id}).status_code == 403
    )
    assert mutate(world.client, "/reports/export", {"responsible_id": admin_id}).status_code == 403
    exported = mutate(world.client, "/reports/export", {"preset": "inicio"})
    assert exported.status_code == 200 and "text/csv" in exported.headers["content-type"]
    assert "Admin Aurora" not in exported.text
    assert "proprio" in exported.text
    for forbidden in (
        "ranking",
        "posição",
        "domina",
        "precisa de curso",
        "precisa contratar",
        "incompetente",
    ):
        assert forbidden not in json.dumps(result, ensure_ascii=False).lower()
    with Session(world.admin_engine) as db:
        export = db.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == world.a, AuditEvent.action == "relatorio_exportado"
            )
        )
        assert export and export.actor_id == world.technician_id


@pytest.mark.parametrize(
    "text_value", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", " \t=1+1", "\n@x", "\v=1+1"]
)
def test_csv_formula_neutralization(text_value):
    assert safe_cell(text_value).startswith("'")
    assert safe_cell("Relato comum") == "Relato comum"


def test_csv_actual_client_and_employee_cells(world):
    client_id = work_tests.prepare(world)
    assert (
        mutate(world.client, f"/clients/{client_id}", {"name": "=SUM(A1)"}, "PATCH").status_code
        == 200
    )
    admin_id = world.client.get("/api/v1/me").json()["id"]
    with Session(world.admin_engine) as db, db.begin():
        db.get(User, admin_id).name = "+Nome fictício"
    work_tests.create(world, client_id)
    response = mutate(world.client, "/reports/export", {"preset": "inicio"})
    assert response.status_code == 200
    cells = [
        cell
        for row in csv.reader(io.StringIO(response.text.lstrip("\ufeff")), delimiter=";")
        for cell in row
    ]
    assert "'=SUM(A1)" in cells and "'+Nome fictício" in cells


def test_teams_current_membership_filters_and_isolation(world):
    client_id = work_tests.prepare(world)
    own_admin_id = world.client.get("/api/v1/me").json()["id"]
    made = mutate(
        world.client,
        "/teams",
        {"name": "Equipe fictícia Fiscal", "member_ids": [world.technician_id]},
    )
    assert made.status_code == 201, made.text
    team = made.json()
    work_tests.create(world, client_id, category="fiscal", system="SGBR")
    login(world.client, world.technician, world.password)
    work_tests.create(world, client_id, category="fiscal", system="SGBR")
    assert mutate(world.client, "/teams", {"name": "Indevida"}).status_code == 403
    login(world.client, world.admin_a, world.password)
    result = dashboard(world.client, team_id=team["id"], category="fiscal", system="SGBR")
    assert result["totals"]["registered_records"] == 1 and len(result["people"]) == 1
    assert (
        mutate(
            world.client,
            f"/teams/{team['id']}",
            {"name": team["name"], "member_ids": [own_admin_id], "revision": 99},
            "PATCH",
        ).status_code
        == 409
    )
    login(world.client, world.admin_b, world.password)
    assert world.client.get("/api/v1/teams").json() == []
    assert world.client.get("/api/v1/reports", params={"team_id": team["id"]}).status_code == 404
    other_id = world.client.get("/api/v1/me").json()["id"]
    login(world.client, world.admin_a, world.password)
    assert (
        mutate(world.client, "/teams", {"name": "Inválida", "member_ids": [other_id]}).status_code
        == 404
    )


def test_period_calendars_dst_and_invalid_ranges():
    day = period(
        ReportFilters(preset="dia"),
        "America/Sao_Paulo",
        instant=datetime(2026, 11, 1, 2, 30, tzinfo=UTC),
    )
    assert day["start_date"] == date(2026, 10, 31)
    week = period(
        ReportFilters(preset="semana"),
        "America/Sao_Paulo",
        instant=datetime(2026, 11, 1, 2, 30, tzinfo=UTC),
    )
    assert week["start_date"] == date(2026, 10, 26) and week["end_date"] == date(2026, 11, 1)
    month = period(
        ReportFilters(preset="mes"), "Asia/Tokyo", instant=datetime(2026, 10, 31, 23, tzinfo=UTC)
    )
    assert month["start_date"] == date(2026, 11, 1) and month["end_date"] == date(2026, 11, 30)
    lower, upper = date_bounds(date(2026, 3, 8), date(2026, 3, 8), "America/New_York")
    assert (upper - lower).total_seconds() == 23 * 3600
    assert sample([])["median_seconds"] is None and sample([])["n"] == 0
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    pauses = [
        SimpleNamespace(
            entrada_em=instant + timedelta(seconds=10), saida_em=instant + timedelta(seconds=30)
        ),
        SimpleNamespace(
            entrada_em=instant + timedelta(seconds=20), saida_em=instant + timedelta(seconds=40)
        ),
    ]
    assert elapsed(instant, instant + timedelta(seconds=100), pauses) == (100, 70)


def test_empty_reports_invalid_query_and_snapshot_workload(world):
    login(world.client, world.admin_a, world.password)
    empty = dashboard(world.client)
    assert empty["totals"]["registered_records"] == 0
    assert empty["times"]["resolution"]["net"]["median_seconds"] is None
    assert empty["notice"] == reports.NOTICE and empty["history"]["total"] == 0
    assert world.client.get("/api/v1/reports?preset=livre").status_code == 422
    assert (
        world.client.get(
            "/api/v1/reports?preset=livre&start_date=2026-11-10&end_date=2026-11-01"
        ).status_code
        == 422
    )
    assert world.client.get("/api/v1/reports?organization_id=alheia").status_code == 422
    client_id = work_tests.prepare(world)
    ticket = work_tests.create(world, client_id, "chamado", assignee_id=world.technician_id)
    result = dashboard(world.client)
    assert len(result["queue"]) == 1 and result["queue"][0]["id"] == ticket["ticket_id"]
    assert result["workload"][-1]["active_tickets"] == 1
    login(world.client, world.technician, world.password)
    assert dashboard(world.client)["workload"][-1]["active_tickets"] == 1


def test_organization_timezone_change_preserves_editorial_and_media_policy(world):
    login(world.client, world.admin_a, world.password)
    settings = {"publisher_roles": ["administrador"], "allow_self_publish": False}
    assert mutate(world.client, "/knowledge/policy", settings, "PATCH").status_code == 200
    assert (
        mutate(
            world.client,
            "/media/settings",
            {"retention": "apos_dias", "retention_days": 42},
            "PATCH",
        ).status_code
        == 200
    )
    changed = mutate(
        world.client,
        "/organizations/current",
        {"name": "Aurora fictícia", "timezone": "Asia/Tokyo"},
        "PATCH",
    )
    assert changed.status_code == 200
    assert world.client.get("/api/v1/knowledge/policy").json()["publisher_roles"] == [
        "administrador"
    ]
    assert world.client.get("/api/v1/media/settings").json()["retention_days"] == 42
    assert (
        mutate(
            world.client,
            "/organizations/current",
            {"name": "Aurora fictícia", "settings": {"knowledge": True}},
            "PATCH",
        ).status_code
        == 422
    )


def test_daily_weekly_monthly_all_presets_and_grouping(world, monkeypatch):
    client_id = work_tests.prepare(world)
    work_tests.create(world, client_id, ocorrido_em="2026-10-31T23:30:00-03:00")
    work_tests.create(world, client_id, ocorrido_em="2026-11-01T00:15:00-03:00")
    monkeypatch.setattr(reports, "now", lambda: datetime(2026, 11, 1, 15, tzinfo=UTC))
    for preset, expected in (("dia", 1), ("semana", 2), ("mes", 1), ("inicio", 2)):
        value = dashboard(world.client, preset=preset)
        assert value["totals"]["registered_records"] == expected
    for granularity, buckets in (
        ("dia", ["2026-10-31", "2026-11-01"]),
        ("semana", ["2026-10-26"]),
        ("mes", ["2026-10-01", "2026-11-01"]),
    ):
        result = dashboard(world.client, preset="inicio", granularity=granularity)
        assert sorted({row["bucket"] for row in result["series"]}) == buckets
        assert sum(row["records"] for row in result["series"]) == 2


def test_csv_complete_history_is_not_silently_truncated_to_ui_page(world):
    client_id = work_tests.prepare(world)
    user_id = world.client.get("/api/v1/me").json()["id"]
    instant = datetime(2026, 11, 1, 15, tzinfo=UTC)
    with Session(world.admin_engine) as db, db.begin():
        for index in range(101):
            db.add(
                Record(
                    organization_id=world.a,
                    client_id=client_id,
                    author_id=user_id,
                    type="finalizacao",
                    texto_original=f"Relato fictício {index}",
                    status="aguardando_revisao",
                    ocorrido_em=instant,
                )
            )
    result = dashboard(world.client, preset="inicio")
    assert result["history"]["total"] == 101 and len(result["history"]["items"]) == 100
    second = dashboard(world.client, preset="inicio", history_offset=100)
    assert len(second["history"]["items"]) == 1
    response = mutate(world.client, "/reports/export", {"preset": "inicio", "history_offset": 100})
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text.lstrip("\ufeff")), delimiter=";"))
    assert len([row for row in rows if row and row[0] == "Histórico completo"]) == 101
