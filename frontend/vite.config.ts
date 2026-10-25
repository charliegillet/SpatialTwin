import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      // Two pages: the operator app and the phone exit sign (sign.html, no three.js). The key "index" keeps the
      // operator entry chunk named as before.
      input: {
        index: fileURLToPath(new URL('./index.html', import.meta.url)),
        sign: fileURLToPath(new URL('./sign.html', import.meta.url)),
      },
      output: {
        // three.js and its React bindings ship in one lazy chunk; the entry chunk never imports it.
        manualChunks(id) {
          // keep Vite's dynamic-import helper out of the three chunk so the entry never imports it
          // the polyfill gets its own chunk so the phone sign page (no React) does not load react-vendor for it
          if (id.includes('vite/modulepreload-polyfill')) return 'preload-polyfill';
          if (id.includes('vite/preload-helper')) return 'react-vendor';
          if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return 'react-vendor';
          if (/node_modules[\\/](three|three-stdlib|@react-three|react-reconciler|troika-[^\\/]+|meshline|camera-controls|maath|its-fine|zustand|suspend-react|react-use-measure|use-sync-external-store|@monogrid|hls\.js|stats-gl|tunnel-rat|utility-types|bidi-js|webgl-sdf-generator|potpack|meshoptimizer|detect-gpu)[\\/]/.test(id)) return 'three-scene';
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
