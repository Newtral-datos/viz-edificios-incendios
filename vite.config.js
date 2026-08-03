import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Repo de GitHub Pages: https://<usuario>.github.io/viz-edificios-incendios/
// Actualiza este subpath si el repo de destino final tiene otro nombre. El
// build de producción (usado por `npm run build`/`deploy` y por
// `npm run preview`, que también corre en modo producción) necesita
// servirse bajo ese subpath; el servidor de desarrollo sigue en la raíz.
const REPO_BASE = '/viz-edificios-incendios/'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? REPO_BASE : '/',
  plugins: [svelte()],
  worker: {
    format: 'es',
  },
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
}))
