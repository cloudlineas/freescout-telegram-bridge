# Contributing

Thanks for taking a look. This is a small, deliberately focused project — the
best contributions are the ones that keep it that way.

## Getting set up

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
ruff check . && ruff format --check .
```

The test suite mocks the Telegram API, so you do **not** need a bot token to run
it. CI runs exactly those three commands on Python 3.12.

To exercise the real path end to end, copy `.env.example` to `.env`, fill it in,
then use `docker-compose.dev.yml` and `send_test_webhook.py` as described in the
README.

## Scope

Please open an issue before starting on anything large. Things likely to be
declined:

- **A pluggable notifier framework.** Adding Signal, ntfy or Slack behind an
  abstraction is a bigger change than adding one of them concretely. If you want
  another transport, propose it as a transport, not as a plugin system.
- **A URL-scheme option for the "Open in FreeScout" link.** This has been tried.
  `x-safari-https://` and `intent://` are accepted by the Bot API but stripped
  by the mobile client, producing a link that silently stops working. See the
  README FAQ.
- **Returning 200 when delivery fails.** The bridge exists because silent
  delivery failure is hard to notice. A rejected or unreachable Telegram must
  produce a 502 so FreeScout logs it.

## Pull requests

- One logical change per PR.
- Add or update tests for anything behavioural — especially signature
  verification, event filtering and escaping.
- Keep `ruff format` clean.
- Note user-visible changes in `CHANGELOG.md` under `Unreleased`.

## Security

Please do not open a public issue for a security problem. Report it privately
via GitHub's *Security → Report a vulnerability* on this repository.
