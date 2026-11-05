import { defineConfig } from 'vite'
import fs from 'fs'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'


function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id) {
      if (id.startsWith('figma:asset/')) {
        const filename = id.replace('figma:asset/', '')
        return path.resolve(__dirname, 'src/assets', filename)
      }
    },
  }
}

// SPA fallback for GitHub Pages: copy dist/index.html → dist/404.html
// so deep links like /VenueFlow/experience resolve to the SPA entry.
function gitHubPagesSpaFallback() {
  return {
    name: 'github-pages-spa-fallback',
    apply: 'build' as const,
    closeBundle() {
      const dist = path.resolve(__dirname, 'dist')
      const src = path.join(dist, 'index.html')
      const dest = path.join(dist, '404.html')
      if (fs.existsSync(src)) fs.copyFileSync(src, dest)
    },
  }
}

// Custom domain venueflow.ie serves from /. CI sets VITE_BASE=/.
// Local fallback keeps the project-page path for https://alanmaizon.github.io/VenueFlow/
const base = process.env.VITE_BASE ?? '/VenueFlow/'

// Replit's preview (scripts/replit-demo.sh) serves the dev server on port 5000
// behind its own *.replit.dev hostname and proxies /api to the local backend.
// Elsewhere the dev server keeps Vite's defaults (port 5173, localhost only).
const replitDevServer = process.env.REPL_ID
  ? {
      host: '0.0.0.0',
      port: 5000,
      strictPort: true,
      allowedHosts: ['.replit.dev', '.repl.co'],
      proxy: {
        '/api': 'http://127.0.0.1:8000',
      },
    }
  : undefined

export default defineConfig({
  base,
  server: replitDevServer,
  plugins: [
    figmaAssetResolver(),
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
    gitHubPagesSpaFallback(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
