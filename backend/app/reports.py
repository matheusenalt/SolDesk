"""Relatórios factuais. Definições anteriores ao código em docs/METRICAS.md."""

import csv
import io
import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import or_

from app.insight_models import ArticleConsultation, Team
from app.models import Client, Organization, OrganizationMembership, User, now
from app.schemas import Input
from app.work_models import KnowledgeArticle, Record, Ticket, TicketEvent, TicketInterval

CONTEXT = (
    "Muitos chamados abertos podem refletir demanda, especialização, distribuição desigual, "
    "escalonamento adequado, complexidade não medida ou classificação equivocada. "
    "Os números não explicam essas causas; a gestão interpreta os fatos."
)
NOTICE = "Estatísticas refletem apenas atendimentos registrados."
SMALL_SAMPLE = "Amostra pequena (n < 5); interprete os tempos com cautela."
ACTIONS = (
    "abriu",
    "assumiu",
    "comentou",
    "encaminhou",
    "movimentou",
    "resolveu",
    "encerrou",
    "reabriu",
    "aguardando_terceiros",
)
CHANGES = ("status", "assignee_id", "priority", "category", "system")
COMMENTS = {"chamado_comentario", "chamado_resposta", "chamado_esclarecimento"}
TERMINAL = {"resolvido", "encerrado"}


class ReportFilters(Input):
    preset: Literal["dia", "semana", "mes", "inicio", "livre"] = "dia"
    start_date: date | None = None
    end_date: date | None = None
    client_id: str | None = Field(default=None, min_length=36, max_length=36)
    responsible_id: str | None = Field(default=None, min_length=36, max_length=36)
    team_id: str | None = Field(default=None, min_length=36, max_length=36)
    category: str = Field(default="", max_length=80)
    system: str = Field(default="", max_length=80)
    system_id: str | None = Field(default=None, min_length=36, max_length=36)
    granularity: Literal["dia", "semana", "mes"] = "dia"
    history_offset: int = Field(default=0, ge=0)


def date_bounds(first: date, last: date, timezone: str):
    zone = ZoneInfo(timezone)
    return (
        datetime.combine(first, time.min, zone).astimezone(UTC),
        datetime.combine(last + timedelta(days=1), time.min, zone).astimezone(UTC),
    )


def period(filters, timezone, earliest=None, instant=None):
    today = (instant or now()).astimezone(ZoneInfo(timezone)).date()
    if filters.preset == "livre":
        if not filters.start_date or not filters.end_date:
            raise HTTPException(422, "Informe início e fim do período livre")
        first, last = filters.start_date, filters.end_date
    elif filters.preset == "inicio":
        first, last = earliest or today, today
    elif filters.preset == "semana":
        first = today - timedelta(days=today.weekday())
        last = first + timedelta(days=6)
    elif filters.preset == "mes":
        first = today.replace(day=1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        first = last = today
    if first > last or (last - first).days > 3660:
        raise HTTPException(
            422, "Use período válido de até 3661 dias; reduza a janela ou os filtros"
        )
    start, end = date_bounds(first, last, timezone)
    return {
        "preset": filters.preset,
        "start_date": first,
        "end_date": last,
        "start_utc": start,
        "end_utc": end,
        "timezone": timezone,
    }


def bounded(ctx, query, maximum=10000):
    rows = list(ctx.db.scalars(query.limit(maximum + 1)))
    if len(rows) > maximum:
        raise HTTPException(
            422, "Há muitos dados para este relatório. Restrinja cliente, categoria ou sistema"
        )
    return rows


def people_scope(ctx, filters):
    members = list(ctx.db.scalars(ctx.query(OrganizationMembership)))
    names = {member.user_id: ctx.db.get(User, member.user_id).name for member in members}
    selected = set(names)
    if ctx.membership.role == "tecnico":
        selected = {ctx.user.id}
        if filters.responsible_id and filters.responsible_id != ctx.user.id:
            raise HTTPException(403, "Você pode consultar somente os próprios números")
    if filters.responsible_id:
        if filters.responsible_id not in names:
            raise HTTPException(404, "Pessoa não encontrada na organização")
        selected &= {filters.responsible_id}
    if filters.team_id:
        selected &= set(ctx.get(Team, filters.team_id).member_ids)
    return {identifier: names[identifier] for identifier in selected}


def load_facts(ctx, filters, people):
    record_query, ticket_query = ctx.query(Record), ctx.query(Ticket)
    if filters.system_id:
        from app.system_models import SoftwareSystem

        ctx.get(SoftwareSystem, filters.system_id)
        record_query = record_query.where(Record.system_id == filters.system_id)
        ticket_query = ticket_query.where(Ticket.system_id == filters.system_id)
    if filters.client_id:
        ctx.get(Client, filters.client_id)
    for field in ("client_id", "category", "system"):
        value = getattr(filters, field)
        if value:
            record_query = record_query.where(getattr(Record, field) == value)
            ticket_query = ticket_query.where(getattr(Ticket, field) == value)
    record_query = record_query.where(Record.author_id.in_(people))
    relevant_events = (
        ctx.query(TicketEvent)
        .with_only_columns(TicketEvent.ticket_id)
        .where(
            or_(
                TicketEvent.actor_id.in_(people),
                TicketEvent.after["assignee_id"].as_string().in_(people),
            )
        )
    )
    ticket_query = ticket_query.where(
        or_(
            Ticket.opened_by.in_(people),
            Ticket.assignee_id.in_(people),
            Ticket.id.in_(relevant_events),
        )
    )
    records, tickets = bounded(ctx, record_query), bounded(ctx, ticket_query)
    identifiers = [ticket.id for ticket in tickets]
    events = bounded(
        ctx,
        ctx.query(TicketEvent)
        .where(TicketEvent.ticket_id.in_(identifiers))
        .order_by(TicketEvent.ocorrido_em, TicketEvent.id),
        50000,
    )
    intervals = bounded(
        ctx, ctx.query(TicketInterval).where(TicketInterval.ticket_id.in_(identifiers)), 20000
    )
    return records, tickets, events, intervals


def is_movement(event):
    return event.change == "chamado_alterado" and any(
        event.before.get(key) != event.after.get(key) for key in CHANGES
    )


def actions_for(tickets, events):
    actions = [
        {"kind": "abriu", "person": t.opened_by, "ticket": t.id, "at": t.aberto_em} for t in tickets
    ]
    for event in events:

        def add(kind, person=None, event=event):
            if person or event.actor_id:
                actions.append(
                    {
                        "kind": kind,
                        "person": person or event.actor_id,
                        "ticket": event.ticket_id,
                        "at": event.ocorrido_em,
                    }
                )

        if event.change == "chamado_aberto":
            if event.after.get("assignee_id"):
                add("assumiu", event.after["assignee_id"])
            continue
        if event.change in COMMENTS:
            add("comentou")
        movement = is_movement(event)
        if movement:
            add("movimentou")
            if event.after.get("assignee_id") != event.before.get("assignee_id"):
                add("encaminhou")
                if event.after.get("assignee_id"):
                    add("assumiu", event.after["assignee_id"])
        if event.change not in COMMENTS and not movement:
            continue
        before, after = event.before.get("status"), event.after.get("status")
        if before == after:
            continue
        kind = {
            "resolvido": "resolveu",
            "encerrado": "encerrou",
            "reaberto": "reabriu",
            "aguardando_terceiros": "aguardando_terceiros",
        }.get(after)
        if kind:
            add(kind)
    return actions


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    return round(
        values[lower]
        + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower),
        3,
    )


def sample(values):
    return {
        "median_seconds": percentile(values, 0.5),
        "p90_seconds": percentile(values, 0.9),
        "n": len(values),
        "warning": SMALL_SAMPLE if len(values) < 5 else None,
    }


def elapsed(start, end, intervals):
    if end < start:
        return None
    clipped = []
    for interval in intervals:
        left, right = max(start, interval.entrada_em), min(end, interval.saida_em or end)
        if interval.saida_em and interval.saida_em < interval.entrada_em:
            return None
        if left < right:
            clipped.append((left, right))
    merged = []
    for left, right in sorted(clipped):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    gross = (end - start).total_seconds()
    return gross, max(0, gross - sum((right - left).total_seconds() for left, right in merged))


def contains(window, value):
    return window["start_utc"] <= value < window["end_utc"]


def time_metrics(tickets, events, intervals, people, window):
    by_ticket, pauses = defaultdict(list), defaultdict(list)
    for event in events:
        by_ticket[event.ticket_id].append(event)
    for interval in intervals:
        pauses[interval.ticket_id].append(interval)
    first, resolution, unique, excluded = [], [], set(), 0
    for ticket in tickets:
        cycle_start, first_event = ticket.aberto_em, None
        for event in by_ticket[ticket.id]:
            human = is_movement(event) or event.change in COMMENTS
            if human and first_event is None:
                first_event = event
            changed = human and event.before.get("status") != event.after.get("status")
            if changed and event.after.get("status") == "reaberto":
                cycle_start = event.ocorrido_em
            if (
                changed
                and event.after.get("status") == "resolvido"
                and event.actor_id in people
                and contains(window, event.ocorrido_em)
            ):
                duration = elapsed(cycle_start, event.ocorrido_em, pauses[ticket.id])
                if duration is None:
                    excluded += 1
                else:
                    resolution.append(duration)
                    unique.add(ticket.id)
        if (
            first_event
            and first_event.actor_id in people
            and contains(window, first_event.ocorrido_em)
        ):
            duration = elapsed(ticket.aberto_em, first_event.ocorrido_em, pauses[ticket.id])
            if duration is None:
                excluded += 1
            else:
                first.append(duration)

    def summarize(rows):
        return {"gross": sample([row[0] for row in rows]), "net": sample([row[1] for row in rows])}

    return {
        "first_action": summarize(first),
        "resolution": summarize(resolution),
        "resolution_unique_tickets": len(unique),
        "excluded_samples": excluded,
    }


def totals(records, actions, people, window):
    current = [r for r in records if contains(window, r.ocorrido_em)]
    valid = [r for r in current if r.status != "cancelado"]
    result = {
        "registered_records": len(valid),
        "cancelled_records": len(current) - len(valid),
        "confirmed_finalizations": sum(
            r.type == "finalizacao" and r.status == "confirmado" for r in valid
        ),
        "awaiting_review": sum(
            r.type == "finalizacao" and r.status == "aguardando_revisao" for r in valid
        ),
        "other_provisional_finalizations": sum(
            r.type == "finalizacao" and r.status not in {"confirmado", "aguardando_revisao"}
            for r in valid
        ),
    }
    for kind in ACTIONS:
        rows = [
            a
            for a in actions
            if a["kind"] == kind and a["person"] in people and contains(window, a["at"])
        ]
        result[kind] = {"actions": len(rows), "unique_tickets": len({a["ticket"] for a in rows})}
    return result


def local_bucket(instant, timezone, granularity):
    day = instant.astimezone(ZoneInfo(timezone)).date()
    if granularity == "semana":
        day -= timedelta(days=day.weekday())
    if granularity == "mes":
        day = day.replace(day=1)
    return day.isoformat()


def workload(tickets, events, records, people, window, instant):
    states, index, rows = {}, 0, []
    first, last, timezone = (
        window["start_date"],
        min(window["end_date"], instant.astimezone(ZoneInfo(window["timezone"])).date()),
        window["timezone"],
    )
    pending = Counter(
        local_bucket(r.ocorrido_em, timezone, "dia")
        for r in records
        if r.status == "aguardando_revisao"
    )
    registered = Counter(
        local_bucket(r.ocorrido_em, timezone, "dia") for r in records if r.status != "cancelado"
    )
    while first <= last:
        _, end = date_bounds(first, first, timezone)
        cutoff = min(end, instant)
        while index < len(events) and events[index].ocorrido_em < cutoff:
            event = events[index]
            if event.after.get("status") and event.after.get("assignee_id"):
                states[event.ticket_id] = (event.after["status"], event.after["assignee_id"])
            index += 1
        rows.append(
            {
                "date": first.isoformat(),
                "records": registered[first.isoformat()],
                "active_tickets": sum(
                    state not in TERMINAL and person in people for state, person in states.values()
                ),
                "pending_review_current_by_fact": pending[first.isoformat()],
            }
        )
        first += timedelta(days=1)
    known = {e.ticket_id for e in events if e.change == "chamado_aberto"}
    return rows, sum(t.id not in known for t in tickets)


def report(ctx, filters, instant=None, *, full_history=False):
    instant = instant or now()
    org = ctx.db.get(Organization, ctx.organization_id)
    people = people_scope(ctx, filters)
    records, tickets, events, intervals = load_facts(ctx, filters, people)
    actions = actions_for(tickets, events)
    earliest = min(
        [r.ocorrido_em for r in records] + [a["at"] for a in actions if a["person"] in people],
        default=instant,
    )
    window = period(
        filters, org.timezone, earliest.astimezone(ZoneInfo(org.timezone)).date(), instant
    )
    days = (window["end_date"] - window["start_date"]).days + 1
    prior_last = window["start_date"] - timedelta(days=1)
    prior = {"start_date": prior_last - timedelta(days=days - 1), "end_date": prior_last}
    prior["start_utc"], prior["end_utc"] = date_bounds(
        prior["start_date"], prior_last, org.timezone
    )
    current = [r for r in records if contains(window, r.ocorrido_em) and r.status != "cancelado"]
    selected_actions = [a for a in actions if a["person"] in people and contains(window, a["at"])]
    clients = {
        identifier: name
        for identifier, name in ctx.db.execute(
            ctx.query(Client).with_only_columns(Client.id, Client.name)
        )
    }
    people_rows = []
    for identifier, name in sorted(people.items(), key=lambda pair: (pair[1].casefold(), pair[0])):
        own_records = [r for r in records if r.author_id == identifier]
        people_rows.append(
            {"id": identifier, "name": name, **totals(own_records, actions, {identifier}, window)}
        )
    buckets = {}
    for record in current:
        key = (
            local_bucket(record.ocorrido_em, org.timezone, filters.granularity),
            record.author_id,
        )
        bucket = buckets.setdefault(
            key,
            {
                "bucket": key[0],
                "person_id": key[1],
                "person_name": people[key[1]],
                "records": 0,
                "actions": Counter(),
            },
        )
        bucket["records"] += 1
    for action in selected_actions:
        key = (local_bucket(action["at"], org.timezone, filters.granularity), action["person"])
        bucket = buckets.setdefault(
            key,
            {
                "bucket": key[0],
                "person_id": key[1],
                "person_name": people[key[1]],
                "records": 0,
                "actions": Counter(),
            },
        )
        bucket["actions"][action["kind"]] += 1
    classifications = Counter((r.author_id, r.category, r.system) for r in current)
    topics = [
        {
            "person_id": key[0],
            "person_name": people[key[0]],
            "category": key[1],
            "system": key[2],
            "records": count,
        }
        for key, count in classifications.items()
    ]
    client_counts = Counter(r.client_id for r in current if r.client_id is not None)
    active_ids = {action["ticket"] for action in selected_actions}
    ticket_counts = Counter(
        (t.category, t.system, t.priority) for t in tickets if t.id in active_ids
    )
    queue = [
        {
            "id": t.id,
            "code": t.code,
            "client_id": t.client_id,
            "client_name": clients[t.client_id],
            "assignee_id": t.assignee_id,
            "assignee_name": people[t.assignee_id],
            "priority": t.priority,
            "status": t.status,
            "category": t.category,
            "system": t.system,
            "age_seconds": max(0, (instant - t.aberto_em).total_seconds()),
        }
        for t in tickets
        if t.status not in TERMINAL and t.assignee_id in people
    ]
    load, missing_history = workload(tickets, events, records, people, window, instant)
    article_views = []
    # Eventos deliberadamente não guardam leitor. Técnico não recebe agregado dos colegas.
    if ctx.membership.role != "tecnico" and not filters.responsible_id and not filters.team_id:
        view_query = ctx.query(ArticleConsultation).where(
            ArticleConsultation.ocorrido_em >= window["start_utc"],
            ArticleConsultation.ocorrido_em < window["end_utc"],
        )
        articles = {a.id: a for a in bounded(ctx, ctx.query(KnowledgeArticle))}
        views = bounded(ctx, view_query, 50000)
        counts = Counter(
            v.article_id
            for v in views
            if v.article_id in articles
            and (
                not filters.client_id
                or articles[v.article_id].client_id in {None, filters.client_id}
            )
            and (not filters.category or articles[v.article_id].category == filters.category)
            and (not filters.system or articles[v.article_id].system == filters.system)
            and (not filters.system_id or articles[v.article_id].system_id == filters.system_id)
        )
        article_views = [
            {"article_id": key, "title": articles[key].title, "consultations": value}
            for key, value in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ]
    history = sorted(current, key=lambda r: (r.ocorrido_em, r.id), reverse=True)
    return {
        "scope": "proprio" if ctx.membership.role == "tecnico" else "organizacao",
        "notice": NOTICE,
        "interpretation_context": CONTEXT,
        "generated_at": instant,
        "period": window,
        "filters": filters.model_dump(mode="json"),
        "totals": totals(records, actions, people, window),
        "comparison": {"period": prior, "totals": totals(records, actions, people, prior)},
        "people": people_rows,
        "series": sorted(
            buckets.values(), key=lambda b: (b["bucket"], b["person_name"].casefold())
        ),
        "classifications": sorted(
            topics, key=lambda row: (row["person_name"].casefold(), row["category"], row["system"])
        ),
        "ticket_distribution": [
            {"category": key[0], "system": key[1], "priority": key[2], "unique_tickets": count}
            for key, count in sorted(ticket_counts.items())
        ],
        "clients": [
            {"id": key, "name": clients[key], "records": value}
            for key, value in sorted(
                client_counts.items(),
                key=lambda pair: (-pair[1], clients[pair[0]]),
            )
        ],
        "internal_activities": sum(r.internal_activity for r in current),
        "article_consultations": article_views,
        "article_consultations_scope": "agregado_organizacao_sem_leitor"
        if ctx.membership.role != "tecnico" and not filters.responsible_id and not filters.team_id
        else "indisponivel_por_pessoa",
        "times": time_metrics(tickets, events, intervals, people, window),
        "queue": sorted(queue, key=lambda row: (row["assignee_name"].casefold(), row["code"])),
        "workload": load,
        "missing_history_tickets": missing_history,
        "history": {
            "total": len(history),
            "items": [
                {
                    "id": r.id,
                    "client_id": r.client_id,
                    "client_name": clients.get(r.client_id),
                    "system_id": r.system_id,
                    "system_name_snapshot": r.system_name_snapshot,
                    "legacy_system_snapshot": r.legacy_system_snapshot,
                    "author_id": r.author_id,
                    "author_name": people[r.author_id],
                    "type": r.type,
                    "status": r.status,
                    "ocorrido_em": r.ocorrido_em,
                    "category": r.category,
                    "system": r.system,
                }
                for r in (
                    history
                    if full_history
                    else history[filters.history_offset : filters.history_offset + 100]
                )
            ],
        },
    }


def safe_cell(value):
    value = str(value) if value is not None else ""
    return "'" + value if re.match(r"^[\s\ufeff]*[=+\-@＝＋－＠]", value) else value


def csv_report(value):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", quoting=csv.QUOTE_ALL)

    def row(*cells):
        writer.writerow([safe_cell(cell) for cell in cells])

    row(
        "Seção",
        "Indicador",
        "Pessoa",
        "Cliente",
        "Período",
        "Quantidade / segundos",
        "Tickets únicos",
    )
    row("Contexto", value["notice"])
    row("Contexto", value["interpretation_context"])
    row("Escopo", value["scope"])
    row("Fuso", value["period"]["timezone"])
    row("Período", f"{value['period']['start_date']} a {value['period']['end_date']}")
    row("Filtros", str(value["filters"]))
    labels = {
        "registered_records": "Registros",
        "cancelled_records": "Cancelados",
        "confirmed_finalizations": "Finalizações confirmadas",
        "awaiting_review": "Finalizações aguardando revisão",
        "other_provisional_finalizations": "Outras finalizações provisórias",
    }
    for section, totals_value in (
        ("Resumo", value["totals"]),
        ("Comparação", value["comparison"]["totals"]),
    ):
        for key, count in totals_value.items():
            row(
                section,
                labels.get(key, key),
                "",
                "",
                "",
                count["actions"] if isinstance(count, dict) else count,
                count.get("unique_tickets", "") if isinstance(count, dict) else "",
            )
    for person in value["people"]:
        for key, count in person.items():
            if key in {"id", "name"}:
                continue
            row(
                "Pessoa",
                labels.get(key, key),
                person["name"],
                "",
                "",
                count["actions"] if isinstance(count, dict) else count,
                count.get("unique_tickets", "") if isinstance(count, dict) else "",
            )
    for item in value["series"]:
        row("Distribuição", "Registros", item["person_name"], "", item["bucket"], item["records"])
        for action, count in item["actions"].items():
            row("Distribuição", action, item["person_name"], "", item["bucket"], count)
    for item in value["classifications"]:
        row(
            "Assuntos",
            f"{item['category']} / {item['system']}",
            item["person_name"],
            "",
            "",
            item["records"],
        )
    for item in value["clients"]:
        row("Cliente", "Registros", "", item["name"], "", item["records"])
    for item in value["ticket_distribution"]:
        row(
            "Classificação atual dos tickets com ações no período",
            f"{item['category']} / {item['system']} / {item['priority']}",
            "",
            "",
            "",
            "",
            item["unique_tickets"],
        )
    for item in value["article_consultations"]:
        row("Artigo", item["title"], "", "", "", item["consultations"])
    for metric in ("first_action", "resolution"):
        for mode in ("gross", "net"):
            item = value["times"][metric][mode]
            for stat in ("median_seconds", "p90_seconds", "n"):
                labels_time = {
                    "first_action": "Primeira ação",
                    "resolution": "Ciclos de resolução",
                    "gross": "Bruto",
                    "net": "Descontando pausas",
                    "median_seconds": "Mediana (s)",
                    "p90_seconds": "P90 (s)",
                    "n": "Amostra (n)",
                }
                row(
                    "Tempos",
                    f"{labels_time[metric]} / {labels_time[mode]} / {labels_time[stat]}",
                    "",
                    "",
                    "",
                    item[stat],
                )
    for item in value["queue"]:
        row(
            "Fila atual",
            f"{item['code']} / {item['status']} / {item['priority']}",
            item["assignee_name"],
            item["client_name"],
            "",
            item["age_seconds"],
        )
    for item in value["workload"]:
        row("Carga", "Registros", "", "", item["date"], item["records"])
        row("Carga", "Chamados simultâneos", "", "", item["date"], item["active_tickets"])
        row(
            "Pendências atuais por fato",
            "Aguardando revisão",
            "",
            "",
            item["date"],
            item["pending_review_current_by_fact"],
        )
    for item in value["history"]["items"]:
        row(
            "Histórico completo",
            f"{item['type']} / {item['status']}",
            item["author_name"],
            item["client_name"],
            item["ocorrido_em"].astimezone(ZoneInfo(value["period"]["timezone"])).isoformat(),
            item["id"],
        )
    return "\ufeff" + stream.getvalue()
