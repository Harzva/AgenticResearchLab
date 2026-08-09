# AgenticResearchLab contributor rules

- Keep the core CLI dependency-light and runnable on Python 3.11+.
- Every research recommendation must cite catalog evidence; never invent papers, venues, code, or metrics.
- Raw PDFs, private corpora, vector indexes, API keys, cookies, and local absolute paths must not be committed.
- Add public resources to `src/agentic_research_lab/data/topics.json`, then regenerate the Awesome page.
- Mark missing code or uncertain publication status explicitly instead of guessing.
- Run `python -m unittest discover -s tests -v` before accepting changes.
