# Recorded demo evidence

`v0.1-reference/` was produced by the installed console command on 2026-09-05:

```text
.venv\Scripts\jurytrace.exe demo --output receipts\v0.1-reference
```

The raw summary records dataset SHA-256
`1787c91a532efe8bafd4383ffcb641967f77e2c7de70d3a3453bb267f06e5495`,
five traces, four agreements, one review item, and one fixture false acceptance.
All ten judge calls have unknown token counts and costs because the deterministic
offline fixtures report neither. `fixture_judges: true` and the exact two fixture
configurations are included in the receipt.

The SQLite file is intentionally ignored as generated local state. The committed
JSON, JSONL, and HTML files are the inspectable raw/reference outputs. These
artifacts measure the fixed fixture demo only; they are not live-model evidence.

Verification on Python 3.12.9: `pytest` passed 20 tests, `ruff check .` passed,
and `pip wheel --no-deps --wheel-dir dist .` built `jurytrace-0.1.0` with SHA-256
`a7d8ee2a7dc6ce0d857936c965c7fa3f86a70a75cd497065ab2d3ace22010031`.
That wheel was installed into a separate virtual environment, and its packaged
demo completed from `C:\Windows\Temp`, outside the source checkout. Python 3.11
was not installed on this machine, and the Docker CLI was unavailable. CI is
configured to exercise Python 3.11, 3.12, and 3.13 when run by GitHub Actions.
