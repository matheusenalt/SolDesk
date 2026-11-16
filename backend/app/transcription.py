"""Transcrição opcional e organização por regras com evidência verificável."""

import re
from importlib.metadata import version
from typing import Protocol

from pydantic import Field, field_validator

from app.schemas import Input

DEFAULT_GLOSSARY = [
    {"term": "Firebird", "aliases": ["fire bird"]},
    {"term": "CFOP", "aliases": []},
    {"term": "Sintegra", "aliases": []},
    {"term": "SGBR", "aliases": []},
    {"term": "Cervantes", "aliases": []},
]
DEFAULT_FIELDS = {
    "finalizacao": [
        ("reason", "Motivo", ["Motivo", "Problema"]),
        ("procedure", "Procedimento", ["Procedimento", "Solução"]),
        ("result", "Resultado", ["Resultado"]),
    ],
    "chamado": [
        ("problem", "Problema", ["Problema"]),
        ("initial_diagnosis", "Diagnóstico inicial", ["Diagnóstico", "Diagnóstico inicial"]),
        ("request", "Pedido", ["Pedido"]),
        ("priority", "Prioridade", ["Prioridade"]),
    ],
    "conhecimento": [
        ("title", "Título", ["Título"]),
        ("problem", "Problema", ["Problema"]),
        ("cause", "Causa", ["Causa"]),
        ("procedure", "Procedimento", ["Procedimento", "Solução"]),
        ("result", "Resultado", ["Resultado"]),
    ],
}


def default_fields(kind):
    return [
        {"key": key, "label": label, "markers": markers}
        for key, label, markers in DEFAULT_FIELDS[kind]
    ]


class GlossaryInput(Input):
    term: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("term", "aliases")
    @classmethod
    def words_only(cls, value):
        words = value if isinstance(value, list) else [value]
        if any(
            not word.strip() or len(word) > 80 or not all(c.isalpha() or c in " -" for c in word)
            for word in words
        ):
            raise ValueError(
                "Glossário aceita somente palavras; números e códigos não são normalizados"
            )
        return value


class TemplateField(Input):
    key: str = Field(pattern=r"^[a-z_]{1,40}$")
    label: str = Field(min_length=1, max_length=80)
    markers: list[str] = Field(min_length=1, max_length=6)

    @field_validator("markers")
    @classmethod
    def markers_only(cls, values):
        if any(
            not value.strip() or len(value) > 80 or not all(c.isalpha() or c == " " for c in value)
            for value in values
        ):
            raise ValueError("Use marcadores textuais explícitos")
        return values


class GroundedSection(Input):
    field: str
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class GroundedDraft(Input):
    sections: list[GroundedSection] = Field(max_length=30)


class Organizer(Protocol):
    def organize(self, text: str, fields: list[dict]) -> dict: ...


def validate_grounding(text, fields, draft):
    """Contrato para organizador futuro: rejeita todo trecho sem evidência literal."""
    parsed = GroundedDraft.model_validate(draft)
    allowed = {field["key"] for field in fields}
    for section in parsed.sections:
        if (
            section.field not in allowed
            or section.end > len(text)
            or section.start >= section.end
            or text[section.start : section.end] != section.text
        ):
            raise ValueError("Saída não fundamentada na transcrição")
    return parsed.model_dump()


class RulesOrganizer:
    def organize(self, text, fields):
        markers = {
            marker.casefold(): field["key"] for field in fields for marker in field["markers"]
        }
        pattern = (
            r"(?<!\w)("
            + "|".join(re.escape(marker) for marker in sorted(markers, key=len, reverse=True))
            + r")\s*:\s*"
        )
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        # Sem marcador, ou com prefixo livre: conservar a descrição integral.
        if not matches or text[: matches[0].start()].strip():
            return {"text": text, "sections": [], "mode": "descricao_integral"}
        sections = []
        for index, match in enumerate(matches):
            start, end = (
                match.end(),
                matches[index + 1].start() if index + 1 < len(matches) else len(text),
            )
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                sections.append(
                    {
                        "field": markers[match.group(1).casefold()],
                        "text": text[start:end],
                        "start": start,
                        "end": end,
                    }
                )
        result = validate_grounding(text, fields, {"sections": sections})
        if not sections:
            return {"text": text, "sections": [], "mode": "descricao_integral"}
        labels = {field["key"]: field["label"] for field in fields}
        return {
            "text": "\n".join(f"{labels[s['field']]}: {s['text']}" for s in sections),
            "sections": result["sections"],
            "mode": "marcadores",
        }


def normalize_terms(text, glossary):
    for item in glossary:
        GlossaryInput.model_validate(item)
        for word in [item["term"], *item["aliases"]]:
            text = re.sub(
                r"(?<!\w)" + re.escape(word) + r"(?!\w)",
                lambda _m, term=item["term"]: term,
                text,
                flags=re.IGNORECASE,
            )
    return text


def sensitive_warnings(text):
    patterns = {
        "possivel_credencial": r"\b(senha|password|token|chave)\b|https?://[^\s/@]+:[^\s/@]+@",
        "endereco_ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }
    return [
        {"kind": kind, "start": match.start(), "end": match.end()}
        for kind, pattern in patterns.items()
        for match in re.finditer(pattern, text, re.IGNORECASE)
    ]


class TranscriptionProvider(Protocol):
    def transcribe(self, audio: str, language: str, glossary: list[dict]) -> dict: ...


class MockProvider:
    """Não reconhece fala nem inventa relato: reutiliza o texto informado pelo autor."""

    def __init__(self, reference_text):
        self.reference_text = reference_text

    def transcribe(self, audio, language, glossary):
        return {
            "text": self.reference_text,
            "segments": [
                {
                    "start": 0,
                    "end": 1,
                    "text": self.reference_text,
                    "uncertain": True,
                    "confidence": None,
                }
            ],
            "metadata": {
                "provider": "mock",
                "model": "texto_informado",
                "version": "1",
                "simulado": True,
                "language": language,
            },
        }


class FasterWhisperProvider:
    def __init__(self, settings):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            settings.whisper_model_path,
            device="cpu",
            compute_type="int8",
            cpu_threads=settings.whisper_cpu_threads,
            num_workers=1,
            local_files_only=True,
        )

    def transcribe(self, audio, language, glossary):
        segments, info = self.model.transcribe(
            audio,
            language=language,
            initial_prompt=", ".join(item["term"] for item in glossary),
            beam_size=3,
            vad_filter=True,
        )
        rows = [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "uncertain": s.avg_logprob < -0.7 or s.no_speech_prob > 0.5,
                "confidence": s.avg_logprob,
            }
            for s in segments
        ]
        return {
            "text": "".join(s["text"] for s in rows).strip(),
            "segments": rows,
            "metadata": {
                "provider": "faster_whisper",
                "model": "local",
                "version": version("faster-whisper"),
                "simulado": False,
                "language": info.language,
            },
        }
