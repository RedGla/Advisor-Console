# Evaluation Evidence

`eval/results.md` is the canonical generated evaluation artifact. Do not maintain a second copied results table or rubric here; that would allow the evidence to drift.

Generate it with:

```bash
python eval/run_eval.py --dry-run
```

This produces **DRY_RUN** evidence only. Prompt rows are marked `NOT_EVALUATED`, enforcement rows are structural placeholders, and every rubric score is `N/A`. A dry run verifies that the evaluator can load prompts and generate the artifact; it does not verify model quality, grounding, guardrails, latency, or provider behavior.

For a live run, set `EVAL_BASE_URL`, `EVAL_EMAIL`, `EVAL_PASSWORD`, and optionally `EVAL_ENVIRONMENT` and `OPENROUTER_MODEL` before running without `--dry-run`.

The generated artifact records timestamp, commit SHA, model, environment, prompt ID, response, actual token counts, cost, latency, pass/fail, and reason. Its rubric is the PRD weighted 1/3/5 rubric:

Only a run without `--dry-run` is **LIVE** evaluation evidence. Live rows contain results from the deployed backend, and live enforcement requests are reported separately from model-quality prompts.

| Criterion | Weight |
|---|---:|
| Task success/relevance | 0.20 |
| Grounding fidelity | 0.20 |
| Guardrail enforcement | 0.20 |
| Robustness | 0.15 |
| Architecture/code quality | 0.15 |
| Eval rigor/writeup | 0.10 |

OAuth, provider access, and secrets are never included in generated evidence.
