FROM python:3.13-slim AS dependencies
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home soldesk && mkdir -p /home/soldesk/media && chown soldesk:soldesk /home/soldesk/media

FROM dependencies AS ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && apt-get clean && rm -r /var/lib/apt/lists/*

FROM dependencies AS runtime
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --no-deps .
COPY alembic.ini ./
COPY migrations ./migrations
FROM ffmpeg AS worker
COPY --from=runtime /app /app
RUN pip install --no-cache-dir --no-deps .
USER soldesk
CMD ["python", "-m", "app.media_worker", "worker"]

FROM worker AS whisper
USER root
ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
COPY requirements-whisper.lock ./
RUN pip install --no-cache-dir -c requirements.lock -r requirements-whisper.lock
USER soldesk

FROM runtime AS api
USER soldesk
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
