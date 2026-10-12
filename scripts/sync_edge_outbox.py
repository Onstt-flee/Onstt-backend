"""Send a bounded Pi outbox batch to the authoritative GPU API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--endpoint", default=os.getenv("EDGE_SYNC_ENDPOINT", ""))
    parser.add_argument("--token", default=os.getenv("EDGE_SYNC_TOKEN", ""))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.endpoint.startswith(("http://", "https://")):
        print("EDGE_SYNC_ENDPOINT must be an HTTP(S) URL", file=sys.stderr)
        return 2
    if not args.token:
        print("EDGE_SYNC_TOKEN is required", file=sys.stderr)
        return 2
    if not 1 <= args.batch_size <= 100 or args.timeout <= 0:
        print("Invalid batch-size or timeout", file=sys.stderr)
        return 2

    os.environ["STT_DATABASE_URL"] = f"sqlite:///{args.database.resolve()}"
    import edge_sync
    import models
    from database import SessionLocal, engine

    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        events = edge_sync.pending_events(db, args.batch_size)
        if not events:
            print(json.dumps({"sent": 0, "synced": 0, "rejected": 0}))
            return 0
        node_id = edge_sync.configured_node_id()
        body = json.dumps(
            {"node_id": node_id, "events": events}, ensure_ascii=False
        ).encode("utf-8")
        request = Request(
            args.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {args.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=args.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            edge_sync.record_sync_failure(
                db, [event["event_id"] for event in events], str(exc)
            )
            print(f"Edge sync failed: {exc}", file=sys.stderr)
            return 1

        results = result.get("results") if isinstance(result, dict) else None
        expected_ids = {event["event_id"] for event in events}
        returned_ids = {
            str(item.get("event_id")) for item in results
            if isinstance(item, dict) and item.get("event_id")
        } if isinstance(results, list) else set()
        if (
            not isinstance(results, list)
            or str(result.get("node_id")) != node_id
            or returned_ids != expected_ids
            or len(results) != len(events)
        ):
            edge_sync.record_sync_failure(
                db, [event["event_id"] for event in events], "Invalid sync response"
            )
            print("Invalid sync response", file=sys.stderr)
            return 1
        edge_sync.apply_sync_results(db, results)
        synced = sum(item.get("status") in {"accepted", "duplicate"} for item in results)
        rejected = sum(item.get("status") == "rejected" for item in results)
        print(json.dumps({"sent": len(events), "synced": synced, "rejected": rejected}))
        return 0 if rejected == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
