# Evaluation Evidence

`eval/results.md` is the canonical generated evaluation artifact. Do not maintain a second copied results table or rubric here; that would allow the evidence to drift.

Generate it with:

```bash
python eval/run_eval.py --dry-run
```

For a live run, set `EVAL_BASE_URL`, `EVAL_EMAIL`, `EVAL_PASSWORD`, and optionally `EVAL_ENVIRONMENT` and `OPENROUTER_MODEL` before running without `--dry-run`.

The generated artifact records timestamp, commit SHA, model, environment, prompt ID, response, actual token counts, cost, latency, pass/fail, and reason. Its rubric is the PRD weighted 1/3/5 rubric:

| Criterion | Weight |
|---|---:|
| Task success/relevance | 0.20 |
| Grounding fidelity | 0.20 |
| Guardrail enforcement | 0.20 |
| Robustness | 0.15 |
| Architecture/code quality | 0.15 |
| Eval rigor/writeup | 0.10 |

OAuth, provider access, and secrets are never included in generated evidence.
