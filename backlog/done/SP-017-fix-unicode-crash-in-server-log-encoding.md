# SP-017: Fix Receipt Upload Failure on Non-Latin-1 Text (Server Log Encoding Crash)

**Priority**: High
**Status**: Done
**Fulfils**: n/a (infrastructure — logging bug that silently discarded successfully-extracted receipts)
**Deployed**: b6f3230 (2026-08-19)

## Description
Uploading a receipt whose extracted text contains a character outside Windows' `cp1252` code page (e.g. Turkish `İ`, or other accented/non-Latin-1 characters) failed even though Claude successfully extracted the receipt data. The failure happened in a `print()` debug statement, not in extraction or parsing, and it destroyed the already-successful result.

## Acceptance Criteria
- [x] Uploading a receipt whose store name or item text contains non-Latin-1 characters (e.g. Turkish `İ`) completes successfully instead of failing with an unhandled encoding error
- [x] The receipt is saved with its extracted data intact, not discarded
- [x] Re-uploading the documented repro file (`20260817_005650.jpg`, LC Waikiki receipt) after the fix and a server restart succeeds, confirmed by the account holder

## Notes / Context
**Confirmed real-world repro case**: uploading `20260817_005650.jpg` (LC Waikiki, a Turkish brand) failed. `server.log` showed:

```
Starting receipt processing for file: 20260817_005650.jpg
Saved temporary file: ./uploads\1786921619_20260817_005650.jpg
Extracting data from receipt: ./uploads\1786921619_20260817_005650.jpg
Received response from Claude
Unexpected error: 'charmap' codec can't encode character 'İ' in position 68: character maps to <undefined>
Deleted temporary file: ./uploads\1786921619_20260817_005650.jpg
```

Root cause, traced end to end:
1. Claude successfully extracted the receipt (`Received response from Claude`) — extraction itself was never the problem.
2. `app/services/llm_service.py`'s `extract_receipt_data()` then runs `print(f"Response preview: {response_text[:200]}...")` to log a preview.
3. `run_server.py` redirects `sys.stdout` to `server.log` via `open('server.log', 'w', buffering=1)`, with no `encoding=` argument — on Windows this defaults to `cp1252`, which cannot encode `İ` (U+0130, Turkish dotted capital I).
4. The resulting `UnicodeEncodeError` was caught by the broad `except Exception as e:` handler at the bottom of `extract_receipt_data()`, logged as `"Unexpected error: ..."`, and **re-raised**.
5. `routes.py`'s upload handler caught the re-raised exception, deleted the temp upload, and redirected — discarding the receipt data Claude had already successfully produced.

Net effect: any receipt containing non-Latin-1 text (foreign store names, accented characters, etc.) would always fail on Windows, regardless of whether extraction succeeded — a pure logging bug masquerading as an extraction failure.

## Implementation Notes
**Completed**: 2026-08-17

**`run_server.py`** — one-line fix: added `encoding='utf-8'` to the `sys.stdout` redirect:
```python
sys.stdout = open('server.log', 'w', buffering=1, encoding='utf-8')
```
`sys.stderr` is aliased to the same stream (`sys.stderr = sys.stdout`), so this also fixes traceback logging for the same class of error.

No changes needed to `llm_service.py` or `routes.py` — the extraction and error-handling logic were already correct; the bug was purely in how the log file was opened.

**Verification**: killed stale Python processes, cleared `app/__pycache__`, restarted via `run_server.py` (`Start-Process` per the project's standard restart procedure), then re-uploaded `20260817_005650.jpg` through the running app. Upload succeeded and the receipt was saved. Confirmed by the account holder.

**Tests**: none added — this is a Windows-console-encoding-specific bug with no existing test harness around log output encoding; verification was a real end-to-end re-upload.
