# AgenticResearchLab contributor rules

- Keep the core CLI dependency-light and runnable on Python 3.11+.
- Every research recommendation must cite catalog evidence; never invent papers, venues, code, or metrics.
- Raw PDFs, private corpora, vector indexes, API keys, cookies, and local absolute paths must not be committed.
- Add public resources to `src/agentic_research_lab/data/topics.json`, then regenerate the Awesome page.
- Rebuild the exhaustive conference catalog with `arl corpus-build`; never hand-copy local download fields into it.
- Keep unknown authors, abstracts, PDFs, and code links explicit instead of guessing them.
- Run `python -m unittest discover -s tests -v` before accepting changes.
