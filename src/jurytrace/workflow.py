"""Bounded LangGraph jury workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from .models import JudgeFailure, JudgeResult, RunSummary, TraceDecision, Trajectory
from .providers import Judge, MalformedJudgeOutput
from .report import write_report
from .store import ReviewStore


@dataclass(frozen=True, slots=True)
class JuryConfig:
    deadline_seconds: float = 10.0
    max_calls: int = 200
    max_traces: int = 100

    def __post_init__(self) -> None:
        if not math.isfinite(self.deadline_seconds) or self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be finite and positive")
        if (
            isinstance(self.max_calls, bool)
            or isinstance(self.max_traces, bool)
            or not isinstance(self.max_calls, int)
            or not isinstance(self.max_traces, int)
            or self.max_calls <= 0
            or self.max_traces <= 0
        ):
            raise ValueError("max_calls and max_traces must be positive integers")


@dataclass(frozen=True, slots=True)
class JuryRun:
    summary: RunSummary
    summary_path: Path
    receipts_path: Path
    report_path: Path
    database_path: Path


class JuryState(TypedDict, total=False):
    run_id: str
    dataset_hash: str
    trajectories: list[Trajectory]
    results: list[JudgeResult]
    failures: list[JudgeFailure]
    decisions: list[TraceDecision]
    summary: RunSummary


def load_jsonl(path: Path, max_traces: int) -> tuple[list[Trajectory], str]:
    raw = path.read_bytes()
    dataset_hash = hashlib.sha256(raw).hexdigest()
    traces: list[Trajectory] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        if not raw_line.strip():
            continue
        if len(traces) >= max_traces:
            raise ValueError(f"dataset exceeds max_traces={max_traces}")
        try:
            item = Trajectory.model_validate_json(raw_line)
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if item.trace_id in seen:
            raise ValueError(f"duplicate trace_id at line {line_number}: {item.trace_id}")
        seen.add(item.trace_id)
        traces.append(item)
    if not traces:
        raise ValueError("dataset contains no trajectories")
    return traces, dataset_hash


def validate_evidence(trace: Trajectory, result: JudgeResult) -> None:
    if result.trace_id != trace.trace_id:
        raise ValueError("judge result trace_id does not match dispatched trace")
    for span in result.evidence:
        source = getattr(trace, span.source)
        if span.end > len(source) or source[span.start : span.end] != span.quote:
            raise ValueError(
                f"invalid evidence span {span.source}[{span.start}:{span.end}] for {trace.trace_id}"
            )


async def _judge_one(judge: Judge, trace: Trajectory, deadline: float) -> JudgeResult | JudgeFailure:
    try:
        async with asyncio.timeout(deadline):
            raw = await judge.evaluate(trace)
        result = JudgeResult.model_validate(raw)
        if result.judge_id != judge.judge_id:
            raise ValueError("judge result judge_id does not match configured judge")
        validate_evidence(trace, result)
        return result
    except TimeoutError:
        return JudgeFailure(
            trace_id=trace.trace_id,
            judge_id=judge.judge_id,
            kind="timeout",
            message=f"judge exceeded {deadline:g}s deadline",
        )
    except ValidationError as exc:
        return JudgeFailure(
            trace_id=trace.trace_id,
            judge_id=judge.judge_id,
            kind="malformed_output",
            message=str(exc)[:1000],
        )
    except MalformedJudgeOutput as exc:
        return JudgeFailure(
            trace_id=trace.trace_id,
            judge_id=judge.judge_id,
            kind="malformed_output",
            message=str(exc)[:1000],
        )
    except ValueError as exc:
        return JudgeFailure(
            trace_id=trace.trace_id,
            judge_id=judge.judge_id,
            kind="invalid_evidence",
            message=str(exc)[:1000],
        )
    except Exception as exc:  # noqa: BLE001 - provider boundary becomes an inspectable failure
        return JudgeFailure(
            trace_id=trace.trace_id,
            judge_id=judge.judge_id,
            kind="provider_error",
            message=f"{type(exc).__name__}: {str(exc)[:900]}",
        )


def validate_judges(judges: list[Judge]) -> None:
    if len(judges) != 2:
        raise ValueError("jurytrace v0.1 requires exactly two judges")
    identities = {judge.configuration_key for judge in judges}
    if len(identities) != 2 or len({judge.judge_id for judge in judges}) != 2:
        raise ValueError("judges must have distinct configurations and judge IDs")


def build_graph(
    judges: list[Judge], config: JuryConfig, store: ReviewStore
) -> Any:
    validate_judges(judges)

    def hard_gates(state: JuryState) -> dict[str, object]:
        call_count = len(state["trajectories"]) * len(judges)
        if call_count > config.max_calls:
            raise ValueError(f"planned calls {call_count} exceed max_calls={config.max_calls}")
        return {}

    async def dispatch(state: JuryState) -> dict[str, object]:
        calls = [
            _judge_one(judge, trace, config.deadline_seconds)
            for trace in state["trajectories"]
            for judge in judges
        ]
        returned = await asyncio.gather(*calls)
        return {
            "results": [item for item in returned if isinstance(item, JudgeResult)],
            "failures": [item for item in returned if isinstance(item, JudgeFailure)],
        }

    def decide(state: JuryState) -> dict[str, object]:
        decisions: list[TraceDecision] = []
        for trace in state["trajectories"]:
            results = [item for item in state["results"] if item.trace_id == trace.trace_id]
            failures = [item for item in state["failures"] if item.trace_id == trace.trace_id]
            verdicts = {item.verdict for item in results}
            agreed = len(results) == len(judges) and len(verdicts) == 1 and not failures
            decisions.append(
                TraceDecision(
                    trace_id=trace.trace_id,
                    status="agreed" if agreed else "review_required",
                    decision=results[0].verdict if agreed else None,
                    judge_results=results,
                    failures=failures,
                )
            )
        prompt_known = [item.prompt_tokens for item in state["results"] if item.prompt_tokens is not None]
        completion_known = [
            item.completion_tokens for item in state["results"] if item.completion_tokens is not None
        ]
        costs = [item.cost_usd for item in state["results"] if item.cost_usd is not None]
        labels = {trace.trace_id: trace.golden_label for trace in state["trajectories"]}
        false_accepts = sum(
            decision.status == "agreed"
            and decision.decision == "accept"
            and labels[decision.trace_id] == "reject"
            for decision in decisions
        )
        summary = RunSummary(
            run_id=state["run_id"],
            dataset_hash=state["dataset_hash"],
            fixture_judges=all(judge.is_fixture for judge in judges),
            judge_configurations=[judge.describe() for judge in judges],
            trace_count=len(decisions),
            agreement_count=sum(item.status == "agreed" for item in decisions),
            review_count=sum(item.status == "review_required" for item in decisions),
            false_acceptance_count=false_accepts,
            provider_prompt_tokens=sum(prompt_known),
            provider_completion_tokens=sum(completion_known),
            unknown_token_results=sum(
                item.prompt_tokens is None or item.completion_tokens is None for item in state["results"]
            ) + len(state["failures"]),
            known_cost_usd=sum(costs),
            unknown_cost_results=sum(item.cost_usd is None for item in state["results"])
            + len(state["failures"]),
            failed_call_count=len(state["failures"]),
            decisions=decisions,
        )
        return {"decisions": decisions, "summary": summary}

    def route(state: JuryState) -> str:
        return "persist_reviews" if any(d.status == "review_required" for d in state["decisions"]) else "persist_clean"

    async def persist_reviews(state: JuryState) -> dict[str, object]:
        for decision in state["decisions"]:
            if decision.status == "review_required":
                store.enqueue(state["dataset_hash"], state["run_id"], decision)
        return {}

    def persist_clean(_state: JuryState) -> dict[str, object]:
        return {}

    graph = StateGraph(JuryState)
    graph.add_node("hard_gates", hard_gates)
    graph.add_node("dispatch_judges", dispatch)
    graph.add_node("score_and_compare", decide)
    graph.add_node("persist_reviews", persist_reviews)
    graph.add_node("persist_clean", persist_clean)
    graph.set_entry_point("hard_gates")
    graph.add_edge("hard_gates", "dispatch_judges")
    graph.add_edge("dispatch_judges", "score_and_compare")
    graph.add_conditional_edges(
        "score_and_compare", route, {"persist_reviews": "persist_reviews", "persist_clean": "persist_clean"}
    )
    graph.add_edge("persist_reviews", END)
    graph.add_edge("persist_clean", END)
    return graph.compile()


async def run_dataset(
    dataset_path: Path,
    judges: list[Judge],
    output_dir: Path,
    database_path: Path | None = None,
    config: JuryConfig | None = None,
) -> JuryRun:
    config = config or JuryConfig()
    trajectories, dataset_hash = load_jsonl(dataset_path, config.max_traces)
    validate_judges(judges)
    planned_calls = len(trajectories) * len(judges)
    if planned_calls > config.max_calls:
        raise ValueError(f"planned calls {planned_calls} exceed max_calls={config.max_calls}")
    external_database = database_path is not None
    database_path = database_path or output_dir / "reviews.sqlite3"
    summary_path = output_dir / "summary.json"
    receipts_path = output_dir / "judge-receipts.jsonl"
    report_path = output_dir / "report.html"
    output_targets = [summary_path, receipts_path, report_path]
    targets = [*output_targets, database_path]
    source = dataset_path.resolve()
    resolved_targets = [target.resolve() for target in targets]
    if len(set(resolved_targets)) != len(resolved_targets):
        raise ValueError("output artifacts and database must use distinct paths")
    if source in resolved_targets:
        raise ValueError("output artifacts and database must not overwrite the input dataset")
    collision_targets = output_targets if external_database else targets
    existing = [str(target) for target in collision_targets if target.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite existing run artifacts: {', '.join(existing)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"jt-{dataset_hash[:12]}-{uuid.uuid4().hex[:8]}"
    with ReviewStore(database_path) as store:
        graph = build_graph(judges, config, store)
        final: JuryState = await graph.ainvoke(
            {"run_id": run_id, "dataset_hash": dataset_hash, "trajectories": trajectories}
        )
    summary = final["summary"]
    with summary_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(summary.model_dump_json(indent=2))
    with receipts_path.open("x", encoding="utf-8", newline="\n") as handle:
        for decision in summary.decisions:
            record = {
                "run_id": run_id,
                "dataset_hash": dataset_hash,
                **decision.model_dump(mode="json"),
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    write_report(summary, report_path)
    return JuryRun(summary, summary_path, receipts_path, report_path, database_path)
