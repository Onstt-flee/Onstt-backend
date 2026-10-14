# GPU dual-model feedback staging

This profile keeps the judgment response synchronous and moves verification to
a persistent DB-backed worker. It is disabled by default and does not expose
feedback to learners or overwrite `judgment_results`.

## Resource envelope

- judgment Qwen3-4B + v0.2-D: port 1234, GPU reservation 0.30
- feedback Qwen3-8B + feedback-v0.1: port 1235, reservation 0.50
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
4. Start `feedback-worker.service`, then enable audit enqueue only in staging.
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
