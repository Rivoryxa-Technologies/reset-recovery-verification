# Contributing

Keep changes focused on the reset-flush teaching objective. Please run the complete matrix before submitting a change:

```sh
python3 tools/run.py --seeds 1,17,2026
```

A change is ready when all correct cases pass and all mutants fail with the named reset-flush marker. Include the generated `summary.json` verdict in your change description, but do not commit generated `runs/` evidence. New tests should be deterministic around the behavior they claim to cover; seeded random traffic may supplement that proof.

Use clear commit messages, retain SPDX headers, and update the README if the observable contract changes.
