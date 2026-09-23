# Evaluation test matrix

| Scenario | Automated coverage |
|---|---|
| System-prompt extraction | `backend/tests/test_provider_failure.py`, `eval/prompts.json:p5` |
| Grounding-document extraction | `eval/prompts.json:p6` |
| Cap bypass | `backend/tests/test_cap_race.py`, `backend/tests/test_quota_correctness.py` |
| Rate-limit bypass | `backend/tests/test_rate_limit_race.py`, `backend/tests/test_quota_correctness.py` |
| Cross-user conversation access | `backend/tests/test_ownership.py` |
| Docs cold-cache outage | `backend/tests/test_docs_failure.py::test_docs_service_failure_no_cache` |
| Docs stale-cache outage | `backend/tests/test_docs_failure.py::test_docs_service_failure_warm_cache` |
| Provider timeout | `backend/tests/test_provider_failure.py::test_llm_provider_timeout` |
| DB outage | `backend/tests/test_db_failure.py` |
| Grounding relevant query | `backend/tests/test_grounding_edge_cases.py` |
| Grounding irrelevant query | `backend/tests/test_grounding_edge_cases.py` |
