import argparse
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from database import Base
from scripts.run_feedback_actual_shadow import (
    SAMPLE_SIZE,
    run,
    select_rows,
    selection_sha256,
    source_counts,
)


MODEL = "judgment-v02d"
ADAPTER = "judgment-qwen3-4b-failure-focus-v0.2-d"
HASH = "a" * 64


def build_source(path: Path, count: int = SAMPLE_SIZE) -> None:
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        session = models.Session(topic="actual-source")
        db.add(session)
        db.flush()
        for index in range(count):
            text = f"今日は公園に行きます。{index}"
            utterance = models.Utterance(
                session_id=session.id,
                stt_text=text,
                language="ja",
                stt_model="test-stt",
            )
            db.add(utterance)
            db.flush()
            judgment = models.JudgmentResult(
                utterance_id=utterance.id,
                decision="acceptable",
                corrected_text=text,
                edits="[]",
                error_types="[]",
                reason_ko="문법적으로 허용됩니다.",
                classification_review_required=False,
                strategy="d_only",
                model_name=MODEL,
                adapter_name=ADAPTER,
                selection_reason="test",
                contract_version="judgment-v0.2",
                latency_ms=100.0,
                context=None,
                learner_level="N5",
            )
            db.add(judgment)
            db.flush()
            db.add(models.JudgmentProvenance(
                judgment_id=judgment.id,
                runtime="gpu_bf16",
                node_id=None,
                quantization="BF16",
                judgment_model=MODEL,
                judgment_adapter=ADAPTER,
                model_sha256=HASH,
                adapter_sha256=HASH,
            ))
        db.commit()
    engine.dispose()


def agree_runner(text, *, context, learner_level, judgment, model_name):
    return {
        "verdict": "agree",
        "issue_codes": [],
        "recommended_judgment": None,
        "review_reason_ko": "판단이 타당합니다.",
        "latency_ms": 12.5,
    }


class FeedbackActualShadowTests(unittest.TestCase):
    def test_run_copies_200_to_isolated_db_without_writing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            isolated = root / "isolated.sqlite3"
            summary_path = root / "summary.json"
            build_source(source)
            args = argparse.Namespace(
                source_database=source,
                isolated_database=isolated,
                summary=summary_path,
                after_judgment_id=0,
                judgment_model=MODEL,
                judgment_adapter=ADAPTER,
                overwrite=False,
            )
            environment = {
                "FEEDBACK_AUDIT_ENABLED": "true",
                "FEEDBACK_MODEL": "feedback-qwen3-8b-v03",
                "FEEDBACK_ADAPTER": "feedback-verifier-v0.3",
                "FEEDBACK_MODEL_SHA256": HASH,
                "FEEDBACK_ADMIN_TOKEN": "x" * 32,
            }
            with patch.dict(os.environ, environment, clear=False):
                result = run(args, worker_runner=agree_runner)

            self.assertTrue(result["operational_gate"]["passed"])
            self.assertEqual(result["feedback"]["audit_count"], SAMPLE_SIZE)
            self.assertEqual(result["feedback"]["verdict_counts"], {"agree": SAMPLE_SIZE})
            self.assertTrue(result["integrity"]["source_database_unchanged"])
            self.assertTrue(result["integrity"]["isolated_judgments_unchanged"])
            tracked = summary_path.read_text(encoding="utf-8")
            self.assertNotIn("今日は公園に行きます", tracked)
            self.assertNotIn('"user_id"', tracked)

    def test_selection_requires_exactly_200_eligible_gpu_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.sqlite3"
            build_source(source, SAMPLE_SIZE - 1)
            import sqlite3
            connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            with connection:
                self.assertEqual(source_counts(connection)["judgment_results"], 199)
                with self.assertRaisesRegex(ValueError, "insufficient eligible"):
                    select_rows(
                        connection,
                        after_judgment_id=0,
                        judgment_model=MODEL,
                        judgment_adapter=ADAPTER,
                    )

    def test_selection_hash_is_deterministic_and_cursor_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.sqlite3"
            build_source(source, SAMPLE_SIZE + 1)
            import sqlite3
            connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            with connection:
                first = select_rows(
                    connection,
                    after_judgment_id=0,
                    judgment_model=MODEL,
                    judgment_adapter=ADAPTER,
                )
                self.assertEqual(first[0]["source_judgment_id"], 1)
                self.assertEqual(selection_sha256(first), selection_sha256(first))
                with self.assertRaisesRegex(ValueError, "insufficient eligible"):
                    select_rows(
                        connection,
                        after_judgment_id=2,
                        judgment_model=MODEL,
                        judgment_adapter=ADAPTER,
                    )


if __name__ == "__main__":
    unittest.main()
