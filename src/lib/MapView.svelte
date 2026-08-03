<script>
	import { onMount, onDestroy } from 'svelte';
	import { Map as MapLibreMap, NavigationControl, Popup, addProtocol, setWorkerUrl } from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { Protocol } from 'pmtiles';
	import { nombreProvincia } from './provincias.js';

	// maplibre-gl-worker.mjs importa por ruta relativa fija a
	// "./maplibre-gl-shared.mjs", así que no puede pasar por el pipeline de
	// hashing de Vite (`?url` solo copiaría el primero y rompería esa
	// import). Ambos ficheros se copian tal cual a public/ en cada
	// `npm install` (ver scripts/copy-maplibre-worker.mjs) y se sirven aquí
	// como estáticos, con el `base` de Vite aplicado a mano.
	setWorkerUrl(`${import.meta.env.BASE_URL}maplibre-gl-worker.mjs`);

	const protocol = new Protocol();
	addProtocol('pmtiles', protocol.tile);

	const FIRE_COLOR = '#ff2a01';
	const BUILDING_COLOR = '#01f3b3';
	const BUILDING_BORDER_COLOR = '#494949';
	const BUILDING_BORDER_OPACITY = 0.7;
	const BUILDING_HIGHLIGHT_COLOR = '#16181a';
	const EDIFICIOS_SOURCE_LAYER = 'edificios_afectados';

	// Expresión de estilo compartida por fill-opacity/line-color/line-width:
	// un edificio se resalta si está bajo el ratón (hover) o si es el que se
	// ha clicado (selected, se mantiene resaltado mientras el popup esté
	// abierto).
	const HIGHLIGHTED = [
		'any',
		['boolean', ['feature-state', 'hover'], false],
		['boolean', ['feature-state', 'selected'], false]
	];

	const EDIFICIOS_URL = `pmtiles://${import.meta.env.BASE_URL}data/edificios_afectados.pmtiles`;
	const INCENDIOS_URL = `pmtiles://${import.meta.env.BASE_URL}data/incendios.pmtiles`;
	// Variante histórica (2016..año anterior), generada por
	// scripts/edificios_historicos.py + app/scripts/prepare_data.py. Puede no
	// existir todavía (si esos pasos nunca se han ejecutado): las capas
	// "-historico" de abajo simplemente no tendrán teselas que pintar
	// mientras tanto.
	const EDIFICIOS_URL_HISTORICO = `pmtiles://${import.meta.env.BASE_URL}data/edificios_afectados_historico.pmtiles`;
	const INCENDIOS_URL_HISTORICO = `pmtiles://${import.meta.env.BASE_URL}data/incendios_historico.pmtiles`;

	// Límites provinciales (capa de referencia, no forma parte del pipeline
	// de incendios): estático, no lo genera prepare_data.py, así que vive
	// directamente en public/ (no en public/data/, reservada a lo que ese
	// script regenera) — igual que logo_newtral.png. Generado con
	// `tippecanoe -o spain_provincias.pmtiles -f -l limites_spain -Z 2 -z 14
	// --no-tiny-polygon-reduction-at-maximum-zoom --simplify-only-low-zooms
	// --exclude-all spain_provincias.geojson` (mismos flags que el
	// limites_spain.pmtiles que sustituye, solo con más detalle —fronteras
	// entre provincias, no solo el contorno nacional— y --exclude-all
	// porque el geojson de origen trae properties de aportado a mano
	// (shapeName, shapeISO...) que esta capa no usa, igual que antes se
	// despojaban a mano).
	const LIMITES_URL = `pmtiles://${import.meta.env.BASE_URL}spain_provincias.pmtiles`;

	// Basemap: estilo vectorial "Positron" de CARTO (mismos datos que las
	// teselas raster light_all que se usaban antes, pero editable — ver
	// localizarEtiquetasCarto() más abajo).
	const CARTO_STYLE_URL = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

	// El estilo de CARTO fija el texto de los topónimos administrativos
	// (país/región/continente/algunos núcleos a poco zoom) a {name_en} —
	// place_state, place_country_1/2, place_continent, y los primeros stops
	// de place_city_*/place_hamlet/place_villages/place_town/watername_*—,
	// de ahí que aparecieran en inglés ("CASTILE AND LEÓN", "NAVARRE") en
	// vez de en español. {name} es el nombre local en el esquema de
	// OpenMapTiles que usa CARTO, así que sustituirlo en el texto ya
	// serializado de cada text-field (sin tocar el resto de la expresión,
	// que en varias capas es un array de stops por zoom, no un string
	// suelto) basta para que salgan en español.
	//
	// place_state (el nombre de la comunidad autónoma) trae además
	// "minzoom": 5 en el propio estilo, mientras que la vista inicial/de
	// "restablecer" ronda zoom ~4.7 (ver irAVistaCompleta): con las teselas
	// raster de antes esas etiquetas sí se veían desde ahí (el renderizado
	// raster de CARTO usa sus propias reglas de visibilidad, más permisivas
	// a poca escala, distintas de las que trae declaradas este estilo
	// vectorial), así que al adoptar el estilo vectorial para poder
	// traducirlas dejaron de verse de lejos. Se baja ese minzoom al
	// parchear el estilo, igual que name_en -> name. place_country_1/2 no
	// hace falta tocarlo: ya tiene minzoom 2, por debajo de ese umbral.
	const PLACE_STATE_MINZOOM = 3;

	function localizarEtiquetasCarto(estilo) {
		const layers = estilo.layers.map((layer) => {
			const textField = layer.layout?.['text-field'];
			const localizado =
				textField === undefined
					? undefined
					: JSON.parse(JSON.stringify(textField).replaceAll('name_en', 'name'));
			return {
				...layer,
				...(layer.id === 'place_state' && { minzoom: PLACE_STATE_MINZOOM }),
				...(localizado !== undefined && { layout: { ...layer.layout, 'text-field': localizado } })
			};
		});
		return { ...estilo, layers };
	}

	// Límite de paneo/zoom-out del mapa: un rectángulo que cubre península +
	// Baleares + Ceuta/Melilla (hasta lon ~5, lat ~44.5) y Canarias (hasta
	// lon ~-19.5, lat ~27), con un margen amplio alrededor para poder alejar
	// la vista o desplazarse de más sin toparse enseguida con el borde (un
	// margen ajustado deja el rectángulo más pequeño que el propio
	// viewport en poco zoom, y entonces no hay ni espacio para hacer scroll
	// horizontal). Al ser un único rectángulo también incluye
	// océano/Portugal/Francia/Marruecos de por medio, inevitable si
	// Canarias y la península deben caber en el mismo maxBounds.
	const SPAIN_BOUNDS = [
		[-35, 10],
		[20, 60]
	];

	// Encuadre del botón "restablecer vista": a propósito NO reutiliza
	// SPAIN_BOUNDS. fitBounds centra la vista en el punto medio de las
	// latitudes del rectángulo proyectadas en Mercator, no en la media
	// aritmética — con un rectángulo tan alto como SPAIN_BOUNDS (10°-60°) ese
	// punto medio cae muy al norte (~39°N, hacia Castilla y León) porque la
	// proyección Mercator "estira" mucho más los grados cerca de 60° que
	// cerca de 10°, así que encuadrar SPAIN_BOUNDS tal cual deja Canarias
	// fuera por abajo. Este rectángulo, ceñido al territorio real
	// (península + Baleares + Ceuta/Melilla hasta lat ~44.5, Canarias hasta
	// lat ~27) en vez de al margen de paneo, sí centra ambas partes.
	const RESET_VIEW_BOUNDS = [
		[-19.5, 26.8],
		[5.2, 44.5]
	];

	// Control de mapa (mismo IControl que NavigationControl) para volver al
	// encuadre que muestra toda España (ver irAVistaCompleta()).
	function crearControlRestablecerVista() {
		let container;
		return {
			onAdd(map) {
				container = document.createElement('div');
				container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
				const button = document.createElement('button');
				button.type = 'button';
				button.className = 'reset-view-ctrl';
				button.setAttribute('aria-label', 'Restablecer vista');
				button.title = 'Restablecer vista';
				button.innerHTML =
					'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
					'<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>' +
					'<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>';
				button.addEventListener('click', () => irAVistaCompleta(600));
				container.appendChild(button);
				return container;
			},
			onRemove() {
				container?.parentNode?.removeChild(container);
			}
		};
	}

	// A partir de qué zoom se dibujan los edificios: son huellas de
	// construcción reales (unos pocos metros de lado), invisibles como
	// relleno a escala de toda España. El perímetro del incendio (mucho más
	// grande) sí se ve a cualquier zoom y sirve de referencia para saber
	// dónde acercarse.
	const EDIFICIOS_MINZOOM = 9;
	// Hasta qué zoom aguanta el punto de centroide (ver capa
	// edificios-centroides más abajo) antes de desvanecerse del todo. Es
	// mayor que EDIFICIOS_MINZOOM a propósito: el polígono real ya se
	// dibuja desde zoom 9, pero sigue siendo diminuto, así que el punto se
	// mantiene visible unos zooms más de solape para no perder de vista el
	// edificio justo cuando más se necesita. Tiene que coincidir con el
	// maxzoom real con el que 06_generar_pmtiles.py tesela el polígono (14,
	// fijo por ahora) y con EDIFICIOS_CENTROIDES_MAXZOOM en
	// app/scripts/prepare_data.py, que tesela los centroides hasta este
	// mismo zoom: si se subiera por encima del maxzoom del polígono,
	// tile-join generaría teselas propias en esos zooms de más que solo
	// tendrían el punto (sin polígono, que no llega tan lejos) y, al
	// existir esa tesela, MapLibre ya no haría "overzoom" reutilizando la
	// última tesela del polígono que sí lo tiene — el edificio real
	// desaparecería justo en el tramo final del desvanecido.
	const EDIFICIOS_CENTROIDES_MAXZOOM = 14;

	// Catastro solo usa estos 6 valores de currentUse en todo el territorio
	// (comprobado sobre data/01_geojson completo); el resto de valores del
	// catálogo INSPIRE (hoteles, ocio...) no aparecen en los datos.
	const USOS = {
		'1_residential': 'Residencial',
		'2_agriculture': 'Agrario',
		'3_industrial': 'Industrial',
		'4_1_office': 'Oficinas',
		'4_2_retail': 'Comercial',
		'4_3_publicServices': 'Servicios públicos'
	};

	// mostrarCentroides vive en App.svelte (mismo patrón que vista) porque el
	// interruptor ahora es parte del Sidebar, no un control del mapa: aquí
	// solo se lee para aplicar la visibilidad de la capa, ver el $effect más
	// abajo.
	let { vista = 'actual', mostrarCentroides = true } = $props();

	let mapContainer;
	let map;
	let popup;
	// Feature completa (no solo el id): con dos variantes de datos
	// (actual/histórico) a la vez en el estilo, hover/clic necesitan saber
	// también de qué source/source-layer viene el feature para poder
	// limpiar el feature-state correcto (ver setEdificioState()).
	let hovered = null;
	let selected = null;
	// Se pone a true en el evento 'load' del mapa; el $effect de más abajo
	// lo usa para no intentar tocar capas antes de que existan.
	let mapReady = $state(false);

	const EDIFICIOS_LAYERS = ['edificios-fill', 'edificios-fill-historico'];
	const INCENDIOS_LAYERS = ['incendios-fill', 'incendios-fill-historico'];
	// Las capas que genera capasDataset() para la variante "actual" (sin
	// sufijo) cuya visibilidad depende solo de `vista`; aplicarVista() añade
	// "-historico" para tocar también la variante histórica de cada una.
	// edificios-centroides no está aquí: su visibilidad depende además del
	// interruptor de mostrarCentroides, así que se gestiona aparte en
	// aplicarVisibilidadCentroides().
	const DATASET_LAYER_IDS = ['incendios-fill', 'incendios-line', 'edificios-fill', 'edificios-line'];

	// Genera las 5 capas de un dataset (incendios + edificios) parametrizadas
	// por sufijo/fuente/visibilidad inicial, para no duplicar literalmente la
	// definición de estilo entre la variante actual y la histórica: ambas
	// coexisten siempre en el mapa (ver sources más abajo) y sólo se
	// distinguen por qué fuente leen y si arrancan visibles u ocultas — el
	// $effect sobre `vista` alterna la visibilidad después, sin recrear nada.
	function capasDataset(sufijo, edificiosSource, incendiosSource, visible) {
		const visibility = visible ? 'visible' : 'none';
		return [
			{
				id: `incendios-fill${sufijo}`,
				type: 'fill',
				source: incendiosSource,
				'source-layer': 'incendios',
				layout: { visibility },
				paint: { 'fill-color': FIRE_COLOR, 'fill-opacity': 0.16 }
			},
			{
				id: `incendios-line${sufijo}`,
				type: 'line',
				source: incendiosSource,
				'source-layer': 'incendios',
				layout: { visibility },
				paint: { 'line-color': FIRE_COLOR, 'line-width': 1.4 }
			},
			{
				// Punto del centroide de cada edificio, generado por
				// app/scripts/prepare_data.py: a escala de toda España el
				// polígono real (huella del edificio) es sub-píxel e
				// invisible, así que este punto sirve para "ver" los
				// edificios afectados desde lejos, incluidos los que están
				// solos (sin otros edificios cerca que formen una mancha
				// visible). El desvanecido (circle-opacity/circle-stroke-
				// opacity) solo ocurre entre EDIFICIOS_MINZOOM y
				// EDIFICIOS_CENTROIDES_MAXZOOM —el tramo de solape real con
				// el polígono, ver ambas constantes más arriba—, no desde
				// zoom 2: con solo dos paradas (interpolate usa el valor de
				// la primera para cualquier zoom anterior) el punto se
				// mantiene a opacidad plena mientras se navega de lejos, y
				// solo empieza a desvanecerse justo cuando el polígono
				// empieza a dibujarse. Antes el propio cubic-bezier corría a
				// lo largo de todo el rango 2→13: al ser una curva ease
				// simétrica, el grueso del desvanecido caía sobre zoom
				// 5-9 —antes de que el polígono existiera—, así que el punto
				// ya estaba casi invisible al llegar a zoom 9 y luego se
				// quedaba como un resto tenue el resto del solape, en vez de
				// desvanecerse junto con la aparición del polígono. La curva
				// cubic-bezier ("ease", arranca y termina sin velocidad, como
				// una transición CSS) se mantiene para que ese tramo más
				// corto no se note como un corte brusco.
				id: `edificios-centroides${sufijo}`,
				type: 'circle',
				source: edificiosSource,
				'source-layer': 'edificios_centroides',
				maxzoom: EDIFICIOS_CENTROIDES_MAXZOOM,
				layout: { visibility },
				paint: {
					'circle-color': BUILDING_COLOR,
					'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 3, EDIFICIOS_CENTROIDES_MAXZOOM, 7],
					'circle-opacity': [
						'interpolate', ['cubic-bezier', 0.42, 0, 0.58, 1], ['zoom'],
						EDIFICIOS_MINZOOM, 0.75,
						EDIFICIOS_CENTROIDES_MAXZOOM, 0
					],
					'circle-stroke-color': BUILDING_BORDER_COLOR,
					'circle-stroke-width': 1,
					'circle-stroke-opacity': [
						'interpolate', ['cubic-bezier', 0.42, 0, 0.58, 1], ['zoom'],
						EDIFICIOS_MINZOOM, BUILDING_BORDER_OPACITY,
						EDIFICIOS_CENTROIDES_MAXZOOM, 0
					]
				}
			},
			{
				id: `edificios-fill${sufijo}`,
				type: 'fill',
				source: edificiosSource,
				'source-layer': EDIFICIOS_SOURCE_LAYER,
				minzoom: EDIFICIOS_MINZOOM,
				layout: { visibility },
				paint: {
					'fill-color': BUILDING_COLOR,
					'fill-opacity': ['case', HIGHLIGHTED, 1, 0.85]
				}
			},
			{
				id: `edificios-line${sufijo}`,
				type: 'line',
				source: edificiosSource,
				'source-layer': EDIFICIOS_SOURCE_LAYER,
				minzoom: EDIFICIOS_MINZOOM,
				layout: { visibility },
				paint: {
					'line-color': ['case', HIGHLIGHTED, BUILDING_HIGHLIGHT_COLOR, BUILDING_BORDER_COLOR],
					'line-width': ['case', HIGHLIGHTED, 2, 0.6],
					'line-opacity': ['case', HIGHLIGHTED, 1, BUILDING_BORDER_OPACITY]
				}
			}
		];
	}

	onMount(async () => {
		// El basemap raster (light_all) que se usaba antes viene de este mismo
		// estilo vectorial de CARTO, pero pre-renderizado con los topónimos
		// administrativos (país/región/continente) fijados a {name_en} — de
		// ahí "CASTILE AND LEÓN", "NAVARRE" en vez de en español. Cargando el
		// estilo vectorial directamente se puede parchear ese campo antes de
		// dárselo al mapa: ver localizarEtiquetasCarto().
		const cartoStyle = localizarEtiquetasCarto(await fetch(CARTO_STYLE_URL).then((r) => r.json()));

		map = new MapLibreMap({
			container: mapContainer,
			style: {
				version: 8,
				sources: {
					...cartoStyle.sources,
					incendios: { type: 'vector', url: INCENDIOS_URL },
					'incendios-historico': { type: 'vector', url: INCENDIOS_URL_HISTORICO },
					// promoteId por source-layer (no un string suelto): la
					// fuente tiene dos capas — "edificios_afectados" (el
					// polígono real, con `reference`, la referencia
					// catastral única que se usa como id de feature-state
					// para resaltar en hover/clic, ver más abajo) y
					// "edificios_centroides" (puntos sin atributos, solo
					// decorativos, ver EDIFICIOS_MINZOOM). Sin esto maplibre
					// no tiene forma de identificar features individuales de
					// un vector tile.
					edificios: {
						type: 'vector',
						url: EDIFICIOS_URL,
						promoteId: { [EDIFICIOS_SOURCE_LAYER]: 'reference' }
					},
					// Misma estructura que "edificios" (source-layer con el
					// mismo nombre dentro de un pmtiles distinto, generado
					// por scripts/edificios_historicos.py + prepare_data.py),
					// en una fuente separada para poder tener ambas variantes
					// cargadas a la vez y solo alternar qué capas se ven (ver
					// capasDataset()/el $effect sobre `vista` más abajo).
					'edificios-historico': {
						type: 'vector',
						url: EDIFICIOS_URL_HISTORICO,
						promoteId: { [EDIFICIOS_SOURCE_LAYER]: 'reference' }
					},
					limites: { type: 'vector', url: LIMITES_URL }
				},
				sprite: cartoStyle.sprite,
				glyphs: cartoStyle.glyphs,
				layers: [
					...cartoStyle.layers,
					{
						id: 'limites-line',
						type: 'line',
						source: 'limites',
						'source-layer': 'limites_spain',
						paint: { 'line-color': '#494949', 'line-width': 1 }
					},
					...capasDataset('', 'edificios', 'incendios', vista === 'actual'),
					...capasDataset('-historico', 'edificios-historico', 'incendios-historico', vista === 'historico')
				]
			},
			center: [-3.7, 40.2],
			zoom: 5,
			maxBounds: SPAIN_BOUNDS
		});

		map.addControl(new NavigationControl(), 'top-right');
		map.addControl(crearControlRestablecerVista(), 'top-right');
		popup = new Popup({ closeButton: true, maxWidth: '280px' });
		// El popup se reutiliza (mismo objeto) para incendios y edificios, así
		// que "close" solo salta cuando el usuario lo cierra de verdad (botón,
		// clic fuera, Escape) y no al pasar de un edificio a otro con clic
		// directo (ver clearSelected() explícito en los handlers de clic).
		popup.on('close', clearSelected);

		map.on('load', () => {
			mapReady = true;
		});

		for (const layerId of [...INCENDIOS_LAYERS, ...EDIFICIOS_LAYERS]) {
			map.on('mouseenter', layerId, () => {
				map.getCanvas().style.cursor = 'pointer';
			});
			map.on('mouseleave', layerId, () => {
				map.getCanvas().style.cursor = '';
			});
		}

		// Resalta el edificio bajo el ratón (feature-state "hover", ver
		// HIGHLIGHTED arriba). mousemove en vez de mouseenter porque el
		// usuario puede pasar de un edificio a otro sin que el ratón salga
		// nunca de la capa. Los mismos handlers sirven para la capa actual y
		// la histórica (EDIFICIOS_LAYERS): qué source/source-layer tocar en
		// setFeatureState sale del propio feature del evento, no de una
		// constante fija, así que no hace falta duplicar esta lógica.
		for (const layerId of EDIFICIOS_LAYERS) {
			map.on('mousemove', layerId, (e) => {
				if (!e.features.length) return;
				const feature = e.features[0];
				if (hovered && hovered.id === feature.id && hovered.source === feature.source) return;
				clearHover();
				hovered = feature;
				setEdificioState(feature, { hover: true });
			});
			map.on('mouseleave', layerId, clearHover);

			map.on('click', layerId, (e) => {
				clearSelected();
				selected = e.features[0];
				setEdificioState(selected, { selected: true });
				showPopup(e, 'edificios');
			});
		}

		for (const layerId of INCENDIOS_LAYERS) {
			map.on('click', layerId, (e) => {
				// Si el clic también toca un edificio, el popup del edificio
				// ya se encarga (es la capa más específica de las dos).
				const edificios = map.queryRenderedFeatures(e.point, { layers: EDIFICIOS_LAYERS });
				if (edificios.length) return;
				clearSelected();
				showPopup(e, 'incendios');
			});
		}

		return () => map.remove();
	});

	// Alterna qué dataset se ve al cambiar de pestaña (Sidebar): no se
	// destruyen/recrean fuentes ni capas, solo su visibilidad (ambas están
	// siempre declaradas en el estilo, ver capasDataset() arriba), y se
	// reencuadra el mapa al nuevo dataset activo. Guardado tras `mapReady`
	// porque `vista` (prop) puede cambiar antes de que el mapa exista.
	$effect(() => {
		const v = vista;
		if (!mapReady) return;
		aplicarVista(v);
	});

	// El interruptor de puntos vive en el Sidebar (ver App.svelte), así que
	// su cambio llega aquí como prop en vez de como evento de un control del
	// mapa: este efecto es el que de verdad mueve la capa cuando cambia.
	$effect(() => {
		mostrarCentroides;
		if (!mapReady) return;
		aplicarVisibilidadCentroides();
	});

	// El mapa siempre se encuadra en la vista completa (RESET_VIEW_BOUNDS,
	// misma que el botón de restablecer) tanto al arrancar como al cambiar
	// de pestaña (actual/histórico) — nunca se ajusta a los datos afectados
	// de esa vista en concreto: así el punto de partida es siempre el mismo,
	// sin importar qué pestaña esté activa. Solo la primera vez (al
	// arrancar) el encuadre es instantáneo (duration 0); al cambiar de
	// pestaña después sí se anima.
	let primeraCarga = true;

	function aplicarVista(v) {
		for (const base of DATASET_LAYER_IDS) {
			map.setLayoutProperty(base, 'visibility', v === 'actual' ? 'visible' : 'none');
			map.setLayoutProperty(`${base}-historico`, 'visibility', v === 'historico' ? 'visible' : 'none');
		}
		aplicarVisibilidadCentroides();
		irAVistaCompleta(primeraCarga ? 0 : 600);
		primeraCarga = false;
	}

	// edificios-centroides depende de dos condiciones a la vez (la vista
	// activa Y el interruptor de mostrarCentroides, ver Sidebar), así que va
	// aparte del bucle genérico de aplicarVista() — se llama tanto desde ahí
	// (al arrancar o cambiar de pestaña) como desde el $effect sobre
	// mostrarCentroides más abajo (que no debe tocar ni la vista ni el
	// encuadre, solo esta capa).
	function aplicarVisibilidadCentroides() {
		const visibilidad = mostrarCentroides ? 'visible' : 'none';
		map.setLayoutProperty('edificios-centroides', 'visibility', vista === 'actual' ? visibilidad : 'none');
		map.setLayoutProperty('edificios-centroides-historico', 'visibility', vista === 'historico' ? visibilidad : 'none');
	}

	// Encuadre fijo con España + Canarias (RESET_VIEW_BOUNDS), usado tanto al
	// arrancar como por el botón de "restablecer vista". cameraForBounds() en
	// vez de fitBounds() directo: da el {center, zoom} que fitBounds usaría,
	// para poder restar 0.2 al zoom resultante (un pelín más alejado que el
	// encuadre exacto de los bounds, a petición) antes de animar.
	function irAVistaCompleta(duration) {
		const camera = map.cameraForBounds(RESET_VIEW_BOUNDS, { padding: 0 });
		if (!camera) return;
		map.easeTo({ center: camera.center, zoom: camera.zoom - 0.2, duration });
	}

	function setEdificioState(feature, state) {
		map.setFeatureState({ source: feature.source, sourceLayer: feature.sourceLayer, id: feature.id }, state);
	}

	function clearHover() {
		if (hovered) setEdificioState(hovered, { hover: false });
		hovered = null;
	}

	function clearSelected() {
		if (selected) setEdificioState(selected, { selected: false });
		selected = null;
	}

	function showPopup(e, kind) {
		const props = e.features[0].properties;
		popup
			.setLngLat(e.lngLat)
			.setHTML(kind === 'edificios' ? edificioHTML(props) : incendioHTML(props))
			.addTo(map);
	}

	function row(label, value) {
		return value == null || value === '' ? '' : `<div><dt>${label}</dt><dd>${value}</dd></div>`;
	}

	function edificioHTML(p) {
		const viviendas =
			p.numberOfDwellings > 0
				? `${p.numberOfDwellings} ${p.numberOfDwellings === 1 ? 'vivienda' : 'viviendas'}`
				: null;
		// "beginning" es la fecha de construcción del GML de Catastro
		// (siempre a 1 de enero: solo el año es un dato real).
		const anioConstruccion = p.beginning ? p.beginning.slice(0, 4) : null;
		const provincia = nombreProvincia(p.PROVINCIA);
		return `
			<div class="popup">
				<div class="popup-header">
					<span class="popup-icon building" aria-hidden="true"></span>
					<div class="popup-title">
						<strong>Uso: ${USOS[p.currentUse] ?? 'Edificio'}</strong>
						<span class="popup-sub">${p.COMMUNE ?? ''}</span>
						${provincia ? `<span class="popup-sub">${provincia}</span>` : ''}
					</div>
				</div>
				<dl class="popup-rows">
					${row('Referencia catastral', p.reference)}
					${row('Construcción', anioConstruccion)}
					${row('Viviendas', viviendas)}
					${row('Incendio', p.FECHA_INCENDIO)}
				</dl>
			</div>
		`;
	}

	function incendioHTML(p) {
		return `
			<div class="popup">
				<div class="popup-header">
					<span class="popup-icon fire" aria-hidden="true"></span>
					<div class="popup-title">
						<strong>${p.COMMUNE ?? 'Incendio'}</strong>
						<span class="popup-sub">${p.PROVINCE ?? ''}</span>
					</div>
				</div>
				<dl class="popup-rows">
					${row('Inicio', p.FECHA_INCENDIO)}
					${row('Superficie', p.HECTAREAS != null ? `${p.HECTAREAS} ha` : null)}
				</dl>
			</div>
		`;
	}

	onDestroy(() => {
		if (map) map.remove();
	});
</script>

<div class="map" bind:this={mapContainer}></div>

<style>
	.map {
		position: absolute;
		inset: 0;
	}

	:global(.reset-view-ctrl) {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 29px;
		height: 29px;
		color: #333;
	}

	:global(.reset-view-ctrl:hover) {
		color: #000;
	}

	:global(.maplibregl-popup-content) {
		padding: 12px 14px;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--card);
		box-shadow: var(--shadow-lg);
		font-family: var(--font);
	}

	:global(.maplibregl-popup-close-button) {
		right: 6px;
		top: 4px;
		width: 20px;
		height: 20px;
		font-size: 16px;
		line-height: 1;
		color: var(--ink-muted);
		border-radius: 50%;
	}

	:global(.maplibregl-popup-close-button:hover) {
		color: var(--ink);
		background: var(--card-2);
	}

	:global(.maplibregl-popup-anchor-bottom .maplibregl-popup-tip) {
		border-top-color: var(--card);
	}

	:global(.maplibregl-popup-anchor-top .maplibregl-popup-tip) {
		border-bottom-color: var(--card);
	}

	:global(.maplibregl-popup-anchor-left .maplibregl-popup-tip) {
		border-right-color: var(--card);
	}

	:global(.maplibregl-popup-anchor-right .maplibregl-popup-tip) {
		border-left-color: var(--card);
	}

	:global(.popup) {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 170px;
		color: var(--ink);
	}

	:global(.popup-header) {
		display: flex;
		align-items: flex-start;
		gap: 8px;
	}

	:global(.popup-icon) {
		flex-shrink: 0;
		width: 10px;
		height: 10px;
		margin-top: 3px;
		border-radius: 3px;
	}

	:global(.popup-icon.fire) {
		background: var(--fire);
	}

	:global(.popup-icon.building) {
		background: #01f3b3;
	}

	:global(.popup-title) {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	:global(.popup-title strong) {
		font-size: 13.5px;
		font-weight: 700;
		line-height: 1.25;
	}

	:global(.popup-sub) {
		font-size: 11.5px;
		color: var(--ink-muted);
	}

	:global(.popup-rows) {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding-top: 8px;
		border-top: 1px solid var(--border);
	}

	:global(.popup-rows > div) {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 14px;
	}

	:global(.popup-rows dt) {
		font-size: 11px;
		color: var(--ink-muted);
	}

	:global(.popup-rows dd) {
		margin: 0;
		font-family: var(--font-mono);
		font-size: 12px;
		font-weight: 600;
		color: var(--ink);
		text-align: right;
	}
</style>
