# GPU dual-model feedback staging

This profile keeps the judgment response synchronous and moves verification to
a persistent DB-backed worker. It is disabled by default and does not expose
feedback to learners or overwrite `judgment_results`.

The selected verifier is `feedback-verifier-v0.3`. It passed the generated-validated
GPU internal holdout but is authorized only for GPU-judgment shadow with no
learner exposure. Pi intake is deferred.

## Resource envelope

- judgment Qwen3-4B + v0.2-D: port 1234, GPU reservation 0.30
- feedback Qwen3-8B + feedback-v0.3: port 1235, reservation 0.50
- total configured reservation: 0.80; feedback concurrency: one
- Qwen3-14B remains an offline upper-bound model only

Do not run the original `judgment-vllm.service` at 0.80 together with these
units. Stop it first, then use `judgment-vllm-dual.service` and
`feedback-vllm.service`. Service installation and activation require an
operator; repository changes never activate them.

## Safe activation order

1. Verify all model/adapter SHA-256 values and write a mode-0600 environment file.
2. Start both vLLM services and verify their aliases through `/v1/models`.
3. Run contract smoke tests while `FEEDBACK_AUDIT_ENABLED=false`.
4. Start `feedback-worker.service`, then enable audit enqueue only in staging. The worker entrypoint resolves the repository root explicitly so direct script execution from systemd does not depend on an inherited `PYTHONPATH`.
5. Check protected `/ready/feedback`, `/health/feedback`, audits, and issue groups.

The admin token must contain at least 32 characters. List APIs exclude source
text; the detail API is privileged and intended only for investigation.

The service config separates Qwen reasoning from OpenAI `content` with
`--reasoning-parser qwen3`. This was added after the consumed v0.1 holdout found
an empty think wrapper in every content string. It is not retroactively applied
to that result and must be validated once on a new sealed holdout before use.

## Failure semantics

Audit transport/contract failures are retried after 1, 5, and 30 minutes, at
most three attempts. Failed audits remain visible to administrators. They do
not modify or fail the judgment response. Pi judgments enter the same queue
only after an idempotent GPU edge-sync transaction succeeds.

## Actual stored STT operational shadow

The completed 200-item operational run used
`scripts/build_feedback_actual_inputs.py` to create a private, content-bearing
snapshot from stored Japanese STT. It then used
`scripts/run_feedback_synthetic_shadow.py` with
`actual_stored_stt_operational_shadow_only` scope to run judgment and feedback
inside an isolated database.

The judgment path applies exactly one retry only for non-correction
text-preservation violations. The tracked result contains aggregates and hashes
only. This run is label-free operational evidence, not a language-quality
evaluation.

See
`training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md` for the fixed
result and limitations.

## Actual admin HTTP and Swagger smoke

Use the fixed actual-shadow SQLite only through a temporary copy. The verifier
starts loopback FastAPI processes, checks Swagger/OpenAPI, authentication,
content-free projections, retry rejection, model-unavailable readiness and the
disabled feature state, then terminates both processes.

```bash
venv/bin/python scripts/verify_feedback_admin_http.py \
  --database /home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1.sqlite3 \
  --output evaluation/feedback/actual_shadow_v0.1.admin-http.result.json \
  --port 18001 \
  --overwrite
```

Ports 18001 and 18002 must be free. The script generates an ephemeral admin
token, never writes it to the result, and verifies that the source database and
temporary database copy remain byte-identical. It records only HTTP statuses,
counts, booleans and SHA-256 values.

A passing result is access-control and wiring evidence only. It does not approve
learner exposure, language quality, automatic retraining or production-default
activation.

## Persisted GPU judgment audit

`scripts/run_feedback_actual_shadow.py` is the supported handoff when 200
eligible GPU judgments already exist in the source database. It opens the source
SQLite database in read-only mode and copies exactly 200 eligible `gpu_bf16`,
`judgment-v02d`, `judgment-v0.2-D` records into a private isolated database.
The feedback model is run against the copy, never against the source DB.

Prerequisites:

- both source tables and judgment provenance are present;
- 200 eligible judgments exist after the explicit cursor;
- feedback vLLM alias `feedback-qwen3-8b-v03` is ready on loopback;
- the content-bearing isolated DB is outside the Git workspace;
- the tracked summary path does not already exist unless `--overwrite` is
  explicitly intended.

Example:

```bash
set -a
source /home/cap-minsung/.config/stt-api/feedback-staging.env
set +a

FEEDBACK_AUDIT_ENABLED=true venv/bin/python scripts/run_feedback_actual_shadow.py \
  --source-database /home/cap-minsung/stt_api/stt_data.db \
  --isolated-database /home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1.sqlite3 \
  --summary evaluation/feedback/actual_shadow_v0.1.result.json \
  --after-judgment-id 0
```

Change the cursor only from a previously fixed run record. The script fails
closed when fewer than 200 eligible rows exist, when provenance is missing, or
when the source DB, selected judgment snapshot, isolated judgments, queue, or
audit uniqueness checks do not remain consistent.

The summary contains counts, aggregate latency and hashes only. The isolated DB
contains source text and must remain outside Git. Even a passing run is
label-free operational evidence and cannot be reported as grammar accuracy or
used to enable learner-visible warnings.
