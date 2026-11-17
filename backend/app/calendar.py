"""Projeção consultada diretamente nas fontes, com seus escopos de acesso."""

from datetime import datetime, time

from sqlalchemy import Date, String, and_, cast, func, literal, or_, select, union_all

from app.calendar_models import CalendarEvent, CalendarParticipant
from app.task_models import Task
from app.task_routes import query as task_query
from app.task_routes import zone
from app.work import ticket_query
from app.work_models import Attendance, Record, Ticket


def event_query(ctx):
    q = ctx.query(CalendarEvent)
    if ctx.membership.role == "tecnico":
        participants = ctx.query(CalendarParticipant).with_only_columns(
            CalendarParticipant.event_id
        )
        participants = participants.where(
            CalendarParticipant.user_id == ctx.user.id, CalendarParticipant.active.is_(True)
        )
        q = q.where(
            or_(
                CalendarEvent.author_id == ctx.user.id,
                CalendarEvent.assignee_id == ctx.user.id,
                CalendarEvent.id.in_(participants),
            )
        )
    return q


def sources(ctx, date_from, date_until, *, include_cancelled=False, assignee_id=None, team=None):
    from app.attendance_routes import query as attendance_query

    timezone = zone(ctx)
    lower = datetime.combine(date_from, time.min, timezone)
    upper = datetime.combine(date_until, time.min, timezone)

    def instant_range(column):
        return and_(column >= lower, column < upper)

    def day_range(column):
        return and_(column >= date_from, column < date_until)

    def local_date(column):
        return cast(func.timezone(str(timezone), column), Date)

    def columns(kind, model, title, description, day, start, end, client_id, assignee, team_id):
        return (
            (literal(kind + ":") + model.id).label("id"),
            literal(kind).label("type"),
            model.id.label("origin_id"),
            title.label("title"),
            description.label("description"),
            day.label("data"),
            start.label("inicio_em"),
            end.label("fim_em"),
            client_id.label("client_id"),
            assignee.label("assignee_id"),
            team_id.label("team_id"),
            model.status.label("status"),
            model.revision.label("revision"),
        )

    def restrict(q, assignee, team_id=None):
        if assignee_id:
            q = q.where(assignee == assignee_id)
        if team is not None:
            condition = assignee.in_(team.member_ids)
            if team_id is not None:
                condition = or_(condition, team_id == team.id)
            q = q.where(condition)
        return q

    empty_id = cast(literal(None), String)
    empty_instant = cast(literal(None), CalendarEvent.inicio_em.type)
    tasks = task_query(ctx).where(
        or_(
            and_(Task.agendado_em.is_(None), day_range(Task.prevista_para)),
            instant_range(Task.agendado_em),
        )
    )
    if not include_cancelled:
        tasks = tasks.where(Task.status != "cancelada")
    # Separar data civil de instante evita transformar o predicado temporal em função.
    tasks = restrict(tasks, Task.assignee_id, Task.team_id).with_only_columns(
        *columns(
            "task",
            Task,
            Task.title,
            Task.description,
            func.coalesce(local_date(Task.agendado_em), Task.prevista_para),
            Task.agendado_em,
            empty_instant,
            Task.client_id,
            Task.assignee_id,
            Task.team_id,
        )
    )
    tickets = restrict(ticket_query(ctx).where(instant_range(Ticket.prazo_em)), Ticket.assignee_id)
    tickets = tickets.with_only_columns(
        *columns(
            "ticket",
            Ticket,
            Ticket.code,
            Ticket.description,
            local_date(Ticket.prazo_em),
            Ticket.prazo_em,
            empty_instant,
            Ticket.client_id,
            Ticket.assignee_id,
            empty_id,
        )
    )
    attendances = restrict(
        attendance_query(ctx).where(instant_range(Attendance.retomada_em)), Attendance.assignee_id
    )
    attendances = attendances.with_only_columns(
        *columns(
            "attendance",
            Attendance,
            literal("Retomada de atendimento"),
            Attendance.next_action,
            local_date(Attendance.retomada_em),
            Attendance.retomada_em,
            empty_instant,
            Record.client_id,
            Attendance.assignee_id,
            empty_id,
        )
    )
    events = event_query(ctx).where(
        or_(
            and_(CalendarEvent.inicio_em.is_(None), day_range(CalendarEvent.data)),
            and_(
                CalendarEvent.inicio_em < upper,
                or_(
                    CalendarEvent.fim_em > lower,
                    and_(CalendarEvent.fim_em.is_(None), CalendarEvent.inicio_em >= lower),
                ),
            ),
        )
    )
    if not include_cancelled:
        events = events.where(CalendarEvent.status == "ativo")
    events = restrict(events, CalendarEvent.assignee_id).with_only_columns(
        *columns(
            "event",
            CalendarEvent,
            CalendarEvent.title,
            CalendarEvent.description,
            func.coalesce(local_date(CalendarEvent.inicio_em), CalendarEvent.data),
            CalendarEvent.inicio_em,
            CalendarEvent.fim_em,
            CalendarEvent.client_id,
            CalendarEvent.assignee_id,
            empty_id,
        )
    )
    return {"task": tasks, "ticket": tickets, "attendance": attendances, "event": events}


def unified(ctx, date_from, date_until, **filters):
    return union_all(*sources(ctx, date_from, date_until, **filters).values()).subquery()


def page(ctx, date_from, date_until, offset, limit, **filters):
    items = unified(ctx, date_from, date_until, **filters)
    total = ctx.db.scalar(select(func.count()).select_from(items))
    rows = ctx.db.execute(
        select(items)
        .order_by(items.c.data, items.c.inicio_em.nullsfirst(), items.c.id)
        .offset(offset)
        .limit(limit)
    ).mappings()
    return {
        "total": total,
        "timezone": str(zone(ctx)),
        "date_from": date_from,
        "date_until": date_until,
        "items": [dict(row) for row in rows],
    }
