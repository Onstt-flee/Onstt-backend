"""API lifecycle ordering tests for the bounded judgment shadow worker."""

import asyncio
import unittest
from unittest.mock import patch

import main


class JudgmentShadowLifecycleTests(unittest.TestCase):
    def test_startup_opens_runtime_before_starting_shadow_worker(self):
        order = []
        with patch.object(main, "set_accepting", side_effect=lambda value: order.append(("runtime", value))), patch.object(
            main, "start_judgment_shadow_worker", side_effect=lambda: order.append(("shadow", True))
        ):
            main.judgment_runtime_startup()
        self.assertEqual(order, [("runtime", True), ("shadow", True)])

    def test_shutdown_drains_shadow_before_closing_runtime_capacity(self):
        order = []
        with patch.dict("os.environ", {"JUDGMENT_SHUTDOWN_GRACE_SECONDS": "1"}, clear=False), patch.object(
            main, "stop_judgment_shadow_worker", side_effect=lambda timeout: order.append(("shadow", timeout)) or True
        ), patch.object(
            main, "set_accepting", side_effect=lambda value: order.append(("runtime", value))
        ), patch.object(
            main, "wait_for_idle", side_effect=lambda timeout: order.append(("idle", timeout)) or True
        ):
            asyncio.run(main.judgment_runtime_shutdown())
        self.assertEqual(order[0], ("shadow", 1.0))
        self.assertEqual(order[1], ("runtime", False))
        self.assertEqual(order[2][0], "idle")
        self.assertGreaterEqual(order[2][1], 0.0)
        self.assertLessEqual(order[2][1], 1.0)


if __name__ == "__main__":
    unittest.main()
