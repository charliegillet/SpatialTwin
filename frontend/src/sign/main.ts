import './sign.css';
import { startProposePage } from './proposePage.ts';
import { startSignPage } from './signPage.ts';

/**
 * Phone entry (sign.html). Reached through /s/<token>, which sets the scoped cookie and redirects here with
 * ?venue=…&exit=… (exit sign) or ?venue=…&mode=propose. The query is only a hint: the server decides from the
 * cookie which venue and exit this phone may read. Must be served by uvicorn from frontend/dist, never vite --host.
 */
const params = new URLSearchParams(window.location.search);
const venue = params.get('venue') ?? '';
const exit = params.get('exit');
const root = document.getElementById('app');

if (root) {
  if (!/^[a-z0-9-]{3,40}$/.test(venue)) {
    root.textContent = '';
    const main = document.createElement('main');
    main.className = 'propose expired';
    const title = document.createElement('h1');
    title.className = 'propose-title';
    title.textContent = 'Scan a sign QR code';
    const text = document.createElement('p');
    text.className = 'propose-venue';
    text.textContent = 'This page is opened from the QR code on the presenter screen.';
    main.append(title, text);
    root.appendChild(main);
  } else if (params.get('mode') === 'propose') {
    startProposePage(root);
  } else {
    startSignPage(root, venue, exit && /^[A-Z0-9_]{1,32}$/.test(exit) ? exit : null);
  }
}
