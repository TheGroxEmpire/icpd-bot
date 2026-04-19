FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --no-cache-dir ".[dev]"

CMD ["python", "-m", "icpd_bot"]
