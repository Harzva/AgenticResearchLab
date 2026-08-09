# Conference paper corpus schema

`conference_agent_papers_2026.json` is the complete, public-safe projection of the external
conference manifest.

## Top-level fields

- `schema_version`: version of this public representation.
- `id`, `title`, `description`: catalog identity and scope.
- `summary`: record counts and metadata coverage.
- `papers`: all sanitized paper records.

## Paper fields

- `id`: stable `{conference}-{year}-{paper_id}` identifier.
- `conference`, `year`, `paper_id`, `title`: source identity.
- `authors`: ordered author names, or an empty list when unavailable.
- `abstract`: full source abstract, or null when unavailable.
- `track`: conference track, or null when unavailable.
- `selection`: selection rule, status, and provenance from the source manifest.
- `links`: public addresses for the official page, official PDF, resolved PDF, OpenReview,
  arXiv abstract, arXiv PDF, and verified code repository.

All link keys are present. Unknown values use null rather than guessed URLs.

## Public-safety contract

The exporter never publishes:

- local PDF paths;
- download errors or local diagnostics;
- credentials, cookies, or environment values;
- raw private notes or chat logs.

`downloaded_path` and `download_error` are explicitly rejected by catalog validation. Every
non-null link must use HTTP or HTTPS, and every paper must have an official public page.
