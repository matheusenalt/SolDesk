import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Password = Annotated[str, StringConstraints(strip_whitespace=False)]

Role = Literal["administrador", "gestor", "tecnico"]
Situation = Literal["ativo", "inativo"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmailInput(Input):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value.lower()


class Login(EmailInput):
    password: Password = Field(min_length=1, max_length=128)


class Signup(Login):
    name: str = Field(min_length=2, max_length=160)
    organization_name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    timezone: str = "America/Sao_Paulo"

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Fuso IANA inválido") from error
        return value


class PasswordChange(Input):
    current_password: Password = Field(min_length=1, max_length=128)
    new_password: Password = Field(min_length=12, max_length=128)


class MembershipChange(Input):
    role: Role
    situation: Situation


class InvitationInput(EmailInput):
    role: Role


class TemporaryUser(InvitationInput):
    name: str = Field(min_length=2, max_length=160)


class AcceptInvitation(Login):
    token: str = Field(min_length=32, max_length=128)
    name: str = Field(min_length=2, max_length=160)


class ExternalRef(Input):
    provider: str = Field(min_length=1, max_length=80)
    identifier: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=160)


class ClientInput(Input):
    name: str = Field(min_length=2, max_length=160)
    nickname: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    notes: str = Field(default="", max_length=4000)
    situation: Situation = "ativo"
    external_refs: list[ExternalRef] = Field(default_factory=list, max_length=20)

    @field_validator("email")
    @classmethod
    def optional_email(cls, value):
        return EmailInput(email=value).email if value else ""


class OrganizationChange(Input):
    name: str = Field(min_length=2, max_length=160)
    timezone: str = "America/Sao_Paulo"
    settings: dict[str, bool] = Field(default_factory=dict, max_length=20)

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value):
        return Signup.timezone_valid(value)


class OrganizationSelection(Input):
    organization_id: str = Field(min_length=36, max_length=36)
