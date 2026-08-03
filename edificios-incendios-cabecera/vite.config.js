import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'
import { existsSync, readFileSync } from 'fs'

// Mismo repo de GitHub Pages que la app del mapa (viz-edificios-incendios),
// pero publicado bajo un subpath propio en vez de en la raíz: el deploy
// (ver package.json, "gh-pages -e edificios-incendios-cabecera") escribe el
// build de esta cabecera en esa subcarpeta del branch gh-pages sin tocar el
// resto del sitio, así que queda visible en
// https://<usuario>.github.io/viz-edificios-incendios/edificios-incendios-cabecera/
const REPO_BASE = '/viz-edificios-incendios/edificios-incendios-cabecera/'

// Esta cabecera no genera datos propios: reutiliza el resumen.json que ya
// genera app/scripts/prepare_data.py para la app del mapa (ver docstring de
// src/App.svelte). En producción vive un nivel por encima de esta cabecera,
// en el mismo repo; en dev se sirve desde disco (ver el plugin más abajo),
// porque ese path solo existe de verdad una vez desplegadas ambas apps
// juntas.
const RESUMEN_URL_PRODUCCION = '/viz-edificios-incendios/data/resumen.json'
const RESUMEN_URL_DEV = '/data/resumen.json'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? REPO_BASE : '/',
  define: {
    __RESUMEN_URL__: JSON.stringify(mode === 'production' ? RESUMEN_URL_PRODUCCION : RESUMEN_URL_DEV),
  },
  plugins: [
    svelte(),
    {
      // Sirve resumen.json directamente desde ../public/data/ (el mismo
      // archivo que usa la app del mapa, generado ahí por
      // `npm run prepare-data`), igual que hace el ejemplo de referencia
      // (PANEL_INCENDIOS/2026/viz-cabecera) con su propio stats.json.
      name: 'serve-resumen-dev',
      configureServer(server) {
        server.middlewares.use(RESUMEN_URL_DEV, (_req, res) => {
          const file = resolve('../public/data/resumen.json')
          if (!existsSync(file)) {
            res.statusCode = 404
            res.end('No existe ../public/data/resumen.json — ejecuta antes `npm run prepare-data` en app/.')
            return
          }
          res.setHeader('Content-Type', 'application/json')
          res.end(readFileSync(file, 'utf-8'))
        })
      },
    },
  ],
}))
