# Human Evaluation Guide

This guide defines the maintainer workflow for ARL-401, ARL-402, and ARL-403. The committed
files are annotation scaffolds, not completed Gold Sets. Automated generation may select public
paper candidates, but it must never invent human queries, judgments, reviewer agreement, or
adjudication.

## Evaluation layers

| Layer | Suite | Purpose | Merge/release behavior |
| --- | --- | --- | --- |
| Required | `smoke` | Deterministic engineering regression | Must pass on every push and PR |
| Scheduled | `smoke` + scaffold validation | Detect drift and preserve reports | Runs weekly and on demand |
| Manual | `human` | Semantic, page, and citation quality | Blocks Stable release until reviewed |

The `human` suite is currently `0.1.0-draft`. `arl eval-validate human` must return a structurally
valid but non-ready result. This is expected until all minimum sample counts pass independent
annotation and adjudication.

## Create or inspect the scaffolds

```bash
# Preview a fresh version in the ignored local workspace.
arl eval-scaffold --output .arl/evaluation-seed --fulltext-limit 100

arl eval-validate smoke --require-ready
arl eval-validate human
```

The repository already contains the current draft. The command refuses to overwrite an existing
target; do not use `--force` on active annotation files. It is reserved for maintainers who have
verified that a generated draft contains no human work.

The scaffold command produces:

```text
evals/
├── suites/
│   ├── smoke-v1.json
│   └── human-v1.draft.json
└── human/
    ├── fulltext_quality_v1.draft.json
    ├── semantic_retrieval_v1.draft.json
    └── citation_quality_v1.draft.json
```

The full-text draft contains 100 deterministic, conference-balanced public paper candidates.
Its page, Chunk, extraction, and review fields remain empty. Retrieval and citation drafts remain
empty because their natural-language queries and Claim–Evidence judgments must be authored by
maintainers.

## Common annotation contract

Every human dataset carries:

- `schema_version`, dataset `version`, stable `id`, and `task`;
- exact corpus ID, catalog version, Schema version, source checksum, and paper count;
- `review_status`, which remains `draft` until final adjudication;
- a minimum sample count and an annotation policy requiring two independent annotators;
- per-example `annotations` and an `adjudication` object;
- explicit null or missing judgments instead of guessed values.

Use pseudonymous maintainer IDs such as `reviewer-a`; do not place email addresses, chat logs, local
paths, or private notes in public datasets.

## ARL-401 — Full-text quality

For each seeded paper, locate the matching local Chunk without copying its text into Git. Record:

- public `paper_id`, PDF URL, page range, and non-sensitive Chunk ID;
- whether extraction succeeded;
- whether the extracted document title matches the catalog paper;
- whether the stored page is correct;
- whether the Chunk boundary preserves a coherent section or paragraph;
- a controlled error category when any judgment fails.

Recommended error categories are `download`, `encrypted`, `empty-text`, `ocr-needed`,
`page-offset`, `header-footer`, `broken-boundary`, and `other`. Both annotators work independently;
the adjudicator then writes the final booleans and sets `adjudication.status` to `resolved`.

## ARL-402 — Bilingual semantic retrieval

Maintainers must author at least 120 natural research queries. The set should include Chinese and
English, synonym/paraphrase queries, cross-language retrieval, negated constraints, compositional
requirements, and difficult negatives. Do not derive a query by copying the target paper title.

Each example records:

- `language`: `zh`, `en`, or the deliberately tested cross-language direction;
- a natural `query`;
- one or more `relevant_paper_ids`;
- `difficulty` and tested `phenomena`;
- two independent relevance judgments and a resolved adjudication.

The release thresholds are `Recall@20 ≥ 0.85` and `nDCG@20 ≥ 0.75`. Results must also be inspected
by language and failure category; an aggregate score cannot hide a failed Chinese or cross-language
slice.

## ARL-403 — Citation quality

Maintainers author at least 100 Query–Claim–Evidence audits. Each example records the query, Claim,
cited paper, cited pages, support label, paper correctness, and page correctness. The support label
must distinguish `support`, `partial`, and `not-support`.

The release thresholds are at least 98% paper accuracy and 95% page accuracy. A correct paper with
the wrong page fails page accuracy; a topically related passage that does not support the exact
Claim must not be marked `support`.

## Promote a draft to reviewed

Promotion is a deliberate maintainer operation:

1. Complete the minimum number of examples with two distinct annotators each.
2. Resolve every adjudication and remove all null final judgments.
3. Run `arl eval-validate` and fix every structural or readiness error.
4. Change dataset provenance and `review_status` to `reviewed`; assign a non-draft semantic version.
5. Update the suite paths, suite version, and suite `review_status` together.
6. Run the human gate manually and inspect both JSON and Markdown reports.
7. Review the diff for secrets, private paths, copied full text, and personal reviewer data.

```bash
arl evaluate --suite human \
  --output .arl/evaluation/human-v1.json \
  --report .arl/evaluation/human-v1.md
```

Until these steps succeed, the Human Gate must remain blocked and the corresponding Roadmap items
must not be marked complete.

## Versioned reports and baselines

```bash
arl evaluate --suite smoke \
  --output evals/latest_metrics.json \
  --report evals/latest_metrics.md

arl evaluate --suite smoke \
  --baseline evals/latest_metrics.json \
  --output .arl/evaluation/current.json
```

Reports bind results to the suite version, dataset version, catalog version, source checksum,
thresholds, and offline/store mode. A baseline comparison contains metric values and deltas but
does not persist the baseline's local filesystem path.
