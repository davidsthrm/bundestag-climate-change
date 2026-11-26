---
marp: true
paginate: true
title: Heat Without Debate?
---

<!-- Skeleton for the 20-min talk (#16). Outline follows CRISP-DM like the paper.
     Research question and hypotheses: take them from README.md when filling in (single source). -->

# Heat Without Debate?
## Parliamentary Attention to Climate Change in the German Bundestag

2004 – 2026 · NLP module

---

# Research question

<!-- from README.md#research-question -->
TODO

---

# Data: text meets structured signals

- Plenary speeches 2004–2026: **206,915 speeches**, **5.14 M sentences**
- Physical signal: temperature anomaly (GISTEMP, DWD), disasters (EM-DAT)
- Public attention: Google Trends (DE)
- Join: one monthly panel

---

# Relevance filter

- Keyword dictionary, substring match
- **54,664** climate-relevant sentences (1.06 %)
- **2,408** speeches with climate as main topic

TODO: precision check after human review

---

# Stance: three methods

1. Lexicon + TF-IDF
2. Embeddings + classifier
3. LLM

TODO: gold set, κ, macro-F1

---

# Time series

TODO: attention vs. Trends vs. temperature

---

# Results & robustness

TODO

---

# Conclusion

TODO
