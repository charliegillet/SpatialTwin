import {
  canSend, doorAxis, HAZARD_INFO, labelPoint, mapViewBox, nameLines, parsePlan, PROPOSAL_STATUS_LABELS, proposeErrorMessage, roomAt, tapToMetres,
  type HazardType, type Plan, type ProposalPublic, type ProposerState, type Spot,
} from './signView.ts';

const URL_PATH = '/api/public/hazard-proposals';
const POLL_MS = 4_000;
const SVG_NS = 'http://www.w3.org/2000/svg';

// Static, hand-written 24x24 icons (no user data is ever interpolated into them).
const ICONS: Record<HazardType, string> = {
  FIRE: '<path d="M12 2c1 4 6 6 6 12a6 6 0 0 1-12 0c0-3 2-4 3-6 1 2 2 2 2 3 1-3 0-6 1-9z" fill="currentColor"/>',
  SMOKE: '<g fill="currentColor"><circle cx="8" cy="15" r="4"/><circle cx="14" cy="13" r="5"/><circle cx="18" cy="16" r="3"/><rect x="5" y="15" width="15" height="4"/></g>',
  GAS: '<g fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M3 8c3-3 5 3 9 0s6 3 9 0"/><path d="M3 14c3-3 5 3 9 0s6 3 9 0"/><path d="M3 20c3-3 5 3 9 0s6 3 9 0"/></g>',
  CHEMICAL: '<path d="M9 2h6v2h-1v5l5 9a2 2 0 0 1-2 3H7a2 2 0 0 1-2-3l5-9V4H9z" fill="currentColor"/>',
  WATER: '<path d="M12 2c4 5 7 8 7 12a7 7 0 0 1-14 0c0-4 3-7 7-12z" fill="currentColor"/>',
};

function element<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, parent?: HTMLElement, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  parent?.appendChild(node);
  return node;
}

function svgNode<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, parent?: Element, text?: string): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  parent?.appendChild(node);
  return node;
}

function icon(type: HazardType, parent: HTMLElement): void {
  const svg = svgNode('svg', { viewBox: '0 0 24 24', width: 28, height: 28, 'aria-hidden': 'true', class: 'propose-icon' }, parent);
  svg.innerHTML = ICONS[type];
  svg.style.color = HAZARD_INFO[type].colour;
}

function isProposerState(raw: unknown): raw is ProposerState {
  const value = raw as ProposerState | null;
  return !!value && typeof value.venue_id === 'string' && Array.isArray(value.rooms) && Array.isArray(value.hazard_types)
    && Array.isArray(value.mine) && typeof value.active === 'boolean' && parsePlan(value.plan) !== null;
}

function pin(parent: Element, spot: Spot, type: HazardType, radius: number, className: string): void {
  const group = svgNode('g', { class: className, transform: `translate(${spot.x} ${spot.y})` }, parent);
  svgNode('circle', { r: radius, fill: HAZARD_INFO[type].colour, class: 'pin-dot' }, group);
  svgNode('circle', { r: radius * 0.35, fill: '#0c0f10' }, group);
}

/**
 * A phone proposes a hazard: pick a type, tap any spot on the floor plan, send. It changes nothing by itself: the
 * operator confirms or rejects it on the laptop, and only a confirmed proposal becomes a (simulated) hazard in the
 * twin at exactly the tapped spot. Plain DOM + SVG so the phone bundle stays small.
 */
export function startProposePage(root: HTMLElement): void {
  let data: ProposerState | null = null;
  let type: HazardType | null = null;
  let spot: Spot | null = null;
  let busy = false;
  let expired = false;
  let message = '';
  let messageTone: 'ok' | 'error' = 'ok';
  let planKey = '';
  let mapSvg: SVGSVGElement | null = null;
  let plan: Plan | null = null;

  root.textContent = '';
  const page = element('main', 'propose', root);
  const header = element('header', 'propose-head', page);
  element('h1', 'propose-title', header, 'Drop a hazard');
  const venue = element('p', 'propose-venue', header, 'Connecting…');
  element('p', 'propose-rule', header, 'Simulated. Your phone only proposes: the operator confirms or rejects it on the laptop before anything changes.');

  const typeSection = element('section', 'propose-section', page);
  element('h2', 'propose-label', typeSection, '1 · What is it?');
  const types = element('div', 'propose-types', typeSection);
  const mapSection = element('section', 'propose-section', page);
  element('h2', 'propose-label', mapSection, '2 · Tap where it is');
  const mapHost = element('div', 'propose-map', mapSection);
  const legend = element('p', 'propose-legend', mapSection, 'Green marks are exits; a square with S is an interior stair. Gaps in walls are doors.');
  const where = element('p', 'propose-where', mapSection, 'Tap the plan to place the pin.');
  where.setAttribute('aria-live', 'polite');
  const send = element('button', 'propose-send', page, 'Send proposal');
  send.type = 'button';
  const status = element('p', 'propose-status', page);
  status.setAttribute('role', 'status');
  const mineSection = element('section', 'propose-section', page);
  element('h2', 'propose-label', mineSection, 'Your proposals');
  const mine = element('ul', 'propose-mine', mineSection);

  function chooseType(value: HazardType): void { type = value; render(); }

  function drawMap(): void {
    mapHost.textContent = '';
    mapSvg = null;
    if (!plan) return;
    const { box, aspect } = mapViewBox(plan);
    const svg = svgNode('svg', { viewBox: box, class: 'plan-svg', role: 'img', 'aria-label': 'Floor plan. Tap a spot to place the hazard pin.', preserveAspectRatio: 'xMidYMid meet' });
    svg.style.aspectRatio = String(aspect);
    // Strokes, labels and marks are in metres; scale them with the venue so a big building stays legible on a phone.
    const unit = (plan.extent[0] / 40) * 1.6;
    for (const room of plan.rooms) {
      svgNode('polygon', { points: room.polygon.map(p => p.join(',')).join(' '), class: 'plan-room', 'stroke-width': 0.18 * unit }, svg);
    }
    for (const door of plan.doors) {
      const vertical = doorAxis(plan, door.position) === 'vertical';
      const half = door.width / 2;
      const [x, y] = door.position;
      svgNode('line', {
        x1: vertical ? x : x - half, x2: vertical ? x : x + half, y1: vertical ? y - half : y, y2: vertical ? y + half : y,
        class: 'plan-door', 'stroke-width': 0.5 * unit,
      }, svg);
    }
    for (const room of plan.rooms) {
      const [cx, cy] = labelPoint(room.polygon);
      const lines = nameLines(room.name);
      const label = svgNode('text', { x: cx, y: cy - (lines.length - 1) * 0.6 * unit, class: 'plan-name', 'font-size': unit, 'text-anchor': 'middle', 'dominant-baseline': 'middle' }, svg);
      lines.forEach((line, index) => svgNode('tspan', { x: cx, dy: index === 0 ? 0 : 1.2 * unit }, label, line));
    }
    for (const exit of plan.exits) {
      const [x, y] = exit.position;
      const r = 0.9 * unit;
      if (exit.kind === 'stair') svgNode('rect', { x: x - r, y: y - r, width: 2 * r, height: 2 * r, rx: r * 0.25, class: 'plan-exit' }, svg);
      else svgNode('circle', { cx: x, cy: y, r, class: 'plan-exit' }, svg);
      svgNode('text', { x, y, class: 'plan-exit-label', 'font-size': r * 1.15, 'text-anchor': 'middle', 'dominant-baseline': 'central' }, svg, exit.kind === 'stair' ? 'S' : exit.id);
    }
    svgNode('g', { class: 'plan-pins' }, svg);
    svg.addEventListener('click', (event: MouseEvent) => {
      if (!plan || busy) return;
      const point = tapToMetres(plan, svg.getBoundingClientRect(), event.clientX, event.clientY);
      if (!roomAt(plan, point.x, point.y)) {
        message = 'That spot is outside the building. Tap inside a room.';
        messageTone = 'error';
      } else {
        spot = point;
        message = '';
      }
      render();
    });
    mapHost.appendChild(svg);
    mapSvg = svg;
  }

  function drawPins(): void {
    const layer = mapSvg?.querySelector('.plan-pins');
    if (!layer || !plan) return;
    layer.textContent = '';
    const unit = (plan.extent[0] / 40) * 1.6;
    for (const item of data?.mine ?? []) {
      if (item.position) pin(layer, item.position, item.type, 0.8 * unit, `pin-mine status-${item.status}`);
    }
    if (spot) pin(layer, spot, type ?? 'FIRE', 1.15 * unit, 'pin-new');
  }

  function render(): void {
    if (expired) {
      page.className = 'propose expired';
      venue.textContent = 'This link has expired. Scan the new QR code on the presenter screen.';
      typeSection.hidden = mapSection.hidden = mineSection.hidden = send.hidden = true;
      status.textContent = '';
      return;
    }
    venue.textContent = data ? `${data.venue_name}${data.active ? '' : ' · not on the presenter screen right now'}` : 'Connecting…';
    if (data && !types.childElementCount) {
      for (const value of data.hazard_types) {
        const info = HAZARD_INFO[value];
        const button = element('button', `propose-choice hazard-${value.toLowerCase()}`, types);
        button.type = 'button';
        button.dataset.value = value;
        icon(value, button);
        const text = element('span', 'propose-choice-text', button);
        element('strong', '', text, info?.label ?? value);
        element('small', '', text, info?.meaning ?? '');
        button.addEventListener('click', () => chooseType(value));
      }
    }
    const nextPlanKey = data ? JSON.stringify(data.plan) : '';
    if (nextPlanKey !== planKey) {
      planKey = nextPlanKey;
      plan = data ? parsePlan(data.plan) : null;
      spot = null;
      drawMap();
    }
    for (const button of types.querySelectorAll<HTMLButtonElement>('button')) button.setAttribute('aria-pressed', String(button.dataset.value === type));
    drawPins();
    const picked = spot && plan ? roomAt(plan, spot.x, spot.y) : null;
    where.textContent = spot && picked
      ? `${type ? HAZARD_INFO[type].label : 'Hazard'} pin in ${picked.name} (${spot.x.toFixed(1)} m, ${spot.y.toFixed(1)} m)`
      : 'Tap the plan to place the pin.';
    legend.hidden = !plan;
    send.disabled = !canSend(type, spot, busy, data?.active ?? false);
    send.textContent = busy ? 'Sending…' : 'Send proposal';
    status.textContent = message;
    status.dataset.tone = messageTone;
    mine.textContent = '';
    const items: ProposalPublic[] = [...(data?.mine ?? [])].reverse();
    if (!items.length) element('li', 'propose-empty', mine, 'None yet');
    for (const item of items) {
      const row = element('li', `propose-item status-${item.status}`, mine);
      const head = element('strong', '', row);
      const dot = element('i', 'propose-dot', head);
      dot.style.background = HAZARD_INFO[item.type]?.colour ?? '#a1ada7';
      head.append(`${HAZARD_INFO[item.type]?.label ?? item.type} · ${item.room}`);
      element('span', '', row, PROPOSAL_STATUS_LABELS[item.status] ?? item.status);
    }
  }

  async function load(): Promise<void> {
    if (expired) return;
    try {
      const response = await fetch(URL_PATH, { cache: 'no-store', credentials: 'same-origin' });
      if (response.status === 403 || response.status === 410) { expired = true; render(); return; }
      const body: unknown = await response.json();
      if (response.ok && isProposerState(body)) data = body;
    } catch { /* keep the last view; the next poll retries */ }
    render();
  }

  send.addEventListener('click', async () => {
    if (!canSend(type, spot, busy, data?.active ?? false)) return;
    busy = true;
    message = '';
    render();
    try {
      const response = await fetch(URL_PATH, {
        method: 'POST', cache: 'no-store', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, position: spot }),
      });
      if (response.status === 201) {
        message = 'Sent. The operator will confirm or reject it on the laptop.';
        messageTone = 'ok';
        type = null;
        spot = null;
      } else {
        const body = await response.json().catch(() => null) as { detail?: { code?: string; retry_after_seconds?: number } } | null;
        message = proposeErrorMessage(response.status, body?.detail?.code ?? null, body?.detail?.retry_after_seconds ?? null);
        messageTone = 'error';
        if (response.status === 403 || response.status === 410) expired = true;
      }
    } catch {
      message = 'The laptop did not answer. Check the Wi-Fi and try again.';
      messageTone = 'error';
    } finally {
      busy = false;
    }
    await load();
  });

  window.setInterval(() => { if (document.visibilityState === 'visible') void load(); }, POLL_MS);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') void load(); });
  render();
  void load();
}
