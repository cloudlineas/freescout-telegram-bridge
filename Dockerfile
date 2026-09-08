# Pinned by digest. Dependabot proposes both digest refreshes and new Python
# releases; CI runs the built container, so a base bump that breaks the
# runtime fails the PR instead of merging green.
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

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
