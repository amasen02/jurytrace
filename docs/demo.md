# Demo guide

Run from the repository root after installing the development dependencies:

```bash
jurytrace demo --output receipts/latest
```

The five synthetic trajectories demonstrate a clean agreement, shared reject,
judge disagreement, instruction-like trace data, and a fixture false acceptance
against a supplied golden label. Inspect:

- `summary.json` for aggregate measurements and all typed decisions;
- `judge-receipts.jsonl` for one durable record per trace;
- `report.html` for the escaped static report;
- `reviews.sqlite3` with `jurytrace queue` for pending human work.

Then resolve the disagreement using the exact hash printed in `summary.json`:

```bash
jurytrace resolve --database receipts/latest/reviews.sqlite3 \
  --run-id RUN_ID --dataset-hash HASH --trace-id judge-disagreement --decision reject \
  --resolver demo-reviewer --note "The output explicitly hid a tool error."
```

Re-running against the same database preserves an existing resolved state. Use
a new output directory for a clean demonstration.

The demo is offline and deterministic. The optional Ollama command in the README
is a separate live-provider exercise and requires two locally available models.
