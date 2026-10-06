# anthropic-training

A workbook for Anthropic training, not a final application. Shared execution
code lives in `runner.py`; each folder in `lessons/` contains only prompts and
test cases. No Jumpstart source was present in this repository, so this runner
provides a small starting point rather than adapting an existing app.

## Lesson order

The folders follow the nine chapters of Anthropic's public
[Prompt Engineering Interactive Tutorial](https://github.com/anthropics/prompt-eng-interactive-tutorial):

1. `01-basic-prompt-structure`
2. `02-being-clear-and-direct`
3. `03-assigning-roles`
4. `04-separating-data-from-instructions`
5. `05-formatting-output`
6. `06-precognition`
7. `07-using-examples`
8. `08-avoiding-hallucinations`
9. `09-building-complex-prompts`

These are original starter exercises, not copied course materials or an official
certification syllabus. The public tutorial also has advanced appendices; add
folders for those or your own training lessons as needed.

## Run a lesson

Python 3.9+ is sufficient; no packages need installing. From the repository root:

```sh
python runner.py --list
python runner.py 02-being-clear-and-direct --dry-run
```

Dry runs print each rendered API request without requiring credentials or making
network calls. For a live run, set `ANTHROPIC_API_KEY` in your environment and
choose a model available to your account:

```sh
python runner.py 02-being-clear-and-direct --model YOUR_MODEL_ID
```

Alternatively, set `ANTHROPIC_MODEL`. The runner does not load `.env` files.
Never commit credentials. Live runs send lesson prompts and inputs to Anthropic
and incur normal API charges. Use `--max-tokens` (default 1024) and `--timeout`
(seconds, default 60) to control response limits.

Results are printed as one JSON object per case with output and a
`passed`, `failed`, or `ungraded` status. Exit codes: **0** for no failed checks
(including dry runs and ungraded cases), **1** for failed checks, **2** for
configuration, file, or API errors. API errors stop the run; earlier results
remain printed. Truncated responses are errors, not passing test results.

## Add or edit a lesson

Create `lessons/<lesson-name>/` with:

- `prompt.txt`: a UTF-8 prompt containing `{{input}}`, replaced literally with
  each test case's input (no code or template expressions are evaluated).
- `test_cases.json`: a nonempty JSON list of cases in execution order.
- Optional `system.txt`: a shared system prompt for this lesson.

For example, a case can be:

```json
{"name": "positive-review", "input": "Great service!", "expected": "positive"}
```

Case names must be unique nonempty strings and inputs must be strings.
`expected` checks exact text after trimming leading/trailing whitespace.
Alternatively, `contains` is a nonempty list of case-sensitive substrings that
must all appear. If both are present, both checks must pass. Without either,
the response is ungraded for manual review (useful for open-ended exercises).
These checks are simple practice aids, not comprehensive model evaluations;
model responses may vary between runs.

Keep lesson folders data-only: no duplicated runner code, dependencies, or app
scaffolding. The runner discovers new folders automatically, so adding lessons
does not require changing Python code. Run it from another directory by using
the absolute path to `runner.py`; lesson paths are relative to the runner.

## Runner tests

Offline tests use Python's standard library and make no real API calls:

```sh
python -m unittest discover -s tests -v
```
