const paperLimit = 24;
const routeLimit = 3;
const fieldWidth = 620;
const fieldHeight = 420;
const font = 'system-ui, sans-serif';
const colors = {
  paper: '#c1b4e7',
  venue: '#aa92f5',
  route: '#facf9a',
  text: '#f7f2ff',
  selected: '#fff0b9',
  venueEdge: '#635684',
  routeEdge: '#a28a70',
};

function nodeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function samplePapers(papers, selectedId) {
  const buckets = new Map();
  for (const paper of papers) {
    if (!buckets.has(paper.venue)) buckets.set(paper.venue, []);
    buckets.get(paper.venue).push(paper);
  }

  const sample = [];
  for (let row = 0; sample.length < Math.min(paperLimit, papers.length); row += 1) {
    for (const bucket of buckets.values()) {
      if (bucket[row]) sample.push(bucket[row]);
      if (sample.length === paperLimit) break;
    }
  }
  const selected = papers.find(paper => paper.id === selectedId);
  if (selected && !sample.includes(selected)) {
    const sameVenue = sample.map(paper => paper.venue).lastIndexOf(selected.venue);
    sample[sameVenue === -1 ? sample.length - 1 : sameVenue] = selected;
  }
  return sample;
}

function buildModel(papers, venueNames) {
  const groups = new Map();
  const routeNodes = new Map();
  const nodes = [];
  const edges = [];

  for (const paper of papers) {
    if (!groups.has(paper.venue)) groups.set(paper.venue, []);
    groups.get(paper.venue).push(paper);
  }

  Array.from(groups.entries()).forEach(([venue, group], index) => {
    const angle = (2 * Math.PI * index) / groups.size - Math.PI / 2;
    const singleVenue = groups.size === 1;
    const center = {
      type: 'venue',
      label: venueNames.get(venue) || venue,
      x: singleVenue ? 0 : Math.cos(angle) * 192,
      y: singleVenue ? 0 : Math.sin(angle) * 114,
    };
    nodes.push(center);

    group.forEach((paper, position) => {
      const offset = (position - (group.length - 1) / 2) * 0.37;
      const paperAngle = singleVenue
        ? (2 * Math.PI * position) / group.length - Math.PI / 2
        : angle + offset;
      const radius = singleVenue ? 124 + (position % 2) * 34 : 64 + (position % 2) * 20;
      const node = {
        type: 'paper',
        label: paper.title,
        paper,
        x: center.x + Math.cos(paperAngle) * radius * (singleVenue ? 1.33 : 1),
        y: center.y + Math.sin(paperAngle) * radius * (singleVenue ? 0.81 : 1),
      };
      nodes.push(node);
      edges.push({ source: center, target: node, type: 'venue' });
      for (const route of paper.routes || []) {
        if (!route.id || !route.label || !route.term || !route.evidence) continue;
        if (!routeNodes.has(route.id)) routeNodes.set(route.id, { label: route.label, papers: new Set() });
        routeNodes.get(route.id).papers.add(node);
      }
    });
  });

  const sharedRoutes = Array.from(routeNodes.values())
    .filter(route => route.papers.size >= 2)
    .sort((left, right) => right.papers.size - left.papers.size || left.label.localeCompare(right.label))
    .slice(0, routeLimit);
  sharedRoutes.forEach((route, index) => {
    const node = {
      type: 'route',
      label: route.label,
      x: (index - (sharedRoutes.length - 1) / 2) * 72,
      y: groups.size === 1 ? 71 : 28 + (index % 2) * -42,
    };
    nodes.push(node);
    for (const paper of route.papers) edges.push({ source: node, target: paper, type: 'route' });
  });
  return { nodes, edges, hasRoutes: sharedRoutes.length > 0 };
}

export function createPaperGraph(container, { onSelectPaper }) {
  const tools = nodeElement('div', 'graph-tools');
  const viewport = nodeElement('div', 'graph-viewport');
  const canvas = nodeElement('canvas');
  canvas.setAttribute('aria-hidden', 'true');
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  canvas.style.touchAction = 'pan-y pinch-zoom';
  const empty = nodeElement('p', 'graph-empty');
  viewport.append(canvas, empty);

  const legend = nodeElement('div', 'graph-legend');
  const venueKey = nodeElement('span', 'graph-legend-venue', '实线　收录于会议或期刊');
  const routeKey = nodeElement('span', 'graph-legend-route', '虚线　标题或摘要关键词');
  legend.append(venueKey, routeKey);
  const note = nodeElement('p', 'graph-note');
  const keyboard = nodeElement('form', 'graph-keyboard');
  const choiceLabel = nodeElement('label');
  const select = nodeElement('select');
  const open = nodeElement('button', '', '打开论文');
  open.type = 'submit';
  choiceLabel.append(nodeElement('span', '', '从图谱打开论文'), select);
  keyboard.append(choiceLabel, open);
  container.replaceChildren(tools, viewport, legend, note, keyboard);

  const context = canvas.getContext('2d');
  const listeners = new AbortController();
  const view = { zoom: 1, x: 0, y: 0 };
  let width = 0;
  let height = 0;
  let ratio = 1;
  let displayScale = 1;
  let model = { nodes: [], edges: [], hasRoutes: false };
  let activeId = '';
  let hovered = null;
  let drag = null;

  function listen(element, event, action, options = {}) {
    element.addEventListener(event, action, { ...options, signal: listeners.signal });
  }

  function addButton(label, description, action) {
    const button = nodeElement('button', '', label);
    button.type = 'button';
    button.setAttribute('aria-label', description);
    listen(button, 'click', action);
    tools.append(button);
    return button;
  }

  const smaller = addButton('−', '缩小关系图', () => zoom(0.8, width / 2, height / 2));
  const larger = addButton('+', '放大关系图', () => zoom(1.25, width / 2, height / 2));
  addButton('重置', '重置关系图视图', reset);
  listen(select, 'change', () => { open.disabled = !select.value; });
  listen(keyboard, 'submit', event => {
    event.preventDefault();
    if (select.value) onSelectPaper(select.value);
  });

  function reset() {
    view.zoom = 1;
    view.x = 0;
    view.y = 0;
    draw();
  }

  function zoom(factor, x, y) {
    const next = Math.max(0.68, Math.min(3.2, view.zoom * factor));
    const delta = next / view.zoom;
    const relativeX = x - width / 2;
    const relativeY = y - height / 2;
    view.x = relativeX - (relativeX - view.x) * delta;
    view.y = relativeY - (relativeY - view.y) * delta;
    view.zoom = next;
    draw();
  }

  function point(node) {
    const zoomed = displayScale * view.zoom;
    return { x: width / 2 + view.x + node.x * zoomed, y: height / 2 + view.y + node.y * zoomed };
  }

  function label(node, position, size) {
    const highlighted = node.paper?.id === activeId || node === hovered;
    const text = node.type === 'paper' && node.label.length > 38
      ? `${node.label.slice(0, 37).trimEnd()}…`
      : node.label;
    context.font = `${highlighted || node.type === 'venue' ? 600 : 400} ${highlighted ? 12 : 10}px ${font}`;
    context.textBaseline = 'middle';
    const textWidth = Math.min(context.measureText(text).width, width - 12);
    const x = Math.max(6, Math.min(width - textWidth - 6, position.x - textWidth / 2));
    const y = position.y < size + 16 ? position.y + size + 8 : position.y - size - 8;
    context.lineJoin = 'round';
    context.lineWidth = 4;
    context.strokeStyle = '#252034';
    context.strokeText(text, x, y, textWidth);
    context.fillStyle = highlighted ? colors.selected : colors.text;
    context.fillText(text, x, y, textWidth);
  }

  function draw() {
    if (!context || width < 24 || height < 24) return;
    smaller.disabled = view.zoom <= 0.68;
    larger.disabled = view.zoom >= 3.2;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    for (const edge of model.edges) {
      const from = point(edge.source);
      const to = point(edge.target);
      const selected = edge.target.paper?.id === activeId;
      context.beginPath();
      context.setLineDash(edge.type === 'route' ? [2, 4] : []);
      context.strokeStyle = selected ? colors.venue : colors[`${edge.type}Edge`];
      context.lineWidth = selected ? 1.4 : 0.9;
      context.moveTo(from.x, from.y);
      context.lineTo(to.x, to.y);
      context.stroke();
    }
    context.setLineDash([]);

    const labels = [];
    for (const node of model.nodes) {
      const position = point(node);
      const highlighted = node.paper?.id === activeId || node === hovered;
      const size = node.type === 'venue' ? 6 : highlighted ? 5.5 : 3.5;
      context.beginPath();
      if (node.type === 'route') {
        context.moveTo(position.x, position.y - size);
        context.lineTo(position.x + size, position.y);
        context.lineTo(position.x, position.y + size);
        context.lineTo(position.x - size, position.y);
        context.closePath();
      } else {
        context.arc(position.x, position.y, size, 0, Math.PI * 2);
      }
      context.fillStyle = highlighted ? colors.selected : colors[node.type];
      context.fill();
      if (node.type !== 'paper' || highlighted) labels.push({ node, position, size });
    }
    for (const entry of labels) label(entry.node, entry.position, entry.size);
  }

  function resize() {
    const bounds = viewport.getBoundingClientRect();
    width = bounds.width;
    height = bounds.height;
    ratio = Math.min(window.devicePixelRatio || 1, 2);
    displayScale = Math.min(width / fieldWidth, height / fieldHeight);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    draw();
  }

  function hit(event) {
    const bounds = canvas.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    let nearest = null;
    let distance = 12;
    for (const node of model.nodes) {
      const position = point(node);
      const difference = Math.hypot(position.x - x, position.y - y);
      if (difference < distance) {
        distance = difference;
        nearest = node;
      }
    }
    return nearest;
  }

  function activate(node) {
    if (!node) return;
    if (node.paper) {
      onSelectPaper(node.paper.id);
      return;
    }
    view.x = -node.x * displayScale * view.zoom;
    view.y = -node.y * displayScale * view.zoom;
    draw();
  }

  listen(canvas, 'pointerdown', event => {
    if (!event.isPrimary || event.button !== 0) return;
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y, moved: false };
    canvas.setPointerCapture?.(event.pointerId);
  });
  listen(canvas, 'pointermove', event => {
    if (drag?.id === event.pointerId) {
      const x = event.clientX - drag.x;
      const y = event.clientY - drag.y;
      drag.moved ||= Math.hypot(x, y) > 4;
      if (drag.moved) {
        view.x = drag.viewX + x;
        view.y = drag.viewY + y;
        canvas.style.cursor = 'grabbing';
        draw();
      }
      return;
    }
    const next = hit(event);
    if (next === hovered) return;
    hovered = next;
    canvas.style.cursor = hovered ? 'pointer' : 'grab';
    draw();
  });
  listen(canvas, 'pointerup', event => {
    if (drag?.id !== event.pointerId) return;
    if (!drag.moved) activate(hit(event));
    drag = null;
    canvas.style.cursor = 'grab';
  });
  listen(canvas, 'pointercancel', () => {
    drag = null;
    canvas.style.cursor = 'grab';
  });
  listen(canvas, 'pointerleave', () => {
    hovered = null;
    draw();
  });
  listen(canvas, 'wheel', event => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const bounds = canvas.getBoundingClientRect();
    zoom(event.deltaY < 0 ? 1.14 : 0.88, event.clientX - bounds.left, event.clientY - bounds.top);
  }, { passive: false });

  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
  if (observer) observer.observe(viewport);
  else listen(window, 'resize', resize);

  let signature = '';
  function setVisible(element, visible) {
    element.hidden = !visible;
    element.style.display = visible ? '' : 'none';
  }

  function update({ papers, selectedId, venueNames }) {
    const sample = samplePapers(papers, selectedId);
    const key = JSON.stringify(sample.map(paper => paper.id));
    activeId = selectedId || '';
    if (signature !== key) {
      signature = key;
      model = buildModel(sample, venueNames);
      hovered = null;
      view.zoom = 1;
      view.x = 0;
      view.y = 0;
      const placeholder = nodeElement('option', '', '选择论文…');
      placeholder.value = '';
      select.replaceChildren(placeholder, ...sample.map(paper => {
        const venue = venueNames.get(paper.venue) || paper.venue;
        const title = nodeElement('option', '', `${venue} · ${paper.title}`);
        title.value = paper.id;
        return title;
      }));
    }
    select.value = sample.some(paper => paper.id === activeId) ? activeId : '';
    open.disabled = !select.value;
    const available = Boolean(context && sample.length);
    setVisible(canvas, available);
    if (available) canvas.style.display = 'block';
    setVisible(tools, available);
    setVisible(legend, available);
    setVisible(keyboard, sample.length > 0);
    setVisible(routeKey, model.hasRoutes);
    setVisible(empty, !available);
    empty.textContent = sample.length ? '可从下方选择论文。' : '当前没有匹配的论文。';
    setVisible(note, available);
    note.textContent = `显示 ${sample.length} / ${papers.length} 篇。拖动平移，点击论文节点查看详情。`;
    resize();
  }

  return {
    update,
    destroy() {
      observer?.disconnect();
      listeners.abort();
      container.replaceChildren();
    },
  };
}
