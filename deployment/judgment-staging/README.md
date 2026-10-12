# Judgment staging service templates

This directory contains GPU-server-specific staging templates. They are not authorization to expose model output to learners. The checked-in environment example stays disabled. Runtime model retention and exclusion rules are fixed in [`MODEL_POLICY.md`](MODEL_POLICY.md).

- root-managed templates are retained for a future administrator-managed deployment;
- `user/` contains the no-sudo user-service variant used for the current staging verification;
- `scripts/install_judgment_user_services.sh` installs but never starts or enables the user services;
- `scripts/manage_judgment_user_staging.py` performs fail-closed start, status, and stop transitions.

Safety invariants:

- both HTTP services bind only to `127.0.0.1`;
- the API has exactly one Uvicorn worker;
- process-local concurrency is capped separately by `JUDGMENT_MAX_CONCURRENCY`;
- response-independent shadow work uses one bounded consumer with explicit queue size and item TTL;
- a content- and user-independent token bucket admits about one shadow item per second and counts excess input separately as `sampled_out`;
- the API uses an isolated staging database in the user state directory;
- readiness remains unavailable until the fixed `judgment-v02d` alias exists;
- the API fails its `ExecStartPre` check unless an operator explicitly enables the feature in the private runtime environment file;
- neither user unit has an `[Install]` section, so it cannot be enabled accidentally.

Install, verification, and rollback commands are documented in `docs/JUDGMENT_STAGING_RUNBOOK.md`. Do not put credentials, user content, database copies, raw model output, or model weights in this directory.
