# AgentHot 十站参考

2026-11-20 核对各站公开首页、栏目或官方文档。账号功能的观察来自官方说明和可见入口。

| 网站 | 公开页面观察 | AgentHot 采用判断 |
| --- | --- | --- |
| **CodexRadar** | 公告、短快讯和实测各占一段。内容分区可以直达，正式分榜给测试时间、分数、耗时、费用和实测原作。测试规则变化也有明确说明。 [首页](https://codexradar.com/) · [模型实测](https://codexradar.com/#iq) · [新闻](https://codexradar.com/#news) | 首页把专题、短动态、实测记录分层。测试条目把时间窗、条件、代价和原始材料放在结论旁边。 |
| **RSDL** | 首页自动发现论文，论文栏目索引公众号的中文编辑内容。来源、方向和有代码是筛选入口。浏览器实测论文详情有 DOI 链接，首页同时显示收录日期与最近同步。 [RSDL 首页](https://rsdl.info/) · [论文栏目](https://rsdl.info/papers) | 同一论文用稳定 ID 连接新鲜线索、正式解读和知识库。列表写清源发布日期与收录日期。 |
| **Hugging Face Daily Papers** | 首页有每日、每周、每月及邮件订阅入口。卡片公开提交者、机构和社区互动数字，标题进入独立论文页。 [Daily Papers](https://huggingface.co/papers) | 以日期浏览精选，保留 RSS 跟订。互动数字带来源和统计窗口，使用独立的证据标签显示论文状态。 |
| **GitHub Trending** | 今日、本周、本月并列。仓库项能看到简述、语言、累计星标和该窗口的新增星标。 [GitHub Trending](https://github.com/trending) | 项目卡给可点击仓库与版本。有可靠窗口数据时才显示新增关注，累计和本期分别标注。 |
| **OpenReview** | 官方论坛指南同屏呈现评审、回复、决定、修改记录和可见范围，并提供按类别排序和筛选。会议直链在本次浏览先显示加载，单文直链遇到浏览器验证。 [论坛指南](https://docs.openreview.net/getting-started/using-the-new-forum-page) · [ICLR 2026](https://openreview.net/group?id=ICLR.cc%2F2026%2FConference) | 详情把预印本、正式论文、评审与版本分开列出。期刊或会议状态以可核对的决定或出版记录填写。 |
| **Semantic Scholar** | 官方帮助页说明研究订阅跟随资料夹，用户可在账户内分别打开和关闭邮件提醒。此次查看的是公开说明。 [研究订阅帮助](https://webflow.semanticscholar.org/faq/research-feed-alert) | 全站 RSS 保持易找。若增加分主题订阅，筛选条件可以保存，订阅偏好可随时调整。 |
| **Hacker News** | 密集列表保留原站和独立讨论链接，附投稿时距、积分与评论数。历史页面可按日、月、年回看并标注 UTC。 [实时列表](https://news.ycombinator.com/) · [历史](https://news.ycombinator.com/front) | 快讯可用更紧凑的单行列表。原文和讨论分开，日期归档统一口径。社区讨论可补充线索，结论链接回可核证据。 |
| **Product Hunt** | 发布归档给可跳到具体日期的日历，并有 Newsletter 入口。官方更新记录说明榜单分数与社区投票、讨论有关。 [发布归档](https://www.producthunt.com/leaderboard) · [产品更新](https://www.producthunt.com/changes) | 为日更专题提供过去任意一天的稳定入口。首期先做最近日期列表，长历史再采用月历。 |
| **arXiv** | 人工智能近期条目按日期分页。每项带稳定编号、作者、分类和 PDF，部分同时提供 HTML。页面还可跳转当日新增与更新。 [cs.AI 近期论文](https://arxiv.org/list/cs.AI/recent) | 标题下显示预印本 ID 和版本或日期来源，一个入口直达官方全文。把修订挂到原条目下。 |
| **Cool Papers** | 分类页的条目连续展示作者、摘要和 UTC 发布时间。条目旁可见 PDF、复制链接、Kimi 和关联论文入口。 [Cool Papers 人工智能分类](https://papers.cool/arxiv/cs.AI) | 把复制引用、原文、关联材料和 Agent 读取动作集中在详情的固定位置，检索列表保留阅读所需摘要。 |

## 本轮优先落地

1. **首页先说明今天读什么。** 当期专题置顶，后接简短发现流和可筛选列表。主题、日期与原文入口始终好找。
2. **证据紧挨结论。** 条目写清研究问题、可复查的结果与最小验证动作。模型与实验对比给出同口径基线、版本、成本和时间窗口。
3. **读完能继续。** 详情提供论文、公开 PDF、作者代码、复现验证和相关工作。历史专题、RSS、JSON 和 Agent 可直接读取的 Markdown 共用同一条目链接。
4. **读者能看出数据的新旧。** 定期核对元数据并保留来源日期、收录时间和专题发布时间。公开关注度信号附测量窗口与来源，编辑精选说明选题和依据。
