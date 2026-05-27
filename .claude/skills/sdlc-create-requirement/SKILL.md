---
name: sdlc-create-requirement
description: Create a new backlog requirement (SP file) for the ShoppingTracker project. Use when the user asks to create a requirement, add a backlog item, or start a new user story.
---

## Creating a new SP requirement

When invoked, follow these steps in order.

### Step 1 — Ask the user for two things

Ask in plain text (a single message):
- **Name**: a short title for the requirement (e.g. "Delete receipt", "Add search filter")
- **Description**: 1–3 sentences explaining what needs to be done and why

Wait for the user's reply before continuing.

### Step 2 — Read the current SP counter

Read `CLAUDE.md` and find the line `**Last SP number: NNN**`.
Next SP number = NNN + 1, zero-padded to 3 digits (e.g. 0→001, 1→002, 12→013).

### Step 3 — Derive the filename slug

Transform the name the user provided:
1. Lowercase everything
2. Replace spaces with hyphens
3. Remove any character that is not a letter, digit, or hyphen
4. Trim leading/trailing hyphens

Target file: `backlog/SP-NNN-{slug}.md`

### Step 4 — Create the SP file

Write `backlog/SP-NNN-{slug}.md` using this exact structure,
filling in the SP number, title, and description:

```
# SP-NNN: {Title}

**Priority**: High | Medium | Low
**Status**: Open

## Description
{Description from user}

## Acceptance Criteria
- [ ] Observable, testable condition 1
- [ ] Observable, testable condition 2

## Notes / Context
Background, links, constraints, design sketches.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
```

### Step 5 — Update the counter in CLAUDE.md

In `CLAUDE.md`, change the line:
  `**Last SP number: NNN**`
to:
  `**Last SP number: NNN+1**`   (zero-padded to 3 digits)

### Step 6 — Confirm to the user

Report:
- File created: `backlog/SP-NNN-{slug}.md`
- Counter updated from NNN → NNN+1
- Reminder: open the file to fill in Priority, Acceptance Criteria, and Notes before starting implementation
