FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system novatech && adduser --system --ingroup novatech novatech

COPY pyproject.toml ./
COPY backend ./backend
COPY alembic ./alembic
COPY alembic.ini ./
COPY frontend ./frontend
COPY seed ./seed

RUN pip install --upgrade pip setuptools wheel \
    && pip install .

USER novatech
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
