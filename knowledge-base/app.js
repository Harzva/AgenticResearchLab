import { createPaperGraph } from "./graph.js";
import { findRelatedPapers, makeResearchBrief } from "./research.js";

const content = document.querySelector("#content");
const venuesNav = document.querySelector("#venues");
const announcement = document.querySelector("#announcement");
const toast = document.querySelector("#toast");
const pageSize = 18;
const order = ["cvpr", "iclr", "icml", "aaai", "eccv", "ijcai", "tpami"];
const modes = [["search", "文献检索"], ["writing", "论文写作"], ["experiment", "实验设计"]];
const storageKey = "harzva-research-papers-v1";
let catalog;
let paperById;
let venueNames;
let searchIndex;
let routeOptions;
let graph;
let state;
let saved = new Set();
let research = { topic: "", mode: "search", matches: [] };
let toastTimer;

function escape(value) {
  return String(value ?? "").replace(/[&<>"\x27]/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "\x27": "&#39;",
  })[ch]);
}

function external(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function link(label, url, variant = "") {
  const safe = external(url);
  return safe ? `<a class="${variant}" href="${escape(safe)}" target="_blank" rel="noopener noreferrer">${escape(label)}</a>` : "";
}

function dataPath(paper, extension) {
  return `./papers/${encodeURIComponent(paper.id)}.${extension}`;
}

function readState() {
  const params = new URLSearchParams(location.search);
  const validId = params.get("paper");
  const venue = params.get("venue") || "all";
  const year = params.get("year") || "";
  return {
    view: params.get("view") === "research" ? "research" : "papers",
    id: paperById.has(validId) ? validId : null,
    venue: venueNames.has(venue) ? venue : "all",
    year: /^\d{4}$/.test(year) ? year : "",
    term: (params.get("q") || "").slice(0, 200),
    route: routeOptions.has(params.get("route")) ? params.get("route") : "",
    page: Math.max(1, Math.min(999, Number.parseInt(params.get("page"), 10) || 1)),
  };
}

function routeURL(change = {}) {
  const target = { ...state, ...change };
  const params = new URLSearchParams();
  if (target.view === "research") params.set("view", "research");
  if (target.venue !== "all") params.set("venue", target.venue);
  if (target.year) params.set("year", target.year);
  if (target.term) params.set("q", target.term);
  if (target.route) params.set("route", target.route);
  if (target.id) params.set("paper", target.id);
  if (target.page > 1) params.set("page", String(target.page));
  return location.pathname + (params.size ? `?${params}` : "");
}

function go(url, { replace = false, redraw = true, focus = false } = {}) {
  history[replace ? "replaceState" : "pushState"](null, "", url);
  state = readState();
  if (redraw) render();
  if (focus) content.querySelector("h1")?.focus();
}

function localLink(label, changes, attrs = "") {
  return `<a href="${escape(routeURL(changes))}" data-local ${attrs}>${label}</a>`;
}

function filters() {
  const keywords = state.term.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return catalog.papers.filter(paper =>
    (state.venue === "all" || paper.venue === state.venue) &&
    (!state.year || String(paper.year) === state.year) &&
    (!state.route || paper.routes?.some(route => route.id === state.route)) &&
    keywords.every(word => searchIndex.get(paper.id).includes(word))
  );
}

function venueLink(id, name, count) {
  const current = state.view === "papers" && state.venue === id ? 'aria-current="page"' : "";
  return localLink(`<span>${escape(name)}</span><span class="venue-count">${count.toLocaleString("zh-CN")}</span>`,
    { view: "papers", venue: id, id: null, year: "", term: "", route: "", page: 1 },
    `class="venue-link" ${current}`);
}

function renderNavigation() {
  const venueOrder = id => order.includes(id) ? order.indexOf(id) : order.length;
  const sorted = [...catalog.venues].sort((a, b) => venueOrder(a.id) - venueOrder(b.id) || a.name.localeCompare(b.name));
  const groups = [["conference", "会议"], ["journal", "期刊"]];
  venuesNav.innerHTML = venueLink("all", "全部论文", catalog.papers.length) + groups.map(([kind, label]) => {
    const venues = sorted.filter(venue => venue.kind === kind);
    if (!venues.length) return "";
    return `<section class="venue-group" aria-label="${label}"><h3>${label}</h3>${
      venues.map(venue => venueLink(venue.id, venue.name, venue.count)).join("")}</section>`;
  }).join("");
  document.querySelectorAll("[data-view]").forEach(item => {
    const view = item.dataset.view;
    item.href = routeURL({ view, id: null });
    item.toggleAttribute("aria-current", state.view === view);
    if (state.view === view) item.setAttribute("aria-current", "page");
  });
  const counter = document.querySelector("#saved-count");
  counter.textContent = saved.size;
  counter.hidden = saved.size === 0;
}

function meta(paper) {
  const venue = venueNames.get(paper.venue) ?? paper.venue;
  return `<span class="paper-venue">${escape(venue)}</span>${paper.year ? `<span>${escape(paper.year)}</span>` : ""}`;
}

function row(paper) {
  const authors = paper.authors?.slice(0, 3).join(", ");
  const remainder = paper.authors?.length > 3 ? " 等" : "";
  return `<article class="paper-row">
    <div class="paper-meta">${meta(paper)}${paper.pdf_url ? '<span class="paper-format">PDF</span>' : ""}</div>
    <h2>${localLink(escape(paper.title), { id: paper.id })}</h2>
    ${authors ? `<p class="authors">${escape(authors)}${remainder}</p>` : ""}
    ${paper.summary_zh ? `<p class="row-summary">${escape(paper.summary_zh)}</p>` : ""}
  </article>`;
}

function browse() {
  const current = state.venue === "all" ? "论文目录" : venueNames.get(state.venue);
  const years = [...new Set(catalog.papers.filter(p => p.year && (state.venue === "all" || p.venue === state.venue))
    .map(p => String(p.year)))].sort((a, b) => Number(b) - Number(a));
  return `<header class="section-head"><h1 tabindex="-1">${escape(current)}</h1></header>
    <form id="filters" class="filters" role="search">
      <label class="search-field"><span class="sr-only">搜索论文</span>
        <input id="query" name="q" type="search" maxlength="200" value="${escape(state.term)}" placeholder="搜索题目、作者或摘要"></label>
      <label class="year-field"><span class="sr-only">发表年份</span><select name="year">
        <option value="">所有年份</option>${years.map(year => `<option${state.year === year ? " selected" : ""} value="${year}">${year}</option>`).join("")}
      </select></label>
      <button type="submit" class="control">搜索</button>
    </form>
    <div id="results" aria-live="polite"></div>`;
}

function renderResults({ updateGraph = true } = {}) {
  const match = filters();
  const totalPages = Math.max(1, Math.ceil(match.length / pageSize));
  const page = Math.min(state.page, totalPages);
  const start = (page - 1) * pageSize;
  const routeName = routeOptions.get(state.route)?.label;
  const label = match.length ? `${start + 1}–${Math.min(start + pageSize, match.length)} / ${match.length.toLocaleString("zh-CN")} 篇` : "0 篇";
  document.querySelector("#results").innerHTML = `<div class="results-head"><span>${label}</span>
    ${routeName ? localLink(`${escape(routeName)} ×`, { route: "", page: 1 }, 'class="filter-chip" aria-label="清除技术路线筛选"') : ""}</div>
    ${match.length ? match.slice(start, start + pageSize).map(row).join("") :
      `<div class="empty"><p>没有符合条件的论文。</p>${localLink("清除筛选", { term: "", year: "", route: "", page: 1 })}</div>`}
    ${totalPages > 1 ? `<nav class="pagination" aria-label="论文分页">
      ${page > 1 ? localLink("上一页", { page: page - 1 }, 'class="control"') : '<span class="control disabled">上一页</span>'}
      <span>${page} / ${totalPages}</span>
      ${page < totalPages ? localLink("下一页", { page: page + 1 }, 'class="control"') : '<span class="control disabled">下一页</span>'}</nav>` : ""}`;
  if (updateGraph) graph.update({ papers: match, selectedId: null, venueNames });
}

function paperDetail(paper) {
  const routes = paper.routes ?? [];
  const savedPaper = saved.has(paper.id);
  const authors = paper.authors?.join(", ");
  const body = [
    paper.summary_zh ? `<section><h2>中文导读</h2><p>${escape(paper.summary_zh)}</p></section>` : "",
    paper.abstract ? `<section><h2>摘要</h2><p lang="en">${escape(paper.abstract)}</p></section>` : "",
    routes.length ? `<section><h2>技术路线</h2><p class="muted">根据可核对的标题或摘要线索匹配，用于找相近方法。</p>
      <ul class="route-evidence">${routes.map(route => `<li>${localLink(escape(route.label), {
        view: "papers", id: null, venue: "all", route: route.id, term: "", year: "", page: 1,
      })}<q>${escape(route.evidence || route.term)}</q></li>`).join("")}</ul></section>` : "",
    paper.bibtex ? `<section><h2>引用</h2><details><summary>BibTeX</summary><pre>${escape(paper.bibtex)}</pre>
      <button type="button" class="control" data-action="copy-citation">复制 BibTeX</button></details></section>` : "",
  ].join("");
  return `<article class="detail">
    <div class="crumb">${localLink("返回论文目录", { id: null })}</div>
    <header><div class="paper-meta">${meta(paper)}</div><h1 tabindex="-1" lang="en">${escape(paper.title)}</h1>
      ${authors ? `<p class="authors">${escape(authors)}</p>` : ""}</header>
    <div class="action-row">
      ${link("下载 PDF", paper.pdf_url, "control primary")}${link("论文原文", paper.paper_url, "control")}${link("开源代码", paper.code_url, "control")}
      <button type="button" class="control" data-action="toggle-saved" aria-pressed="${savedPaper}">${savedPaper ? "已加入对照" : "加入科研对照"}</button>
    </div>
    <section class="agent-links"><h2>给 Agent 的链接</h2><p class="muted">JSON 含原文、可下载 PDF 和来源。没有公开 PDF 的条目会保留原文入口。</p>
      <div class="action-row"><a class="control" href="${dataPath(paper, "json")}">JSON</a>
        <a class="control" href="${dataPath(paper, "md")}">Markdown</a>
        <button type="button" class="control" data-action="copy-paper">复制 Agent 链接</button>
        ${paper.pdf_url ? '<button type="button" class="control" data-action="copy-pdf">复制 PDF 地址</button>' : ""}</div></section>
    ${body}
    <footer class="source">${link("目录来源", paper.source_url)}${paper.doi ? `<span>DOI ${escape(paper.doi)}</span>` : ""}</footer>
  </article>`;
}

function researchView() {
  const references = [...saved].map(id => paperById.get(id)).filter(Boolean);
  return `<header class="section-head"><h1 tabindex="-1">科研工作台</h1></header>
    <p class="workbench-intro">写下一个问题，从公开文献找到相近方法，再生成可交给 Agent 的检索、写作或实验计划。</p>
    <form id="research-form" class="research-form">
      <label for="research-topic">研究问题</label>
      <div class="research-query"><input id="research-topic" name="topic" maxlength="300" value="${escape(research.topic)}" placeholder="例如 移动端 Agent 如何使用记忆纠正操作错误">
      <button class="control primary" type="submit">找相近论文</button></div>
    </form>
    <div id="research-suggestions"></div>
    <section class="workbench-section"><div class="workbench-heading"><h2>技术路线对照</h2></div>
      <p class="muted">按标题和摘要里的线索找相近技术，进入论文可查看匹配证据。</p>
      <ul class="research-routes">${[...routeOptions].map(([id, route]) => `<li>${localLink(
        `${escape(route.label)} <span>${route.count}</span>`,
        { view: "papers", venue: "all", id: null, route: id, term: "", year: "", page: 1 },
      )}</li>`).join("")}</ul>
    </section>
    <section class="workbench-section"><div class="workbench-heading"><h2>科研对照</h2>
      ${localLink("浏览论文", { view: "papers", id: null })}</div>
      ${references.length ? `<ul class="saved-list">${references.map(paper => `<li>
        ${localLink(escape(paper.title), { view: "papers", id: paper.id })}
        <button type="button" class="control" data-action="remove-saved" data-id="${escape(paper.id)}">移除</button></li>`).join("")}</ul>` :
        '<p class="muted">在论文详情中加入对照，也可以从上面的匹配结果加入。</p>'}</section>
    <section class="workbench-section"><div class="workbench-heading"><h2>生成科研计划</h2></div>
      <label class="sr-only" for="research-mode">科研计划类型</label>
      <select id="research-mode">${modes.map(([mode, label]) => `<option value="${mode}"${research.mode === mode ? " selected" : ""}>${label}</option>`).join("")}</select>
      <label class="sr-only" for="research-output">Markdown 计划</label><textarea id="research-output" rows="12" readonly></textarea>
      <div class="action-row"><button type="button" class="control primary" data-action="copy-research">复制 Markdown</button>
      <button type="button" class="control" data-action="download-research">下载 Markdown</button></div></section>
    <section class="workbench-section"><div class="workbench-heading"><h2>开放科研工具</h2></div>
      <ul class="resource-list"><li><a href="https://github.com/Harzva/AgenticResearchLab">AgenticResearchLab</a> <span>本地检索、证据与研究提案。</span></li>
      <li><a href="https://github.com/karpathy/autoresearch">autoresearch</a> <span>定义预算，在基线之上重复实验并保留记录。</span></li>
      <li><a href="https://github.com/google-research/rrsi">RRSI</a> <span>把候选改动、评估集与晋升条件写入实验流程。</span></li></ul>
    </section>`;
}

function updateResearch() {
  const panel = document.querySelector("#research-suggestions");
  const list = research.matches;
  panel.innerHTML = !research.topic ? "" : `<section class="workbench-section"><h2>相近论文</h2>
    ${list.length ? `<ul class="saved-list">${list.map(({ paper, matches }) => `<li><div>
      ${localLink(escape(paper.title), { view: "papers", id: paper.id, term: "", route: "" })}
      <p class="muted">匹配到 ${escape(matches.slice(0, 4).join("、"))}</p></div>
      <button type="button" class="control" data-action="save-match" data-id="${escape(paper.id)}"${saved.has(paper.id) ? " disabled" : ""}>${saved.has(paper.id) ? "已加入" : "加入对照"}</button></li>`).join("")}</ul>` :
      '<p class="muted">目录里找不到关键词匹配。可以改用任务或方法的英文名。</p>'}
    <div class="research-outside"><span>扩展检索</span>
      ${link("arXiv", `https://arxiv.org/search/?searchtype=all&query=${encodeURIComponent(research.topic)}`)}
      ${link("Semantic Scholar", `https://www.semanticscholar.org/search?q=${encodeURIComponent(research.topic)}`)}
    </div></section>`;
  const papers = [...saved].map(id => paperById.get(id)).filter(Boolean);
  document.querySelector("#research-output").value = makeResearchBrief({ topic: research.topic, papers, mode: research.mode });
  graph.update({ papers: papers.length ? papers : list.map(item => item.paper), selectedId: null, venueNames });
}

function render() {
  renderNavigation();
  if (state.view === "research") {
    content.innerHTML = researchView();
    updateResearch();
  } else if (state.id) {
    const paper = paperById.get(state.id);
    content.innerHTML = paperDetail(paper);
    let neighbors = filters();
    if (!neighbors.includes(paper)) neighbors = [paper, ...neighbors];
    graph.update({ papers: neighbors, selectedId: paper.id, venueNames });
  } else {
    content.innerHTML = browse();
    renderResults();
  }
}

function persist() {
  try { localStorage.setItem(storageKey, JSON.stringify([...saved])); } catch { /* Session memory still works. */ }
}

function notice(message) {
  announcement.textContent = message;
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2400);
}

async function copy(text) {
  if (!text) return;
  try {
    if (!navigator.clipboard) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(text);
    notice("已复制");
  } catch {
    notice("当前浏览器未允许复制，请手动选择链接或文本");
  }
}

function download(text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "agent-research-plan.md";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function changeSaved(id, keep) {
  if (!paperById.has(id)) return;
  if (keep) saved.add(id); else saved.delete(id);
  persist();
  render();
  const selector = state.view === "research" ? "#research-topic" : '[data-action="toggle-saved"]';
  document.querySelector(selector)?.focus({ preventScroll: true });
  notice(keep ? "已加入科研对照" : "已移除对照论文");
}

function bind() {
  addEventListener("popstate", () => { state = readState(); render(); });
  document.addEventListener("click", event => {
    const navigator = event.target.closest("[data-local], [data-view]");
    if (navigator && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button)) {
      event.preventDefault();
      go(navigator.getAttribute("href"), { focus: true });
      return;
    }
    const action = event.target.closest("[data-action]");
    if (!action) return;
    const paper = paperById.get(state.id);
    switch (action.dataset.action) {
      case "copy-paper": copy(new URL(dataPath(paper, "json"), location.href).href); break;
      case "copy-pdf": copy(external(paper.pdf_url)); break;
      case "copy-citation": copy(paper.bibtex); break;
      case "toggle-saved": changeSaved(paper.id, !saved.has(paper.id)); break;
      case "save-match": changeSaved(action.dataset.id, true); break;
      case "remove-saved": changeSaved(action.dataset.id, false); break;
      case "copy-research": copy(document.querySelector("#research-output").value); break;
      case "download-research": download(document.querySelector("#research-output").value); break;
      default: break;
    }
  });
  content.addEventListener("submit", event => {
    const form = event.target;
    const values = new FormData(form);
    if (form.id === "filters") {
      event.preventDefault();
      go(routeURL({ term: values.get("q").trim(), year: values.get("year"), page: 1 }), { redraw: false });
      renderResults();
    } else if (form.id === "research-form") {
      event.preventDefault();
      research.topic = values.get("topic").trim();
      research.matches = findRelatedPapers(catalog.papers, research.topic);
      updateResearch();
    }
  });
  content.addEventListener("change", event => {
    if (event.target.name === "year") event.target.form.requestSubmit();
    if (event.target.id === "research-mode") {
      research.mode = event.target.value;
      updateResearch();
    }
  });
  content.addEventListener("input", event => {
    if (event.target.id !== "research-topic") return;
    const topic = event.target.value.trim();
    if (topic === research.topic) return;
    research.topic = topic;
    research.matches = [];
    document.querySelector("#research-suggestions").innerHTML = "";
    const papers = [...saved].map(id => paperById.get(id)).filter(Boolean);
    document.querySelector("#research-output").value = makeResearchBrief({ topic, papers, mode: research.mode });
  });
}

async function start() {
  try {
    const response = await fetch("./catalog.json", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
    catalog = await response.json();
    if (catalog.schema_version !== 1 || !Array.isArray(catalog.papers) || !Array.isArray(catalog.venues)) {
      throw new Error("Unsupported paper catalog");
    }
    paperById = new Map(catalog.papers.map(paper => [paper.id, paper]));
    venueNames = new Map(catalog.venues.map(venue => [venue.id, venue.name]));
    routeOptions = new Map();
    for (const paper of catalog.papers) {
      for (const route of paper.routes ?? []) {
        const previous = routeOptions.get(route.id);
        routeOptions.set(route.id, { label: route.label, count: (previous?.count ?? 0) + 1 });
      }
    }
    searchIndex = new Map(catalog.papers.map(paper => [paper.id, [
      paper.title, paper.authors?.join(" "), paper.abstract, paper.summary_zh, paper.doi, paper.year, venueNames.get(paper.venue),
    ].filter(Boolean).join(" ").toLowerCase()]));
    try {
      const value = JSON.parse(localStorage.getItem(storageKey) || "[]");
      if (Array.isArray(value)) saved = new Set(value.filter(id => paperById.has(id)));
    } catch { /* Start with an empty local list. */ }
    state = readState();
    graph = createPaperGraph(document.querySelector("#graph"), {
      onSelectPaper(id) { go(routeURL({ view: "papers", id }), { focus: true }); },
    });
    bind();
    render();
  } catch (error) {
    console.error(error);
    content.innerHTML = '<header class="section-head"><h1>论文目录</h1></header><p class="state-message">暂时无法载入论文目录。<a href="./">重试</a>或查看 <a href="./llms.txt">Agent 使用说明</a>。</p>';
  } finally {
    content.setAttribute("aria-busy", "false");
  }
}

start();
