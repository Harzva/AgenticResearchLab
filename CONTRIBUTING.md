# Contributing

## Adding a mobile-agent resource

Edit `src/agentic_research_lab/data/topics.json` and provide:

- a stable unique ID;
- title, year, kind, scope, and concise factual summary;
- tags useful for retrieval;
- an authoritative paper or project URL;
- official author-linked code URL when one exists;
- the detected license, or `license-not-declared` / `license-review-required`.

Do not copy abstracts verbatim. Summaries should be short factual paraphrases.

Then regenerate and verify:

```bash
arl awesome mobile-agentic-ai --write awesome/mobile-agentic-ai/README.md
python -m unittest discover -s tests -v
arl evaluate
python scripts/validate_repository.py
python scripts/check_public_safety.py
```

## Scope

- `mobile`: methods and systems that operate smartphones/tablets.
- `mobile-benchmark`: mobile-specific environments, datasets, and evaluations.
- `cross-platform-gui`: foundational GUI work with demonstrated relevance to mobile agents.
- `meta`: reading lists and ecosystem maps.

General HCI, mobile networking, or app-testing papers do not qualify unless autonomous agent behavior is central.

## Public-repository safety

Never commit raw PDFs, private notes, chat logs, API keys, cookies, `.env` files, local absolute paths, or generated private indexes.

## Rebuilding the complete paper corpus

The full conference catalog and its Awesome pages are generated artifacts:

```bash
arl corpus-build --manifest /path/to/conference-agent-papers-2026.csv
python -m unittest discover -s tests -v
```

The exporter deliberately removes `downloaded_path` and `download_error`. Do not manually add
local paths to the public JSON. Code links may be added only when they point to an official or
author-linked repository; leave `code` null when a repository has not been verified.

Repository verification exceptions belong in
`src/agentic_research_lab/data/code_link_decisions.json`. Rebuilds must preserve negative and
manual decisions as audit evidence, and must never promote an unavailable candidate into
`links.code`.
