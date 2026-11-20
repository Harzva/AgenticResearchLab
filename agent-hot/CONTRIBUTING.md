# 参与 AgentHot

登录 GitHub 后，可直接在公开仓库提出建议。

- [推荐一条内容](https://github.com/Harzva/AgenticResearchLab/issues/new?template=agenthot-submit.yml)。附论文、作者的仓库或官方报告，以及一条可在原始来源中核对的证据。
- [报告错误](https://github.com/Harzva/AgenticResearchLab/issues/new?template=agenthot-correct.yml)。说明受影响的页面、发现的问题和建议修正。从站内打开表单时可带上条目 ID 或专题日期和页面地址。
- [提交复现记录](https://github.com/Harzva/AgenticResearchLab/issues/new?template=agenthot-reproduction.yml)。可提议一项小实验，也可为已有笔记补充实际运行或独立复核的证据。

请使用公开来源和自己的简短概述。分享 PDF 时附公开链接。GitHub Issue、PR 和评论可公开阅读。

## 实验笔记

从详情页打开提交表单时，GitHub 会收到关联精选 ID、笔记 ID 和正式页面地址。直接投稿时填写关联精选，有现成笔记再附其 ID。 [浏览实验笔记](https://harzva.online/agent-hot/?view=community)

- 待复现的笔记记录一个明确的核对目标、固定版本的材料、最小操作步骤和预期产物。核对论文、评分清单或运行入口后，实验结果仍记为未评估。
- 公开运行记录要附代码、数据或评分清单版本、实验环境、实际命令、比较标准、观察结果以及与该次运行对应的公开证据。依赖安装或环境启动失败时记录阻塞和日志，科学结果仍记为未评估。完成可比较的运行后，可按证据记录复现、部分复现或未复现。
- 独立复核由另一位参与者完成。附公开回执、日期和核对范围，并指向同一实验版本及运行证据。

## 提交修改

可以先用 Issue 对齐内容，也可以直接发 PR。修订精选时编辑 `agent-hot/content/items.json`，保留已有条目的 ID，并在 PR 描述附相关 Issue 和原始来源。修订每日专题时，请在 Issue 中说明具体日期、来源及改法，由维护者复核线上记录。

复现投稿先在 Issue 中讨论。维护者核对公开范围和证据后，由 PR 写入 `agent-hot/content/community.json`。新笔记 ID 以关联精选 ID 开头，补充已有笔记时沿用其 ID。GitHub Issue 是投稿入口，公开笔记以审阅并合并的数据为准。

在本地可构建供审阅的静态版本。输出目录使用新目录或空目录。

```bash
python3 agent-hot/build.py --out build/agent-hot-preview
PYTHONDONTWRITEBYTECODE=1 python3 agent-hot/test_daily.py -v
```

构建会生成 `community/index.json` 和每条笔记的 `community/<id>.md`。例如 PaperBench 笔记可分别从索引和 Markdown 读取。 [JSON 索引](https://harzva.online/agent-hot/community/index.json) · [PaperBench 笔记](https://harzva.online/agent-hot/community/paperbench-aqua-test-split.md)

## 审阅与发布

1. 维护者核对事实、原始链接和重复条目，需要补充时会在 Issue 或 PR 中说明。
2. PR 的 Build AgentHot 工作流运行校验并提供 `agent-hot` 静态预览产物。审阅者可从成功的运行记录下载检查。 [现有工作流](../.github/workflows/agent-hot.yml)
3. 审阅通过后，维护者合并 PR，并从 `main` 的成功构建发布到正式站点。 [发布手册](DEPLOY.md)
