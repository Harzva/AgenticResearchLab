const state = { papers: [] };

const escapeHtml = (value) => String(value ?? "").replace(
  /[&<>"']/g,
  (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character],
);

const tokens = (value) => {
  const normalized = String(value ?? "").toLocaleLowerCase().normalize("NFKC");
  const words = normalized.match(/[\p{L}\p{N}][\p{L}\p{N}_.+-]*/gu) ?? [];
  return [...new Set(words)];
};

const normalizeSearchText = (value) => String(value ?? "").toLocaleLowerCase().normalize("NFKC");

function scorePaper(paper, queryTokens, phrase) {
  const { title, abstract, taxonomy } = paper.searchText;
  let score = phrase && title.includes(phrase) ? 30 : 0;
  score += phrase && abstract.includes(phrase) ? 8 : 0;
  for (const token of queryTokens) {
    if (title.includes(token)) score += 10;
    if (taxonomy.includes(token)) score += 5;
    if (abstract.includes(token)) score += 2;
  }
  return score;
}

function runSearch() {
  const query = document.querySelector("#query").value.trim();
  const conference = document.querySelector("#conference").value;
  const withCode = document.querySelector("#with-code").checked;
  const queryTokens = tokens(query);
  const phrase = normalizeSearchText(query);

  const ranked = state.papers
    .filter((paper) => !conference || paper.conference === conference)
    .filter((paper) => !withCode || paper.links.code)
    .map((paper) => ({ paper, score: scorePaper(paper, queryTokens, phrase) }))
    .filter((item) => !query || item.score > 0)
    .sort((left, right) => right.score - left.score || left.paper.title.localeCompare(right.paper.title));

  renderResults(ranked.slice(0, 12), ranked.length);
}

function paperLinks(paper) {
  const links = [
    ["Paper", paper.links.official_page],
    ["PDF", paper.links.pdf],
    ["Code", paper.links.code],
  ].filter(([, url]) => url);
  return links.map(([label, url]) => `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${label} ↗</a>`).join("");
}

function renderResults(items, total) {
  const count = document.querySelector("#result-count");
  const results = document.querySelector("#results");
  count.textContent = `${total.toLocaleString()} matching papers · showing ${Math.min(items.length, 12)}`;
  if (!items.length) {
    results.innerHTML = '<div class="empty-state">No matching papers. Try a broader failure mode, environment, or component.</div>';
    return;
  }
  results.innerHTML = items.map(({ paper }) => {
    const excerpt = paper.abstract ? `${paper.abstract.slice(0, 245)}${paper.abstract.length > 245 ? "…" : ""}` : "Abstract unavailable in the public source.";
    const tags = paper.taxonomy.slice(0, 5).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");
    return `<article class="paper">
      <div class="paper-head">
        <h3><a href="${escapeHtml(paper.links.official_page)}" target="_blank" rel="noreferrer">${escapeHtml(paper.title)}</a></h3>
        <div class="paper-meta">${escapeHtml(paper.conference)} ${paper.year}</div>
      </div>
      <p>${escapeHtml(excerpt)}</p>
      <div class="tags">${tags}</div>
      <div class="paper-links">${paperLinks(paper)}</div>
    </article>`;
  }).join("");
}

async function loadCatalog() {
  const status = document.querySelector("#load-status");
  try {
    const response = await fetch("data/catalog.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.papers = payload.papers.map((paper) => ({
      ...paper,
      searchText: {
        title: normalizeSearchText(paper.title),
        abstract: normalizeSearchText(paper.abstract),
        taxonomy: normalizeSearchText(paper.taxonomy.join(" ")),
      },
    }));
    document.querySelector("#paper-count").textContent = payload.summary.papers.toLocaleString();
    document.querySelector("#code-count").textContent = payload.summary.with_code.toLocaleString();
    const conferences = Object.keys(payload.summary.conferences);
    document.querySelector("#conference").insertAdjacentHTML(
      "beforeend",
      conferences.map((conference) => `<option>${escapeHtml(conference)}</option>`).join(""),
    );
    status.textContent = `Catalog ${payload.catalog_version} · ${payload.summary.papers.toLocaleString()} public records loaded`;
    document.body.dataset.ready = "true";
    runSearch();
  } catch (error) {
    status.textContent = `Catalog unavailable: ${error.message}`;
    document.querySelector("#results").innerHTML = '<div class="empty-state">The static catalog could not be loaded. Open the GitHub repository for the source data.</div>';
  }
}

document.querySelector("#search-button").addEventListener("click", runSearch);
document.querySelector("#query").addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
document.querySelector("#conference").addEventListener("change", runSearch);
document.querySelector("#with-code").addEventListener("change", runSearch);
document.querySelectorAll("[data-query]").forEach((button) => button.addEventListener("click", () => {
  document.querySelector("#query").value = button.dataset.query;
  runSearch();
}));
loadCatalog();
