# Extensions and future work

Purpose: ideas that are **not decided** and not part of the course project's scope.
An idea moves to [decisions.md](decisions.md) only after both team members agreed in an issue or PR.
Do not implement anything from this file without such an agreement.

## Proposed second goal: protocol analyser (to decide in the review of PR #20)
Different from the ideas below: this would become a goal of the project next to answering the
research question, and the main content of the deployment chapter.
- Input: one plenary protocol (XML or session number).
- The pipeline runs on it: convert, relevance filter, stance.
- Output page: whether climate was a topic and how much, which speakers and parties, and the
  stance per window with its text.
- Shows the NLP methods working on unseen input, not only charts of the finished analysis.
- Needs the relevance filter (#5) and the best stance method (#9–#13) first, so it comes last.
- If agreed: move to [decisions.md](decisions.md), add an issue, update the deployment line in
  [paper.md](paper.md).

## Analysis
- Split `contra` into kinds (e.g. denial, delay, cost, "solutions won't work"), following an
  existing claim taxonomy.
- Speaker-level panel via `speaker_id`: separate "MPs changed their position" from "the
  composition of parliament changed".
- Correct the time-series estimates for stance-classifier error, using the gold set as a
  probability sample (design-based supervised learning, prediction-powered inference).
- Report how much the LLM stance results change across prompts and models.

## Product (possible private extension after the course)
- Presentable, usable interface on top of the `viz/` app: clicking a month or party shows the
  speech windows behind the number, with a link to the protocol.
- Live monitor: scheduled update from Bundestag Open Data after each sitting week.
- Release of the gold set, the labelled windows and the best model; short workshop paper.
- Constraints for anything public: EM-DAT does not allow redistribution; stance labels per MP are
  model output about real people and need visible error rates and a link to the source speech.
