---
name: sdlc-implement
description: Implement a backlog story end-to-end for the ShoppingTracker project. Use when the user asks to implement, develop, build, or work on a story or SP item (e.g. /sdlc-implement 003). Covers the full cycle: stopping the app, planning, coding, testing, and starting the app again. Assumes the story status is Ready (already verified).
---

## Implementing a SP story

When invoked with a parameter (e.g. `/sdlc-implement 003`), follow these steps in order.

### Step 1 — Locate the SP file

The parameter is the SP number (e.g. `003`). Find the matching file:
- Look in `backlog/SP-{number}-*.md`
- If not found, stop and report: "SP-{number} not found in backlog/ — only stories in the backlog can be implemented."
- If found but status is not `Ready`, stop and report: "SP-{number} has status '{status}' — only Ready stories can be implemented. Run /sdlc-verify-requirement {number} first."

Read the full SP file content.

### Step 2 — Stop the application

Kill any running Python server processes to avoid stale state:

```powershell
Get-WmiObject Win32_Process | Where-Object { $_.Name -like "python*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

### Step 3 — Mark status as In Progress

Edit the SP file: change
  `**Status**: Ready`
to
  `**Status**: In Progress`

Report to the user: "Starting implementation of SP-{number}: {title}"

### Step 4 — Plan the implementation

Enter plan mode to design the implementation approach. Explore the codebase thoroughly to understand existing patterns before proposing changes. The plan should cover all files to be created or modified, the approach for each acceptance criterion, and any migration or data changes needed.

Present the plan for user approval before proceeding.

### Step 5 — Implement the changes

Execute the approved implementation plan. Follow the existing code style and patterns in the project. After making changes, clear the Python cache:

```powershell
Get-ChildItem -Recurse ".\app" -Filter "__pycache__" | Remove-Item -Recurse -Force
```

### Step 6 — Plan the tests

Enter plan mode again to design tests for the new functionality. Tests must:
- Cover all acceptance criteria from the SP file
- Not make real Anthropic API calls (mock the LLM)
- Follow the patterns in `conftest.py` and the existing test files under `tests/`

Present the test plan for user approval before proceeding.

### Step 7 — Implement the tests

Write the tests according to the approved plan.

### Step 8 — Start the application

Clear cache and start the server:

```powershell
Get-ChildItem -Recurse ".\app" -Filter "__pycache__" | Remove-Item -Recurse -Force

Start-Process `
  -FilePath ".\venv\Scripts\python.exe" `
  -ArgumentList "run_server.py" `
  -WorkingDirectory (Get-Location).Path `
  -WindowStyle Hidden
```

Wait 3 seconds, then verify the server is up:

```powershell
Start-Sleep -Seconds 3
Invoke-WebRequest -Uri "http://127.0.0.1:5001/" -UseBasicParsing -TimeoutSec 5 | Select-Object -ExpandProperty StatusCode
```

A response of `200` confirms the server is running.

### Step 9 — Run the tests

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

If any tests fail, fix them before proceeding. Do not move to the next step with a failing test suite.

### Step 10 — Mark status as In Testing

Edit the SP file: change
  `**Status**: In Progress`
to
  `**Status**: In Testing`

Report a summary to the user:
```
SP-{number}: {title}
Status: In Testing

Implementation complete. Server running at http://127.0.0.1:5001
Tests: {N} passed

Next step: run /sdlc-done {number} when testing is confirmed.
```
