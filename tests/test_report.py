from pathlib import Path

from jurytrace.models import RunSummary, TraceDecision
from jurytrace.report import write_report


def test_report_escapes_untrusted_trace_id(tmp_path: Path) -> None:
    summary = RunSummary(
        run_id="run",
        dataset_hash="a" * 64,
        fixture_judges=True,
        judge_configurations=[],
        trace_count=1,
        agreement_count=0,
        review_count=1,
        false_acceptance_count=0,
        provider_prompt_tokens=0,
        provider_completion_tokens=0,
        unknown_token_results=0,
        known_cost_usd=0,
        unknown_cost_results=0,
        failed_call_count=0,
        decisions=[TraceDecision(trace_id="<script>alert(1)</script>", status="review_required")],
    )
    target = tmp_path / "report.html"
    write_report(summary, target)
    rendered = target.read_text(encoding="utf-8")
    assert "<script>alert" not in rendered
    assert "&lt;script&gt;" in rendered
