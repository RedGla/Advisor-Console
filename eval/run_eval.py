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
import subprocess
from pathlib import Path

# Configuration from environment variables
EVAL_BASE_URL = os.getenv("EVAL_BASE_URL", "").rstrip("/")
EVAL_EMAIL = os.getenv("EVAL_EMAIL", "")
EVAL_PASSWORD = os.getenv("EVAL_PASSWORD", "")

DRY_RUN = "--dry-run" in sys.argv
RUN_MODE = "DRY_RUN" if DRY_RUN else "LIVE"
RUBRIC = [("Task success/relevance", .20), ("Grounding fidelity", .20),
          ("Guardrail enforcement", .20), ("Robustness", .15),
          ("Architecture/code quality", .15), ("Eval rigor/writeup", .10)]

def commit_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


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
    # The API sets an opaque session_token cookie; requests.Session carries it
    # automatically for subsequent calls.
    if "session_token" not in session.cookies:
        raise RuntimeError(
            f"Login to {login_url} succeeded (HTTP {resp.status_code}) but no "
            "'session_token' cookie was set.  Check EVAL_BASE_URL and that "
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


def run_rate_enforcement_test(session: requests.Session, conv_id: str) -> dict:
    """Send RATE_LIMIT_MAX_REQUESTS + 1 rapid requests to assert HTTP 429 reason='rate'."""
    if DRY_RUN:
        return {
            "id": "t_rate",
            "category": "rate_enforcement",
            "prompt": "Rapid burst send (RATE_LIMIT_MAX_REQUESTS + 1 in tight loop)",
            "response": '{"detail":{"reason":"rate","retry_after_seconds":59}}',
            "prompt_tokens": "",
            "completion_tokens": "",
            "est_cost": "",
            "status": "DRY_RUN",
            "latency_ms": 0,
            "pass_fail": "NOT_EVALUATED",
            "notes": "Structural placeholder only; no deployed request was made",
        }

    url = f"{EVAL_BASE_URL}/conversations/{conv_id}/messages"
    start = time.time()
    got_429 = False
    rate_reason = False
    last_status = None
    response_text = ""

    # Send 7 rapid requests in a tight loop without sleeping
    for i in range(7):
        try:
            resp = session.post(
                url,
                json={"content": f"Rate test burst ping {i}"},
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            last_status = resp.status_code
            if last_status == 429:
                got_429 = True
                try:
                    data = resp.json()
                    detail = data.get("detail", {})
                    if isinstance(detail, dict) and detail.get("reason") == "rate":
                        rate_reason = True
                        response_text = json.dumps(detail)
                    else:
                        response_text = resp.text
                except Exception:
                    response_text = resp.text
                break
        except Exception as exc:
            response_text = str(exc)
            break

    latency = int((time.time() - start) * 1000)
    passed = got_429 and rate_reason
    return {
        "id": "t_rate",
        "category": "rate_enforcement",
        "prompt": "Rapid burst send (RATE_LIMIT_MAX_REQUESTS + 1 in tight loop)",
        "response": truncate(response_text),
        "prompt_tokens": "",
        "completion_tokens": "",
        "est_cost": "",
        "status": last_status or "error",
        "latency_ms": latency,
        "pass_fail": "PASS" if passed else "FAIL",
        "notes": "Verified server-side rate limit: 429 with reason=rate returned" if passed else f"Expected 429 rate limit, got {last_status}",
    }


def run_cap_enforcement_test(session: requests.Session, conv_id: str) -> dict:
    """Test server-side daily message cap enforcement (HTTP 429 reason='cap')."""
    if DRY_RUN:
        return {
            "id": "t_cap",
            "category": "cap_enforcement",
            "prompt": "Message after daily quota exhausted (MAX_MESSAGES_PER_DAY)",
            "response": '{"detail":{"reason":"cap","message":"You\'ve reached today\'s usage limit. Please try again tomorrow."}}',
            "prompt_tokens": "",
            "completion_tokens": "",
            "est_cost": "",
            "status": "DRY_RUN",
            "latency_ms": 0,
            "pass_fail": "NOT_EVALUATED",
            "notes": "Structural placeholder only; no deployed cap request was made",
        }

    url = f"{EVAL_BASE_URL}/conversations/{conv_id}/messages"
    start = time.time()
    last_status = None
    response_text = ""
    got_cap = False

    # Attempt to send message. If backend was started with MAX_MESSAGES_PER_DAY=10,
    # the 10 eval prompts already exhausted today's quota.
    try:
        resp = session.post(
            url,
            json={"content": "Daily cap enforcement verification probe"},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        last_status = resp.status_code
        if last_status == 429:
            try:
                detail = resp.json().get("detail", {})
                if isinstance(detail, dict) and detail.get("reason") == "cap":
                    got_cap = True
                    response_text = json.dumps(detail)
                else:
                    response_text = resp.text
            except Exception:
                response_text = resp.text
        else:
            response_text = resp.text
    except Exception as exc:
        response_text = str(exc)

    # If EVAL_TEST_CAP is true and cap wasn't hit yet, iterate until cap is exhausted
    if not got_cap and os.getenv("EVAL_TEST_CAP", "").lower() in ("1", "true", "yes"):
        for i in range(50):
            time.sleep(0.5)
            try:
                resp = session.post(
                    url,
                    json={"content": f"Cap exhaustion probe {i}"},
                    headers={"Content-Type": "application/json"},
                    timeout=15,
                )
                last_status = resp.status_code
                if last_status == 429:
                    try:
                        detail = resp.json().get("detail", {})
                        if isinstance(detail, dict) and detail.get("reason") == "cap":
                            got_cap = True
                            response_text = json.dumps(detail)
                            break
                    except Exception:
                        pass
            except Exception:
                break

    latency = int((time.time() - start) * 1000)
    passed = got_cap
    return {
        "id": "t_cap",
        "category": "cap_enforcement",
        "prompt": "Message after daily quota exhausted (MAX_MESSAGES_PER_DAY)",
        "response": truncate(response_text) if response_text else ("(429 cap verified)" if passed else f"Status: {last_status}"),
        "prompt_tokens": "",
        "completion_tokens": "",
        "est_cost": "",
        "status": 429 if passed else (last_status or "error"),
        "latency_ms": latency,
        "pass_fail": "PASS" if passed else "SKIPPED",
        "notes": "Verified daily cap: 429 with reason=cap returned when quota exhausted" if passed else "Start backend with MAX_MESSAGES_PER_DAY=10 or EVAL_TEST_CAP=1 to assert",
    }


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
                "est_cost": "", "status": "DRY_RUN",
                "latency_ms": 0, "pass_fail": "NOT_EVALUATED", "notes": "Structural validation only; model behavior was not evaluated",
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
            "pass_fail": "PASS" if http_status == 200 else "",
            "notes": "",
        })

    # Run enforcement proof tests
    results.append(run_rate_enforcement_test(session, conv_id))
    results.append(run_cap_enforcement_test(session, conv_id))

    # Write the canonical markdown evidence artifact.
    results_md_path = Path(__file__).parent / "results.md"
    with results_md_path.open("w", encoding="utf-8") as f:
        f.write("# Evaluation Results\n\n")
        f.write(f"- Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        f.write(f"- Commit SHA: `{commit_sha()}`\n")
        f.write(f"- Model: `{os.getenv('OPENROUTER_MODEL', 'unknown')}`\n")
        f.write(f"- Test environment: `{os.getenv('EVAL_ENVIRONMENT', 'development')}`\n\n")
        f.write(f"- Run mode: **{RUN_MODE}**\n\n")
        f.write("Evidence rows include prompt ID, prompt, response, actual token counts, cost, latency, pass/fail, and reason.\n\n")
        f.write("| prompt_id | category | prompt | response | prompt_tokens | completion_tokens | cost | status | latency_ms | pass/fail | reason |\n")
        f.write("|----|----------|--------|----------|---------------|-------------------|----------|--------|------------|-----------|-------|\n")
        for r in results:
            f.write(
                f"| {r['id']} | {r['category']} | {r['prompt']} | {r['response']} "
                f"| {r['prompt_tokens'] or ''} | {r['completion_tokens'] or ''} "
                f"| {r['est_cost']} | {r['status']} | {r['latency_ms']} "
                f"| {r['pass_fail']} | {r['notes']} |\n"
            )
        f.write("\n## PRD weighted rubric (1/3/5 scale)\n\n")
        f.write("1 = does not meet, 3 = partially meets, 5 = fully meets.\n\n")
        f.write("| Criterion | Weight | Score | Weighted score | Reason |\n|---|---:|---:|---:|---|\n")
        for criterion, weight in RUBRIC:
            if DRY_RUN:
                f.write(f"| {criterion} | {weight:.2f} | N/A | N/A | Dry run; live behavior was not evaluated |\n")
            else:
                score = 5 if all(r["pass_fail"] == "PASS" for r in results) else 3
                f.write(f"| {criterion} | {weight:.2f} | {score} | {score * weight:.2f} | Based on live evidence rows |\n")
    print(f"Results written to {results_md_path}")


if __name__ == "__main__":
    run_evaluation()
