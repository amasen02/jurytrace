# Security policy

Report vulnerabilities privately to the repository owner before public
disclosure. Include the affected version, reproduction steps, impact, and a
minimal non-sensitive fixture.

## Security properties and limits

- Input and judge payloads use strict Pydantic schemas with extra fields denied.
- Calls are bounded by trace count, total calls, and per-call deadlines.
- Evidence quotes must exactly match declared offsets in the original trace.
- Trace IDs and all rendered report content are HTML escaped.
- Ollama defaults to loopback and no paid or remote fallback exists.
- The project does not read API keys or execute text found in trajectories.

Trajectory content and judge rationales may still contain sensitive material.
Receipts and SQLite databases are plaintext, so place them in an access-controlled
directory and apply an appropriate retention policy. A caller can explicitly set
a non-loopback Ollama URL; secure that transport and server outside JuryTrace.

Prompt/data separation and span validation reduce some injection effects but do
not establish that a model followed policy. Fixture tests are not a security
assessment, and the static report is not a certification.

