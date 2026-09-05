"""Strict transport and persistence schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Trajectory(StrictModel):
    trace_id: str = Field(min_length=1, max_length=160)
    input: str = Field(max_length=50_000)
    output: str = Field(max_length=100_000)
    golden_label: Literal["accept", "reject"]

    @field_validator("trace_id")
    @classmethod
    def clean_id(cls, value: str) -> str:
        if value.strip() != value or any(ord(char) < 32 for char in value):
            raise ValueError("trace_id must be trimmed printable text")
        return value


class EvidenceSpan(StrictModel):
    source: Literal["input", "output"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def ordered(self) -> EvidenceSpan:
        if self.end <= self.start:
            raise ValueError("evidence end must be greater than start")
        return self


class JudgeResult(StrictModel):
    trace_id: str
    judge_id: str
    verdict: Literal["accept", "reject"]
    score: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=4_000)
    evidence: list[EvidenceSpan] = Field(min_length=1, max_length=8)
    provider: str
    model: str
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)


class JudgeFailure(StrictModel):
    trace_id: str
    judge_id: str
    kind: Literal["timeout", "malformed_output", "provider_error", "invalid_evidence"]
    message: str


class TraceDecision(StrictModel):
    trace_id: str
    status: Literal["agreed", "review_required"]
    decision: Literal["accept", "reject"] | None = None
    judge_results: list[JudgeResult] = Field(default_factory=list)
    failures: list[JudgeFailure] = Field(default_factory=list)


class HumanResolution(StrictModel):
    run_id: str = Field(min_length=1, max_length=200)
    trace_id: str
    dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["accept", "reject"]
    resolver: str = Field(min_length=1, max_length=200)
    note: str = Field(min_length=1, max_length=2_000)
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("resolver", "note")
    @classmethod
    def non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must contain non-whitespace text")
        return value.strip()


class JudgeConfiguration(StrictModel):
    judge_id: str
    provider: str
    model: str
    is_fixture: bool
    parameters: dict[str, str | float | list[str]]


class RunSummary(StrictModel):
    run_id: str
    dataset_hash: str
    fixture_judges: bool
    judge_configurations: list[JudgeConfiguration]
    trace_count: int
    agreement_count: int
    review_count: int
    false_acceptance_count: int
    provider_prompt_tokens: int
    provider_completion_tokens: int
    unknown_token_results: int
    known_cost_usd: float
    unknown_cost_results: int
    failed_call_count: int
    decisions: list[TraceDecision]
