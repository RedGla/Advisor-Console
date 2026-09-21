import os
import time
import json
import requests
from pathlib import Path

# Configuration from environment variables
EVAL_BASE_URL = os.getenv("EVAL_BASE_URL")
EVAL_EMAIL = os.getenv("EVAL_EMAIL")
EVAL_PASSWORD = os.getenv("EVAL_PASSWORD")

if not all([EVAL_BASE_URL, EVAL_EMAIL, EVAL_PASSWORD]):
    raise EnvironmentError("EVAL_BASE_URL, EVAL_EMAIL, and EVAL_PASSWORD must be set in the environment")

HEADERS = {"Content-Type": "application/json"}

def login():
    """Authenticate and return session with auth token set."""
    login_url = f"{EVAL_BASE_URL.rstrip('/')}/auth/login"
    payload = {"email": EVAL_EMAIL, "password": EVAL_PASSWORD}
    resp = requests.post(login_url, json=payload, headers=HEADERS)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token returned")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return session

def truncate(text: str, length: int = 200) -> str:
    return (text[:length] + "…") if len(text) > length else text

def run_evaluation():
    # Load prompts
    prompts_path = Path(__file__).parent / "prompts.json"
    with prompts_path.open("r", encoding="utf-8") as f:
        prompts = json.load(f)

    session = login()
    results = []

    for prompt in prompts:
        pid = prompt["id"]
        category = prompt["category"]
        text = prompt["prompt"]
        url = f"{EVAL_BASE_URL.rstrip('/')}/conversations/{pid}/messages"
        payload = {"role": "user", "content": text}
        start = time.time()
        try:
            resp = session.post(url, json=payload, headers=HEADERS)
            latency = int((time.time() - start) * 1000)  # ms
            status = resp.status_code
            if status == 429:
                # Rate‑limited – record but continue
                response_text = ""
                prompt_tokens = completion_tokens = est_cost = None
            else:
                resp.raise_for_status()
                data = resp.json()
                # Expected shape – adapt as needed
                response_text = data.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                # Simple cost estimate: $0.00002 per token (adjust as appropriate)
                est_cost = ((prompt_tokens or 0) + (completion_tokens or 0)) * 0.00002
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            status = getattr(e, "response", None).status_code if hasattr(e, "response") else "error"
            response_text = str(e)
            prompt_tokens = completion_tokens = est_cost = None

        results.append({
            "id": pid,
            "category": category,
            "prompt": truncate(text),
            "response": truncate(response_text),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "est_cost": f"${est_cost:.6f}" if est_cost is not None else "",
            "status": status,
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
                f"| {r['id']} | {r['category']} | {r['prompt']} | {r['response']} | {r['prompt_tokens'] or ''} | {r['completion_tokens'] or ''} | {r['est_cost']} | {r['status']} | {r['latency_ms']} | {r['pass_fail']} | {r['notes']} |\n"
            )
    print(f"Results written to {results_md_path}")

if __name__ == "__main__":
    # The script is intended for dry‑run against a local / development server.
    # Users should set the environment variables accordingly before invoking.
    run_evaluation()
