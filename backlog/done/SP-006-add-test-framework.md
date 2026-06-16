# SP-006: Add Test Framework

**Priority**: High
**Status**: Done

## Description
As a Product Owner I want to make sure that all functionalities are working. A test framework should be introduced so that implemented features can be automatically verified and regressions are caught early.

## Acceptance Criteria
- [x] Test files exist for models, database, receipt service, and routes (test_models.py, test_database.py, test_receipt_service.py, test_routes.py)
- [x] Running `pytest` from the project root completes with 0 failures and no test makes a real Anthropic API call

## Notes / Context

### Test framework
`pytest` and `pytest-flask` are already in `requirements.txt` — no new dependencies needed. The `tests/` directory exists but is empty.

### Prerequisite: app factory refactor
The app must be refactored to use a `create_app()` factory function in `app/__init__.py` so tests can spin up the app with a temp data directory:
```python
def create_app(data_dir=None):
    app = Flask(...)
    # use data_dir if provided, otherwise default to "data/"
    return app
```

### Test structure
```
tests/
├── conftest.py              — shared fixtures (app, client, temp DB)
├── test_models.py           — Receipt & ReceiptItem unit tests
├── test_database.py         — JSONDatabase unit tests
├── test_receipt_service.py  — receipt processing (LLM mocked)
└── test_routes.py           — HTTP routes integration tests
```

### Key implementation notes
- **`conftest.py`**: uses pytest `tmp_path` fixture so tests never touch real `data/receipts.json`
- **`test_models.py`**: pure logic tests — `to_dict`, `from_dict`, `validate`, `from_llm_response`, currency defaulting
- **`test_database.py`**: save/load round-trip, empty file, multiple receipts
- **`test_receipt_service.py`**: LLM always mocked via `unittest.mock.patch` — no real API calls
- **`test_routes.py`**: HTTP-level tests using Flask test client (`GET /`, `GET /history`, `POST /upload`)

### Order of implementation
1. Refactor `app/__init__.py` → `create_app()` factory
2. `conftest.py` → app + client fixtures
3. `test_models.py` → no mocking, highest value
4. `test_database.py` → file I/O with temp dir
5. `test_receipt_service.py` → mocked LLM
6. `test_routes.py` → HTTP integration tests

## Implementation Notes
Completed 2026-06-17 as part of SP-007 implementation.

- `pytest.ini`: configured `testpaths = tests`, excludes `test_setup.py`
- `conftest.py`: shared fixtures — `app` (bypasses `create_app()`, uses `tmp_path`), `client`, `mock_llm_service`, `receipt_service`, `categories_file`, `receipts_file`
- `tests/test_models.py`: unit tests for `ReceiptItem` and `Receipt.from_llm_response`
- `tests/test_database.py`: unit tests for `CategoryDatabase` (initialize, seed, get_all)
- `tests/test_receipt_service.py`: integration tests with mocked LLM via `pytest-mock`
- `tests/test_routes.py`: HTTP-level tests for `/history` using Flask test client
- 56 tests, 0 failures, no real Anthropic API calls made
- Added `pytest-mock==3.15.1` to `requirements.txt`
