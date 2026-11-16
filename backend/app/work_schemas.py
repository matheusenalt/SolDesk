from datetime import UTC
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

from app.models import now
from app.schemas import Input

RecordType = Literal["finalizacao", "chamado", "conhecimento"]
Priority = Literal["baixa", "normal", "alta", "urgente"]
TicketState = Literal[
    "aberto",
    "em_andamento",
    "aguardando_esclarecimento",
    "aguardando_terceiros",
    "resolvido",
    "encerrado",
    "reaberto",
]


class Occurrence(Input):
    ocorrido_em: AwareDatetime | None = None

    @field_validator("ocorrido_em")
    @classmethod
    def not_future(cls, value):
        if value and value > now():
            raise ValueError("A data do fato não pode estar no futuro")
        return value.astimezone(UTC) if value else None


class RecordCreate(Occurrence):
    client_id: str = Field(min_length=36, max_length=36)
    type: RecordType
    texto_original: str = Field(min_length=1, max_length=20000)
    capturado_em: AwareDatetime | None = None
    submit: bool = True
    ditado_texto: str | None = Field(default=None, max_length=20000)
    assignee_id: str | None = Field(default=None, min_length=36, max_length=36)
    priority: Priority = "normal"
    category: str = Field(default="", max_length=80)
    system: str = Field(default="", max_length=80)


class TicketCreate(RecordCreate):
    type: Literal["chamado"] = "chamado"


class RecordEdit(Occurrence):
    revision: int = Field(ge=1)
    texto_organizado: str = Field(min_length=1, max_length=20000)
    category: str | None = Field(default=None, max_length=80)
    system: str | None = Field(default=None, max_length=80)


class RecordAction(Input):
    revision: int = Field(ge=1)
    action: Literal["enviar", "confirmar", "devolver", "cancelar", "publicar", "processar"]
    reason: str = Field(default="", max_length=2000)
    audio_reviewed: bool = False
    assignee_id: str | None = Field(default=None, min_length=36, max_length=36)
    priority: Priority = "normal"
    category: str = Field(default="", max_length=80)


class BatchItem(Input):
    id: str = Field(min_length=36, max_length=36)
    revision: int = Field(ge=1)
    audio_reviewed: bool = False


class BatchReview(Input):
    items: list[BatchItem] = Field(min_length=1, max_length=50)


class Derive(Input):
    revision: int = Field(ge=1)
    type: RecordType


class TicketEdit(Input):
    revision: int = Field(ge=1)
    status: TicketState | None = None
    assignee_id: str | None = Field(default=None, min_length=36, max_length=36)
    priority: Priority | None = None
    category: str | None = Field(default=None, max_length=80)
    system: str | None = Field(default=None, max_length=80)


class CommentCreate(Input):
    revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=10000)
    kind: Literal["comentario", "esclarecimento", "resposta"] = "comentario"
    mentioned_user_ids: list[str] = Field(default_factory=list, max_length=20)
