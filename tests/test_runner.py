import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import runner


class RunnerTests(unittest.TestCase):
    def test_all_starter_lessons_load_and_preview_without_credentials(self):
        self.assertEqual(len(runner.list_lessons()), 9)
        with patch.dict(os.environ, {}, clear=True), patch("runner.urlopen") as network:
            for name in runner.list_lessons():
                with self.subTest(lesson=name), contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(runner.main([name, "--dry-run"]), 0)
                    requests = [json.loads(line) for line in output.getvalue().splitlines()]
                    self.assertTrue(requests)
                    for request in requests:
                        self.assertNotIn("{{input}}", request["request"]["messages"][0]["content"])
                self.assertEqual(
                    {path.name for path in (runner.LESSONS / name).iterdir()},
                    {"prompt.txt", "test_cases.json"},
                )
            network.assert_not_called()

    def test_new_lesson_is_discovered_without_runner_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            lesson = Path(directory) / "custom"
            lesson.mkdir()
            (lesson / "prompt.txt").write_text("Say {{input}}", encoding="utf-8")
            (lesson / "system.txt").write_text("Be concise.", encoding="utf-8")
            (lesson / "test_cases.json").write_text(
                '[{"name":"literal","input":"{{input}} $name"}]', encoding="utf-8"
            )
            with patch.object(runner, "LESSONS", Path(directory)):
                self.assertEqual(runner.list_lessons(), ["custom"])
                prompt, system, cases = runner.load_lesson("custom")
                payload = runner.make_request(prompt, system, cases[0], "test-model", 100)
                self.assertEqual(payload["messages"][0]["content"], "Say {{input}} $name")
                self.assertEqual(payload["system"], "Be concise.")

    def test_checks(self):
        self.assertTrue(runner.check_output({"expected": "yes"}, " yes\n"))
        self.assertFalse(runner.check_output({"expected": "yes"}, "YES"))
        self.assertTrue(runner.check_output({"contains": ["a", "b"]}, "abc"))
        self.assertFalse(runner.check_output({"contains": ["a", "z"]}, "abc"))
        self.assertFalse(runner.check_output({"expected": "abc", "contains": ["z"]}, "abc"))
        self.assertIsNone(runner.check_output({}, "anything"))

    def test_invalid_cases_and_unknown_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            lesson = Path(directory) / "custom"
            lesson.mkdir()
            (lesson / "prompt.txt").write_text("{{input}}", encoding="utf-8")
            with patch.object(runner, "LESSONS", Path(directory)):
                for cases in ([], {}, [None], [{"name": "x", "input": 1}],
                              [{"name": "x", "input": "", "contains": []}],
                              [{"name": "x", "input": "", "expected": 1}],
                              [{"name": "x", "input": ""}] * 2):
                    with self.subTest(cases=cases):
                        (lesson / "test_cases.json").write_text(json.dumps(cases), encoding="utf-8")
                        with self.assertRaises(ValueError):
                            runner.load_lesson("custom")
                with self.assertRaises(ValueError):
                    runner.load_lesson("../custom")
                (lesson / "prompt.txt").write_text("No placeholder", encoding="utf-8")
                with self.assertRaises(ValueError):
                    runner.load_lesson("custom")

    def test_live_run_exit_codes(self):
        lesson = "02-being-clear-and-direct"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only"}):
            with patch("runner.call_claude", side_effect=["positive", "negative"]) as api:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main([lesson, "--model", "test-model"]), 0)
                self.assertEqual(api.call_count, 2)
            with patch("runner.call_claude", return_value="wrong"):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main([lesson, "--model", "test-model"]), 1)
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main([lesson]), 2)

    def test_api_request_and_response(self):
        response = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}],
        }
        with patch("runner.urlopen", return_value=io.StringIO(json.dumps(response))) as network:
            self.assertEqual(runner.call_claude({"model": "test-model"}, "test-only", 5), "hello world")
            request = network.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
            self.assertEqual(json.loads(request.data), {"model": "test-model"})
            self.assertEqual(request.get_header("X-api-key"), "test-only")
            self.assertEqual(network.call_args.kwargs["timeout"], 5)

    def test_api_errors_and_truncation(self):
        for error in (HTTPError("url", 401, "unauthorized", {}, None),
                      URLError("offline"), TimeoutError()):
            with self.subTest(error=error), patch("runner.urlopen", side_effect=error):
                with self.assertRaises(ValueError):
                    runner.call_claude({}, "test-only", 5)
        for response in ({"stop_reason": "max_tokens"}, {"stop_reason": "end_turn", "content": []}):
            with patch("runner.urlopen", return_value=io.StringIO(json.dumps(response))):
                with self.assertRaises(ValueError):
                    runner.call_claude({}, "test-only", 5)


if __name__ == "__main__":
    unittest.main()
