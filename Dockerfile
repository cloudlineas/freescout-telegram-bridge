# Pinned by digest; Dependabot proposes the bump when a new 3.12-slim ships.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Runs unprivileged; nothing here needs root.
RUN useradd --create-home --uid 10001 bridge
USER bridge

EXPOSE 8080

# Two workers is plenty for one person's ticket volume; the threads absorb the
# Telegram round-trip so a slow API call can't block the next webhook.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
