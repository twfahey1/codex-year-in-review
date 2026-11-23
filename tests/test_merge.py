"""Regression coverage for overlapping, partially divergent device logs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "codex-year-in-review/scripts/report.py"
NAME = "rollout-example-12345678-1234-1234-1234-123456789abc.jsonl"


def activity(day, turn_id, tokens, cumulative_input):
    stamp = f"2025-01-{day:02}T12:00:00Z"
    return [
        dict(timestamp=stamp, type="event_msg", payload=dict(type="task_started", turn_id=turn_id)),
        dict(timestamp=stamp, type="response_item", payload=dict(type="function_call", call_id=turn_id)),
        dict(timestamp=stamp, type="event_msg", payload=dict(type="token_count", info={
            "total_token_usage": {"input_tokens": cumulative_input},
            "last_token_usage": {"input_tokens": tokens},
        })),
    ]


def write_rollout(folder, events):
    folder.mkdir(parents=True)
    (folder / NAME).write_text("".join(json.dumps(event) + "\n" for event in events))


class MergeTests(unittest.TestCase):
    def test_merge_shared_history_and_both_devices_unique_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local"
            old = root / "old"
            shared = activity(1, "shared", 100, 100)
            write_rollout(local / "sessions", shared + activity(2, "local", 20, 120))
            write_rollout(old / "archived_sessions", shared + activity(3, "old", 20, 120))
            write_rollout(root / "copied-rollouts", shared)
            output = root / "report.html"

            subprocess.run([
                sys.executable, str(SCRIPT), "--codex-home", str(local),
                "--include-logs", str(old),
                "--include-logs", str(root / "copied-rollouts"),
                "--include-logs", str(local / "sessions"),
                "--end", "2025-12-31", "--output", str(output),
            ], check=True, capture_output=True)
            embedded = output.read_text().split("const data=", 1)[1].split(";\n", 1)[0]
            report = json.loads(embedded)

        self.assertEqual(report["chats"], 1)
        self.assertEqual(report["files"], 3)
        self.assertEqual(report["session_logs"], 1)
        self.assertEqual(
            {day: (value["turns"], value["tools"], value["input"]) for day, value in report["days"].items()},
            {"2025-01-01": (1, 1, 100), "2025-01-02": (1, 1, 20), "2025-01-03": (1, 1, 20)},
        )


if __name__ == "__main__":
    unittest.main()
