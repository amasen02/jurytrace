# JuryTrace

JuryTrace shows where two agent-regression judges agree, disagree, or fail to
produce verifiable evidence. It reads typed JSONL trajectories, dispatches two
judges concurrently through a real LangGraph workflow, validates every cited
span against the original trace, and puts unresolved cases in a durable SQLite
review queue.

The default demo uses deterministic offline fixture judges. They test workflow
behavior only; their scores are **not evidence of LLM judge quality**.

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
jurytrace demo --output receipts/latest
pytest
```

Open `receipts/latest/report.html` after the demo. The same run writes a JSON
summary, JSONL decision receipts, and `reviews.sqlite3`.

To judge another dataset:

```bash
jurytrace run examples/sample.jsonl --output receipts/run-example \
  --deadline 10 --max-calls 200 --max-traces 100
```

Each JSONL row must contain `trace_id`, `input`, `output`, and a supplied
`golden_label` of `accept` or `reject`. Duplicate IDs, extra fields, malformed
JSON, over-budget runs, unverifiable evidence, and mismatched judge identities
fail closed or enter review.

## Optional local Ollama judges

JuryTrace can call two independently configured models on an explicit local
Ollama URL. It never falls back to a paid provider.

```bash
jurytrace run examples/sample.jsonl --provider ollama \
  --ollama-url http://127.0.0.1:11434 \
  --model-a llama3.2 --model-b qwen2.5 --output receipts/ollama
```

Ollama's `prompt_eval_count` and `eval_count` are stored when returned. Ollama
does not report a request cost, so cost remains unknown rather than estimated.

## Human resolution

Inspect the queue, then bind a resolution to its exact dataset hash and trace:

```bash
jurytrace queue --database receipts/latest/reviews.sqlite3
jurytrace resolve --database receipts/latest/reviews.sqlite3 \
  --run-id RUN_ID --dataset-hash HASH --trace-id judge-disagreement --decision reject \
  --resolver "reviewer@example" --note "Compared the output with the source trace."
```

Unknown, stale, already-resolved, blank, or invalid resolutions are rejected.
Run outputs are create-only: choose a fresh output directory rather than replacing
existing receipts. An explicitly supplied external review database can collect
immutable queue rows from multiple run IDs.

## What the measurements mean

Agreement means both configured judges returned the same typed verdict with
exact source spans. Disagreement includes differing verdicts and judge failures.
False acceptance means an agreed `accept` conflicts with the dataset's supplied
`reject` golden label. Golden labels are inputs, not objective truth.

The committed receipts come from the synthetic fixture dataset. They establish
repeatability of the orchestration and failure routing, not production readiness,
security certification, model quality, or representativeness.

The raw reference artifacts are in [`receipts/v0.1-reference`](receipts/v0.1-reference).

## Container

```bash
docker build -t jurytrace .
docker run --rm -v "$PWD/receipts/container:/output" jurytrace
```

The local verification machine did not have a Docker CLI, so the Dockerfile is
provided but its image build is not part of the recorded evidence.

See [architecture](docs/architecture.md), [demo guide](docs/demo.md),
[interview notes](docs/interview.md), and [security policy](SECURITY.md).

This repository was built with AI assistance and is intended for human review.
