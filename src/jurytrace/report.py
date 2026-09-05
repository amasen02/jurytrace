"""Safe static HTML export."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .models import RunSummary


def write_report(summary: RunSummary, path: Path) -> None:
    rows = []
    for decision in summary.decisions:
        verdicts = ", ".join(
            f"{html.escape(item.judge_id)}: {item.verdict}" for item in decision.judge_results
        ) or "none"
        failures = "; ".join(html.escape(item.kind) for item in decision.failures) or "none"
        rows.append(
            f"<tr><td>{html.escape(decision.trace_id)}</td><td>{decision.status}</td>"
            f"<td>{verdicts}</td><td>{failures}</td></tr>"
        )
    payload = html.escape(json.dumps(summary.model_dump(mode="json"), indent=2))
    fixture_notice = (
        "Offline fixture judges: these results test orchestration, not model quality."
        if summary.fixture_judges
        else "Local Ollama judges were configured; results are local-run evidence only."
    )
    document = f"""<!doctype html><html><head><meta charset="utf-8">
<title>JuryTrace report</title><style>
body{{font-family:system-ui;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#17202a}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd1d1;padding:.5rem;text-align:left}}
.notice{{background:#fff3cd;padding:1rem;border-left:4px solid #d39e00}}pre{{white-space:pre-wrap}}
</style></head><body><h1>JuryTrace review report</h1>
<p class="notice">{html.escape(fixture_notice)}</p>
<p>Run <code>{html.escape(summary.run_id)}</code> · dataset <code>{summary.dataset_hash}</code></p>
<p>{summary.agreement_count} agreed · {summary.review_count} need review · 
{summary.false_acceptance_count} false acceptances against supplied golden labels</p>
<table><thead><tr><th>Trace</th><th>Status</th><th>Judges</th><th>Failures</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table><h2>Machine-readable summary</h2><pre>{payload}</pre></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(document)
