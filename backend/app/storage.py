"""Objetos privados. Nenhum nome fornecido pelo usuário participa da chave."""

import re
import socket
import struct
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def safe_key(key):
    if not re.fullmatch(r"[0-9a-f-]{36}/[0-9a-f-]{36}", key):
        raise ValueError("Chave de objeto inválida")
    return key


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, key):
        path = self.root / safe_key(key)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Caminho inválido")
        return path

    def put(self, key, data, content_type):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open("xb") as output:
            path.chmod(0o600)
            output.write(data)

    def get(self, key):
        return self.path(key).read_bytes()

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, settings):
        import boto3
        from botocore.config import Config

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                connect_timeout=3,
                read_timeout=10,
                retries={"max_attempts": 2},
                s3={"addressing_style": "path"},
            ),
        )

    def put(self, key, data, content_type):
        self.client.put_object(
            Bucket=self.bucket, Key=safe_key(key), Body=data, ContentType=content_type
        )

    def get(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=safe_key(key))
        try:
            return response["Body"].read()
        finally:
            response["Body"].close()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=safe_key(key))


def storage(settings, backend=None):
    return (
        S3Storage(settings)
        if (backend or settings.storage_backend) == "s3"
        else LocalStorage(settings.storage_local_dir)
    )


def scan_antivirus(settings, data):
    if not settings.clamav_enabled:
        return
    with socket.create_connection(
        (settings.clamav_host, settings.clamav_port), timeout=10
    ) as client:
        client.sendall(b"zINSTREAM\0")
        for start in range(0, len(data), 65536):
            chunk = data[start : start + 65536]
            client.sendall(struct.pack("!I", len(chunk)) + chunk)
        client.sendall(struct.pack("!I", 0))
        response = client.recv(4096)
    if b"OK" not in response or b"FOUND" in response:
        raise ValueError("Arquivo recusado pela verificação antivírus")


FORMATS = {
    "wav": ("audio/wav", {".wav"}, {"audio/wav", "audio/x-wav", "audio/wave"}),
    "webm": ("audio/webm", {".webm"}, {"audio/webm", "video/webm"}),
    "ogg": ("audio/ogg", {".ogg", ".oga", ".opus"}, {"audio/ogg", "application/ogg"}),
    "mp4": ("audio/mp4", {".m4a", ".mp4"}, {"audio/mp4", "audio/x-m4a", "video/mp4"}),
    "aac": ("audio/aac", {".aac"}, {"audio/aac", "audio/x-aac"}),
    "mp3": ("audio/mpeg", {".mp3"}, {"audio/mpeg", "audio/mp3"}),
    "pdf": ("application/pdf", {".pdf"}, {"application/pdf"}),
    "png": ("image/png", {".png"}, {"image/png"}),
    "jpeg": ("image/jpeg", {".jpg", ".jpeg"}, {"image/jpeg"}),
    "txt": ("text/plain", {".txt"}, {"text/plain"}),
}


def identify(data, filename, claimed_type, audio, allowed):
    kind = None
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        kind = "wav"
    elif data.startswith(b"\x1aE\xdf\xa3") and b"webm" in data[:4096]:
        kind = "webm"
    elif data.startswith(b"OggS") and (b"OpusHead" in data[:4096] or b"vorbis" in data[:4096]):
        kind = "ogg"
    elif data[4:8] == b"ftyp" and len(data) >= 24:
        kind = "mp4"
    elif data.startswith(b"ID3") or len(data) > 2 and data[0] == 255 and data[1] & 0xE6 == 0xE2:
        kind = "mp3"
    elif len(data) > 2 and data[0] == 255 and data[1] & 0xF6 == 0xF0:
        kind = "aac"
    elif data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]:
        kind = "pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in data[-16:]:
        kind = "png"
    elif data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        kind = "jpeg"
    elif Path(filename).suffix.lower() == ".txt":
        try:
            value = data.decode("utf-8")
            if "\0" not in value and all(ord(c) >= 32 or c in "\n\r\t" for c in value):
                kind = "txt"
        except UnicodeError:
            pass
    if kind is None or audio != FORMATS[kind][0].startswith("audio/"):
        raise ValueError("Conteúdo não corresponde a um formato permitido")
    mime, suffixes, mimes = FORMATS[kind]
    if not audio and kind not in allowed.split(","):
        raise ValueError("Tipo não permitido nesta instalação")
    if (
        Path(filename).suffix.lower() not in suffixes
        or claimed_type.split(";", 1)[0].lower() not in mimes
    ):
        raise ValueError("Extensão, tipo informado e assinatura do arquivo não correspondem")
    return mime
