from __future__ import annotations

from pathlib import Path

from jurytrace.cli import main


def test_malformed_dataset_returns_clean_cli_error(tmp_path: Path, capsys: object) -> None:
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text('{"trace_id":', encoding="utf-8")
    code = main(["run", str(dataset), "--output", str(tmp_path / "out")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert code == 2
    assert "invalid JSONL at line 1" in captured.err
    assert "Traceback" not in captured.err


def test_invalid_resolution_returns_clean_cli_error(tmp_path: Path, capsys: object) -> None:
    code = main(
        [
            "resolve",
            "--database",
            str(tmp_path / "reviews.sqlite3"),
            "--run-id",
            "run",
            "--dataset-hash",
            "not-a-hash",
            "--trace-id",
            "trace",
            "--decision",
            "accept",
            "--resolver",
            "reviewer",
            "--note",
            "Reviewed.",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert code == 2
    assert "dataset_hash" in captured.err
    assert "Traceback" not in captured.err
