# Interview notes

## Why a graph?

The workflow has an observable decision boundary: validation precedes dispatch,
both asynchronous handoffs finish or time out, results pass deterministic gates,
and only disagreement or failure reaches persistence. LangGraph makes those
transitions and the conditional review route inspectable without letting a judge
control orchestration.

## Why exact spans?

A fluent rationale can cite text that does not exist. Every judge must identify
`input` or `output`, offsets, and the exact quote. JuryTrace slices the original
trajectory and compares it byte-for-character after JSON decoding. This proves
attribution to the provided text, not semantic entailment.

## Why keep failures in the review queue?

Treating timeout or malformed output as reject would mix infrastructure health
with evaluation. Treating it as accept would fail open. Review preserves the
uncertainty and the raw classified failure.

## What does false acceptance mean?

It is an agreed acceptance where the provided golden label says reject. It is
useful for a fixed regression set, but depends entirely on label quality and
does not estimate population behavior.

## What would production work add?

Authenticated reviewer identities, migrations, database concurrency controls,
encrypted retention, provider rate limiting, retry policy, criterion-level
calibration, blinded judge prompts, and evaluation on a representative labeled
dataset. The local Ollama path also needs measured live receipts before making
claims about model behavior.

