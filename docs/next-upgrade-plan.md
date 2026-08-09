# AgenticResearchLab 全面升级计划

> 目标：把 AgenticResearchLab 从“论文目录 + 关键词报告生成器”升级为一个可追溯、可评测、可扩展的 Agentic Research Intelligence 系统。

> **文档状态：0.2 架构与历史实施基线。** 下一阶段的优先级、任务编号、质量指标和
> `0.2 Beta → 1.0 → 2.0` 发布门槛已经迁移到 [执行 Roadmap](ROADMAP.md)。下文的
> “当前主要缺口”保留为升级前问题记录，应结合实施快照阅读。

本文曾作为 `0.2` 的实施基线；其中的工作流、Schema、验收门槛与产物继续有效，
后续功能、Issue 和里程碑统一映射到新的执行 Roadmap。

## 实施快照（2026-08-09）

本轮已交付可运行的 `0.2.0` 全面升级 Beta：M0–M2 已达到退出条件，M3–M7
已形成端到端实现并进入 Beta。当前公开目录包含 1,242 篇论文、158 个显式代码
候选与 154 个在线验证通过的 GitHub 仓库；本机验证已将 989/989 个可用 PDF
解析为 30,909 个页码级 Chunk，并建立 1,242 个确定性向量、194 个实体和 4,816
条关系。CLI、本地 Dashboard/API、工程画像、Proposal 工作区、评测、CI、Schema
和 README 已同步。

仍未将 M8/1.0 标记为完成：现有 100 条检索集是确定性 smoke Gold，而不是人工
撰写的中英文语义 Gold；taxonomy 和 Proposal 引擎是规则型 Beta。发布时必须保留
这一限制说明，不能把 smoke 指标表述为通用语义检索质量。

## 1. 当前基线

仓库已经具备以下能力：

- 32 条人工精选的 Mobile Agentic AI 论文、基准与开源项目；
- 1,242 篇 AAAI、ICLR、ICML、IJCAI、ECCV 2026 Agent/Agentic 论文；
- 1,242 个公开论文主页、989 个直接 PDF、689 个 arXiv、315 个 OpenReview；
- 结构化 JSON、按会议拆分的 Awesome 页面和中文/英文词法检索；
- `analyze-topic`、`analyze-repo`、`corpus-search`、`corpus-show` 等基础 CLI；
- 本地 PDF、私有路径、公开元数据相互隔离的安全边界。

当前主要缺口：

1. `code` 字段仍为零覆盖，即使部分摘要已经包含 GitHub 地址；
2. 检索主要依赖标题、摘要和词法重叠，没有论文全文、章节和页码级证据；
3. 没有论文之间的任务、方法、基准、失败模式与引用关系；
4. 仓库分析只读取 README 和少量配置文件，不能建立完整的工程能力画像；
5. 创新建议仍是固定维度模板，不能输出最近工作对照、可证伪 Claim 和实验矩阵；
6. 没有专门评测检索质量、创新建议质量和引用正确性的测试集；
7. 没有稳定的增量同步、失败恢复、数据版本和变更审计机制。

## 2. 目标产品

升级后的系统应完成一条闭环：

```text
论文源 / PDF / 代码仓库 / 用户工程 / 研究选题
                    │
                    ▼
        采集、规范化、去重、来源验证
                    │
                    ▼
     全文切分 + 代码画像 + 研究实体抽取
                    │
                    ▼
    词法检索 + 向量检索 + 关系图谱召回
                    │
                    ▼
 最近工作矩阵 + 能力缺口 + 失败机制分析
                    │
                    ▼
  Agentic 必要性判断 + 创新候选生成与否决
                    │
                    ▼
 Claim、方法蓝图、Baseline、实验和复现计划
```

最终用户应能输入：

- 一个自然语言选题；
- 一个本地工程目录；
- 一个 GitHub 仓库地址；
- 一篇种子论文或一组论文；

并得到：

- 最接近的论文、代码和基准；
- 每个结论对应的论文、章节、页码或仓库证据；
- 当前方案与最近工作的差异矩阵；
- 3–5 个按可信度排序的 Agentic 创新候选；
- 每个候选的必要性、Claim、方法结构、实验、消融、成本和否决条件；
- 可保存、可重放、可继续迭代的研究工作区。

## 3. 产品原则和边界

### 3.1 必须遵守

- Evidence first：没有证据的内容必须标记为假设，不能写成事实。
- Agentic necessity first：先证明固定工作流或单模型不足，再设计 Agent。
- Rejection before generation：先运行否决门槛，再扩写论文想法。
- Public-safe by default：公开仓库只保存公共元数据、许可允许的派生信息和短证据片段。
- Local-first：PDF、全文、向量、私有工程画像和模型密钥默认只保存在本机。
- Deterministic core：采集、清洗、索引、引用和评测必须可重放；LLM 只负责受约束的语义步骤。
- Missing is data：缺失作者、PDF、代码和摘要时保留缺失状态，不进行猜测。

### 3.2 暂不进入本阶段

- 自动投稿、自动联系作者或自动发布研究结论；
- 自动运行来源不明的第三方代码；
- 在公开仓库提交原始 PDF 或整篇论文全文；
- 训练或微调大型模型；
- 以多 Agent 数量、Prompt 长度或推理次数本身作为创新性。

## 4. 目标架构

### 4.1 分层

| 层 | 职责 | 建议实现 |
| --- | --- | --- |
| Source | 会议、arXiv、OpenReview、PDF、GitHub、本地工程 | Connector 接口 |
| Normalize | 统一 ID、去重、状态、来源和链接 | JSON Schema + dataclass |
| Enrich | 代码、作者、领域标签、任务、基准、方法、限制 | 规则优先，模型可选 |
| Local Store | 全文、Chunk、工程画像、任务运行状态 | SQLite + 本地文件目录 |
| Search | BM25/FTS5、向量、字段过滤、重排 | SQLite FTS5 + 可选 embeddings |
| Knowledge | Paper–Method–Task–Benchmark–Repo–Failure 关系 | SQLite 关系表，暂不引入图数据库 |
| Research | 最近工作、缺口、Claim、方法、实验与否决 | 可审计 Pipeline |
| Interface | CLI、Python API、后续本地 Web UI | Typer/FastAPI 可在后续引入 |
| Evaluation | 检索、引用、代码匹配、报告质量、回归 | 固定 Gold Set + CI |

### 4.2 数据边界

公开 Git 数据：

- 论文公共元数据；
- 已验证代码仓库地址与验证证据；
- 研究分类体系；
- 聚合统计和 Awesome 页面；
- 不包含大段版权全文的派生标签与结构化摘要。

本机 `.arl/` 数据：

```text
.arl/
├── catalog.sqlite3       # 论文、实体、关系和运行状态
├── fulltext/             # PDF 提取文本，不提交 Git
├── chunks/               # 带页码和章节信息的 Chunk
├── indexes/              # FTS/向量索引
├── repos/                # 用户明确允许缓存的代码仓库
├── workspaces/           # 选题和工程分析工作区
└── logs/                 # 不含密钥的结构化运行日志
```

## 5. 核心数据模型 v2

### 5.1 Paper

在当前字段上新增：

- `canonical_id`、`doi`、`version`、`updated_at`；
- `topics`、`tasks`、`environments`、`modalities`；
- `agentic_components`：planning、memory、reflection、tools、multi-agent、verification 等；
- `methods`、`benchmarks`、`datasets`、`metrics`；
- `claims`、`limitations`、`failure_modes`；
- `artifacts`：paper、pdf、project、code、dataset、demo；
- `evidence`：来源 URL、页码、章节、抽取方式和置信度；
- `enrichment_status`：pending、verified、ambiguous、not-found、rejected。

### 5.2 Repository

- `url`、`canonical_owner_repo`、`license`、`default_branch`；
- `paper_ids`、`verification_method`、`verification_evidence`；
- `languages`、`frameworks`、`entrypoints`、`tests`、`environments`；
- `installability`、`reproducibility_assets`、`last_verified_at`；
- `status`：verified、probable、ambiguous、unavailable、archived。

### 5.3 ProjectProfile

- 产品目标、用户、输入、输出和作用环境；
- 已有模块、数据流、外部工具和模型调用；
- 状态、反馈、记忆、规划、验证和恢复机制；
- 测试、指标、部署约束、安全和隐私边界；
- 确定性 Baseline 与潜在 Agentic 必要性。

### 5.4 ResearchProposal

- `problem`、`target_failure_condition`、`agentic_necessity`；
- `nearest_work` 和逐项差异；
- `falsifiable_claim`；
- `method_blueprint` 和模块责任；
- `baseline_ladder`、`experiment_matrix`、`ablation_matrix`；
- `metrics`、`budget`、`risk`、`rejection_gates`；
- 每个事实和判断的 Evidence 引用。

## 6. 工作流 A：代码仓库富化

这是下一批最优先实现的功能。

### 6.1 候选发现顺序

1. 从摘要、官方页和 arXiv 文本中抽取显式 GitHub/GitLab/项目主页地址；
2. 从论文标题、arXiv ID、OpenReview ID 和作者信息查询候选仓库；
3. 检查候选仓库 README、Citation、论文 ID 和作者组织；
4. 对多候选或匿名仓库标记 `ambiguous`，不自动公开；
5. 只有通过验证的仓库写入公共 `code` 字段。

### 6.2 验证等级

| 等级 | 条件 | 是否进入公开目录 |
| --- | --- | --- |
| Verified | 论文/作者主页直接链接，或仓库明确包含标题/论文 ID | 是 |
| Probable | 标题、作者、时间高度匹配，但缺少直接互链 | 默认否 |
| Ambiguous | 存在多个候选或身份冲突 | 否 |
| Rejected | 明确不相关、镜像、聚合仓库或恶意地址 | 否 |
| Not found | 完成搜索但未发现候选 | 保留状态 |

### 6.3 验收标准

- 能从当前摘要中抽取并验证显式代码链接；
- 代码匹配 Gold Set 精确率必须达到 100%，再追求覆盖率；
- 每条代码链接保存验证来源和验证方法；
- 重跑不会产生重复仓库或覆盖人工裁决；
- 网络失败可恢复，并具有速率限制和缓存。

## 7. 工作流 B：全文与引用感知知识库

### 7.1 PDF 管线

```text
resolve → download/checksum → extract → detect sections → chunk → index → validate
```

每个 Chunk 至少保存：

- `paper_id`、`chunk_id`；
- 页码范围、章节标题和段落序号；
- 文本、语言、Token 数；
- PDF checksum、提取器版本；
- 是否来自正文、表格、图注、参考文献或附录。

### 7.2 技术选择

- 第一解析器：PyMuPDF，可作为 `fulltext` 可选依赖；
- OCR 只作为扫描 PDF 的失败回退，不进入默认安装；
- 存储：SQLite 元数据 + 本机压缩文本文件；
- 词法检索：SQLite FTS5；
- 向量检索：可选 `sentence-transformers`，索引不提交 Git；
- 引用展示必须包含论文、章节、页码和公共 URL。

### 7.3 验收标准

- 对已有 989 个 PDF，至少 95% 能产生非空、可定位页码的全文；
- 抽样 100 篇检查标题、摘要、章节和页码一致性；
- 同一 PDF checksum 重跑不重复解析；
- 失败记录包含稳定错误码，可单独重试；
- 报告中的证据可跳转到对应论文和页码。

## 8. 工作流 C：混合检索与研究关系图

### 8.1 检索阶段

1. Query 解析：任务、环境、方法、Agentic 组件、失败条件和会议过滤；
2. Candidate generation：标题/摘要 FTS、全文 FTS、向量召回、关系召回；
3. Dedup：论文版本、标题变体和重复项目统一；
4. Rerank：任务、环境、失败机制优先于表面关键词；
5. Evidence pack：返回可引用 Chunk，而不是只有论文标题。

### 8.2 研究关系

最小关系集合：

```text
Paper ─proposes→ Method
Paper ─evaluates_on→ Benchmark
Paper ─uses→ Dataset
Paper ─targets→ Task
Method ─contains→ AgenticComponent
Method ─fails_under→ FailureCondition
Paper ─implemented_by→ Repository
Paper ─extends/compares_with→ Paper
Project ─shares_gap_with→ FailureCondition
Proposal ─supported_by/contradicted_by→ Evidence
```

### 8.3 评测目标

- 建立不少于 100 个中英文真实研究 Query 的 Gold Set；
- Recall@20 ≥ 0.85；
- nDCG@10 ≥ 0.75；
- Mobile Agentic 子集必须单独报告；
- 每次修改检索策略都输出前后对比，禁止只展示成功案例。

## 9. 工作流 D：Agentic 创新引擎

### 9.1 六阶段 Pipeline

1. **Problem framing**：明确任务、环境、用户、输入输出和失败代价；
2. **Non-agent baseline**：构造最强固定流程或单模型方案；
3. **Nearest-work matrix**：按任务、环境、组件、监督和评测对照最近工作；
4. **Gap mechanism**：把“没有做过”升级为可解释的失败机制；
5. **Proposal generation**：生成不同复杂度的候选，而不是一个答案；
6. **Rejection tournament**：用必要性、新颖性、可测量性、成本、安全和复现门槛淘汰候选。

### 9.2 每个候选必须输出

- 一句话问题定义；
- Agentic 必要性证明；
- 最近 3–10 项工作及差异；
- 可证伪 Claim；
- Observe–Decide–Act–Verify 数据流；
- 组件接口和状态所有权；
- Baseline 阶梯；
- 主实验、消融、鲁棒性和失败分析；
- Token、延迟、能耗或调用成本预算；
- 隐私、安全和不可逆操作控制；
- “什么结果会证明这个方向不值得继续”。

### 9.3 候选评分

```text
score = evidence_strength
      × agentic_necessity
      × novelty_distance
      × testability
      × reproducibility
      × expected_impact
      ÷ implementation_cost
      ÷ safety_risk
```

评分只用于排序，不能替代证据和人工判断。

## 10. 工作流 E：工程到论文

### 10.1 工程画像升级

从当前 README 级扫描升级为：

- 语言、框架、模块、入口、测试、CI、数据集和部署方式；
- 模型调用、工具调用、状态存储和外部服务；
- 关键接口、数据流和失败处理；
- 移动工程额外解析 Android Manifest、Gradle、Swift Package、Xcode、Flutter 配置；
- 识别已有 Agentic 组件和实际缺失能力。

### 10.2 安全要求

- 默认只读；
- 遵守 `.gitignore`，跳过 `.env`、凭据、构建物和大文件；
- 不把源码全文发送给远程模型，除非用户显式启用；
- 报告只引用必要的本地文件和行号；
- 不自动执行第三方项目脚本。

### 10.3 输出

- `project-profile.json`；
- `nearest-work.md`；
- `agentic-necessity.md`；
- `proposal-candidates.md`；
- `experiment-plan.md`；
- `rejection-report.md`。

## 11. Mobile Agentic AI 专项升级

把现有 32 条精选目录升级为领域知识视图：

- 环境：Android、iOS、跨 App、动态通知、WebView、设备设置；
- 感知：截图、UI Tree、Accessibility、OCR、多模态 grounding；
- 控制：点击、输入、手势、系统 API、端云工具；
- Agentic 能力：规划、记忆、反思、探索、恢复、多 Agent；
- 风险：环境注入、越权、隐私泄露、误操作、不可逆动作；
- 效率：端侧模型、端云路由、延迟、能耗、Token；
- 评测：AndroidWorld、AndroidLab、MobileWorld、B-MoCA、MobileBench 等。

专项产物：

- Mobile Agentic taxonomy；
- Benchmark/Environment 对照表；
- 论文–代码–基准覆盖矩阵；
- 典型失败模式库；
- 10 个经过否决门槛的高质量移动端创新候选；
- 可复用的 Mobile Agentic 实验设计模板。

## 12. CLI 和接口规划

建议逐步形成以下命令：

```bash
arl sync papers
arl enrich code --paper-id ...
arl fulltext build --missing-only
arl index build --lexical --embedding
arl retrieve "mobile agent privacy memory" --evidence
arl paper show <paper-id>
arl repo inspect /path/to/repo
arl compare <paper-id> <paper-id>
arl propose --topic "..." --workspace outputs/topic-name
arl reject outputs/topic-name/proposals.json
arl evaluate retrieval
arl evaluate proposals
arl serve
```

所有写操作需要支持：

- `--dry-run`；
- `--resume`；
- `--json`；
- 明确的退出码；
- 结构化运行摘要；
- 输入、版本和配置快照。

## 13. 评测与质量体系

### 13.1 数据测试

- ID 唯一性、URL 格式、Schema、计数和分页一致性；
- 私有路径、凭据和下载诊断不得进入公开数据；
- 增量导入前后记录不得无故减少；
- 人工验证的字段不能被低置信度自动结果覆盖。

### 13.2 检索测试

- 中英文 Query；
- 标题不共享关键词但任务相同的语义 Query；
- 负例和高相似度误召回；
- 会议、年份、环境和 Agentic 组件过滤；
- Recall、nDCG、MRR 和引用定位准确率。

### 13.3 Proposal 测试

- 是否给出最强非 Agent Baseline；
- 是否引用真正最近工作；
- Claim 是否可证伪；
- 增益是否可能完全来自更多推理算力；
- 实验是否覆盖消融、成本、安全和失败分析；
- 是否存在伪造论文、代码、指标或结果。

### 13.4 发布门槛

- 单元测试、集成测试、格式和安全扫描全部通过；
- 生成物与源数据一致；
- Wheel 包含公共目录但不包含本机数据；
- CLI 在无网络、无模型密钥时仍可完成目录检索；
- 任何联网或模型功能都可以显式关闭。

## 14. 分阶段实施路线

| 阶段 | 目标 | 主要产物 | 退出条件 |
| --- | --- | --- | --- |
| M0 基线固化 | 锁定 Schema、数据版本和回归集 | ADR、数据快照、Gold Set v0 | 当前能力可重复构建 |
| M1 代码富化 | 从零代码覆盖升级为证据验证的代码映射 | Repository schema、enricher、代码矩阵 | Gold Set 精确率 100% |
| M2 全文知识库 | 为可用 PDF 建立页码级 Chunk | PDF pipeline、FTS5、本机 Store | ≥95% 可用 PDF 解析成功 |
| M3 混合检索 | 词法、语义和关系融合 | Retriever、reranker、评测报告 | Recall@20 ≥0.85 |
| M4 研究图谱 | 建立任务、方法、基准和失败关系 | taxonomy、entity/edge tables | 抽样实体和关系可追溯 |
| M5 创新引擎 | 生成并否决可测量的研究候选 | Proposal schema、矩阵和报告 | 每个事实具有 Evidence |
| M6 工程到论文 | 深入分析本地/GitHub 工程 | ProjectProfile、适配器、报告包 | 真实工程端到端通过 |
| M7 产品化 | 本地 Web、工作区、导出与协作 | API/UI、版本化 workspace | CLI/API 结果一致 |
| M8 Release 1.0 | 稳定安装、文档、CI 和公开发布 | Wheel、release notes、示例 | 所有发布门槛通过 |

## 15. 建议八周执行顺序

| 周次 | 重点 | 可演示结果 |
| --- | --- | --- |
| 第 1 周 | M0 + Repository Schema | 数据版本、Gold Set、代码候选抽取 |
| 第 2 周 | M1 代码验证与 Awesome 更新 | 论文–代码映射和覆盖报告 |
| 第 3 周 | M2 PDF 下载状态与全文解析 | 可按页检索 989 篇可用 PDF |
| 第 4 周 | M3 FTS5、向量和混合重排 | 中英文 Evidence 检索 |
| 第 5 周 | M4 taxonomy 与关系抽取 | Mobile Agentic 关系视图 |
| 第 6 周 | M5 最近工作矩阵与 Claim 生成 | 可引用的创新候选报告 |
| 第 7 周 | M6 工程画像与实验计划 | 一个真实工程升级为论文方案 |
| 第 8 周 | M7 轻量本地 UI + 全量评测 | 可演示的本地 Research Lab |

周次是建议节奏；每个阶段是否完成以退出条件为准，而不是以时间为准。

## 16. 下一批立即执行任务

### P0：本轮之后立即开始

- [x] ARL-101：建立 `Paper v2`、`Repository`、`Evidence` JSON Schema；
- [x] ARL-102：为公共数据增加 `catalog_version` 和输入 checksum；
- [x] ARL-103：从 938 篇摘要中抽取 GitHub/GitLab/项目地址候选；
- [x] ARL-104：实现仓库验证器和人工裁决文件；
- [x] ARL-105：生成论文–代码覆盖率报告；
- [x] ARL-106：建立 100 条代码匹配 Gold Set；
- [x] ARL-107：增加 `arl enrich-code --dry-run --resume`；
- [x] ARL-108：确保自动结果不能覆盖人工验证结果。

### P1：代码富化稳定后

- [x] ARL-201：设计 `.arl/catalog.sqlite3`；
- [x] ARL-202：实现 PDF checksum、解析状态和错误码；
- [x] ARL-203：实现 PyMuPDF 页码级提取；
- [x] ARL-204：实现章节检测和 Chunk Schema；
- [x] ARL-205：建立 SQLite FTS5 索引；
- [x] ARL-206：实现 Evidence 引用格式；
- [ ] ARL-207：建立全文抽样质量集。

### P2：检索稳定后

- [x] ARL-301：建立 Agentic taxonomy 和实体抽取器；
- [x] ARL-302：实现混合召回和字段过滤；
- [ ] ARL-303：建立 100 条中英文检索 Gold Set；
- [x] ARL-304：实现最近工作差异矩阵；
- [x] ARL-305：实现 Claim、Baseline 和实验 Schema；
- [x] ARL-306：实现候选否决 Tournament；
- [x] ARL-307：建立 Proposal 质量回归集。

## 17. 全面完成的定义

只有同时满足以下条件，全面升级才算完成：

1. 论文、代码、全文、实体和关系能够增量同步且可重放；
2. 检索结果能定位到论文页码、章节或代码证据；
3. 代码链接全部具有验证来源，没有自动猜测进入公开目录；
4. 工程分析不只依赖 README，并且默认不泄露源码和密钥；
5. 每个创新候选包含最近工作、Agentic 必要性、Claim、实验和否决条件；
6. 检索与 Proposal 都有固定评测集和量化回归报告；
7. 无网络、无模型密钥时仍能完成本地检索和确定性分析；
8. 公共仓库、Wheel、本机 Store 和生成报告之间的安全边界清晰；
9. README、Schema、CLI 帮助、示例和 CI 与实现保持一致；
10. 一个真实 Mobile 项目能够端到端生成可引用、可执行、可否决的 Agentic Paper 研究方案。
