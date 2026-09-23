import subprocess
import sys
from pathlib import Path

def test_dry_run_generates_canonical_metadata_and_prd_rubric():
    root = Path(__file__).parent.parent
    subprocess.run([sys.executable, "eval/run_eval.py", "--dry-run"], cwd=root, check=True)
    text = (root / "eval" / "results.md").read_text(encoding="utf-8")
    for label in ("Timestamp:", "Commit SHA:", "Model:", "Test environment:",
                  "prompt_tokens", "completion_tokens", "cost", "latency_ms",
                  "pass/fail", "reason"):
        assert label in text
    assert "Run mode: **DRY_RUN**" in text
    assert "NOT_EVALUATED" in text
    assert "| N/A | N/A | Dry run; live behavior was not evaluated |" in text
    assert "| PASS |" not in text
    for criterion, weight in (("Task success/relevance", "0.20"), ("Grounding fidelity", "0.20"),
                              ("Guardrail enforcement", "0.20"), ("Robustness", "0.15"),
                              ("Architecture/code quality", "0.15"), ("Eval rigor/writeup", "0.10")):
        assert criterion in text and weight in text
    assert "0–3" not in text and "0-3" not in text
