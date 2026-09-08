# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-09-08

### Changed

- `PREVIEW_CHARS` default raised from `120` back to `160`. 120 cut the body
  mid-sentence more often than it saved a line; the rendered line count depends
  on client width either way.

## 0.2.0 - 2026-09-08

### Changed

- The subject is now shown in bold on its own line instead of being prefixed
  with `Subject:`, so the notification leads with what the ticket is about.
- The body preview is collapsed to a single paragraph before truncation, so a
  hard-wrapped email no longer arrives as a column of stubs.
- `PREVIEW_CHARS` now defaults to `120` (was `300`).

## 0.1.0 - 2026-09-08

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
  digest-pinned `python:3.14-slim` base.
- pytest suite covering signature verification, event filtering, HTML escaping,
  preview truncation, sender fallbacks and the 502 failure paths, with the
  Telegram call mocked.
- `send_test_webhook.py` for posting correctly-signed fake webhooks at a running
  bridge.

<!-- 0.1.0 and 0.2.0 predate the squash of this repository's history and have no
     tag to link to; their images remain on GHCR. -->
[Unreleased]: https://github.com/cloudlineas/freescout-telegram-bridge/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/cloudlineas/freescout-telegram-bridge/releases/tag/v0.2.1
