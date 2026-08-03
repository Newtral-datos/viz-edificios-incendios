# Edificios calcinados

Mapa interactivo de los edificios de Catastro afectados por los incendios de
la temporada 2026, cruzados con los perímetros de incendios del panel de
incendios. Es la app de visualización del pipeline de datos del repo
principal (`../scripts`).

## Stack

- [Svelte 5](https://svelte.dev/) + [Vite](https://vitejs.dev/)
- [MapLibre GL](https://maplibre.org/) para el mapa, con tiles CartoDB
  Positron (basados en datos de OpenStreetMap)
- [PMTiles](https://protomaps.com/docs/pmtiles) para servir tanto los
  edificios afectados como los perímetros de incendios como vector tiles,
  sin depender de un servidor de teselas

## Datos

Esta app no genera datos por sí misma: los toma de las salidas del pipeline
del repo principal y del panel de incendios (geojson diario, fuera de este
repo). `scripts/prepare_data.py` prepara todo lo que necesita `public/data/`:

```bash
python3 scripts/prepare_data.py   # o: npm run prepare-data
```

Genera (sin trackear en git, ver `.gitignore`):

- `public/data/edificios_afectados.pmtiles` — copia de
  `../data/03_pmtiles/edificios_afectados.pmtiles` (requiere haber corrido
  antes `../scripts/05_edificios_afectados.py` y
  `../scripts/06_generar_pmtiles.py`, o `../PIPELINE_EDIFICIOS_AFECTADOS.py`).
- `public/data/incendios.pmtiles` — perímetros de incendios de la temporada
  actual (filtrados por `AÑO == año actual`), convertidos de geojson a
  pmtiles con tippecanoe porque el geojson diario del panel pesa 140MB+.
- `public/data/resumen.json` — total de edificios afectados y desglose por
  provincia, leído de `../data/02_edificios_afectados/_resumen_afectados.csv`.

Como el geojson de incendios es el de **hoy**, hay que volver a ejecutar
`prepare_data.py` (después de haber corrido de nuevo el pipeline principal)
para refrescar el mapa con los datos de otro día.

## Desarrollo

```bash
npm install
npm run prepare-data   # genera public/data/ (ver arriba)
npm run dev             # servidor de desarrollo
npm run build           # build de producción en dist/
npm run preview         # sirve el build de producción
```

## Estructura

```
app/
├── public/
│   ├── data/              # pmtiles + resumen.json (generados, no en git)
│   └── logo_newtral.png
├── scripts/
│   └── prepare_data.py    # prepara public/data/ a partir del pipeline principal
├── src/
│   ├── App.svelte         # orquesta el mapa y el panel lateral
│   ├── app.css             # tokens de diseño (color, tipografía) y estilos base
│   └── lib/
│       ├── MapView.svelte     # mapa MapLibre + capas pmtiles de incendios/edificios
│       └── Sidebar.svelte     # panel de capas, cifra total y provincias más afectadas
└── vite.config.js
```

## Capas del mapa

- **Perímetros de incendios** (`incendios.pmtiles`, capa `incendios`):
  relleno y contorno en rojo, visibles a cualquier zoom.
- **Edificios afectados** (`edificios_afectados.pmtiles`, capa
  `edificios_afectados`): huellas de Catastro en morado, visibles a partir
  de zoom 9 — a escala de toda España son sub-píxel, así que sirven de
  referencia el perímetro del incendio para saber dónde acercarse.

Ambas capas se pueden ocultar de forma independiente desde el panel lateral,
y al hacer clic sobre un edificio o un incendio se abre un popup con sus
atributos (uso, viviendas, fecha del incendio, hectáreas...).
