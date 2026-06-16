---
name: sdlc-list
description: List ShoppingTracker backlog stories with their status. Use when the user asks to list, show, or print stories or the backlog (e.g. /sdlc-list, /sdlc-list active, /sdlc-list done, /sdlc-list all). Accepts an optional filter parameter.
---

## Listing SP stories

When invoked (e.g. `/sdlc-list` or `/sdlc-list done`), follow these steps.

### Step 1 — Determine the filter

Read the optional parameter (if provided). Apply this mapping:

| Parameter | Stories to include |
|-----------|-------------------|
| `active` (default, or no parameter) | Open, Ready, In Progress, In Testing |
| `done` | Done |
| `all` | All statuses |

If an unrecognised parameter is given, report: "Unknown filter '{value}'. Use: active, done, or all." and stop.

### Step 2 — Collect SP files

- Active and all stories: read `**Status**` from every `backlog/SP-*.md` (skip `TEMPLATE.md`)
- Done and all stories: read `**Status**` from every `backlog/done/SP-*.md`

For each file, extract:
- **ID** — the number from the filename (e.g. `SP-003` → `003`)
- **Title** — the `# SP-NNN: {Title}` heading from the file content
- **Status** — the `**Status**: {value}` line from the file content

### Step 3 — Sort

Apply this status order (lowest index first):

1. Ready
2. In Progress
3. In Testing
4. Open
5. Done

Within each status group, sort by ID ascending.

### Step 4 — Print the table

Output the list in this format:

```
ID      Title                                        Status
------  -------------------------------------------  -----------
003     Grouping Receipts by Month                   Ready
004     Filtering Purchases                          Open
001     Add Support for Currencies                   Done
```

Column widths: ID = 6, Title = 43, Status = 11. Truncate title with `…` if over 43 chars.

If no stories match the filter, print: "No stories found for filter '{filter}'."
