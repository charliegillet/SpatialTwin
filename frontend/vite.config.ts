import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // three.js and its React bindings ship in one lazy chunk; the entry chunk never imports it.
        manualChunks(id) {
          // keep Vite's dynamic-import helper out of the three chunk so the entry never imports it
          if (id.includes('vite/preload-helper') || id.includes('vite/modulepreload-polyfill')) return 'react-vendor';
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
