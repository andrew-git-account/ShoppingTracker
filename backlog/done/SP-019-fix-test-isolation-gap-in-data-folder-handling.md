# SP-019: Fix Test-Isolation Gap in DATA_FOLDER Handling

**Priority**: Medium
**Status**: Done
**Fulfils**: n/a (infrastructure — test-isolation bug fix, no user-visible behavior change)

## Description
`tests/conftest.py`'s `app` fixture does `monkeypatch.setenv('DATA_FOLDER', str(tmp_path))` before calling `app.main.create_app()`, to keep tests isolated from the real local `data/receipts.json`. But `app/main.py` calls `load_dotenv(override=True)`, and `.env` sets `DATA_FOLDER=./data`. Because `override=True`, if `app.main` is imported for the first time in a given pytest process after the monkeypatch runs, `load_dotenv` overwrites the monkeypatched `DATA_FOLDER` back to `./data` before `create_app()` reads it — meaning that test run touches the real local database instead of an isolated tmp one.

## Acceptance Criteria
- [x] Running `pytest tests/test_routes.py -v` as the very first thing in a brand-new process (i.e. worst-case import order, no other test having already imported `app.main` first) does not modify `data/receipts.json` or `data/allowed_users.json` at all — verified by comparing file content/hashes before and after the run.
- [x] The fix does not rely on import order or test execution order to work — it holds regardless of which test happens to trigger the first import of `app.main`.
- [x] A regression test (or equivalent verification approach) exists that would catch this class of bug if it recurs — e.g. asserting the test app's data path is under `tmp_path`, not the real `data/` directory.
- [x] Real local development usage (running `run_server.py` normally, outside of tests) is unaffected — `.env`'s `DATA_FOLDER=./data` still governs normal app startup.

## Notes / Context
- **Root cause**: `app/main.py`'s module-level (or `create_app()`-level — needs confirming exactly where) call to `load_dotenv(override=True)` only executes once per Python process, on first import of `app.main`. If that first import happens *after* a test's `monkeypatch.setenv('DATA_FOLDER', ...)` call, `load_dotenv(override=True)` stomps it back to the `.env` value. If `app.main` was already imported earlier in the same pytest session (by an earlier test file), the module is cached and `load_dotenv` doesn't re-run, so the monkeypatch correctly sticks — this is why the bug is import-order-dependent and doesn't reproduce every time.
- **This is the confirmed root cause of a recurring issue**: `backlog/done/SP-004-filtering-purchases.md` previously documented finding and cleaning up stray test-polluted receipts (`user_email: "test@example.com"`, `store_name: "Test Store"`) in the real `data/receipts.json`. Those reappeared by the time SP-005 was implemented (2026-08-19), confirming the underlying bug was never actually fixed — only its symptom was cleaned up once.
- **Reproduced directly during SP-005** (2026-08-19): running a fresh, isolated Python process that constructs the app via `create_app()` with `DATA_FOLDER` monkeypatched *beforehand* still initialized against the real `./data` path — confirmed by seeing `Database initialized: ./data\receipts.json` in the output despite the monkeypatch having been set first.
- Possible approaches to weigh (not prescriptive — pick whichever fits the codebase best):
  1. Make `app/main.py` not call `load_dotenv(override=True)` unconditionally — e.g. only load `.env` values for variables not already present in `os.environ`, or guard the call so it doesn't clobber an already-set variable.
  2. Have `tests/conftest.py`'s `app` fixture patch `dotenv.load_dotenv` itself to a no-op during tests, so the module-level call becomes inert regardless of import timing.
  3. Force a fresh import of `app.main` after monkeypatching (e.g. `importlib.reload`), so the module-level `load_dotenv(override=True)` always runs *after* the env var is already correctly set for that test.
- Relevant files: `app/main.py` (the `load_dotenv(override=True)` call and `create_app()`), `tests/conftest.py` (the `app` fixture doing the monkeypatch), `.env` (`DATA_FOLDER=./data`).
- Verification should include actually running the affected test file in total isolation (a fresh `python -m pytest tests/test_routes.py -v` invocation, not part of the full suite) since that's the scenario that reproduces the bug.

## Implementation Notes
_Completed 2026-08-19._

- `app/main.py` — replaced the blanket `load_dotenv(override=True)` with logic that first clears any pre-existing environment variables whose value is an empty string, then calls `load_dotenv()` normally (default `override=False`). This preserves the original fix's intent (Windows sets `ANTHROPIC_API_KEY=""` at the OS level, which would otherwise block `.env` from filling it in) while no longer clobbering a real, non-empty value — whether set by the OS or by a test's `monkeypatch.setenv(...)` — with `.env`'s value. The fix is order-independent by construction: it only ever overwrites a *blank* value, never a real one, regardless of when `app.main` is first imported relative to any monkeypatching.
- `run_server.py` — untouched. It has its own separate `load_dotenv(override=True)` call before importing `app.main`, but it's the real production/dev entry point (never used by tests), so there's no test-isolation concern there.
- `tests/test_app_isolation.py` (new) — regression test asserting the `app` fixture's database path lands under `tmp_path`, not the real `data/` directory.
- **Manual verification** (beyond the automated suite, since this bug is specifically about process/import-order behavior):
  - Ran `pytest tests/test_routes.py -v` alone in a fresh process (the exact worst-case scenario that reproduces the bug) — 62 passed, and `data/receipts.json`/`data/allowed_users.json` SHA-256 hashes were byte-identical before and after.
  - Started the server normally via `run_server.py` — `server.log` confirmed `Database initialized: ./data\receipts.json` and the LLM service initialized without the original `ANTHROPIC_API_KEY not found` error, confirming no regression.
- No data migrations. No dependency changes.
- Tests: 1 added, 192 passed (full suite).
