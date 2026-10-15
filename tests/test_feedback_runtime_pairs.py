import json
from pathlib import Path
import tempfile
import unittest

from evaluation.judgment.runner import PROMPT_VERSION_V2, parse_model_output
from scripts.prepare_feedback_runtime_pairs import build_summary, canonical_json, sha_json, sha_path


HASHES = {
    "gpu_model_sha256": "a" * 64,
    "gpu_adapter_sha256": "b" * 64,
    "pi_model_sha256": "c" * 64,
    "pi_adapter_sha256": "d" * 64,
}


def make_row(index: int, text: str | None = None) -> dict:
    text = text or f"例文{index}です。"
    model_input = {"text": text, "context": None, "learner_level": "N5"}
    raw = canonical_json({
        "decision": "acceptable", "corrected_text": text,
        "error_types": [], "reason_ko": "문법적으로 허용됩니다.",
    })
    parsed, error = parse_model_output(raw, text, PROMPT_VERSION_V2)
    assert parsed is not None, error
    return {
        "schema_version": "0.1", "run_id": "test", "id": f"T-{index:03d}",
        "input": model_input, "input_sha256": sha_json(model_input), "request": {},
        "response": {
            "transport_success": True, "contract_valid": True,
            "raw_text": raw, "parsed_judgment": parsed,
        },
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def prepare(root: Path, gpu_rows: list[dict], pi_rows: list[dict]) -> dict:
    gpu, pi = root / "gpu.jsonl", root / "pi.jsonl"
    manifest, benchmark = root / "gpu.manifest.json", root / "pi.summary.json"
    write_jsonl(gpu, gpu_rows); write_jsonl(pi, pi_rows)
    manifest.write_text(json.dumps({"output_sha256": sha_path(gpu)}), encoding="utf-8")
    benchmark.write_text(json.dumps({
        "schema_version": "pi5-benchmark-summary-v0.2", "passed": True,
        "sample_count": len(pi_rows), "contains_request_content": False,
        "artifacts": {
            "raw_run_sha256": sha_path(pi), "quantization": "Q5_K_M",
            "model_sha256": HASHES["pi_model_sha256"],
            "adapter_sha256": HASHES["pi_adapter_sha256"],
        },
    }), encoding="utf-8")
    return {"gpu_path": gpu, "pi_path": pi, "gpu_manifest_path": manifest,
            "pi_benchmark_path": benchmark, **HASHES, "pi_quantization": "Q5_K_M"}


class FeedbackRuntimePairTests(unittest.TestCase):
    def test_tracked_gpu_half_is_content_free_and_still_blocked(self):
        path = Path(__file__).resolve().parents[1] / "evaluation/feedback/runtime_pairs_v0.1.gpu.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(summary["records"], 50)
        self.assertEqual(summary["transport_success_count"], 50)
        self.assertEqual(summary["contract_valid_count"], 50)
        self.assertEqual(summary["pi_pair_count"], 0)
        self.assertFalse(summary["contains_request_content"])
        self.assertFalse(summary["source_gap_analysis_ready"])
        self.assertFalse(summary["feedback_holdout_ready"])
        self.assertIn("missing_actual_pi_run", summary["blocking_reasons"])
        encoded = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn("JG-", encoded)
        self.assertNotIn("text", encoded)

    def test_fifty_attested_pairs_produce_content_free_summary_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); rows = [make_row(i) for i in range(50)]
            summary = build_summary(**prepare(root, rows, rows))
            self.assertTrue(summary["source_gap_analysis_ready"])
            self.assertFalse(summary["feedback_holdout_ready"])
            self.assertEqual(summary["pair_count"], 50)
            self.assertEqual(summary["agreement"]["decision_rate"], 1.0)
            self.assertEqual(summary["blocking_reasons"], ["missing_independent_feedback_labels"])
            encoded = json.dumps(summary, ensure_ascii=False)
            self.assertNotIn("例文", encoded)
            self.assertNotIn("T-", encoded)

    def test_different_input_sets_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); gpu = [make_row(i) for i in range(50)]
            pi = [make_row(i) for i in range(50)]; pi[0] = make_row(0, "別の文です。")
            with self.assertRaisesRegex(ValueError, "input sets must match"):
                build_summary(**prepare(root, gpu, pi))

    def test_unattested_pi_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); rows = [make_row(i) for i in range(50)]
            args = prepare(root, rows, rows)
            benchmark = json.loads(args["pi_benchmark_path"].read_text())
            benchmark["artifacts"]["raw_run_sha256"] = "0" * 64
            args["pi_benchmark_path"].write_text(json.dumps(benchmark), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not attest"):
                build_summary(**args)


if __name__ == "__main__":
    unittest.main()
