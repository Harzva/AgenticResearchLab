<div align="center">

# AgenticResearchLab

### Turn projects and topics into evidence-grounded agentic research.

[AgentHot](https://harzva.online/agent-hot/) · [Agent 论文知识库](https://harzva.online/agent-papers/) · [Mobile Agentic AI](awesome/mobile-agentic-ai/README.md) · [All 1,242 Agentic Papers](awesome/all-agentic-papers-2026/README.md) · [Upgrade Plan](docs/next-upgrade-plan.md) · [Research Method](docs/research-method.md) · [Contributing](CONTRIBUTING.md)

</div>

AgenticResearchLab is a local-first research tool for answering a concrete question:

> Given a software project or research topic, what would make it a necessary, novel, and testable agentic research contribution?

It combines curated topic catalogs, an external paper corpus, deterministic retrieval, and rejection-oriented research checks. It does **not** treat “add multiple agents” as novelty and does not invent papers, repositories, results, or venues.

## Agent 论文知识库

按论文发表的会议或期刊浏览，首批收录 CVPR、ICLR、ICML、AAAI、ECCV、IJCAI 和 TPAMI。图谱实线表示论文的发表来源，虚线依据题目或摘要中的技术关键词。科研工作台可找相近论文、保存对照清单，并生成检索、写作或实验计划。

把 [Agent 入口](https://harzva.online/agent-papers/llms.txt) 或论文详情中的 JSON 链接交给 Agent，即可获取书目、原文和已有的公网 PDF 地址。下载由原站提供。公开页面还提供 [JSON 目录](https://harzva.online/agent-papers/catalog.json) 和 [CSV 目录](https://harzva.online/agent-papers/catalog.csv)。

本地预览需要 Python 3.11+。从仓库根目录构建到新目录，然后在浏览器打开 `http://127.0.0.1:8080/`。

```sh
python3 knowledge-base/build.py --out build/agent-papers
python3 -m http.server 8080 --bind 127.0.0.1 --directory build/agent-papers
```

[公开数据来源与同步](knowledge-base/sources/README.md) · [GitHub 构建、部署与回滚](knowledge-base/DEPLOY.md)

## AgentHot

Agent 研究与开源热点。首期专题《Agent 怎么做科研？从找论文到跑实验》按找文献、提问题、做实验、看反馈再迭代组织。每条精选保留可核对的证据、验证方法和一手来源。

[每日专题](https://harzva.online/agent-hot/?view=daily) 每天北京时间 14:00 更新。新文献专题根据 arXiv 公开订阅源聚合。新文献不足时，会从不同研究方向轮换发布基础文献回顾。保留日期页及机器可读版本。

在 AgentHot 按 `Ctrl/⌘ + K` 搜索精选和每日专题。收藏保存在当前浏览器，可以导出 Markdown 资料单供自己或 Agent 使用。读者可以通过 GitHub 推荐研究或从对应页面提交纠错。

[专题归档](https://harzva.online/agent-hot/?view=archive) · [每日专题 RSS](https://harzva.online/agent-hot/daily/rss.xml) · [实验笔记](https://harzva.online/agent-hot/?view=community) · [Agent 入口](https://harzva.online/agent-hot/llms.txt) · [参与共建](agent-hot/CONTRIBUTING.md) · [十站对照](agent-hot/REFERENCES.md) · [构建与发布](agent-hot/DEPLOY.md)

## First built-in topic

The first vertical is [Awesome Mobile Agentic AI](awesome/mobile-agentic-ai/README.md), covering:

- Android and smartphone agents
- mobile GUI perception and grounding
- planning, memory, reflection, and multi-agent coordination
- personalization, privacy, safety, and environmental injection
- AndroidWorld, AndroidLab, MobileWorld, B-MoCA, LlamaTouch, and related benchmarks
- verified open-source implementations and cross-platform GUI foundations

The curated catalog contains 32 evidence-linked resources and can be searched without an API key.

## Complete 2026 conference corpus

[Awesome Conference Agent and Agentic Papers 2026](awesome/all-agentic-papers-2026/README.md)
contains every one of the **1,242** records in the connected conference manifest:

| Conference | Papers |
| --- | ---: |
| AAAI 2026 | 298 |
| ICLR 2026 | 316 |
| ICML 2026 | 460 |
| IJCAI 2026 | 162 |
| ECCV 2026 | 6 |

Every record has an official public page. The catalog also preserves all available PDF,
OpenReview, arXiv, author, abstract, track, selection, and provenance fields. Missing fields
remain explicit instead of being inferred. See the [corpus schema](docs/corpus-schema.md).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

arl topics
arl search "mobile privacy safety"
arl analyze-topic "A privacy-aware mobile assistant with long-term memory"
arl corpus-search "mobile agent memory"
arl corpus-search "GUI agent safety" --conference ICML --limit 20
arl corpus-show icml-2026-64842
```

Analyze a local project:

```bash
arl analyze-repo /path/to/project --output outputs/
```

Inspect an external paper manifest:

```bash
arl corpus-stats --manifest /path/to/conference-agent-papers-2026.csv
```

Rebuild the sanitized public catalog and all conference pages:

```bash
arl corpus-build --manifest /path/to/conference-agent-papers-2026.csv
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
├── awesome/all-agentic-papers-2026/ # Complete conference corpus pages
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

The committed catalog is sanitized and contains public metadata only. The following remain
outside Git:

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

Early MVP. The implementation sequence, architecture decisions, quality gates, and release
criteria are defined in the [comprehensive upgrade plan](docs/next-upgrade-plan.md).

## License

MIT. Individual linked projects and papers retain their own licenses and copyrights.
