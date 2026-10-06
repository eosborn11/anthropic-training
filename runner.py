"""Shared runner for data-only prompt engineering lessons."""

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LESSONS = Path(__file__).resolve().parent / "lessons"


def list_lessons():
    return sorted(
        path.name
        for path in LESSONS.iterdir()
        if path.is_dir() and (path / "prompt.txt").is_file()
    )


def load_lesson(name):
    if name not in list_lessons():
        raise ValueError(f"Unknown lesson: {name}. Use --list to see available lessons.")
    folder = LESSONS / name
    prompt = (folder / "prompt.txt").read_text(encoding="utf-8")
    if "{{input}}" not in prompt:
        raise ValueError("prompt.txt must contain the {{input}} placeholder.")
    cases = json.loads((folder / "test_cases.json").read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("test_cases.json must be a nonempty list.")
    names = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each test case must be an object.")
        name = case.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Test case names must be nonempty, unique strings.")
        names.add(name)
        if not isinstance(case.get("input"), str):
            raise ValueError(f"{name}: input must be a string.")
        if "expected" in case and not isinstance(case["expected"], str):
            raise ValueError(f"{name}: expected must be a string.")
        if "contains" in case and (
            not isinstance(case["contains"], list)
            or not case["contains"]
            or any(not isinstance(text, str) or not text for text in case["contains"])
        ):
            raise ValueError(f"{name}: contains must be a nonempty list of strings.")
    system_file = folder / "system.txt"
    system = system_file.read_text(encoding="utf-8") if system_file.exists() else None
    return prompt, system, cases


def make_request(prompt, system, case, model, max_tokens):
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt.replace("{{input}}", case["input"])}
        ],
    }
    if system is not None:
        payload["system"] = system
    return payload


def call_claude(payload, api_key, timeout):
    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        raise ValueError(f"Claude API returned HTTP {error.code}.") from None
    except (URLError, TimeoutError):
        raise ValueError("Could not reach the Claude API.") from None
    if result.get("stop_reason") != "end_turn":
        raise ValueError("Claude did not complete its response; check max_tokens.")
    text = "".join(
        block["text"] for block in result.get("content", []) if block.get("type") == "text"
    )
    if not text:
        raise ValueError("Claude returned no text.")
    return text


def check_output(case, output):
    checks = []
    if "expected" in case:
        checks.append(output.strip() == case["expected"].strip())
    if "contains" in case:
        checks.append(all(text in output for text in case["contains"]))
    return all(checks) if checks else None


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson", nargs="?", help="Lesson folder name")
    parser.add_argument("--list", action="store_true", help="List available lessons")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL"))
    parser.add_argument("--max-tokens", type=positive_int, default=1024)
    parser.add_argument("--timeout", type=positive_int, default=60, help="API timeout in seconds")
    args = parser.parse_args(argv)
    try:
        if args.list:
            print("\n".join(list_lessons()))
            return 0
        if not args.lesson:
            parser.error("specify a lesson or --list")
        prompt, system, cases = load_lesson(args.lesson)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not args.dry_run and (not api_key or not args.model):
            raise ValueError(
                "Live runs require ANTHROPIC_API_KEY and --model (or ANTHROPIC_MODEL)."
            )
        failed = False
        for case in cases:
            payload = make_request(prompt, system, case, args.model, args.max_tokens)
            if args.dry_run:
                print(json.dumps({"case": case["name"], "request": payload}, ensure_ascii=False))
                continue
            output = call_claude(payload, api_key, args.timeout)
            passed = check_output(case, output)
            failed |= passed is False
            print(json.dumps({
                "case": case["name"],
                "output": output,
                "status": "ungraded" if passed is None else "passed" if passed else "failed",
            }, ensure_ascii=False))
        return 1 if failed else 0
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
