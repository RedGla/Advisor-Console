# Evaluation Evidence

`eval/results.md` is the canonical generated evaluation artifact. Do not maintain a second copied results table or rubric here; that would allow the evidence to drift.

Run a structural dry run with:

```bash
python eval/run_eval.py --dry-run
```

Dry runs write `advisor-console-eval-dry-run.md` in the system temporary
directory and never modify `eval/results.md`. Prompt rows are marked
`NOT_EVALUATED`, enforcement rows are structural placeholders, and every rubric
score is `N/A`.

For a live quality run, set `EVAL_BASE_URL`, `EVAL_EMAIL`, `EVAL_PASSWORD`,
`EVAL_ORIGIN`, `EVAL_ENVIRONMENT`, and `EVAL_MODEL` (or `OPENROUTER_MODEL`).
Each quality prompt gets a fresh conversation. Default pacing derives from
`EVAL_RATE_LIMIT_REQUESTS` and `EVAL_RATE_LIMIT_WINDOW_SECONDS`; override it
with `EVAL_PACING_SECONDS` only when deployment settings are known.

```bash
python eval/run_eval.py --suite quality
```

Rate and cap enforcement are separate staging-only suites. Rate sends the
configured request limit plus one. Cap exhaustion requires both an explicit
flag and an explicit paid-call bound:

```bash
python eval/run_eval.py --suite rate
python eval/run_eval.py --suite cap --allow-cap-exhaustion
```

Set `EVAL_CAP_MAX_PAID_CALLS` before the cap command. It is also a hard bound
on total cap-probe requests, so a missing/misconfigured cap cannot spend past
that number. Never run enforcement suites against production or weaken
production limits for evaluation.

The generated artifact records deployment URL, timestamps, commit SHA, model,
environment, isolated conversation ID, prompt, response, actual token counts,
cost, latency, pass/fail, and evidence-based reason. Long responses are
excerpted and adversarial extraction responses are redacted from the committed
artifact. Its rubric is the PRD
weighted 1/3/5 rubric:

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
