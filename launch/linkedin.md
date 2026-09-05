I built JuryTrace to answer a practical question in agent evaluations: when two regression judges disagree, can we inspect why and route the case to a human without losing provenance?

It runs two configured judges concurrently through a real async LangGraph workflow. Every proposed verdict must include evidence spans that exactly match the original input or output. Disagreements, timeouts, malformed responses, provider errors, and invalid evidence enter a SQLite queue keyed to the run ID, dataset hash, and trace ID.

The reference receipt is intentionally modest: five synthetic traces, four agreements, one review item, and one fixture false acceptance. The offline fixture tests orchestration, not LLM judge quality. Golden labels stay out of provider prompts, and Ollama costs remain unknown when the provider cannot report them. Configuration diversity is useful, but it is not statistical independence.

Run it, inspect the HTML/JSONL receipts, and resolve the queued case yourself: https://github.com/amasen02/jurytrace

Built with AI assistance; human review is part of the exercise.
