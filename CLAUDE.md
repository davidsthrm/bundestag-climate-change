# CLAUDE.md

Part 1: general coding guidelines, adapted from forrestchang/andrej-karpathy-skills (MIT, commit 2c60614).
Part 2: project rules. **Where the two conflict, Part 2 wins.**

# Part 1: Coding guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

# Part 2: Project rules

## Project
Student project for a university NLP module (paper + presentation, team of two).
Research question: does the Bundestag's attention to climate change follow the physical climate
signal (temperature Germany + global) or public attention (Google Trends)? Period 2004-01 (start
of Google Trends) to today, monthly. Extension: party comparison incl. stance (pro climate action / neutral / contra).
See `README.md` for pipeline and data sources, `config/` for settings, keywords and URLs.

## Working rules
- Do NOT edit files, download data, install packages or run git commands (commit, branch, push)
  on your own. Explain what you want to do and why, show the proposed change, act only when asked.
- Read-only actions (reading files, inspecting data in `data/`, checks that write nothing) are fine.
- No personal names (lecturer, students) anywhere in the repo.
- One branch per task, merged into `main` via pull request. Raw data is never committed.
- Settings (time window, keywords, URLs) live in `config/`, not hard-coded in scripts.
- Every download is logged in `data/raw/MANIFEST.csv` (URL, access time, SHA-256).

## Key decisions
- Speeches: PoliCorp-GermaParl2-PLUS (15th–20th Bundestag, ends 18 Mar 2025) is the main corpus,
  incl. its party mapping.
- Speeches of the 21st Bundestag come from the official Bundestag Open Data XML and are converted
  into PoliCorp's format (same fields, sentence-level `text_raw`, party names mapped to PoliCorp
  labels), then merged. Validate the converter on 20th-Bundestag sessions present in both sources;
  check for overlap/gaps at the boundary.
- Interjections are excluded from the analysis.
- Open: unit of analysis. PoliCorp is sentence-level, `settings.yaml` still says "paragraph".
- Temperature anomalies are relative to 1991–2020, per calendar month (both DE and global).
