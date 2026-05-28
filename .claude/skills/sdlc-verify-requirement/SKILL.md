---
name: sdlc-verify-requirement
description: Verify that a backlog requirement (SP file) is sound, testable, and implementable. Use when the user asks to verify, review, or check a requirement. Accepts the SP number as a parameter (e.g. /sdlc-verify-requirement 001).
---

## Verifying a SP requirement

When invoked with a parameter (e.g. `/sdlc-verify-requirement 001`), follow these steps.

### Step 1 — Locate the SP file

The parameter is the SP number (e.g. `001`). Find the matching file:
- First look in `backlog/SP-{number}-*.md`
- If not found, also check `backlog/done/SP-{number}-*.md`
- If still not found, stop and report: "SP-{number} not found in backlog/ or backlog/done/"

### Step 2 — Read the file

Read the full content of the SP file.

### Step 3 — Evaluate against three criteria

Assess the requirement against each criterion independently:

#### Criterion 1: Sound — Is the requirement clear and well-defined?
- Is the Description filled in (not a placeholder)?
- Is it unambiguous? Could two developers interpret it differently and build different things?
- Is the scope of the deliverable clear — do you know exactly what will exist when it's done?
- Is there enough context to understand WHY this is needed?

#### Criterion 2: Testable — Can "done" be verified objectively?
- Are the Acceptance Criteria present and filled in (not placeholder text like "Observable, testable condition 1")?
- Is each criterion observable/measurable? ("Clicking Delete removes the receipt from the list" — not "it works correctly")
- Could someone who didn't write the requirement independently verify each criterion?

#### Criterion 3: Implementable — Can this be built in a single focused session?
- Is it atomic? (One clear deliverable, not multiple features bundled together)
- Is the scope appropriate? (Not so broad it would take days; not so trivial it's a single line)
- Are there obvious blockers or missing dependencies that would prevent starting?

### Step 4 — Report the verdict

**If all three criteria pass, report:**

```
SP-NNN: {Title}
Verdict: READY TO IMPLEMENT

Sound:           PASS — {one sentence confirming why}
Testable:        PASS — {one sentence confirming why}
Implementable:   PASS — {one sentence confirming why}
```

Then continue to Step 5.

**If any criterion fails, report:**

```
SP-NNN: {Title}
Verdict: NEEDS IMPROVEMENT

Sound:           PASS / FAIL
Testable:        PASS / FAIL
Implementable:   PASS / FAIL

Issues:
- [{Criterion}] {Specific problem observed in the file}
- [{Criterion}] {Specific problem observed in the file}

Suggested improvements:
- {Concrete, actionable change — quote or rewrite the problematic section}
- {Concrete, actionable change}
```

Be specific: quote the actual text that is unclear or missing, and suggest exact wording where possible.

Stop here if the verdict is NEEDS IMPROVEMENT — do not update the file status.

### Step 5 — Update status to Ready (only on PASS)

Edit the SP file: change the line
  `**Status**: Open`
to
  `**Status**: Ready`

Confirm to the user: "Status updated to Ready."
