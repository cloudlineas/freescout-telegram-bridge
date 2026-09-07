# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-07

First public release.

### Added

- Flask webhook receiver for FreeScout's API & Webhooks module, forwarding
  events to Telegram via the Bot API.
- HMAC-SHA1 signature verification of `X-FreeScout-Signature`, compared with
  `hmac.compare_digest`; unsigned, empty and mismatched signatures return 401.
- Event allow-list via `EVENTS`; unsubscribed events are acknowledged with 200
  and dropped so they cannot wedge delivery.
- Telegram HTML messages with every interpolated value escaped, configurable
  preview truncation, optional mailbox labels and an optional "Open in
  FreeScout" link.
- `502` on Telegram rejection or network failure, so FreeScout records the
  failure in its webhook log rather than dropping it silently.
- `/healthz` endpoint reporting subscribed events and signature-check state.
- Multi-arch (`linux/amd64`, `linux/arm64`) container image published to
  `ghcr.io/cloudlineas/freescout-telegram-bridge`, running as uid 10001 on a
  digest-pinned `python:3.12-slim` base.
- pytest suite covering signature verification, event filtering, HTML escaping,
  preview truncation, sender fallbacks and the 502 failure paths, with the
  Telegram call mocked.
- `send_test_webhook.py` for posting correctly-signed fake webhooks at a running
  bridge.

[Unreleased]: https://github.com/cloudlineas/freescout-telegram-bridge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cloudlineas/freescout-telegram-bridge/releases/tag/v0.1.0
