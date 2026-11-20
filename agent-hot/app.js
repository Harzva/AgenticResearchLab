const labels = new Map([["paper", "论文"], ["report", "技术报告"], ["repo", "开源仓库"]]);
const stages = new Map([["literature", "找文献"], ["hypothesis", "提问题"],
  ["experiment", "做实验"], ["iteration", "看反馈再迭代"]]);
const formatCount = new Intl.NumberFormat("zh-CN");
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const $ = selector => document.querySelector(selector);
const feedList = $("#feed-list");
const entry = $("#entry");
const browse = $("#browse");
const searchForm = $("#search-form");
let feed;
let itemsById;
let state;
let archive;
let archiveError = false;
const dailyCache = new Map();
let dailyRender = 0;
const repos = new Map();
let checkingRepos = false;
let checkedReposAt = 0;
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
  } else {
    if (next.kind !== "all") params.set("kind", next.kind);
    if (next.stage) params.set("stage", next.stage);
    if (next.q) params.set("q", next.q);
    if (next.item) params.set("item", next.item);
  }
  return location.pathname + (params.size ? `?${params}` : "");
}

function navigate(url, focus = false) {
  history.pushState(null, "", url);
  state = getState();
  render(focus);
}

function getState() {
  const q = new URLSearchParams(location.search);
  const kind = q.get("kind");
  const stage = q.get("stage");
  const item = q.get("item");
  const day = q.get("day");
  return {
    view: q.get("view") === "daily" ? "daily" : "feed",
    kind: labels.has(kind) ? kind : "all",
    stage: stages.has(stage) ? stage : "",
    q: (q.get("q") ?? "").slice(0, 160),
    item: itemsById?.has(item) ? item : "",
    day: datePattern.test(day ?? "") ? day : "",
  };
}

function internal(label, change, attributes = "") {
  return `<a href="${esc(route(change))}" data-route ${attributes}>${label}</a>`;
}

function matches() {
  const words = state.q.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return feed.items.filter(item =>
    (!state.stage || item.stage === state.stage) &&
    (state.kind === "all" || item.sources.some(source => source.type === state.kind)) &&
    words.every(word => item.searchText.includes(word)),
  );
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

function row(item) {
  return `<article class="feed-row${item.featured ? " featured" : ""}">
    <div class="row-meta"><time datetime="${esc(item.published_at)}">${esc(displayDate(item.published_at))}</time>
      <span>${esc(stages.get(item.stage))}</span>${tags(item)}</div>
    <h3 class="row-head">${internal(esc(item.title), { item: item.id })}</h3>
    <p class="summary">${esc(item.summary)}</p>${repoStats(item)}
  </article>`;
}

function renderFilters() {
  const options = [["all", "全部精选"], ["paper", "论文"], ["report", "研究报告"], ["repo", "开源趋势"]];
  $("#filters").innerHTML = options.map(([kind, name]) => internal(name, { kind, item: "" },
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
    state.kind === "repo" ? `<button class="action" type="button" data-action="repos"${checkingRepos ? " disabled" : ""}>${checkingRepos ? "正在查阅…" : "查看 GitHub 近况"}</button>` : "",
  ].join("");
  feedList.innerHTML = result.length ? result.map(row).join("") : '<p class="empty">没有符合条件的条目。可以清除筛选再试。</p>';
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
  openEntry(`<div class="entry-back">${internal("返回精选", { item: "" })}</div>
    <header><div class="row-meta"><time datetime="${esc(item.published_at)}">${esc(displayDate(item.published_at))}</time>
      <span>${esc(stages.get(item.stage))}</span>${tags(item)}</div>
      <h2 id="entry-title" tabindex="-1">${esc(item.title)}</h2><p class="summary">${esc(item.summary)}</p></header>
    <section class="entry-block"><h3>证据从哪里来</h3>${paras(item.evidence)}</section>
    <section class="entry-block"><h3>从哪一步开始复现</h3>${paras(item.reproduce)}</section>
    <section class="entry-block"><h3>论文、报告与代码</h3>${sourceList(item.sources)}</section>
    <div class="toolbar entry-tools"><a class="action" href="${markdown}">Agent Markdown</a>
      <button class="action" type="button" data-action="copy" data-copy="${markdown}">复制给 Agent</button>
      <a class="action" href="/agent-papers/">浏览论文知识库</a></div>`, focus);
  document.title = `${item.title} · AgentHot`;
}

function modeLabel(mode) { return mode === "fresh" ? "新文献专题" : "基础文献回顾"; }

function renderTeaser() {
  const latest = archive?.editions.find(item => item.date === archive.latest);
  $("#daily-teaser").innerHTML = latest ? `<time datetime="${esc(latest.date)}">${esc(displayDate(latest.date))}</time>
    <p>${internal(esc(latest.title), { view: "daily", day: latest.date })}</p><p class="muted">${modeLabel(latest.mode)} · ${formatCount.format(latest.count)} 条文献</p>` :
    `<p class="muted">${archiveError ? "暂时无法读取专题更新。" : "正在读取最新一期…"}</p>`;
}

function archiveList() {
  if (!archive?.editions.length) return "";
  return `<section class="entry-block"><h3>往期专题</h3><ol class="daily-archive">${archive.editions.map(item => `<li>
    <time datetime="${esc(item.date)}">${esc(displayDate(item.date))}</time>${internal(esc(item.title), { view: "daily", day: item.date },
      (state.day || archive.latest) === item.date ? 'aria-current="page"' : "")}<span class="muted">${modeLabel(item.mode)}</span></li>`
  ).join("")}</ol></section>`;
}

async function getJson(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadArchive() {
  try {
    const data = await getJson("./daily/index.json");
    if (data.schema_version !== 1 || !Array.isArray(data.editions) || !datePattern.test(data.latest) ||
        data.editions.some(item => !datePattern.test(item.date))) throw new Error("Invalid daily archive");
    archive = data;
  } catch { archiveError = true; }
  renderTeaser();
  if (state.view === "daily") renderDaily(false);
}

async function renderDaily(focus) {
  const ticket = ++dailyRender;
  const back = `<div class="entry-back">${internal("返回精选", { view: "feed", day: "", item: "" })}</div>`;
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
    let edition = dailyCache.get(day);
    if (!edition) {
      openEntry(`${back}<h2 id="entry-title" tabindex="-1">每日专题</h2><p class="empty">正在载入 ${esc(displayDate(day))} 专题…</p>`, false);
      edition = await getJson(`${dataPath}.json`);
      if (edition.date !== day || !Array.isArray(edition.items)) throw new Error("Invalid daily edition");
      dailyCache.set(day, edition);
    }
    if (ticket !== dailyRender || state.view !== "daily") return;
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
      <div class="toolbar entry-tools"><a class="action" href="${dataPath}.md">Agent Markdown</a>
      <a class="action" href="${dataPath}.json">专题 JSON</a>
      <button class="action" type="button" data-action="copy" data-copy="${dataPath}.md">复制给 Agent</button></div>
      ${archiveList()}`, focus);
    document.title = `${edition.title} · AgentHot`;
  } catch {
    if (ticket === dailyRender && state.view === "daily") openEntry(`${back}<h2 id="entry-title" tabindex="-1">这期专题暂时无法读取</h2>${archiveList()}`, focus);
  }
}

function render(focus = false) {
  dailyRender++;
  renderFilters();
  renderTeaser();
  const home = $("[data-home]");
  const daily = $('.site-links a[href="?view=daily"]');
  home.toggleAttribute("aria-current", state.view === "feed");
  if (state.view === "feed") home.setAttribute("aria-current", "page");
  daily.toggleAttribute("aria-current", state.view === "daily");
  if (state.view === "daily") daily.setAttribute("aria-current", "page");
  if (state.view === "daily") renderDaily(focus);
  else if (state.item) renderEntry(itemsById.get(state.item), focus);
  else {
    renderBrowse();
    if (focus) $("#browse h2")?.focus();
  }
}

function showNotice(text) {
  const element = $("#notice");
  element.hidden = false;
  element.textContent = text;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { element.hidden = true; }, 3200);
}

async function copyLink(path) {
  try {
    await navigator.clipboard.writeText(new URL(path, location.href).href);
    showNotice("已复制 Agent 链接");
  } catch { showNotice("可打开 Markdown 链接并复制地址"); }
}

async function refreshRepos() {
  if (checkingRepos) return;
  if (Date.now() - checkedReposAt < 600000) { showNotice(`已核对 ${repos.size} 个仓库的 GitHub 近况`); return; }
  const slugs = [...new Set(matches().flatMap(item => item.sources.filter(source => source.type === "repo")
    .map(source => githubSlug(source.url))))].filter(Boolean).slice(0, 12);
  if (!slugs.length) { showNotice("当前结果暂无 GitHub 仓库"); return; }
  checkingRepos = true;
  renderBrowse();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8500);
  await Promise.allSettled(slugs.map(async slug => {
    const res = await fetch(`https://api.github.com/repos/${slug}`, { signal: controller.signal, headers: { Accept: "application/vnd.github+json" } });
    if (!res.ok) return;
    const data = await res.json();
    if (Number.isInteger(data.stargazers_count) && typeof data.pushed_at === "string") {
      repos.set(slug, { stars: data.stargazers_count, pushedAt: data.pushed_at });
    }
  }));
  clearTimeout(timer);
  checkingRepos = false;
  if (slugs.some(slug => repos.has(slug))) checkedReposAt = Date.now();
  if (state.view === "feed" && state.kind === "repo" && !state.item) {
    renderBrowse();
    const count = slugs.filter(slug => repos.has(slug)).length;
    showNotice(count ? `已核对 ${count} 个仓库的 GitHub 近况` : "暂时无法读取近况，可直接打开仓库");
  }
}

function bind() {
  addEventListener("popstate", () => { state = getState(); render(); });
  document.addEventListener("click", event => {
    const link = event.target.closest("[data-route]");
    if (link && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button)) {
      event.preventDefault();
      navigate(link.getAttribute("href"), true);
      return;
    }
    const action = event.target.closest("[data-action]");
    if (action?.dataset.action === "copy") copyLink(action.dataset.copy);
    if (action?.dataset.action === "repos") refreshRepos();
  });
  searchForm.addEventListener("submit", event => {
    event.preventDefault();
    navigate(route({ q: $("#query").value.trim(), item: "" }));
  });
}

try {
  feed = await getJson("./feed.json");
  if (feed.schema_version !== 1 || !Array.isArray(feed.items) || !feed.edition) throw new Error("Invalid feed");
  feed.items = feed.items.map(item => ({ ...item, searchText: [item.title, item.summary, stages.get(item.stage),
    ...item.sources.map(source => source.title)].join(" ").toLowerCase() }))
    .sort((a, b) => b.published_at.localeCompare(a.published_at) || (a.featured ? -1 : 0) + (b.featured ? 1 : 0));
  itemsById = new Map(feed.items.map(item => [item.id, item]));
  state = getState();
  $("#edition-title").textContent = feed.edition.title;
  $("#edition-description").textContent = feed.edition.description;
  $("#edition-date").dateTime = feed.edition.published_at;
  $("#edition-date").textContent = displayDate(feed.edition.published_at);
  $("#browse h2").tabIndex = -1;
  bind();
  render();
  loadArchive();
} catch (error) {
  console.error(error);
  feedList.setAttribute("aria-busy", "false");
  feedList.innerHTML = '<p class="empty">暂时无法载入精选。<a href="./">重试</a>，或直接查看 <a href="./feed.json">JSON</a>。</p>';
}
