import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://flowdesk.io',
  output: 'static',
  build: {
    inlineStylesheets: 'auto',
    assets: '_assets',
  },
  compressHTML: true,
  vite: {
    build: {
      cssMinify: 'esbuild',
    },
  },
});
