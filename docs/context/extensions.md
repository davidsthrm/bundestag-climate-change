# Extensions and future work

Purpose: ideas that are **not decided** and not part of the course project's scope.
An idea moves to [decisions.md](decisions.md) only after both team members agreed in an issue or PR.
Do not implement anything from this file without such an agreement.

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
- The protocol analyser is agreed and no longer listed here: see [decisions.md](decisions.md).
- Live monitor: scheduled update from Bundestag Open Data after each sitting week.
- Release of the gold set, the labelled windows and the best model; short workshop paper.
- Constraints for anything public: EM-DAT does not allow redistribution; stance labels per MP are
  model output about real people and need visible error rates and a link to the source speech.
