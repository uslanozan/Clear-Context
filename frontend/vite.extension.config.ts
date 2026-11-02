import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Builds the Chrome extension into the repo's chrome-extension/ folder, which is committed so
// users can load it unpacked in chrome://extensions without a build. Rebuild after changes.
const root = fileURLToPath(new URL('./extension/', import.meta.url));

export default defineConfig({
  root,
  base: './',
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL('../chrome-extension/', import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        capture: `${root}capture.html`,
        popup: `${root}popup.html`,
        background: `${root}src/background.ts`,
        // A content script must be a single classic file: area.ts imports nothing.
        area: `${root}src/area.ts`,
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
});
