const terms = new Map([
  ["移动端", "mobile GUI smartphone Android"], ["具身", "embodied navigation robotics"],
  ["科研", "scientific research discovery"], ["检索", "retrieval search evidence"],
  ["实验", "experiment benchmark evaluation"], ["医疗", "medical clinical healthcare"],
  ["代码", "code software debugging"], ["记忆", "memory reflection"],
  ["多智能体", "multi-agent coordination"], ["语言", "language multilingual"],
  ["金融", "finance financial economics"], ["教育", "education tutoring learning"],
]);

const commonWords = new Set(["agent", "agents", "for", "and", "the", "with", "using", "study"]);

export function findRelatedPapers(papers, topic, limit = 8) {
  let expanded = topic.toLowerCase();
  for (const [label, keywords] of terms) {
    if (topic.includes(label)) expanded += ` ${keywords}`;
  }
  const tokens = [...new Set(expanded.match(/[a-z0-9]{2,}(?:-[a-z0-9]{2,})?|[\p{Script=Han}]{2,}/gu) ?? [])]
    .filter(token => !commonWords.has(token));
  if (tokens.length === 0) return [];
  return papers.map(paper => {
    const title = paper.title.toLowerCase();
    const body = `${paper.abstract ?? ""} ${paper.summary_zh ?? ""}`.toLowerCase();
    const matches = tokens.filter(token => title.includes(token) || body.includes(token));
    const score = matches.reduce((sum, token) => sum + (title.includes(token) ? 3 : 1), 0);
    return { paper, score, matches };
  }).filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score || b.paper.year - a.paper.year || a.paper.title.localeCompare(b.paper.title))
    .slice(0, limit);
}

function oneLine(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim();
}

function cite(paper, index) {
  const route = paper.routes?.find(item => item.evidence);
  const evidence = route && route.evidence ? `\n  - 线索（标题或摘要） ${oneLine(route.evidence)}` : "";
  return `[${index + 1}] ${oneLine(paper.title)} (${paper.venue.toUpperCase()} ${paper.year ?? "年份待核"})` +
    `\n  - 原文 ${paper.paper_url ?? "待核验"}` +
    (paper.pdf_url ? `\n  - PDF ${paper.pdf_url}` : "") +
    (paper.code_url ? `\n  - 代码 ${paper.code_url}` : "") + evidence;
}

export function makeResearchBrief({ topic, papers, mode }) {
  const objective = oneLine(topic) || "描述你的研究问题、目标场景和约束";
  const headings = { search: "文献检索计划", writing: "相关工作写作提纲", experiment: "可复现实验计划" };
  const modeSections = {
    search: [
      "1. 把研究问题拆成任务、场景、成功标准和约束。写下检索用的中英文同义词。",
      "2. 按会议或期刊查询基线工作，记录检索式、时间范围和纳入标准。沿论文参考文献补充已有方法。",
      "3. 用原文核对纳入理由。为每篇论文写明任务、方法、数据、评测以及支持该判断的页码。",
      "4. 记录检索遗漏和证据缺口。PDF 缺失时保留原文链接并标记需要确认的字段。",
    ],
    writing: [
      "1. 用一句话界定问题和场景。说明哪些相近问题不在本研究范围内。",
      "2. 按可核对的方法对齐目标、输入、工具、记忆、反馈和评测。每项结论引用原文及页码。",
      "3. 逐项比较最接近的工作。把已证实的差异、尚无证据的差异和待实验的假设分开写。",
      "4. 写出可实证检验的研究问题，标记缺失的基线、数据、结果和引用。",
    ],
    experiment: [
      "1. 写出可证伪假设和预先选定的主指标。冻结数据划分、基线、环境、硬件和运行预算。",
      "2. 先复现最接近的公开基线。记录代码版本、模型、随机种子、依赖、运行命令和异常。",
      "3. 每轮只改一个因素。记录对照与消融结果、失败案例、成本及波动，避免用测试集选参数。",
      "4. 事先写下保留或回退条件。报告所有运行和未复现结果，产出可重跑的实验记录。",
    ],
  };
  const sections = modeSections[mode] ?? modeSections.search;
  const lines = [`# ${headings[mode] ?? headings.search}`, "", "## 研究问题", "", objective, "",
    "## 工作步骤", "", ...sections, "", "## 待核对的论文", "",
    ...(papers.length ? papers.map(cite).join("\n\n").split("\n") : ["从目录选取论文后生成引文。"]),
    "", "## 记录字段", "",
    "- 论文与页码 / 任务及数据 / 对照基线 / 指标与成本 / 结果或失败原因 / 复现命令",
    "", "以上是工作计划。具体结论、实验效果与数据来源需由原文或实际运行支持。",
  ];
  return lines.join("\n");
}
