import { GLYPHS } from './glyphs.ts';
import {
  connectionNote, overviewDisplays, parseSignState, signDisplay, type Connection, type SignDisplay, type SignState, type Tone,
} from './signView.ts';

const RETRY_MIN_MS = 2_000;
const RETRY_MAX_MS = 15_000;
const POLL_MS = 3_000;
/** Browser chrome colour per tone, so the whole phone screen reads as the sign. */
const THEME: Record<Tone, string> = { green: '#00843d', red: '#c8102e', amber: '#2a2412', grey: '#151a1b' };

function element<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, parent?: HTMLElement): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  parent?.appendChild(node);
  return node;
}

type WakeLockHandle = { release: () => Promise<void> };

/**
 * One phone = one exit sign (or, for an all-exits link, a grid of every exit). Live updates come from the public SSE;
 * when it fails the page polls the state, retries with backoff, and after STALE_AFTER_MS without news shows "not
 * updating" instead of the last arrow. A 403/410 means the link expired or was revoked.
 */
export function startSignPage(root: HTMLElement, venueId: string, exitId: string | null): void {
  const base = `/api/public/signs/${encodeURIComponent(venueId)}`;
  const query = exitId ? `?exit=${encodeURIComponent(exitId)}` : '';
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const themeMeta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');

  let state: SignState | null = null;
  let connection: Connection = 'connecting';
  let lastMessageAt: number | null = null;
  let source: EventSource | null = null;
  let retryMs = RETRY_MIN_MS;
  let retryTimer: number | undefined;
  let pollTimer: number | undefined;
  let wakeLock: WakeLockHandle | null = null;
  let lastKey = '';

  root.textContent = '';
  const page = element('main', 'sign tone-grey', root);
  const single = element('div', 'sign-face', page);
  const glyph = element('div', 'sign-glyph', single);
  const headline = element('h1', 'sign-headline', single);
  const label = element('p', 'sign-exit', single);
  const detail = element('p', 'sign-detail', single);
  const grid = element('section', 'sign-grid', page);
  grid.hidden = true;
  const foot = element('footer', 'sign-foot', page);
  const chip = element('span', 'sign-chip', foot);
  const note = element('span', 'sign-note', foot);
  const hint = element('button', 'sign-hint', foot);
  hint.type = 'button';
  hint.textContent = 'Full screen';
  const live = element('p', 'sr-only', page);
  live.setAttribute('aria-live', 'polite');

  const fullscreenAvailable = typeof document.documentElement.requestFullscreen === 'function';
  hint.hidden = !fullscreenAvailable;
  const goFullscreen = () => {
    if (fullscreenAvailable && !document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => undefined);
  };
  hint.addEventListener('click', goFullscreen);
  page.addEventListener('dblclick', goFullscreen);
  document.addEventListener('fullscreenchange', () => { hint.hidden = !fullscreenAvailable || !!document.fullscreenElement; });

  function paintTile(tile: HTMLElement, display: SignDisplay): void {
    tile.className = `sign-tile tone-${display.tone}${display.flashing ? ' flashing' : ''}`;
    tile.innerHTML = '';
    const tileGlyph = element('div', `sign-glyph glyph-${display.glyph}`, tile);
    tileGlyph.innerHTML = GLYPHS[display.glyph];
    element('strong', 'sign-tile-headline', tile).textContent = display.headline;
    element('span', 'sign-tile-exit', tile).textContent = display.exitLabel;
    element('span', 'sign-tile-detail', tile).textContent = display.detail;
  }

  function render(): void {
    const now = Date.now();
    const input = { state, exitId, connection, lastMessageAt, now, reducedMotion: !!reducedMotion?.matches };
    const overview = exitId === null && state !== null && state.exits.length > 1 && connection !== 'expired';
    const displays = overview ? overviewDisplays(input) : [signDisplay(input)];
    const chipText = connection === 'expired' ? null : connectionNote(connection, lastMessageAt, now);
    const key = JSON.stringify([overview, displays, chipText]);
    if (key === lastKey) return;
    lastKey = key;
    const main = displays[0];
    const tone: Tone = overview ? 'grey' : main.tone;
    page.className = `sign tone-${tone}${!overview && main.flashing ? ' flashing' : ''}${overview ? ' overview' : ''}`;
    single.hidden = overview;
    grid.hidden = !overview;
    if (overview) {
      grid.textContent = '';
      const title = element('h1', 'sign-grid-title', grid);
      title.textContent = state?.venue_name ?? '';
      for (const display of displays) paintTile(element('article', 'sign-tile', grid), display);
    } else {
      glyph.className = `sign-glyph glyph-${main.glyph}`;
      glyph.innerHTML = GLYPHS[main.glyph];
      headline.textContent = main.headline;
      label.textContent = main.exitLabel;
      label.hidden = !main.exitLabel;
      detail.textContent = main.detail;
    }
    chip.textContent = chipText ?? '';
    chip.hidden = chipText === null;
    note.textContent = main.footnote;
    live.textContent = overview ? displays.map(display => display.announce).join(' ') : main.announce;
    document.title = overview ? `Exit signs · ${state?.venue_name ?? ''}` : `${main.headline}${main.exitLabel ? ` · ${main.exitLabel}` : ''}`;
    themeMeta?.setAttribute('content', THEME[tone]);
  }

  function accept(raw: unknown): void {
    const parsed = parseSignState(raw);
    if (!parsed) return;
    state = parsed;
    lastMessageAt = Date.now();
  }

  function expire(): void {
    connection = 'expired';
    source?.close();
    source = null;
    window.clearTimeout(retryTimer);
    window.clearInterval(pollTimer);
    pollTimer = undefined;
    render();
  }

  async function refresh(): Promise<void> {
    if (connection === 'expired') return;
    try {
      const response = await fetch(base + query, { cache: 'no-store', credentials: 'same-origin' });
      if (response.status === 403 || response.status === 410) return expire();
      if (response.ok) accept(await response.json());
    } catch { /* offline: the stale timer will say so */ }
    render();
  }

  function startPolling(): void {
    if (pollTimer === undefined) pollTimer = window.setInterval(() => { void refresh(); }, POLL_MS);
  }

  function stopPolling(): void {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }

  function markLive(): void {
    connection = 'live';
    retryMs = RETRY_MIN_MS;
    stopPolling();
  }

  function scheduleReconnect(): void {
    window.clearTimeout(retryTimer);
    retryTimer = window.setTimeout(connect, retryMs);
    retryMs = Math.min(RETRY_MAX_MS, retryMs * 2);
  }

  function connect(): void {
    if (connection === 'expired') return;
    source?.close();
    if (typeof EventSource === 'undefined') {
      startPolling();
      void refresh();
      return;
    }
    const events = new EventSource(`${base}/events${query}`);
    source = events;
    events.addEventListener('sign', event => {
      try { accept(JSON.parse((event as MessageEvent<string>).data)); } catch { return; }
      markLive();
      render();
    });
    events.addEventListener('heartbeat', () => { lastMessageAt = Date.now(); markLive(); render(); });
    events.addEventListener('expired', () => expire());
    events.addEventListener('sign_error', () => { events.close(); void refresh(); });
    events.onerror = () => {
      if (connection === 'expired' || source !== events) return;
      connection = 'reconnecting';
      startPolling();
      void refresh();
      // CONNECTING: the browser retries by itself (server sends retry: 3000). CLOSED (a 403/503): retry with backoff.
      if (events.readyState === EventSource.CLOSED) {
        events.close();
        scheduleReconnect();
      }
      render();
    };
  }

  async function keepAwake(): Promise<void> {
    // The Wake Lock API needs a secure context, which a plain-http LAN page is not: then this is a no-op and the
    // phone's own auto-lock setting decides.
    const nav = navigator as Navigator & { wakeLock?: { request: (type: 'screen') => Promise<WakeLockHandle> } };
    if (!nav.wakeLock || wakeLock) return;
    try {
      wakeLock = await nav.wakeLock.request('screen');
      (wakeLock as unknown as EventTarget).addEventListener?.('release', () => { wakeLock = null; });
    } catch { wakeLock = null; }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    void keepAwake();
    if (connection !== 'live') {
      connect();
      void refresh();
    }
  });
  window.addEventListener('pageshow', event => { if (event.persisted) { connect(); void refresh(); } });
  reducedMotion?.addEventListener?.('change', render);
  window.setInterval(render, 1_000);

  render();
  void keepAwake();
  connect();
}
