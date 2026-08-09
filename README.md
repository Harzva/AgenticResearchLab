<div align="center">

# AgenticResearchLab

### Turn projects and topics into evidence-grounded agentic research.

[Mobile Agentic AI](awesome/mobile-agentic-ai/README.md) · [Research Method](docs/research-method.md) · [Contributing](CONTRIBUTING.md)

</div>

AgenticResearchLab is a local-first research tool for answering a concrete question:

> Given a software project or research topic, what would make it a necessary, novel, and testable agentic research contribution?

It combines curated topic catalogs, an external paper corpus, deterministic retrieval, and rejection-oriented research checks. It does **not** treat “add multiple agents” as novelty and does not invent papers, repositories, results, or venues.

## First built-in topic

The first vertical is [Awesome Mobile Agentic AI](awesome/mobile-agentic-ai/README.md), covering:

- Android and smartphone agents
- mobile GUI perception and grounding
- planning, memory, reflection, and multi-agent coordination
- personalization, privacy, safety, and environmental injection
- AndroidWorld, AndroidLab, MobileWorld, B-MoCA, LlamaTouch, and related benchmarks
- verified open-source implementations and cross-platform GUI foundations

The catalog currently contains over 25 evidence-linked resources and can be searched without an API key.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

arl topics
arl search "mobile privacy safety"
arl analyze-topic "A privacy-aware mobile assistant with long-term memory"
arl corpus-search "mobile agent memory"
```

Analyze a local project:

```bash
arl analyze-repo /path/to/project --output outputs/
```

Inspect an external paper manifest:

```bash
arl corpus-stats --manifest /path/to/conference-agent-papers-2026.csv
```

Generate the Awesome page from the machine-readable catalog:

```bash
arl awesome mobile-agentic-ai \
  --write awesome/mobile-agentic-ai/README.md
```

## What the MVP produces

`analyze-topic` and `analyze-repo` currently generate deterministic, evidence-linked opportunity reports containing:

1. nearest papers, benchmarks, and repositories;
2. detected Agentic capability dimensions;
3. missing research dimensions;
4. candidate method upgrades;
5. novelty, baseline, evaluation, ablation, cost, and reproducibility gates.

The deterministic layer is intentional: it provides a testable base before optional LLM synthesis is introduced.

## Architecture

```text
project/topic
    │
    ├── repository/topic profiler
    ├── curated topic catalog
    └── external paper manifest/PDF index
             │
             ▼
      evidence retrieval
             │
             ▼
  capability and gap analysis
             │
             ▼
 novelty + experiment + rejection gates
             │
             ▼
   agentic research opportunity report
```

## Repository layout

```text
AgenticResearchLab/
├── awesome/mobile-agentic-ai/   # Human-readable curated theme
├── docs/                        # Research and contribution contracts
├── src/agentic_research_lab/    # CLI, catalog, corpus, and analysis engine
├── tests/                       # Deterministic unit tests
└── agentic-research-lab.toml.example
```

## Local knowledge base

Raw PDFs and vector indexes belong outside this public repository. Point the CLI to a manifest using:

```bash
export ARL_CORPUS_MANIFEST=/path/to/conference-agent-papers-2026.csv
arl corpus-stats
```

Alternatively, copy `agentic-research-lab.toml.example` to
`agentic-research-lab.local.toml` and set the manifest there. The local file is ignored by Git.

The following are ignored by Git:

- PDFs and raw/private corpora
- vector and SQLite indexes
- generated reports
- `.env` and credentials

## Research standard

A proposed method is not considered Agentic merely because it calls an LLM or assigns role names. A credible proposal should establish:

- an observe–decide–act–verify loop;
- a reason the loop is necessary for the task;
- a concrete gap against the nearest work;
- executable success and failure criteria;
- fair single-model and deterministic-workflow baselines;
- component and inference-compute ablations;
- cost, latency, safety, and reproducibility reporting.

## Status

Early MVP. The next milestones are full-text chunking, citation-aware retrieval, project-to-paper schemas, optional model providers, and reproducible experiment-plan generation.

## License

MIT. Individual linked projects and papers retain their own licenses and copyrights.
