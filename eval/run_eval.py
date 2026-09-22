"""
eval/run_eval.py — automated evaluation runner for Advisor Console.

Usage:
    # Set env vars first:
    #   EVAL_BASE_URL=http://localhost:8000
    #   EVAL_EMAIL=your-test-user@example.com
    #   EVAL_PASSWORD=yourpassword
    python eval/run_eval.py

    # Dry-run (skip actual HTTP calls, write empty results table):
    python eval/run_eval.py --dry-run

Results are written to eval/results.md.  Paste the table into docs/EVAL.md.
"""
import os
import sys
import time
import json
import requests
from pathlib import Path

# Configuration from environment variables
EVAL_BASE_URL = os.getenv("EVAL_BASE_URL", "").rstrip("/")
EVAL_EMAIL = os.getenv("EVAL_EMAIL", "")
EVAL_PASSWORD = os.getenv("EVAL_PASSWORD", "")

DRY_RUN = "--dry-run" in sys.argv


def login() -> requests.Session:
    """Authenticate with session-cookie auth (matching the real API) and
    return a requests.Session that carries the cookie automatically."""
    session = requests.Session()
    if DRY_RUN:
        return session

    if not all([EVAL_BASE_URL, EVAL_EMAIL, EVAL_PASSWORD]):
        raise EnvironmentError(
            "EVAL_BASE_URL, EVAL_EMAIL, and EVAL_PASSWORD must be set in the environment.\n"
            "Use --dry-run to skip HTTP calls."
        )

    login_url = f"{EVAL_BASE_URL}/auth/login"
    resp = session.post(
        login_url,
        json={"email": EVAL_EMAIL, "password": EVAL_PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    # The API sets a session_user_id cookie; requests.Session carries it
    # automatically for subsequent calls.
    if "session_user_id" not in session.cookies:
        raise RuntimeError(
            f"Login to {login_url} succeeded (HTTP {resp.status_code}) but no "
            "'session_user_id' cookie was set.  Check EVAL_BASE_URL and that "
            "COOKIE_SECURE=false for a local dev server."
        )
    return session


def create_eval_conversation(session: requests.Session) -> str:
    """Create a single conversation that all eval prompts will be sent into."""
    if DRY_RUN:
        return "dry-run-conv-id"
    resp = session.post(
        f"{EVAL_BASE_URL}/conversations",
        json={"title": f"Eval run {time.strftime('%Y-%m-%d %H:%M')}"},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def truncate(text: str, length: int = 200) -> str:
    return (text[:length] + "…") if len(text) > length else text


def run_evaluation():
    # Load prompts
    prompts_path = Path(__file__).parent / "prompts.json"
    with prompts_path.open("r", encoding="utf-8") as f:
        prompts = json.load(f)

    session = login()
    conv_id = create_eval_conversation(session)
    results = []

    for prompt in prompts:
        pid = prompt["id"]
        category = prompt["category"]
        text = prompt["prompt"]

        if DRY_RUN:
            results.append({
                "id": pid, "category": category,
                "prompt": truncate(text), "response": "(dry-run)",
                "prompt_tokens": "", "completion_tokens": "",
                "est_cost": "", "status": "dry-run",
                "latency_ms": 0, "pass_fail": "", "notes": "",
            })
            continue

        url = f"{EVAL_BASE_URL}/conversations/{conv_id}/messages"
        payload = {"content": text}
        start = time.time()
        try:
            resp = session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            latency = int((time.time() - start) * 1000)
            http_status = resp.status_code

            if http_status == 429:
                response_text = "(rate-limited)"
                prompt_tokens = completion_tokens = est_cost = None
            else:
                resp.raise_for_status()
                # The endpoint returns the assistant Message object directly:
                # {"id":..., "sender":"assistant", "content":...,
                #  "prompt_tokens":..., "completion_tokens":..., "est_cost":...}
                data = resp.json()
                response_text = data.get("content", "")
                prompt_tokens = data.get("prompt_tokens")
                completion_tokens = data.get("completion_tokens")
                est_cost = data.get("est_cost")

        except Exception as exc:
            latency = int((time.time() - start) * 1000)
            http_status = (
                getattr(exc, "response", None).status_code
                if hasattr(exc, "response") else "error"
            )
            response_text = str(exc)
            prompt_tokens = completion_tokens = est_cost = None

        results.append({
            "id": pid,
            "category": category,
            "prompt": truncate(text),
            "response": truncate(response_text),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "est_cost": f"${est_cost:.6f}" if est_cost is not None else "",
            "status": http_status,
            "latency_ms": latency,
            "pass_fail": "",
            "notes": "",
        })

    # Write markdown table
    results_md_path = Path(__file__).parent / "results.md"
    with results_md_path.open("w", encoding="utf-8") as f:
        f.write("| id | category | prompt | response | prompt_tokens | completion_tokens | est_cost | status | latency_ms | pass/fail | notes |\n")
        f.write("|----|----------|--------|----------|---------------|-------------------|----------|--------|------------|-----------|-------|\n")
        for r in results:
            f.write(
                f"| {r['id']} | {r['category']} | {r['prompt']} | {r['response']} "
                f"| {r['prompt_tokens'] or ''} | {r['completion_tokens'] or ''} "
                f"| {r['est_cost']} | {r['status']} | {r['latency_ms']} "
                f"| {r['pass_fail']} | {r['notes']} |\n"
            )
    print(f"Results written to {results_md_path}")


if __name__ == "__main__":
    run_evaluation()

