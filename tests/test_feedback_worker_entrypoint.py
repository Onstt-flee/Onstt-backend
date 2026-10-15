from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FeedbackWorkerEntrypointTests(unittest.TestCase):
    def test_direct_script_execution_resolves_project_modules(self):
        result = subprocess.run(
            [str(ROOT / "venv/bin/python"), str(ROOT / "scripts/run_feedback_worker.py")],
            cwd="/tmp", capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FEEDBACK_AUDIT_ENABLED is false", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
