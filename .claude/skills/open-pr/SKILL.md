---
name: open-pr
description: Run the pre-PR checks and open a pull request in this project's format. Use when the user asks to open, create or prepare a pull request.
argument-hint: "[issue-number]"
---

Open a pull request for the current branch. Linked issue, if given: $ARGUMENTS

Only run this when the user asked for a PR. Never merge.

1. Checks. Show the user the result of each one; stop if one fails.
   - The branch is not `main` and is up to date with `origin/main`.
   - `git diff --stat main` shows only files that belong to the task.
   - No personal names (students, lecturer) and no account names in the changed files.
   - No file under `data/` is committed.
   - All relative links in changed Markdown files resolve.
   - If the PR changes a decision, data file, schema or method: the matching file in
     `docs/context/` is updated in the same PR.
   - New key numbers for the paper are in the README of the matching `results/` phase.
2. Optional: pass the diff and the issue text to the `reviewer` subagent and show its report.
3. PR body, in this order:
   - `## What changed and why`: short bullets, with `Closes #N` if the PR completes the issue.
   - `## Checks`: the results from step 1.
   - `## New, please confirm or change in review`: a numbered list of every choice in this PR
     that was not agreed in an issue or PR before. Write "Nothing new." if there is none.
   - No @-mentions in the body.
4. Request review from the other team member. Tell the user the PR link.
