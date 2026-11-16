# Pinned by digest. Dependabot proposes both digest refreshes and new Python
# releases; CI runs the built container, so a base bump that breaks the
# runtime fails the PR instead of merging green.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

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
