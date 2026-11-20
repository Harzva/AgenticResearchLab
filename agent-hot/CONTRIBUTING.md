# 参与 AgentHot

登录 GitHub 后，可直接在公开仓库提出建议。

- [推荐一条内容](https://github.com/Harzva/AgenticResearchLab/issues/new?template=agenthot-submit.yml)。附论文、作者的仓库或官方报告，以及一条可在原始来源中核对的证据。
- [报告错误](https://github.com/Harzva/AgenticResearchLab/issues/new?template=agenthot-correct.yml)。说明受影响的页面、发现的问题和建议修正。从站内打开表单时可带上条目 ID 或专题日期和页面地址。

请使用公开来源和自己的简短概述。分享 PDF 时附公开链接。GitHub Issue、PR 和评论可公开阅读。

## 提交修改

可以先用 Issue 对齐内容，也可以直接发 PR。修订精选时编辑 `agent-hot/content/items.json`，保留已有条目的 ID，并在 PR 描述附相关 Issue 和原始来源。修订每日专题时，请在 Issue 中说明具体日期、来源及改法，由维护者复核线上记录。

在本地可构建供审阅的静态版本。输出目录使用新目录或空目录。

```bash
python3 agent-hot/build.py --out build/agent-hot-preview
PYTHONDONTWRITEBYTECODE=1 python3 agent-hot/test_daily.py -v
```

## 审阅与发布

1. 维护者核对事实、原始链接和重复条目，需要补充时会在 Issue 或 PR 中说明。
2. PR 的 Build AgentHot 工作流运行校验并提供 `agent-hot` 静态预览产物。审阅者可从成功的运行记录下载检查。 [现有工作流](../.github/workflows/agent-hot.yml)
3. 审阅通过后，维护者合并 PR，并从 `main` 的成功构建发布到正式站点。 [发布手册](DEPLOY.md)
