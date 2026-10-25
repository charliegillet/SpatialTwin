import type { Glyph } from './signView.ts';

/** Static, hand-drawn pictograms (no user data inside, so innerHTML is safe). Strokes use currentColor. */
const EXIT = `<svg viewBox="0 0 240 140" aria-hidden="true" focusable="false">
  <g fill="none" stroke="currentColor" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 70 H60"/><path d="M42 50 L64 70 L42 90"/>
    <path d="M114 40 L100 80"/>
    <path d="M112 47 L131 59 L146 50"/><path d="M110 47 L92 55 L80 47"/>
    <path d="M100 80 L123 94 L125 122"/><path d="M100 80 L86 104 L64 108"/>
  </g>
  <circle cx="121" cy="22" r="12" fill="currentColor"/>
  <rect x="160" y="14" width="66" height="112" rx="3" fill="none" stroke="currentColor" stroke-width="10"/>
</svg>`;

const CROSS = `<svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
  <g stroke="currentColor" stroke-width="20" stroke-linecap="round"><path d="M18 18 L102 102"/><path d="M102 18 L18 102"/></g>
</svg>`;

const NO_ENTRY = `<svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
  <circle cx="60" cy="60" r="54" fill="currentColor"/><rect class="glyph-cut" x="20" y="50" width="80" height="20" rx="3"/>
</svg>`;

const QUESTION = `<svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
  <circle cx="60" cy="60" r="52" fill="none" stroke="currentColor" stroke-width="10"/>
  <path d="M42 46 C42 30 78 28 78 46 C78 58 60 60 60 74" fill="none" stroke="currentColor" stroke-width="11" stroke-linecap="round"/>
  <circle cx="60" cy="92" r="7" fill="currentColor"/>
</svg>`;

const OFFLINE = `<svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
  <g fill="none" stroke="currentColor" stroke-width="9" stroke-linecap="round">
    <path d="M14 48 C40 22 80 22 106 48"/><path d="M30 66 C48 48 72 48 90 66"/><path d="M46 84 C54 76 66 76 74 84"/>
    <path d="M22 106 L98 22"/>
  </g>
  <circle cx="60" cy="100" r="6" fill="currentColor"/>
</svg>`;

export const GLYPHS: Record<Glyph, string> = { exit: EXIT, cross: CROSS, no_entry: NO_ENTRY, question: QUESTION, offline: OFFLINE };
