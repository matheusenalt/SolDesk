"""Regras transacionais de registros e chamados; nenhum conteúdo é inferido."""

import json

from fastapi import HTTPException
from sqlalchemy import or_, select, text

from app.models import Client, OrganizationMembership, User, now
from app.security import digest
from app.work_models import (
    KnowledgeArticle,
    Notification,
    Record,
    RecordVersion,
    RequestReceipt,
    Ticket,
    TicketComment,
    TicketEvent,
    TicketInterval,
    TicketParticipant,
)

TICKET_TRANSITIONS = {
    "aberto": {"em_andamento", "aguardando_esclarecimento", "aguardando_terceiros", "resolvido"},
    "em_andamento": {"aguardando_esclarecimento", "aguardando_terceiros", "resolvido"},
    "aguardando_esclarecimento": {"em_andamento", "aguardando_terceiros", "resolvido"},
    "aguardando_terceiros": {"em_andamento", "aguardando_esclarecimento", "resolvido"},
    "resolvido": {"encerrado", "reaberto"},
    "encerrado": {"reaberto"},
    "reaberto": {"em_andamento", "aguardando_esclarecimento", "aguardando_terceiros", "resolvido"},
}
WAITING = {"aguardando_esclarecimento", "aguardando_terceiros"}


def active_member(ctx, user_id):
    member = ctx.db.scalar(
        ctx.query(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.situation == "ativo",
        )
    )
    if member is None:
        raise HTTPException(404, "Integrante ativo não encontrado")
    return member


def ticket_query(ctx):
    query = ctx.query(Ticket)
    if ctx.membership.role == "tecnico":
        participating = select(TicketParticipant.ticket_id).where(
            TicketParticipant.organization_id == ctx.organization_id,
            TicketParticipant.user_id == ctx.user.id,
        )
        query = query.where(
            or_(
                Ticket.opened_by == ctx.user.id,
                Ticket.assignee_id == ctx.user.id,
                Ticket.id.in_(participating),
            )
        )
    return query


def record_query(ctx):
    query = ctx.query(Record)
    if ctx.membership.role == "tecnico":
        query = query.where(
            or_(
                Record.author_id == ctx.user.id,
                (Record.type == "finalizacao") & (Record.status == "confirmado"),
                Record.ticket_id.in_(ticket_query(ctx).with_only_columns(Ticket.id)),
            )
        )
    return query


def find_record(ctx, identifier, revision=None):
    query = record_query(ctx).where(Record.id == identifier)
    if revision is not None:
        query = query.with_for_update()
    item = ctx.db.scalar(query)
    if item is None:
        raise HTTPException(404, "Registro não encontrado")
    check_revision(item, revision)
    return item


def find_ticket(ctx, identifier, revision=None):
    query = ticket_query(ctx).where(Ticket.id == identifier)
    if revision is not None:
        query = query.with_for_update()
    item = ctx.db.scalar(query)
    if item is None:
        raise HTTPException(404, "Chamado não encontrado")
    check_revision(item, revision)
    return item


def check_revision(item, revision):
    if revision is not None and item.revision != revision:
        raise HTTPException(409, "Este item foi alterado. Recarregue antes de salvar novamente")


def author_only(ctx, item):
    if item.author_id != ctx.user.id:
        raise HTTPException(403, "Somente o autor pode revisar ou editar este registro")


def record_data(ctx, item):
    fields = (
        "id",
        "client_id",
        "author_id",
        "type",
        "texto_original",
        "texto_organizado",
        "status",
        "revision",
        "origem_record_id",
        "ticket_id",
        "article_id",
        "ocorrido_em",
        "enviado_em",
        "capturado_em",
        "processado_em",
        "revisado_em",
        "revisado_por",
        "publicado_em",
        "cancellation_reason",
    )
    result = {field: getattr(item, field) for field in fields}
    result["author_name"] = ctx.db.get(User, item.author_id).name
    result["client_name"] = ctx.get(Client, item.client_id).name
    result["provisional"] = item.status not in {"confirmado", "publicado"}
    result["age_seconds"] = max(0, int((now() - item.enviado_em).total_seconds()))
    result["article_status"] = "rascunho" if item.article_id else None
    return result


def json_record(ctx, item):
    return json.loads(json.dumps(record_data(ctx, item), default=lambda value: value.isoformat()))


def record_event(ctx, request, item, change, before=None):
    after = json_record(ctx, item)
    ctx.db.add(
        RecordVersion(
            organization_id=ctx.organization_id,
            record_id=item.id,
            revision=item.revision,
            actor_id=ctx.user.id,
            change=change,
            snapshot=after,
        )
    )
    ctx.audit(request, change, "Record", item.id, before, after)


def notify(ctx, user_id, kind, entity, identifier):
    active_member(ctx, user_id)
    ctx.db.add(
        Notification(
            organization_id=ctx.organization_id,
            user_id=user_id,
            type=kind,
            reference_type=entity,
            reference_id=identifier,
        )
    )


def participant(ctx, ticket, user_id):
    active_member(ctx, user_id)
    exists = ctx.db.scalar(
        ctx.query(TicketParticipant).where(
            TicketParticipant.ticket_id == ticket.id,
            TicketParticipant.user_id == user_id,
        )
    )
    if not exists:
        ctx.db.add(
            TicketParticipant(
                organization_id=ctx.organization_id, ticket_id=ticket.id, user_id=user_id
            )
        )
        ctx.db.flush()


def ticket_snapshot(item):
    fields = (
        "status",
        "revision",
        "priority",
        "category",
        "assignee_id",
        "opened_by",
        "resolved_by",
        "closed_by",
        "reopen_count",
        "aberto_em",
        "resolvido_em",
        "encerrado_em",
    )
    return {
        field: getattr(item, field).isoformat()
        if hasattr(getattr(item, field), "isoformat")
        else getattr(item, field)
        for field in fields
    }


def ticket_event(ctx, request, item, change, before=None):
    after = ticket_snapshot(item)
    ctx.db.add(
        TicketEvent(
            organization_id=ctx.organization_id,
            ticket_id=item.id,
            actor_id=ctx.user.id,
            change=change,
            before=before or {},
            after=after,
        )
    )
    ctx.audit(request, change, "Ticket", item.id, before, after)


def send_record(ctx, request, item, assignee_id=None, priority="normal", category=""):
    if item.type == "chamado":
        assignee_id = assignee_id or item.author_id
        active_member(ctx, assignee_id)
        sequence = ctx.db.scalar(
            text("""INSERT INTO ticket_sequence(organization_id,value)
            VALUES (:org,1) ON CONFLICT (organization_id)
            DO UPDATE SET value=ticket_sequence.value+1 RETURNING value"""),
            {"org": ctx.organization_id},
        )
        ticket = Ticket(
            organization_id=ctx.organization_id,
            record_id=item.id,
            client_id=item.client_id,
            code=f"SD-{sequence:06d}",
            description=item.texto_organizado or item.texto_original,
            opened_by=item.author_id,
            assignee_id=assignee_id,
            priority=priority,
            category=category,
        )
        ctx.db.add(ticket)
        ctx.db.flush()
        item.ticket_id = ticket.id
        item.status = "enviado"
        for user_id in {item.author_id, assignee_id}:
            participant(ctx, ticket, user_id)
        notify(ctx, assignee_id, "chamado_atribuido", "ticket", ticket.id)
        ticket_event(ctx, request, ticket, "chamado_aberto")
    else:
        item.status = "aguardando_revisao"
        if item.type == "conhecimento":
            if not item.article_id:
                article = KnowledgeArticle(
                    organization_id=ctx.organization_id,
                    record_id=item.id,
                    author_id=item.author_id,
                    text=item.texto_organizado or item.texto_original,
                )
                ctx.db.add(article)
                ctx.db.flush()
                item.article_id = article.id
        notify(ctx, item.author_id, "registro_pronto_revisao", "record", item.id)


def create_record(ctx, request, body, key=None, scope="records", source=None):
    payload = body.model_dump(mode="json")
    fingerprint = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    key_hash = None
    if key is not None:
        if not 8 <= len(key) <= 128:
            raise HTTPException(422, "Idempotency-Key deve ter de 8 a 128 caracteres")
        key_hash = digest(key)
        lock = f"{ctx.organization_id}:{ctx.user.id}:{scope}:{key_hash}"
        ctx.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": lock}
        )
        receipt = ctx.db.scalar(
            ctx.query(RequestReceipt).where(
                RequestReceipt.user_id == ctx.user.id,
                RequestReceipt.scope == scope,
                RequestReceipt.key_hash == key_hash,
            )
        )
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise HTTPException(409, "Idempotency-Key já usada com outro conteúdo")
            return find_record(ctx, receipt.record_id)
    ctx.get(Client, body.client_id)
    if body.type != "chamado" and (body.assignee_id or body.priority != "normal" or body.category):
        raise HTTPException(422, "Responsável, prioridade e categoria são campos de chamado")
    received = now()
    occurred = source.ocorrido_em if source else body.ocorrido_em or received
    item = Record(
        organization_id=ctx.organization_id,
        client_id=body.client_id,
        author_id=ctx.user.id,
        type=body.type,
        texto_original=body.texto_original,
        ocorrido_em=occurred,
        enviado_em=received,
        capturado_em=body.capturado_em,
        origem_record_id=source.id if source else None,
    )
    ctx.db.add(item)
    ctx.db.flush()
    if body.submit:
        send_record(ctx, request, item, body.assignee_id, body.priority, body.category)
    if occurred != received:
        ctx.audit(
            request,
            "horario_informado",
            "Record",
            item.id,
            {"ocorrido_em": received.isoformat()},
            {"ocorrido_em": occurred.isoformat()},
        )
    record_event(ctx, request, item, "registro_derivado" if source else "registro_criado")
    if key_hash:
        ctx.db.add(
            RequestReceipt(
                organization_id=ctx.organization_id,
                user_id=ctx.user.id,
                scope=scope,
                key_hash=key_hash,
                fingerprint=fingerprint,
                record_id=item.id,
            )
        )
    ctx.db.flush()
    return item


def edit_record(ctx, request, item, body):
    author_only(ctx, item)
    if item.status not in {"rascunho", "aguardando_revisao"}:
        raise HTTPException(409, "O conteúdo deste registro está bloqueado; use Derivar")
    before = json_record(ctx, item)
    item.texto_organizado = body.texto_organizado
    if body.ocorrido_em:
        item.ocorrido_em = body.ocorrido_em
    item.revision += 1
    if item.article_id:
        ctx.get(KnowledgeArticle, item.article_id).text = body.texto_organizado
    if before["ocorrido_em"] != item.ocorrido_em.isoformat():
        ctx.audit(
            request,
            "horario_ajustado",
            "Record",
            item.id,
            {"ocorrido_em": before["ocorrido_em"]},
            {"ocorrido_em": item.ocorrido_em.isoformat()},
        )
    record_event(ctx, request, item, "registro_editado", before)
    ctx.db.flush()


def act_record(ctx, request, item, body):
    before = json_record(ctx, item)
    if body.action in {"processar", "publicar"}:
        raise HTTPException(409, "Processamento e publicação não estão disponíveis nesta fase")
    if body.action == "cancelar":
        if item.author_id != ctx.user.id and ctx.membership.role == "tecnico":
            raise HTTPException(403, "Ação não permitida para este registro")
        if item.status == "cancelado" or item.type == "chamado" and item.ticket_id:
            raise HTTPException(
                409, "Use o ciclo de vida do chamado; este registro não pode ser cancelado"
            )
        if not body.reason:
            raise HTTPException(422, "Informe o motivo do cancelamento")
        item.status, item.cancellation_reason = "cancelado", body.reason
    else:
        author_only(ctx, item)
        if body.action == "confirmar":
            if item.type != "finalizacao" or item.status != "aguardando_revisao":
                raise HTTPException(
                    409, "Somente finalização aguardando revisão pode ser confirmada"
                )
            item.status, item.revisado_em, item.revisado_por = "confirmado", now(), ctx.user.id
        elif body.action == "devolver":
            if item.status != "aguardando_revisao":
                raise HTTPException(409, "Este registro não aguarda revisão")
            item.status = "rascunho"
        elif body.action == "enviar":
            if item.status != "rascunho":
                raise HTTPException(409, "Somente rascunhos podem ser enviados")
            send_record(ctx, request, item, body.assignee_id, body.priority, body.category)
    item.revision += 1
    record_event(ctx, request, item, f"registro_{body.action}", before)
    ctx.db.flush()


def operate_ticket(ctx, item, closing=False):
    allowed = ctx.membership.role in {"administrador", "gestor"}
    allowed |= item.opened_by == ctx.user.id if closing else item.assignee_id == ctx.user.id
    if not allowed:
        raise HTTPException(403, "Somente responsável ou gestão pode alterar este chamado")


def transition_ticket(ctx, item, target):
    if target not in TICKET_TRANSITIONS[item.status]:
        raise HTTPException(409, "Transição de chamado não permitida")
    instant = now()
    if item.status in WAITING:
        interval = ctx.db.scalar(
            ctx.query(TicketInterval).where(
                TicketInterval.ticket_id == item.id,
                TicketInterval.saida_em.is_(None),
            )
        )
        if interval is None:
            raise HTTPException(409, "Intervalo de espera inconsistente")
        interval.saida_em = instant
        ctx.db.flush()
    if target in WAITING:
        ctx.db.add(
            TicketInterval(
                organization_id=ctx.organization_id,
                ticket_id=item.id,
                status=target,
                entrada_em=instant,
            )
        )
    if target == "resolvido":
        item.resolved_by, item.resolvido_em = ctx.user.id, instant
    if target == "encerrado":
        item.closed_by, item.encerrado_em = ctx.user.id, instant
    if target == "reaberto":
        item.reopen_count += 1
    item.status = target


def change_ticket(ctx, request, item, body):
    operate_ticket(ctx, item, closing=body.status == "encerrado")
    if any(
        getattr(body, field) is not None and getattr(body, field) != getattr(item, field)
        for field in ("assignee_id", "priority", "category")
    ):
        operate_ticket(ctx, item)
    before = ticket_snapshot(item)
    if body.assignee_id and body.assignee_id != item.assignee_id:
        participant(ctx, item, body.assignee_id)
        item.assignee_id = body.assignee_id
        notify(ctx, item.assignee_id, "chamado_atribuido", "ticket", item.id)
    if body.priority is not None:
        item.priority = body.priority
    if body.category is not None:
        item.category = body.category
    if body.status:
        transition_ticket(ctx, item, body.status)
    item.revision += 1
    ticket_event(ctx, request, item, "chamado_alterado", before)
    ctx.db.flush()


def comment_ticket(ctx, request, item, body):
    before = ticket_snapshot(item)
    for user_id in set(body.mentioned_user_ids):
        participant(ctx, item, user_id)
    if body.kind == "esclarecimento":
        operate_ticket(ctx, item)
        transition_ticket(ctx, item, "aguardando_esclarecimento")
        notify(ctx, item.opened_by, "esclarecimento_solicitado", "ticket", item.id)
    elif body.kind == "resposta":
        if item.status == "aguardando_esclarecimento":
            transition_ticket(ctx, item, "em_andamento")
        if item.assignee_id != ctx.user.id:
            notify(ctx, item.assignee_id, "resposta_recebida", "ticket", item.id)
    else:
        for user_id in {item.assignee_id, item.opened_by} - {ctx.user.id}:
            notify(ctx, user_id, "resposta_recebida", "ticket", item.id)
    for user_id in set(body.mentioned_user_ids) - {ctx.user.id}:
        notify(ctx, user_id, "mencao", "ticket", item.id)
    ctx.db.add(
        TicketComment(
            organization_id=ctx.organization_id,
            ticket_id=item.id,
            author_id=ctx.user.id,
            text=body.text,
            kind=body.kind,
            mentioned_user_ids=sorted(set(body.mentioned_user_ids)),
        )
    )
    item.revision += 1
    ticket_event(ctx, request, item, f"chamado_{body.kind}", before)
    ctx.db.flush()


def ticket_data(ctx, item):
    fields = (
        "id",
        "record_id",
        "client_id",
        "code",
        "description",
        "opened_by",
        "assignee_id",
        "resolved_by",
        "closed_by",
        "priority",
        "category",
        "status",
        "revision",
        "reopen_count",
        "aberto_em",
        "resolvido_em",
        "encerrado_em",
    )
    result = {field: getattr(item, field) for field in fields}
    result["client_name"] = ctx.get(Client, item.client_id).name
    for field in ("opened_by", "assignee_id", "resolved_by", "closed_by"):
        user = ctx.db.get(User, getattr(item, field)) if getattr(item, field) else None
        result[field + "_name"] = user.name if user else None
    return result
