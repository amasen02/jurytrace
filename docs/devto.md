# JuryTrace: make agent-judge failures inspectable

When an agent regression judge says “accept,” the interesting question is often not the score. It is whether another judge agrees, whether either judge showed its work, and what happens when they do not. JuryTrace is a small Python tool for that boundary: it runs two configured judges over typed JSONL trajectories, validates their evidence, and sends unresolved cases to a durable human queue.

The project is deliberately narrow. It is a workflow and evidence exercise, not a claim that two judges produce objective truth. The committed reference run uses deterministic offline fixture judges. Its five synthetic traces cover a clean agreement, a shared rejection, a disagreement, instruction-like text treated as data, and a fixture false acceptance. The receipt records four agreements, one review item, and one false acceptance against a supplied `reject` golden label. Those numbers demonstrate repeatable routing and reporting; they are not live model-quality evidence.

## What actually runs

The orchestration is a real asynchronous LangGraph workflow. `StateGraph` moves through `hard_gates`, `dispatch_judges`, `score_and_compare`, then either `persist_clean` or `persist_reviews`. The dispatch node creates one coroutine per trajectory and judge and awaits them concurrently with `asyncio.gather`. Each call has its own `asyncio.timeout` boundary. The graph also enforces exactly two judges, distinct judge IDs, distinct configurations, maximum traces, and maximum calls.

The provider boundary returns a typed proposed verdict. A valid result contains `accept` or `reject`, a score, a rationale, and one or more evidence spans. A span names `input` or `output`, character offsets, and a quote. JuryTrace slices the original trajectory and compares that slice with the quote. A wrong trace ID, mismatched judge identity, malformed response, timeout, provider error, or inexact quote cannot become an automatic decision. Equal, valid verdicts become an agreement; differing verdicts or failures become `review_required`.

That distinction matters: exact spans are a machine-checkable property, while the semantic judgment remains a proposal from a provider. A judge can cite the right text and still misunderstand it. The report preserves both facts so a reviewer can inspect the source, verdict, rationale, and failure kind together.

## Golden labels without leaking the answer

Every input row includes a supplied `golden_label`, because the tool can report a fixture false-acceptance count. The Ollama adapter intentionally sends only `trace_id`, `input`, and `output` to the provider. The golden label is withheld until after judging. This prevents the evaluation answer from becoming an instruction in the judge prompt and keeps the metric honest about what it measures.

The label is still not ground truth. It is an input supplied by whoever assembled the dataset. In the reference fixture, both deterministic judges accept `fixture-false-acceptance` while its supplied label is `reject`; JuryTrace reports that mismatch as one false acceptance. Treat that as a useful audit signal, then inspect how the label was made. Do not turn it into a benchmark claim.

The Ollama system message also says trajectory fields are untrusted data, including text that resembles instructions. That reduces accidental instruction following, but the repository documents it as an incomplete prompt-injection defense. The evidence gate is independent of the provider’s prose.

## Human review is part of the design

The disagreement path writes a durable queue row to SQLite, keyed by `(run_id, dataset_hash, trace_id)`. A resolution must supply that exact identity, a decision, a resolver, and a non-empty note. The store updates the resolution and queue status in one transaction. Unknown, stale, blank, or already-resolved resolutions fail instead of silently changing history.

Try the offline path from the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
jurytrace demo --output receipts/latest
pytest
```

Open `receipts/latest/report.html`, inspect `summary.json` and `judge-receipts.jsonl`, then print the queue:

```bash
jurytrace queue --database receipts/latest/reviews.sqlite3
```

Resolve the disagreement with the run ID and dataset hash printed in `summary.json`:

```bash
jurytrace resolve --database receipts/latest/reviews.sqlite3 \
  --run-id RUN_ID --dataset-hash HASH --trace-id judge-disagreement \
  --decision reject --resolver demo-reviewer \
  --note "Compared the output with the source trace."
```

For a local provider exercise, configure two models on loopback Ollama:

```bash
jurytrace run examples/sample.jsonl --provider ollama \
  --ollama-url http://127.0.0.1:11434 --model-a llama3.2 --model-b qwen2.5 \
  --output receipts/ollama
```

Those configurations add model diversity, but they do not establish statistical independence. Shared training data, prompts, provider behavior, and correlated errors remain possible. Ollama token counts are preserved when reported; request cost stays unknown because Ollama does not provide it. In the fixture receipt all ten judge calls have unknown token counts and costs, with known cost `0.0`; that is an explicit unknown, not an estimate.

The recorded verification used Python 3.12.9: 20 tests passed, Ruff passed, and `pip wheel --no-deps --wheel-dir dist .` produced `jurytrace-0.1.0`. That wheel was installed in a separate virtual environment and its demo completed from `C:\Windows\Temp`, outside the source checkout. Python 3.11 and Docker were not available on that machine; CI is configured for Python 3.11, 3.12, and 3.13.

JuryTrace was built with AI assistance and remains intended for human review. The useful exercise is to run the fixture, read the disagreement, and make the human resolution yourself. The artifacts show what the system can verify today—and leave model quality, adoption, production readiness, and costs open until a real dataset and provider run supply that evidence.

Repository: [jurytrace](https://github.com/amasen02/jurytrace).
