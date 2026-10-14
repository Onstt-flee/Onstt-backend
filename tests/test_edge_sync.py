"""Pi outbox and authoritative GPU synchronization tests."""

import json
import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import edge_sync
import main
import models
import schemas


NODE_ID = "11111111-1111-4111-8111-111111111111"
TOKEN = "edge-test-token-with-sufficient-entropy"
HASH_A = "a" * 64
HASH_B = "b" * 64


def memory_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class EdgeSyncTests(unittest.TestCase):
    def setUp(self):
        self.local = memory_session()
        self.remote = memory_session()
        self.env = patch.dict(os.environ, {
            "EDGE_MODE": "true",
            "EDGE_NODE_ID": NODE_ID,
            "EDGE_MODEL_SHA256": HASH_A,
            "EDGE_ADAPTER_SHA256": HASH_B,
            "EDGE_QUANTIZATION": "Q4_K_M",
            "EDGE_SYNC_ENABLED": "true",
            "EDGE_SYNC_TOKEN": TOKEN,
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.local.close()
        self.remote.close()

    def create_local_bundle(self):
        session = crud.create_session(
            self.local, schemas.SessionCreate(user_id=None, topic="offline")
        )
        utterance = crud.create_utterance(self.local, schemas.UtteranceCreate(
            session_id=session.id,
            raw_audio_path="/private/pi/raw.wav",
            audio_path="/private/pi/processed.wav",
            stt_text="学校を行きます。",
            stt_model="faster-whisper-small",
        ))
        result = crud.create_judgment(self.local, utterance.id, {
            "decision": "needs_correction",
            "corrected_text": "学校に行きます。",
            "edits": [{"start": 2, "end": 3, "source": "を", "replacement": "に",
                       "error_type": "particle_misuse"}],
            "error_types": ["particle_misuse"],
            "reason_ko": "목적지 조사를 고칩니다.",
            "classification_review_required": False,
            "strategy": "d_only",
            "model_name": "judgment-v02d",
            "adapter_name": "judgment-qwen3-4b-failure-focus-v0.2-d-q4_k_m",
            "selection_reason": "primary_selected_by_holdout_v0.3",
            "contract_version": "judgment-v0.2",
            "latency_ms": 1000.0,
            "context": None,
            "learner_level": "N5",
        })
        return session, utterance, result

    def request(self):
        events = edge_sync.pending_events(self.local)
        return schemas.EdgeSyncRequest(node_id=NODE_ID, events=events), events

    def test_edge_crud_creates_ordered_content_addressed_outbox(self):
        self.create_local_bundle()
        _, events = self.request()
        self.assertEqual([row["event_type"] for row in events], [
            "session", "utterance", "judgment"
        ])
        self.assertNotIn("audio_path", events[1]["payload"])
        self.assertNotIn("raw_audio_path", events[1]["payload"])
        self.assertEqual(events[2]["payload"]["quantization"], "Q4_K_M")
        self.assertEqual(events[2]["payload"]["model_sha256"], HASH_A)

    def test_sync_is_idempotent_and_preserves_provenance(self):
        self.create_local_bundle()
        request, _ = self.request()
        response = main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
        self.assertEqual([item["status"] for item in response["results"]], [
            "accepted", "accepted", "accepted"
        ])
        self.assertEqual(self.remote.query(models.Session).count(), 1)
        self.assertEqual(self.remote.query(models.Utterance).count(), 1)
        self.assertEqual(self.remote.query(models.JudgmentResult).count(), 1)
        remote_utterance = self.remote.query(models.Utterance).one()
        self.assertIsNone(remote_utterance.raw_audio_path)
        receipt = self.remote.query(models.EdgeSyncReceipt).filter_by(
            event_type="judgment"
        ).one()
        provenance = json.loads(receipt.provenance)
        self.assertEqual(provenance["adapter_sha256"], HASH_B)

        again = main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
        self.assertEqual({item["status"] for item in again["results"]}, {"duplicate"})
        self.assertEqual(self.remote.query(models.JudgmentResult).count(), 1)

    def test_q5_candidate_provenance_is_preserved(self):
        with patch.dict(os.environ, {"EDGE_QUANTIZATION": "Q5_K_M"}, clear=False):
            self.create_local_bundle()
            request, events = self.request()
            self.assertEqual(events[2]["payload"]["quantization"], "Q5_K_M")
            response = main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
        self.assertEqual(response["results"][2]["status"], "accepted")
        receipt = self.remote.query(models.EdgeSyncReceipt).filter_by(
            event_type="judgment"
        ).one()
        self.assertEqual(json.loads(receipt.provenance)["quantization"], "Q5_K_M")

    def test_invalid_edge_quantization_fails_closed(self):
        with patch.dict(os.environ, {"EDGE_QUANTIZATION": "Q6_K"}, clear=False):
            with self.assertRaisesRegex(edge_sync.EdgeConfigurationError, "Q4_K_M"):
                self.create_local_bundle()

    def test_same_event_with_different_payload_is_conflict(self):
        self.create_local_bundle()
        request, events = self.request()
        main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
        changed = dict(events[0])
        changed["payload"] = {**changed["payload"], "topic": "changed"}
        changed["payload_sha256"] = edge_sync.payload_sha256(changed["payload"])
        with self.assertRaises(main.HTTPException) as raised:
            main.sync_edge_events(
                schemas.EdgeSyncRequest(node_id=NODE_ID, events=[changed]),
                f"Bearer {TOKEN}", self.remote,
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_auth_disabled_and_missing_dependency_fail_closed(self):
        self.create_local_bundle()
        request, events = self.request()
        with self.assertRaises(main.HTTPException) as raised:
            main.sync_edge_events(request, "Bearer wrong", self.remote)
        self.assertEqual(raised.exception.status_code, 401)

        with patch.dict(os.environ, {"EDGE_SYNC_ENABLED": "false"}, clear=False):
            with self.assertRaises(main.HTTPException) as raised:
                main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
        self.assertEqual(raised.exception.status_code, 503)

        utterance_only = schemas.EdgeSyncRequest(node_id=NODE_ID, events=[events[1]])
        rejected = main.sync_edge_events(
            utterance_only, f"Bearer {TOKEN}", self.remote
        )["results"][0]
        self.assertEqual(rejected["status"], "rejected")
        self.assertIn("dependency", rejected["error"])

    def test_apply_results_retains_rejected_events(self):
        self.create_local_bundle()
        _, events = self.request()
        edge_sync.apply_sync_results(self.local, [
            {"event_id": events[0]["event_id"], "status": "accepted", "remote_id": 10},
            {"event_id": events[1]["event_id"], "status": "rejected", "error": "later"},
        ])
        first = self.local.get(models.EdgeOutboxEvent, events[0]["event_id"])
        second = self.local.get(models.EdgeOutboxEvent, events[1]["event_id"])
        self.assertEqual(first.status, "synced")
        self.assertEqual(first.remote_id, 10)
        self.assertEqual(second.status, "pending")
        self.assertEqual(second.attempts, 1)

    def test_openapi_exposes_private_sync_contract(self):
        document = main.app.openapi()
        self.assertIn("/edge/v1/sync", document["paths"])

    def test_database_initialization_is_profile_scoped(self):
        with patch.object(main.models.Base.metadata, "create_all") as create, patch.dict(
            os.environ, {"EDGE_MODE": "false", "EDGE_SYNC_ENABLED": "false"}, clear=False
        ):
            main.initialize_database()
        names = {table.name for table in create.call_args.kwargs["tables"]}
        self.assertNotIn("edge_outbox_events", names)
        self.assertNotIn("edge_sync_receipts", names)

        with patch.object(main.models.Base.metadata, "create_all") as create, patch.dict(
            os.environ, {"EDGE_MODE": "true", "EDGE_SYNC_ENABLED": "false"}, clear=False
        ):
            main.initialize_database()
        names = {table.name for table in create.call_args.kwargs["tables"]}
        self.assertIn("edge_outbox_events", names)
        self.assertNotIn("edge_sync_receipts", names)

        with patch.object(main.models.Base.metadata, "create_all") as create, patch.dict(
            os.environ, {"EDGE_MODE": "false", "EDGE_SYNC_ENABLED": "true"}, clear=False
        ):
            main.initialize_database()
        names = {table.name for table in create.call_args.kwargs["tables"]}
        self.assertNotIn("edge_outbox_events", names)
        self.assertIn("edge_sync_receipts", names)

    def test_twenty_offline_bundles_remain_exactly_once_after_three_sends(self):
        for index in range(20):
            session = crud.create_session(
                self.local, schemas.SessionCreate(topic=f"offline-{index}")
            )
            crud.create_utterance(self.local, schemas.UtteranceCreate(
                session_id=session.id, stt_text=f"これはテスト{index}です。"
            ))
        request, events = self.request()
        self.assertEqual(len(events), 40)
        first = main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
        self.assertEqual({row["status"] for row in first["results"]}, {"accepted"})
        for _ in range(2):
            repeated = main.sync_edge_events(request, f"Bearer {TOKEN}", self.remote)
            self.assertEqual({row["status"] for row in repeated["results"]}, {"duplicate"})
        self.assertEqual(self.remote.query(models.Session).count(), 20)
        self.assertEqual(self.remote.query(models.Utterance).count(), 20)
        self.assertEqual(self.remote.query(models.EdgeSyncReceipt).count(), 40)


if __name__ == "__main__":
    unittest.main()
