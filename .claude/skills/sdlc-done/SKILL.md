---
name: sdlc-done
description: Close a completed story in the ShoppingTracker project. Use when the user asks to close, finish, complete, or mark done a story or SP item (e.g. /sdlc-done 003). Checks off acceptance criteria, auto-generates implementation notes, updates status to Done, moves the file to backlog/done/, commits, and asks for confirmation before pushing to GitHub. Assumes the story has been implemented and tested (status In Testing).
---

## Closing a SP story

When invoked with a parameter (e.g. `/sdlc-done 003`), follow these steps in order.

### Step 1 — Locate the SP file

The parameter is the SP number (e.g. `003`). Find the matching file:
- Look in `backlog/SP-{number}-*.md`
- If not found, stop and report: "SP-{number} not found in backlog/"
- If found but status is not `In Testing`, stop and report: "SP-{number} has status '{status}' — only stories In Testing can be closed. Run /sdlc-implement {number} first."

Read the full SP file content.

### Step 2 — Check off all acceptance criteria

Replace every unchecked criterion:
  `- [ ]` → `- [x]`

### Step 3 — Auto-generate Implementation Notes

Run `git diff HEAD` and `git status` to see all changes made since the last commit. Also read the list of new or modified files.

Based on what you find, write concise implementation notes covering:
- Date completed (today's date)
- Each file changed and what was done in it (one line per file or logical group)
- Any migration scripts run, data changes made, or dependencies added
- Test summary: number of tests added and final pass count

Replace the placeholder in the SP file:
  `_Filled in when the work is done, before moving to backlog/done/._`
with the generated notes.

### Step 4 — Update status to Done

Edit the SP file: change
  `**Status**: In Testing`
to
  `**Status**: Done`

### Step 5 — Move to done directory

Move the SP file from `backlog/SP-{number}-*.md` to `backlog/done/SP-{number}-*.md`.

### Step 6 — Stage all changes and generate a commit message

Stage all changed and new files relevant to this story (source code, tests, migration scripts, the SP file itself). Use `git add` on specific files rather than `git add .`.

Generate a commit message with this structure:
```
SP-{number}: {Title}

{2–4 bullet points summarising what was built — one per major area of change}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Show the user the full commit message and the list of staged files before committing. Ask: "Commit and push? (yes / no)"

Wait for the user's reply.

### Step 7 — Commit

If the user confirms, create the commit with the generated message.

### Step 8 — Confirm before pushing

Ask the user: "Push to origin/main? (yes / no)"

Wait for the user's reply. If confirmed, run:

```
git push origin main
```

Report the result. If the push succeeds, print:

```
SP-{number}: {Title}
Status: Done

Committed and pushed to origin/main.
Story closed.
```
