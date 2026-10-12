# Legacy mock runs — not experimental findings

Every run in this folder was produced by the earlier `src/generator.py` **mock extractive
provider** (`generation_meta.provider == "mock"`), which pasted the first ~120 words of the
top-ranked chunk instead of calling a language model. The accuracy, hallucination and
latency numbers here therefore describe that placeholder, not an LLM, and must not be
reported as results.

They are kept only for provenance. Real benchmark runs are written to `results/benchmark/<run-id>/`
by `python -m backend.app.research.benchmark run`.
