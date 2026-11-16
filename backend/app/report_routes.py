from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field
from sqlalchemy import select

from app.access import context
from app.insight_models import Team
from app.models import Organization, OrganizationMembership, User, now
from app.reports import ReportFilters, csv_report, report
from app.schemas import Input
from app.security import check_csrf
from app.work import check_revision
from app.work_models import Record, Ticket

router = APIRouter(
    prefix="/api/v1", tags=["Relatórios e equipes"], dependencies=[Depends(check_csrf)]
)


def management(ctx):
    if ctx.membership.role == "tecnico":
        raise HTTPException(403, "Ação permitida à gestão da organização")


def team_data(item):
    return {
        key: getattr(item, key) for key in ("id", "name", "member_ids", "revision", "atualizado_em")
    }


class TeamInput(Input):
    name: str = Field(min_length=1, max_length=120)
    member_ids: list[str] = Field(default_factory=list, max_length=200)
    revision: int | None = Field(default=None, ge=1)


def save_team(ctx, request, body, item=None):
    ctx.require_admin()
    ctx.db.scalar(
        select(Organization).where(Organization.id == ctx.organization_id).with_for_update()
    )
    if not body.name.strip():
        raise HTTPException(422, "Informe o nome da equipe")
    for identifier in body.member_ids:
        if not ctx.db.scalar(
            ctx.query(OrganizationMembership).where(OrganizationMembership.user_id == identifier)
        ):
            raise HTTPException(404, "Integrante não encontrado nesta organização")
    duplicate = ctx.db.scalar(ctx.query(Team).where(Team.name == body.name.strip()))
    if duplicate and (not item or duplicate.id != item.id):
        raise HTTPException(409, "Já existe equipe com esse nome")
    if item:
        if body.revision is None:
            raise HTTPException(422, "Informe a revisão atual da equipe")
        check_revision(item, body.revision)
        item.revision += 1
    else:
        item = Team(organization_id=ctx.organization_id)
        ctx.db.add(item)
    item.name, item.member_ids, item.atualizado_em = (
        body.name.strip(),
        sorted(set(body.member_ids)),
        now(),
    )
    ctx.db.flush()
    ctx.audit(
        request,
        "equipe_relatorios_alterada",
        "Team",
        item.id,
        {},
        team_data(item) | {"atualizado_em": item.atualizado_em.isoformat()},
    )
    return team_data(item)


@router.get("/teams")
def teams(ctx=Depends(context, scope="function")):
    management(ctx)
    return [
        team_data(item) for item in ctx.db.scalars(ctx.query(Team).order_by(Team.name, Team.id))
    ]


@router.post("/teams", status_code=201)
def new_team(body: TeamInput, request: Request, ctx=Depends(context, scope="function")):
    return save_team(ctx, request, body)


@router.patch("/teams/{identifier}")
def update_team(
    identifier: str, body: TeamInput, request: Request, ctx=Depends(context, scope="function")
):
    ctx.require_admin()
    item = ctx.db.scalar(ctx.query(Team).where(Team.id == identifier).with_for_update())
    if item is None:
        raise HTTPException(404, "Equipe não encontrada")
    return save_team(ctx, request, body, item)


@router.get("/reports/options")
def options(ctx=Depends(context, scope="function")):
    members = list(ctx.db.scalars(ctx.query(OrganizationMembership)))
    people = [
        {"id": m.user_id, "name": ctx.db.get(User, m.user_id).name}
        for m in members
        if ctx.membership.role != "tecnico" or m.user_id == ctx.user.id
    ]
    teams = [
        {"id": item.id, "name": item.name}
        for item in ctx.db.scalars(ctx.query(Team))
        if ctx.membership.role != "tecnico" or ctx.user.id in item.member_ids
    ]
    record_query = ctx.query(Record)
    ticket_query = ctx.query(Ticket)
    if ctx.membership.role == "tecnico":
        record_query = record_query.where(Record.author_id == ctx.user.id)
        ticket_query = ticket_query.where(Ticket.assignee_id == ctx.user.id)
    categories, systems = set(), set()
    for model, query in ((Record, record_query), (Ticket, ticket_query)):
        for category, system in ctx.db.execute(
            query.with_only_columns(model.category, model.system).distinct()
        ):
            if category:
                categories.add(category)
            if system:
                systems.add(system)
    return {
        "people": sorted(people, key=lambda row: row["name"].casefold()),
        "teams": sorted(teams, key=lambda row: row["name"].casefold()),
        "categories": sorted(categories),
        "systems": sorted(systems),
    }


@router.get("/reports")
def dashboard(filters: Annotated[ReportFilters, Query()], ctx=Depends(context, scope="function")):
    return report(ctx, filters)


@router.post("/reports/export")
def export(body: ReportFilters, request: Request, ctx=Depends(context, scope="function")):
    value = report(ctx, body, full_history=True)
    ctx.audit(
        request,
        "relatorio_exportado",
        "Organization",
        ctx.organization_id,
        {},
        {
            "scope": value["scope"],
            "filters": body.model_dump(mode="json"),
            "start": value["period"]["start_date"].isoformat(),
            "end": value["period"]["end_date"].isoformat(),
        },
    )
    return Response(
        csv_report(value),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="soldesk-relatorio.csv"',
            "Cache-Control": "private, no-store",
        },
    )
