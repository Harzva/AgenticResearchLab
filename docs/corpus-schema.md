# Conference paper corpus schema v2

`conference_agent_papers_2026.json` is the complete, public-safe projection of the external
conference manifest.

## Top-level fields

- `schema_version`: version of this public representation (`2.0`).
- `catalog_version`: content-derived catalog version.
- `id`, `title`, `description`: catalog identity and scope.
- `source`: sanitized projection type, record count, and SHA-256 of the input manifest.
- `summary`: record counts and metadata coverage.
- `papers`: all sanitized paper records.

## Paper fields

- `id`, `canonical_id`: stable `{conference}-{year}-{paper_id}` identifier.
- `conference`, `year`, `paper_id`, `title`: source identity.
- `doi`, `version`, `updated_at`: nullable canonical-version metadata; unknown values remain null.
- `authors`: ordered author names, or an empty list when unavailable.
- `abstract`: full source abstract, or null when unavailable.
- `track`: conference track, or null when unavailable.
- `selection`: selection rule, status, and provenance from the source manifest.
- `links`: public addresses for the official page, official PDF, resolved PDF, OpenReview,
  arXiv abstract, arXiv PDF, and verified code repository.
- `topics`, `tasks`, `environments`, `modalities`, `agentic_components`: deterministic
  taxonomy labels derived from public title and abstract evidence.
- `methods`, `benchmarks`, `datasets`, `metrics`, `claims`, `limitations`,
  `failure_modes`: structured research fields; unknown values remain empty arrays.
- `artifacts.code_candidates`: explicit repository URLs extracted from official metadata.
- `evidence`: structured provenance references.
- `enrichment_status`: independent state for code, taxonomy, and local full-text enrichment.

All link keys are present. Unknown values use null rather than guessed URLs.

## Repository catalog

`code_repositories_2026.json` contains every explicit repository candidate, including
negative verification evidence. A repository appears in a paper's `links.code` only when its
live status is `verified` or `archived`.

- `paper_extraction_status` counts paper-level discovery outcomes.
- `repository_status` counts canonical repository verification outcomes.
- `verification` records the paper source page and extraction method.
- `last_verified_at`, `license`, `default_branch`, `archived`, and `languages` come from the
  GitHub API when available.

The persistent `code_link_decisions.json` file makes unavailable and manually adjudicated
candidates reproducible during offline rebuilds.

## Local Evidence store

The public catalog does not contain PDF text. `arl index-build` and `arl fulltext-build` create
`.arl/catalog.sqlite3` locally with paper metadata, FTS5 indexes, page-aware chunks, PDF
checksums, extraction runs, entities, relations, and optional vectors. Evidence responses may
include `paper_id`, `chunk_id`, section, page range, source URL, excerpt, and score.

## Public-safety contract

The exporter never publishes:

- local PDF paths;
- download errors or local diagnostics;
- credentials, cookies, or environment values;
- raw private notes or chat logs.

`downloaded_path` and `download_error` are explicitly rejected by catalog validation. Every
non-null link must use HTTP or HTTPS, and every paper must have an official public page.

The same rule applies to generated evaluation artifacts: aggregate counts and public IDs may be
committed, while PDFs, extracted full text, vectors, local project profiles, credentials, and
absolute machine paths remain under the ignored `.arl/` boundary.
