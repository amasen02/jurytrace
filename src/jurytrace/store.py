"""SQLite review queue and human-resolution store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Self

from .models import HumanResolution, TraceDecision


class ReviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS review_queue (
                dataset_hash TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'resolved')),
                decision_json TEXT NOT NULL,
                PRIMARY KEY(run_id, dataset_hash, trace_id)
            );
            CREATE TABLE IF NOT EXISTS resolutions (
                run_id TEXT NOT NULL,
                dataset_hash TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('accept', 'reject')),
                resolver TEXT NOT NULL,
                note TEXT NOT NULL,
                resolved_at TEXT NOT NULL,
                PRIMARY KEY(run_id, dataset_hash, trace_id),
                FOREIGN KEY(run_id, dataset_hash, trace_id)
                    REFERENCES review_queue(run_id, dataset_hash, trace_id)
            );
            """
        )

    def enqueue(self, dataset_hash: str, run_id: str, decision: TraceDecision) -> None:
        self.connection.execute(
            """INSERT INTO review_queue(dataset_hash, trace_id, run_id, status, decision_json)
               VALUES(?, ?, ?, 'pending', ?)""",
            (dataset_hash, decision.trace_id, run_id, decision.model_dump_json()),
        )
        self.connection.commit()

    def resolve(self, resolution: HumanResolution) -> None:
        row = self.connection.execute(
            "SELECT status FROM review_queue WHERE run_id=? AND dataset_hash=? AND trace_id=?",
            (resolution.run_id, resolution.dataset_hash, resolution.trace_id),
        ).fetchone()
        if row is None:
            raise ValueError("resolution does not match a queued trace and dataset hash")
        if row["status"] == "resolved":
            raise ValueError("trace already has a persisted resolution")
        with self.connection:
            self.connection.execute(
                """INSERT INTO resolutions
                   (run_id, dataset_hash, trace_id, decision, resolver, note, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolution.run_id,
                    resolution.dataset_hash,
                    resolution.trace_id,
                    resolution.decision,
                    resolution.resolver,
                    resolution.note,
                    resolution.resolved_at.isoformat(),
                ),
            )
            self.connection.execute(
                """UPDATE review_queue SET status='resolved'
                   WHERE run_id=? AND dataset_hash=? AND trace_id=?""",
                (resolution.run_id, resolution.dataset_hash, resolution.trace_id),
            )

    def queue(self) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT dataset_hash, trace_id, run_id, status, decision_json
               FROM review_queue ORDER BY run_id, trace_id"""
        ).fetchall()
        return [
            {
                "dataset_hash": row["dataset_hash"],
                "trace_id": row["trace_id"],
                "run_id": row["run_id"],
                "status": row["status"],
                "decision": json.loads(row["decision_json"]),
            }
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
