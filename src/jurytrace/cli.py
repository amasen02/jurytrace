"""Command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from importlib import resources
from pathlib import Path

from .models import HumanResolution
from .providers import FixtureJudge, OllamaJudge
from .store import ReviewStore
from .workflow import JuryConfig, run_dataset


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="jurytrace")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="judge a JSONL regression dataset")
    run.add_argument("dataset", type=Path)
    run.add_argument("--output", type=Path, default=Path("receipts/latest"))
    run.add_argument("--provider", choices=("fixture", "ollama"), default="fixture")
    run.add_argument("--deadline", type=float, default=10.0)
    run.add_argument("--max-calls", type=int, default=200)
    run.add_argument("--max-traces", type=int, default=100)
    run.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    run.add_argument("--model-a", default="llama3.2")
    run.add_argument("--model-b", default="qwen2.5")
    demo = commands.add_parser("demo", help="run the committed offline fixture demo")
    demo.add_argument("--output", type=Path, default=Path("receipts/latest"))
    resolve = commands.add_parser("resolve", help="validate and persist a human resolution")
    resolve.add_argument("--database", type=Path, required=True)
    resolve.add_argument("--run-id", required=True)
    resolve.add_argument("--dataset-hash", required=True)
    resolve.add_argument("--trace-id", required=True)
    resolve.add_argument("--decision", choices=("accept", "reject"), required=True)
    resolve.add_argument("--resolver", required=True)
    resolve.add_argument("--note", required=True)
    queue = commands.add_parser("queue", help="print the persisted review queue")
    queue.add_argument("--database", type=Path, required=True)
    return root


def fixture_judges() -> list[FixtureJudge]:
    return [
        FixtureJudge("fixture-strict", ("unsafe", "error", "fabricated")),
        FixtureJudge("fixture-focused", ("unsafe",)),
    ]


def _main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "resolve":
        resolution = HumanResolution(
            run_id=args.run_id,
            trace_id=args.trace_id,
            dataset_hash=args.dataset_hash,
            decision=args.decision,
            resolver=args.resolver,
            note=args.note,
        )
        with ReviewStore(args.database) as store:
            store.resolve(resolution)
        print(resolution.model_dump_json(indent=2))
        return 0
    if args.command == "queue":
        with ReviewStore(args.database) as store:
            print(json.dumps(store.queue(), indent=2))
        return 0
    if args.command == "demo":
        fixture = resources.files("jurytrace").joinpath("data/sample.jsonl")
        judges = fixture_judges()
        output = args.output
        config = JuryConfig()
    else:
        dataset, output = args.dataset, args.output
        config = JuryConfig(args.deadline, args.max_calls, args.max_traces)
        if args.provider == "fixture":
            judges = fixture_judges()
        else:
            judges = [
                OllamaJudge("ollama-a", args.model_a, args.ollama_url, 0.0),
                OllamaJudge("ollama-b", args.model_b, args.ollama_url, 0.2),
            ]
    if args.command == "demo":
        with resources.as_file(fixture) as dataset:
            result = asyncio.run(run_dataset(dataset, judges, output, config=config))
    else:
        result = asyncio.run(run_dataset(dataset, judges, output, config=config))
    print(result.summary.model_dump_json(indent=2))
    print(f"report: {result.report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
