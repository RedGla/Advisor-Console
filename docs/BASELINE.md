# Phase 0: auditable baseline

## Before changes (2026-09-23)

Source: local `798cd2f0067c4199d812e750e1f6b1b089de6106`; GitHub `dev`
was `14ade491910339e9c633cd27d5a9ea5315ca089e`. The only existing local
difference was tolerant timing-field logging in `backend/main.py`.
Phase 0 does not introduce that application change into the remote proposal.

| Check | Original result |
| --- | --- |
| Backend pytest | 4 passed, 5 failed, 12 errors: no isolated PostgreSQL configured |
| Frontend lint | Failed: `src/pages/Admin.tsx:60`, `no-useless-assignment` |
| Frontend TypeScript + production build | Passed (`npm run build`, 339 modules) |

The initial backend run deliberately used an unreachable local database rather
than credentials from `backend/.env`. These are environment/setup failures,
not evidence that 17 application behaviors are broken.

Exact initial commands (PowerShell, repository root):

```powershell
$env:DATABASE_URL='postgresql://audit:audit@127.0.0.1:1/audit'
$env:PYTHON_DOTENV_DISABLED='1'
python -B -m pytest -p no:cacheprovider -q --tb=short
Set-Location frontend
npm run lint
npm run build
```

The existing `backend/venv` lacked pytest; the initial suite used system Python
3.12 with pytest 8.4.2. No production database or provider was contacted.

## Scope

Only test infrastructure, test doubles/assertions, CI, documentation, and a
behavior-preserving removal of an unused comparator initialization belong here.
The compliance audit's authentication, quota, persistence, and UI behavior
findings remain unresolved. Green checks are a regression baseline, not PRD
compliance certification.

## After Phase 0 setup (local)

Python 3.12.5, Node 24.15.0, PostgreSQL 16 in a disposable Docker container:

| Command | Result |
| --- | --- |
| `python -B -m pytest -p no:cacheprovider -q --tb=short` | 21 passed; 24 existing dependency/cookie deprecation warnings |
| `npm run lint` (frontend directory) | Passed |
| `npm run build` (frontend directory) | Passed, including TypeScript; 339 modules |

Changes: isolate the database and migrate it automatically, suppress .env
loading, provide synthetic Docs content and a dummy API key, block unexpected
provider traffic, reset cache/rate state, align mock replies with the real
timing-field contract, assert provider mocks are reached, and require exactly
one successful request in the rate-race test. No production backend file was
edited. The frontend comparator only drops an initialization overwritten on
both branches; sorting behavior is unchanged.

GitHub Actions results are recorded on the Phase 0 pull request. A local pass
alone is not evidence of a successful Actions run. Commands for a clean setup
are in [TESTING.md](TESTING.md).
