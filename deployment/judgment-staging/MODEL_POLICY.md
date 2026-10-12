# Judgment model retention and runtime policy

Status: fixed on 2026-10-12.

## Runtime model

Only the following model is permitted in the checked-in staging runtime:

- base: `Qwen3-4B-Instruct-2507`
- alias: `judgment-v02d`
- adapter: `judgment-qwen3-4b-failure-focus-v0.2-d`
- feature flag default: `JUDGMENT_ENABLED=false`

The service, environment examples, readiness check, preflight, and systemd
templates must all fail closed when another alias or adapter is configured.
This is a limited staging/shadow selection, not production approval.

## Record-only experiments

v0.1, v0.2-A/B/C/E/F/G/H/I/J and all baseline models are record-only. They
must not be referenced by runtime defaults or deployment templates. Git keeps
only reproducibility material such as source/config lineage, aggregate result
JSON, Markdown reports, manifests, and SHA-256 values.

Model weights, partial downloads, raw inference JSONL, private review material,
and audio are not Git artifacts. They remain in ignored or external paths. The
v0.2-F and v0.2-J adapters may be retained outside the repository for research
reproduction, but they are never loaded by the checked-in staging service.

Existing experiment commits are historical evidence and are not rewritten or
deleted. A future model cycle requires a new unused holdout and a new explicit
runtime-selection decision.
