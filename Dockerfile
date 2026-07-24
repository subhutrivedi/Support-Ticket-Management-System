FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.lock .
RUN pip install --upgrade pip && pip install --requirement requirements.lock

COPY . .
RUN pip install --no-deps . \
    && addgroup --system ticketflow \
    && adduser --system --ingroup ticketflow ticketflow \
    && chown --recursive ticketflow:ticketflow /app

ENV HOME=/tmp PATH=/tmp/.local/bin:${PATH}
USER ticketflow
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
