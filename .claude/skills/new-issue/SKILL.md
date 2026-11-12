---
name: new-issue
description: Draft a GitHub issue in this project's format. Use when the user asks to create or draft an issue.
argument-hint: "[topic]"
---

Draft an issue about: $ARGUMENTS

1. Check the open issues first; if one already covers the topic, propose a comment there instead.
2. Draft in this format and show it to the user. Create the issue only after approval.
   - Title: short, starts with the action or the script (e.g. "Implement 02_relevance.py ...").
   - First line: one or two sentences on what and why, with links to related issues (`#N`).
   - `**Tasks**`: a checklist; each task is one checkable piece of work.
   - `**Open**` (optional): questions both team members still have to decide.
   - `**Depends on**` / `**Blocks**` (optional): issue numbers.
   - `**Done when**`: one sentence that can be verified.
   - One label for the CRISP-DM phase: `crisp-dm: 1 business understanding`,
     `crisp-dm: 2 data understanding`, `crisp-dm: 3 data preparation`, `crisp-dm: 4 modeling`,
     `crisp-dm: 5 evaluation` or `crisp-dm: 6 deployment`.
3. Keep the scope small: one issue is one branch and one PR. No personal names, no @-mentions.
