#!/usr/bin/env python3
"""Run the persistent feedback audit worker as a separate service."""

from database import SessionLocal
from analyzer.feedback_store import configuration_error, feedback_enabled
from analyzer.feedback_worker import run_forever


def main() -> int:
    if not feedback_enabled():
        raise SystemExit("FEEDBACK_AUDIT_ENABLED is false")
    error = configuration_error()
    if error:
        raise SystemExit(f"Invalid feedback configuration: {error}")
    run_forever(SessionLocal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
