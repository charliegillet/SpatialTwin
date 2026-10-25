import {
  canSend, HAZARD_LABELS, PROPOSAL_STATUS_LABELS, proposeErrorMessage, type HazardType, type ProposerState,
} from './signView.ts';

const URL_PATH = '/api/public/hazard-proposals';
const POLL_MS = 4_000;

function element<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, parent?: HTMLElement, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  parent?.appendChild(node);
  return node;
}

function isProposerState(raw: unknown): raw is ProposerState {
  const value = raw as ProposerState | null;
  return !!value && typeof value.venue_id === 'string' && Array.isArray(value.rooms) && Array.isArray(value.hazard_types)
    && Array.isArray(value.mine) && typeof value.active === 'boolean';
}

/**
 * A phone proposes a hazard (type + room). It changes nothing: the operator confirms or rejects it on the laptop, and
 * only a confirmed proposal becomes a (simulated) hazard in the twin. This page shows that status honestly.
 */
export function startProposePage(root: HTMLElement): void {
  let data: ProposerState | null = null;
  let type: HazardType | null = null;
  let room: string | null = null;
  let busy = false;
  let expired = false;
  let message = '';
  let messageTone: 'ok' | 'error' = 'ok';
  let roomsKey = '';

  root.textContent = '';
  const page = element('main', 'propose', root);
  const header = element('header', 'propose-head', page);
  element('h1', 'propose-title', header, 'Propose a hazard');
  const venue = element('p', 'propose-venue', header, 'Connecting…');
  element('p', 'propose-rule', header, 'Simulated. Your phone only proposes: the operator confirms or rejects it on the laptop before anything changes.');

  const typeSection = element('section', 'propose-section', page);
  element('h2', 'propose-label', typeSection, '1 · What is it?');
  const types = element('div', 'propose-types', typeSection);
  const roomSection = element('section', 'propose-section', page);
  element('h2', 'propose-label', roomSection, '2 · Which room?');
  const rooms = element('div', 'propose-rooms', roomSection);
  const send = element('button', 'propose-send', page, 'Send proposal');
  send.type = 'button';
  const status = element('p', 'propose-status', page);
  status.setAttribute('role', 'status');
  const mineSection = element('section', 'propose-section', page);
  element('h2', 'propose-label', mineSection, 'Your proposals');
  const mine = element('ul', 'propose-mine', mineSection);

  function chooseType(value: HazardType): void { type = value; render(); }
  function chooseRoom(value: string): void { room = value; render(); }

  function render(): void {
    if (expired) {
      page.className = 'propose expired';
      venue.textContent = 'This link has expired. Scan the new QR code on the presenter screen.';
      typeSection.hidden = roomSection.hidden = mineSection.hidden = send.hidden = true;
      status.textContent = '';
      return;
    }
    venue.textContent = data ? `${data.venue_name}${data.active ? '' : ' · not on the presenter screen right now'}` : 'Connecting…';
    if (data && !types.childElementCount) {
      for (const value of data.hazard_types) {
        const button = element('button', `propose-choice hazard-${value.toLowerCase()}`, types, HAZARD_LABELS[value] ?? value);
        button.type = 'button';
        button.dataset.value = value;
        button.addEventListener('click', () => chooseType(value));
      }
    }
    const nextRoomsKey = data ? data.rooms.map(item => `${item.id}:${item.name}`).join('|') : '';
    if (nextRoomsKey !== roomsKey) {
      roomsKey = nextRoomsKey;
      rooms.textContent = '';
      for (const item of data?.rooms ?? []) {
        const button = element('button', 'propose-choice', rooms, item.name);
        button.type = 'button';
        button.dataset.value = item.id;
        button.addEventListener('click', () => chooseRoom(item.id));
      }
      if (room && !data?.rooms.some(item => item.id === room)) room = null;
    }
    for (const button of types.querySelectorAll<HTMLButtonElement>('button')) button.setAttribute('aria-pressed', String(button.dataset.value === type));
    for (const button of rooms.querySelectorAll<HTMLButtonElement>('button')) button.setAttribute('aria-pressed', String(button.dataset.value === room));
    send.disabled = !canSend(type, room, busy, data?.active ?? false);
    send.textContent = busy ? 'Sending…' : 'Send proposal';
    status.textContent = message;
    status.dataset.tone = messageTone;
    mine.textContent = '';
    const items = [...(data?.mine ?? [])].reverse();
    if (!items.length) element('li', 'propose-empty', mine, 'None yet');
    for (const item of items) {
      const row = element('li', `propose-item status-${item.status}`, mine);
      element('strong', '', row, `${HAZARD_LABELS[item.type] ?? item.type} · ${item.room}`);
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
    if (!canSend(type, room, busy, data?.active ?? false)) return;
    busy = true;
    message = '';
    render();
    try {
      const response = await fetch(URL_PATH, {
        method: 'POST', cache: 'no-store', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, zone_id: room }),
      });
      if (response.status === 201) {
        message = 'Sent. The operator will confirm or reject it on the laptop.';
        messageTone = 'ok';
        type = null;
        room = null;
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
