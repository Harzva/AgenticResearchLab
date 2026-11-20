const labels = new Map([["paper", "论文"], ["report", "技术报告"], ["repo", "开源仓库"]]);
const stages = new Map([["literature", "找文献"], ["hypothesis", "提问题"],
  ["experiment", "做实验"], ["iteration", "看反馈再迭代"]]);
const formatCount = new Intl.NumberFormat("zh-CN");
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const repository = "https://github.com/Harzva/AgenticResearchLab";
const savedStorage = "agenthot.saved.v1";
const $ = selector => document.querySelector(selector);
const feedList = $("#feed-list");
const entry = $("#entry");
const browse = $("#browse");
const searchForm = $("#search-form");
const searchDialog = $("#search-dialog");
const quickQuery = $("#quick-query");
const quickResults = $("#quick-results");
let saved = readSaved();
let feed;
let feedError = false;
let itemsById;
let state;
let archive;
let archiveError = false;
const dailyCache = new Map();
let dailyRender = 0;
const repos = new Map();
let checkingRepos = false;
let noticeTimer;

function esc(value) {
  return String(value ?? "").replace(/[&<>"\x27]/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "\x27": "&#39;",
  })[ch]);
}

function publicUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : "";
  } catch { return ""; }
}

function remote(label, value, css = "") {
  const url = publicUrl(value);
  return url ? `<a class="${css}" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : "";
}

function displayDate(value) { return String(value ?? "").slice(0, 10).replaceAll("-", "."); }
function paras(value) { return (Array.isArray(value) ? value : [value]).map(text => `<p>${esc(text)}</p>`).join(""); }
function route(changes = {}) {
  const next = { ...state, ...changes };
  const params = new URLSearchParams();
  if (next.view === "daily") {
    params.set("view", "daily");
    if (next.day) params.set("day", next.day);
  } else if (next.view === "archive") {
    params.set("view", "archive");
    if (next.mode) params.set("mode", next.mode);
    if (next.q) params.set("q", next.q);
  } else if (next.view === "saved") {
    params.set("view", "saved");
  } else {
    if (next.kind !== "all") params.set("kind", next.kind);
    if (next.stage) params.set("stage", next.stage);
    if (next.q) params.set("q", next.q);
    if (next.item) params.set("item", next.item);
    if (next.sort !== "recent") params.set("sort", next.sort);
  }
  return location.pathname + (params.size ? `?${params}` : "");
}

function navigate(url, focus = false) {
  const target = new URL(url, location.href);
  if (target.href !== location.href) history.pushState(null, "", target);
  state = getState();
  render(focus);
}

function getState() {
  const q = new URLSearchParams(location.search);
  const kind = q.get("kind");
  const stage = q.get("stage");
  const item = q.get("item");
  const day = q.get("day");
  const view = q.get("view");
  const sort = q.get("sort");
  const mode = q.get("mode");
  return {
    view: ["daily", "archive", "saved"].includes(view) ? view : "feed",
    kind: labels.has(kind) ? kind : "all",
    stage: stages.has(stage) ? stage : "",
    q: (q.get("q") ?? "").slice(0, 160),
    item: itemsById?.has(item) ? item : "",
    day: datePattern.test(day ?? "") ? day : "",
    mode: ["fresh", "review"].includes(mode) ? mode : "",
    sort: ["oldest", "featured"].includes(sort) ? sort : "recent",
  };
}

function internal(label, change, attributes = "") {
  return `<a href="${esc(route(change))}" data-route ${attributes}>${label}</a>`;
}

function words(value) { return value.toLowerCase().trim().split(/\s+/).filter(Boolean); }

function matches(kind = state.kind) {
  const query = words(state.q);
  const result = feed.items.filter(item =>
    (!state.stage || item.stage === state.stage) &&
    (kind === "all" || item.sources.some(source => source.type === kind)) &&
    query.every(word => item.searchText.includes(word)),
  );
  if (state.sort === "oldest") return result.reverse();
  if (state.sort === "featured") return result.sort((a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)));
  return result;
}

function tags(item) {
  const types = new Set(item.sources.map(source => source.type));
  return `<span class="source-badges">${[...labels].filter(([type]) => types.has(type))
    .map(([type, label]) => `<span class="badge badge-${type}">${label}</span>`).join("")}</span>`;
}

function githubSlug(value) {
  try {
    const url = new URL(value);
    const [owner, repository] = url.pathname.split("/").filter(Boolean);
    if (url.hostname !== "github.com" || !owner || !repository || !/^[\w.-]+$/.test(owner) || !/^[\w.-]+$/.test(repository)) return "";
    return `${owner}/${repository.replace(/\.git$/, "")}`;
  } catch { return ""; }
}

function repoStats(item) {
  if (state.kind !== "repo") return "";
  return item.sources.filter(source => source.type === "repo").map(source => {
    const slug = githubSlug(source.url);
    const stats = repos.get(slug);
    return stats ? `<p class="repo-status">${remote(slug, source.url)} <span>★ ${formatCount.format(stats.stars)} · 最近推送 ${esc(displayDate(stats.pushedAt))}</span></p>` : "";
  }).join("");
}

function saveKeyIsValid(key) {
  if (typeof key !== "string") return false;
  return (key.startsWith("paper:") && slugPattern.test(key.slice(6))) ||
    (key.startsWith("daily:") && datePattern.test(key.slice(6)));
}

function readSaved() {
  try {
    const values = JSON.parse(localStorage.getItem(savedStorage) ?? "[]");
    return new Set(Array.isArray(values) ? values.filter(saveKeyIsValid) : []);
  } catch { return new Set(); }
}

function syncSaved() {
  const count = $("#saved-count");
  count.hidden = saved.size === 0;
  count.textContent = saved.size || "";
  for (const button of document.querySelectorAll("[data-save]")) {
    const active = saved.has(button.dataset.save);
    button.setAttribute("aria-pressed", active);
    button.textContent = active ? "已收藏" : "收藏";
  }
}

function saveButton(key) {
  const active = saved.has(key);
  return `<button class="button saved-toggle" type="button" data-action="save" data-save="${esc(key)}" aria-pressed="${active}">${active ? "已收藏" : "收藏"}</button>`;
}

function correction(id, page) {
  const params = new URLSearchParams({ template: "agenthot-correct.yml", id,
    page: new URL(page, "https://harzva.online/").href });
  return remote("到 GitHub 纠错", `${repository}/issues/new?${params}`, "text-action");
}

function documentTools(path, share) {
  return `<a class="button" href="${path}" download>下载 Agent Markdown</a>
    <button class="button" type="button" data-action="copy" data-copy="${path}">复制给 Agent</button>
    <button class="button" type="button" data-action="copy" data-copy="${esc(share)}" data-share>复制页面链接</button>`;
}

function row(item) {
  const pdf = item.sources.find(source => source.pdf_url)?.pdf_url;
  const repo = item.sources.find(source => source.type === "repo");
  return `<article class="feed-row${item.featured ? " featured" : ""}">
    <div class="row-meta"><time datetime="${esc(item.published_at)}">${esc(displayDate(item.published_at))}</time>
      <span>${esc(stages.get(item.stage))}</span>${tags(item)}</div>
    <h3 class="row-head">${internal(esc(item.title), { item: item.id })}</h3>
    <p class="summary">${esc(item.summary)}</p>
    <div class="row-actions">${saveButton(`paper:${item.id}`)}
      ${pdf ? remote("公开 PDF ↗", pdf, "text-action") : ""}
      ${repo ? remote("GitHub ↗", repo.url, "text-action") : ""}</div>${repoStats(item)}
  </article>`;
}

function renderFilters() {
  const options = [["all", "全部精选"], ["paper", "论文"], ["report", "研究报告"], ["repo", "开源趋势"]];
  $("#filters").innerHTML = options.map(([kind, name]) => internal(`${name} <span class="filter-count">${matches(kind).length}</span>`, { kind, item: "" },
    `class="filter"${state.kind === kind ? ' aria-current="page"' : ""}`)).join("");
  $("#edition-steps").innerHTML = [...stages].map(([stage, label]) =>
    internal(label, { view: "feed", stage, item: "" }, state.view === "feed" && state.stage === stage ? 'aria-current="page"' : "")).join("");
  $("#query").value = state.q;
}

function renderBrowse() {
  const result = matches();
  entry.hidden = true;
  browse.hidden = false;
  const stageLabel = state.stage ? `${stages.get(state.stage)} · ` : "";
  $("#result-count").textContent = `${stageLabel}${result.length} 条精选`;
  $("#feed-actions").innerHTML = [
    state.stage || state.q || state.kind !== "all" ? internal("清除筛选", { kind: "all", q: "", stage: "", item: "" }) : "",
    state.kind === "repo" ? `<button class="button" type="button" data-action="repos"${checkingRepos ? " disabled" : ""}>${checkingRepos ? "正在查阅…" : "查看 GitHub 近况"}</button>` : "",
    `<label class="sort-control"><span class="sr-only">排序</span><select id="feed-sort">
      ${[["recent", "最新优先"], ["oldest", "最早优先"], ["featured", "编辑推荐"]]
    .map(([key, label]) => `<option value="${key}"${state.sort === key ? " selected" : ""}>${label}</option>`).join("")}
    </select></label>`,
  ].join("");
  feedList.innerHTML = feedError ? '<p class="empty">暂时无法载入精选。<a href="./">重试</a>，或直接查看 <a href="./feed.json">JSON</a>。</p>'
    : result.length ? result.map(row).join("") : '<p class="empty">没有符合条件的条目。可以清除筛选再试。</p>';
  feedList.setAttribute("aria-busy", "false");
  document.title = "AgentHot · Agent 研究与开源热点";
}

function openEntry(markup, focus) {
  browse.hidden = true;
  entry.hidden = false;
  entry.innerHTML = markup;
  if (focus) $("#entry-title")?.focus();
}

function sourceList(sources) {
  return `<ul class="source-list">${sources.map(source => `<li><span class="badge badge-${source.type}">${labels.get(source.type)}</span>
    ${remote(source.title, source.url, "source-link")}
    ${source.pdf_url ? remote("PDF", source.pdf_url, "source-link download-link") : ""}</li>`).join("")}</ul>`;
}

function renderEntry(item, focus) {
  const markdown = `./items/${encodeURIComponent(item.id)}.md`;
  const share = route({ view: "feed", kind: "all", stage: "", q: "", sort: "recent", item: item.id });
  openEntry(`<div class="entry-back">${internal("返回精选", { item: "" })}</div>
    <header><div class="row-meta"><time datetime="${esc(item.published_at)}">${esc(displayDate(item.published_at))}</time>
      <span>${esc(stages.get(item.stage))}</span>${tags(item)}</div>
      <h2 id="entry-title" tabindex="-1">${esc(item.title)}</h2><p class="summary">${esc(item.summary)}</p></header>
    <section class="entry-block"><h3>证据从哪里来</h3>${paras(item.evidence)}</section>
    <section class="entry-block"><h3>从哪一步开始复现</h3>${paras(item.reproduce)}</section>
    <section class="entry-block"><h3>论文、报告与代码</h3>${sourceList(item.sources)}</section>
    <div class="entry-tools">${saveButton(`paper:${item.id}`)}${documentTools(markdown, share)}
      ${correction(item.id, share)}<a href="/agent-papers/">浏览论文知识库</a></div>`, focus);
  document.title = `${item.title} · AgentHot`;
}

function modeLabel(mode) { return mode === "fresh" ? "新文献专题" : "基础文献回顾"; }
function editionTitle(title) { return title.replace(/^每日(?:专题|回顾)｜/, ""); }

function renderTeaser() {
  const latest = archive?.editions.find(item => item.date === archive.latest);
  if (!latest) {
    $("#daily-teaser").textContent = archiveError ? "暂时无法读取专题归档。" : "正在读取最新一期…";
    return;
  }
  const path = route({ view: "daily", day: latest.date });
  $("#today-title a").href = path;
  $("#today-title a").textContent = editionTitle(latest.title);
  $("#today-link").href = path;
  $("#today-date").textContent = displayDate(latest.date);
  $("#today-summary").textContent = `${modeLabel(latest.mode)} · ${formatCount.format(latest.count)} 条研究来源`;
  $("#daily-teaser").innerHTML = `<ol class="teaser-list">${archive.editions.slice(0, 4).map(item =>
    `<li><time datetime="${esc(item.date)}">${esc(displayDate(item.date).slice(5))}</time>
      ${internal(esc(editionTitle(item.title)), { view: "daily", day: item.date })}</li>`).join("")}</ol>`;
}

function archiveList() {
  if (!archive?.editions.length) return "";
  return `<section class="entry-block"><div class="panel-head"><h3>专题归档</h3>
    ${internal("全部往期 ↗", { view: "archive", mode: "", q: "" })}</div><ol class="daily-archive">${archive.editions.slice(0, 5).map(item => `<li>
    <time datetime="${esc(item.date)}">${esc(displayDate(item.date))}</time>${internal(esc(item.title), { view: "daily", day: item.date },
      (state.day || archive.latest) === item.date ? 'aria-current="page"' : "")}<span class="muted">${modeLabel(item.mode)}</span></li>`
  ).join("")}</ol></section>`;
}

async function getJson(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function getEdition(day) {
  if (!dailyCache.has(day)) {
    const request = getJson(`./daily/${day}.json`).then(edition => {
      if (edition.date !== day || !Array.isArray(edition.items)) throw new Error("Invalid daily edition");
      return edition;
    }).catch(error => {
      dailyCache.delete(day);
      throw error;
    });
    dailyCache.set(day, request);
  }
  return dailyCache.get(day);
}

async function loadArchive() {
  try {
    const data = await getJson("./daily/index.json");
    if (data.schema_version !== 1 || !Array.isArray(data.editions) || !datePattern.test(data.latest) ||
        data.editions.some(item => !datePattern.test(item.date) || typeof item.title !== "string" ||
          !["fresh", "review"].includes(item.mode))) throw new Error("Invalid daily archive");
    archive = { ...data, editions: data.editions.sort((a, b) => b.date.localeCompare(a.date)) };
  } catch { archiveError = true; }
  renderTeaser();
  if (state.view === "daily") renderDaily(false);
  if (state.view === "archive") renderArchive(false);
  if (state.view === "saved") renderSaved(false);
  if (searchDialog.open) renderQuick();
  if (archive) {
    try {
      const edition = await getEdition(archive.latest);
      if (edition.question) {
        const question = $("#today-question");
        question.textContent = edition.question;
        question.hidden = false;
      }
    } catch { /* The headline and archive remain available. */ }
  }
}

function renderArchive(focus) {
  document.title = "专题归档 · AgentHot";
  const query = words(state.q);
  const editions = archive?.editions.filter(item => (!state.mode || state.mode === item.mode) &&
    query.every(word => `${item.title} ${item.date} ${displayDate(item.date)} ${modeLabel(item.mode)}`.toLowerCase().includes(word)));
  const filters = [["", "全部"], ["fresh", "新文献"], ["review", "精选回顾"]];
  const result = !archive ? (archiveError ? "暂时无法读取专题，可刷新页面重试。" : "正在载入专题归档…") :
    editions.length ? "" : "这个筛选没有找到专题。";
  openEntry(`<div class="entry-back">${internal("‹ 每日专题", { view: "daily", day: "" })}</div>
    <h2 id="entry-title" tabindex="-1">专题归档</h2><div class="archive-toolbar">
      <nav class="filters" aria-label="按专题类型筛选">${filters.map(([mode, label]) =>
    internal(label, { mode }, `class="filter"${state.mode === mode ? ' aria-current="page"' : ""}`)).join("")}</nav>
      <form id="archive-search" role="search"><label class="sr-only" for="archive-query">搜索往期专题</label>
      <input id="archive-query" type="search" value="${esc(state.q)}" maxlength="160" placeholder="搜索往期标题或日期">
      <button class="button" type="submit">筛选</button></form></div>
    ${result ? `<p class="empty">${result}</p>` : `<ol class="archive-list">${editions.map(item => `<li class="archive-row">
      <time datetime="${esc(item.date)}">${esc(displayDate(item.date))}</time>
      ${internal(esc(editionTitle(item.title)), { view: "daily", day: item.date })}
      <span class="muted">${modeLabel(item.mode)} · ${formatCount.format(item.count)} 条</span>
      ${saveButton(`daily:${item.date}`)}</li>`).join("")}</ol>`}
    <div class="entry-tools"><a class="button" href="./daily/rss.xml">订阅每日 RSS</a></div>`, focus);
}

function adjacentEditions(day) {
  const index = archive.editions.findIndex(item => item.date === day);
  const newer = archive.editions[index - 1];
  const older = archive.editions[index + 1];
  if (!newer && !older) return "";
  return `<nav class="view-nav" aria-label="切换专题">
    ${older ? internal(`← ${esc(displayDate(older.date))}`, { view: "daily", day: older.date }) : ""}
    ${newer ? internal(`${esc(displayDate(newer.date))} →`, { view: "daily", day: newer.date }) : ""}</nav>`;
}

async function renderDaily(focus) {
  const ticket = ++dailyRender;
  const back = `<div class="entry-back">${internal("‹ 全部往期专题", { view: "archive", mode: "", q: "" })}</div>`;
  document.title = "每日专题 · AgentHot";
  if (!archive) {
    openEntry(`${back}<h2 id="entry-title" tabindex="-1">每日专题</h2><p class="empty">${archiveError ? "暂时无法读取每日专题，可先浏览精选。" : "正在载入每日专题…"}</p>`, focus);
    return;
  }
  const day = state.day || archive.latest;
  if (!archive.editions.some(item => item.date === day)) {
    openEntry(`${back}<h2 id="entry-title" tabindex="-1">没有找到这期专题</h2>${archiveList()}`, focus);
    return;
  }
  const dataPath = `./daily/${day}`;
  try {
    if (!dailyCache.has(day)) {
      openEntry(`${back}<h2 id="entry-title" tabindex="-1">每日专题</h2><p class="empty">正在载入 ${esc(displayDate(day))} 专题…</p>`, false);
    }
    const edition = await getEdition(day);
    if (ticket !== dailyRender || state.view !== "daily") return;
    const share = route({ view: "daily", day });
    const articles = edition.items.map(item => `<article class="daily-paper">
      <h4>${remote(item.title, item.url)}</h4>
      ${item.published_at ? `<time class="muted" datetime="${esc(item.published_at)}">${esc(displayDate(item.published_at))}</time>` : ""}
      ${item.excerpt ? `<p>${esc(item.excerpt)}</p>` : ""}
      ${item.pdf_url ? remote("公开 PDF", item.pdf_url) : ""}</article>`).join("");
    openEntry(`${back}<header><div class="row-meta"><time datetime="${day}">${esc(displayDate(day))}</time>
      <span>${modeLabel(edition.mode)}</span></div>
      <h2 id="entry-title" tabindex="-1">${esc(edition.title)}</h2><p class="summary">${esc(edition.summary)}</p></header>
      ${edition.question ? `<section class="entry-block"><h3>今天可以追问</h3><p>${esc(edition.question)}</p></section>` : ""}
      <section class="entry-block"><h3>相关文献</h3>${articles}</section>
      <div class="entry-tools">${saveButton(`daily:${day}`)}${documentTools(`${dataPath}.md`, share)}
      <a class="button" href="${dataPath}.json">专题 JSON</a>${correction(day, share)}</div>
      ${adjacentEditions(day)}${archiveList()}`, focus);
    document.title = `${edition.title} · AgentHot`;
  } catch {
    if (ticket === dailyRender && state.view === "daily") openEntry(`${back}<h2 id="entry-title" tabindex="-1">这期专题暂时无法读取</h2>${archiveList()}`, focus);
  }
}

function savedRecord(key) {
  const id = key.slice(6);
  if (key.startsWith("daily:")) {
    const item = archive?.editions.find(edition => edition.date === id);
    return { key, title: item?.title ?? `每日专题 ${displayDate(id)}`, category: "每日专题",
      href: route({ view: "daily", day: id }), markdown: `./daily/${id}.md`, sources: [] };
  }
  const item = itemsById.get(id);
  return { key, title: item?.title ?? `已下线条目 ${id}`, category: item ? stages.get(item.stage) : "精选",
    href: item ? route({ view: "feed", kind: "all", stage: "", q: "", sort: "recent", item: id }) : "",
    markdown: item ? `./items/${id}.md` : "", sources: item?.sources ?? [] };
}

function renderSaved(focus) {
  document.title = "我的收藏 · AgentHot";
  const list = [...saved].reverse().map(savedRecord);
  openEntry(`<div class="entry-back"><a href="./" data-route>‹ 返回发现</a></div>
    <h2 id="entry-title" tabindex="-1">我的收藏</h2>
    <p class="summary">收藏保存在当前浏览器。可以导出资料链接，交给 Agent 继续阅读。</p>
    ${list.length ? `<div class="entry-tools"><button class="button primary" type="button" data-action="export">导出收藏 Markdown</button></div>
      <ul class="saved-list">${list.map(record => `<li class="saved-row"><div><span class="muted">${esc(record.category)}</span>
      ${record.href ? `<a href="${esc(record.href)}" data-route>${esc(record.title)}</a>` : `<p>${esc(record.title)}</p>`}</div>
      <button class="button" type="button" data-action="remove" data-save-key="${esc(record.key)}">移除</button></li>`).join("")}</ul>`
    : '<p class="empty">还没有收藏。<a href="./" data-route>浏览研究发现</a>，或去<a href="?view=daily" data-route>读每日专题</a>。</p>'}`, focus);
}

function toggleSaved(key) {
  if (!saveKeyIsValid(key)) return;
  const remove = saved.delete(key);
  if (!remove) saved.add(key);
  let persisted = true;
  try { localStorage.setItem(savedStorage, JSON.stringify([...saved])); } catch { persisted = false; }
  syncSaved();
  if (state.view === "saved") renderSaved(true);
  showNotice(persisted ? (remove ? "已移除收藏" : "已加入收藏") : "收藏仅在本次打开期间保留");
}

function exportSaved() {
  const lines = ["# AgentHot 收藏", ""];
  const absolute = path => new URL(path, location.href).href;
  for (const record of [...saved].reverse().map(savedRecord)) {
    lines.push(`## ${record.title.replace(/\s+/g, " ")}`, "");
    if (record.href) lines.push(`- [查看条目](<${absolute(record.href)}>)`);
    if (record.markdown) lines.push(`- [Agent Markdown](<${absolute(record.markdown)}>)`);
    for (const source of record.sources) {
      const url = publicUrl(source.url);
      const pdf = publicUrl(source.pdf_url);
      if (url) lines.push(`- [${labels.get(source.type)}来源](<${url}>)`);
      if (pdf) lines.push(`- [公开 PDF](<${pdf}>)`);
    }
    lines.push("");
  }
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "agenthot-collection.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function render(focus = false) {
  dailyRender++;
  renderFilters();
  $("#home-hero").hidden = state.view !== "feed" || Boolean(state.item);
  const home = $("[data-home]");
  const daily = $('.site-links a[href="?view=daily"]');
  const collection = $(".mast-saved");
  for (const [node, selected] of [[home, state.view === "feed"],
    [daily, ["daily", "archive"].includes(state.view)], [collection, state.view === "saved"]]) {
    if (selected) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  }
  if (state.view === "daily") renderDaily(focus);
  else if (state.view === "archive") renderArchive(focus);
  else if (state.view === "saved") renderSaved(focus);
  else if (state.item) renderEntry(itemsById.get(state.item), focus);
  else {
    renderBrowse();
    if (focus) $("#browse h2")?.focus();
  }
  syncSaved();
}

function showNotice(text) {
  const element = $("#notice");
  element.textContent = text;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { element.textContent = ""; }, 3200);
}

async function copyLink(path, share) {
  try {
    await navigator.clipboard.writeText(new URL(path, location.href).href);
    showNotice(share ? "已复制页面链接" : "已复制 Agent 链接");
  } catch { showNotice(share ? "可以从地址栏复制链接" : "可从 Markdown 下载链接的菜单复制地址"); }
}

async function refreshRepos() {
  if (checkingRepos) return;
  const slugs = [...new Set(matches().flatMap(item => item.sources.filter(source => source.type === "repo")
    .map(source => githubSlug(source.url))))].filter(Boolean).slice(0, 12);
  if (!slugs.length) { showNotice("当前结果暂无 GitHub 仓库"); return; }
  const pending = slugs.filter(slug => Date.now() - (repos.get(slug)?.checkedAt ?? 0) > 600000);
  if (!pending.length) { showNotice(`已核对 ${slugs.length} 个仓库的 GitHub 近况`); return; }
  checkingRepos = true;
  renderBrowse();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8500);
  await Promise.allSettled(pending.map(async slug => {
    const res = await fetch(`https://api.github.com/repos/${slug}`, { signal: controller.signal, headers: { Accept: "application/vnd.github+json" } });
    if (!res.ok) return;
    const data = await res.json();
    if (Number.isInteger(data.stargazers_count) && typeof data.pushed_at === "string") {
      repos.set(slug, { stars: data.stargazers_count, pushedAt: data.pushed_at, checkedAt: Date.now() });
    }
  }));
  clearTimeout(timer);
  checkingRepos = false;
  if (state.view === "feed" && state.kind === "repo" && !state.item) {
    renderBrowse();
    const count = slugs.filter(slug => repos.has(slug)).length;
    showNotice(count ? `已核对 ${count} 个仓库的 GitHub 近况` : "暂时无法读取近况，可直接打开仓库");
  }
}

function renderQuick() {
  const value = quickQuery.value.trim();
  const query = words(value);
  const contains = text => query.every(word => text.toLowerCase().includes(word));
  const status = $("#quick-status");
  if (!query.length) {
    status.textContent = "可搜索精选研究、项目名称和往期专题。";
    quickResults.innerHTML = `<li>${internal("查看最新每日专题", { view: "daily", day: "" })}</li>
      <li>${internal("浏览往期专题", { view: "archive", mode: "", q: "" })}</li>
      <li>${internal("打开我的收藏", { view: "saved" })}</li>`;
    return;
  }
  const items = feed.items.filter(item => contains(item.searchText));
  const editions = (archive?.editions ?? []).filter(item =>
    contains(`${item.title} ${item.date} ${displayDate(item.date)}`));
  const count = items.length + editions.length;
  status.textContent = count ? `找到 ${count} 条结果` : "AgentHot 暂无匹配，可继续到论文知识库查找。";
  const feedRoute = { view: "feed", kind: "all", stage: "", q: "", sort: "recent" };
  quickResults.innerHTML = items.slice(0, 6).map(item => `<li class="quick-result">${internal(
    `<span>${esc(item.title)}</span><small>${esc(stages.get(item.stage))}</small>`, { ...feedRoute, item: item.id })}</li>`).join("") +
    editions.slice(0, 4).map(item => `<li class="quick-result">${internal(
      `<span>${esc(editionTitle(item.title))}</span><small>${esc(displayDate(item.date))}</small>`, { view: "daily", day: item.date })}</li>`).join("") +
    (items.length > 6 ? `<li>${internal("查看全部精选结果", { ...feedRoute, item: "", q: value })}</li>` : "") +
    (editions.length > 4 ? `<li>${internal("查看全部专题结果", { view: "archive", mode: "", q: value })}</li>` : "") +
    `<li><a href="/agent-papers/?${new URLSearchParams({ q: value })}">到论文知识库搜索 ↗</a></li>`;
}

function openSearch() {
  if (searchDialog.open) { quickQuery.focus(); return; }
  quickQuery.value = state.q;
  renderQuick();
  searchDialog.showModal();
  quickQuery.select();
}

function bind() {
  addEventListener("popstate", () => { state = getState(); render(); });
  addEventListener("storage", event => {
    if (event.key === savedStorage || event.key === null) {
      saved = readSaved();
      syncSaved();
      if (state.view === "saved") renderSaved(false);
    }
  });
  $("#open-search").addEventListener("click", openSearch);
  $("#search-key").textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ K" : "Ctrl K";
  quickQuery.addEventListener("input", renderQuick);
  document.addEventListener("keydown", event => {
    if (event.defaultPrevented || event.isComposing || event.keyCode === 229) return;
    const editable = event.target.closest?.("input, textarea, select, [contenteditable]");
    const shortcut = (event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "k";
    const slash = event.key === "/" && !editable && !event.altKey && !event.metaKey && !event.ctrlKey;
    if (shortcut || slash) {
      event.preventDefault();
      openSearch();
    }
    if (event.key === "ArrowDown" && event.target === quickQuery) {
      const firstLink = quickResults.querySelector("a");
      if (firstLink) {
        event.preventDefault();
        firstLink.focus();
      }
    }
  });
  document.addEventListener("click", event => {
    const link = event.target.closest("[data-route]");
    if (link && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button)) {
      event.preventDefault();
      if (searchDialog.open && searchDialog.contains(link)) searchDialog.close();
      navigate(link.getAttribute("href"), true);
      return;
    }
    const action = event.target.closest("[data-action]");
    if (action?.dataset.action === "copy") copyLink(action.dataset.copy, action.hasAttribute("data-share"));
    if (action?.dataset.action === "repos") refreshRepos();
    if (action?.dataset.action === "save") toggleSaved(action.dataset.save);
    if (action?.dataset.action === "remove") toggleSaved(action.dataset.saveKey);
    if (action?.dataset.action === "export") exportSaved();
  });
  searchForm.addEventListener("submit", event => {
    event.preventDefault();
    navigate(route({ q: $("#query").value.trim(), item: "" }));
  });
  document.addEventListener("submit", event => {
    if (event.target.id === "archive-search") {
      event.preventDefault();
      navigate(route({ q: $("#archive-query").value.trim() }), true);
    }
    if (event.target.id === "quick-form") {
      event.preventDefault();
      quickResults.querySelector("a")?.click();
    }
  });
  document.addEventListener("change", event => {
    if (event.target.id === "feed-sort") {
      navigate(route({ sort: event.target.value }));
      $("#feed-sort")?.focus();
    }
  });
}

try {
  feed = await getJson("./feed.json");
  if (feed.schema_version !== 1 || !Array.isArray(feed.items) || !feed.edition) throw new Error("Invalid feed");
  feed.items = feed.items.map(item => ({ ...item, searchText: [item.title, item.summary, stages.get(item.stage),
    item.evidence, item.reproduce, ...item.sources.flatMap(source => [source.title, source.url])].flat().join(" ").toLowerCase() }))
    .sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at) || Number(Boolean(b.featured)) - Number(Boolean(a.featured)));
  $("#edition-title").textContent = feed.edition.title;
  $("#edition-description").textContent = feed.edition.description;
  $("#edition-date").dateTime = feed.edition.published_at;
  $("#edition-date").textContent = displayDate(feed.edition.published_at);
} catch {
  feed = { items: [] };
  feedError = true;
}
itemsById = new Map(feed.items.map(item => [item.id, item]));
state = getState();
bind();
$("#open-search").disabled = false;
render();
loadArchive();
