<script>
	import MapView from './lib/MapView.svelte';
	import Sidebar from './lib/Sidebar.svelte';

	// Rutas a /public/*: hay que anteponer el base path (vacío en dev, el
	// subpath del repo en el build de GitHub Pages, ver vite.config.js).
	const asset = (path) => `${import.meta.env.BASE_URL}${path}`;

	// 'actual' (temporada 2026, siempre disponible) o 'historico'
	// (2016..año anterior, solo si app/scripts/prepare_data.py --historico
	// ya se ha ejecutado). Vive aquí porque MapView (qué capas de pmtiles
	// mostrar) y Sidebar (qué resumen mostrar, más las pestañas para
	// cambiarla) necesitan compartir el mismo estado.
	let vista = $state('actual');
	// Interruptor de los puntos de centroide a poco zoom (ver MapView),
	// controlado desde el Sidebar; vive aquí por el mismo motivo que
	// `vista`: MapView (aplica la visibilidad de la capa) y Sidebar (dibuja
	// el interruptor) necesitan compartir el mismo estado.
	let mostrarCentroides = $state(true);

	let resumenActual = $state(null);
	let resumenHistorico = $state(null);
	const resumen = $derived(vista === 'historico' ? resumenHistorico : resumenActual);
	// Aparte de `resumen`: la pestaña "histórico" de Sidebar necesita poder
	// rotular su rango de años aunque la vista activa sea "actual" (y por
	// tanto resumen todavía no sea resumenHistorico).
	const periodoHistorico = $derived(resumenHistorico?.periodo ?? null);

	// Ambos se piden una sola vez al montar: son ligeros (resumen.json es de
	// pocos KB), así que no compensa la complejidad de pedir el histórico
	// solo al abrir su pestaña. Si resumen_historico.json todavía no existe
	// (--historico no se ha ejecutado nunca), el fetch falla en silencio y
	// resumenHistorico se queda a null — igual que ya se comportaba este
	// efecto si resumen.json faltaba, sin manejo de errores explícito.
	$effect(() => {
		fetch(asset('data/resumen.json'))
			.then((res) => res.json())
			.then((data) => {
				resumenActual = data;
			});
		fetch(asset('data/resumen_historico.json'))
			.then((res) => res.json())
			.then((data) => {
				resumenHistorico = data;
			})
			.catch(() => {});
	});
</script>

<main>
	<MapView {vista} {mostrarCentroides} />

	<header>
		<span class="eyebrow">Edificios afectados por incendios</span>
		<img class="logo" src={asset('logo_newtral.png')} alt="Newtral" />
	</header>

	<Sidebar {resumen} {periodoHistorico} bind:vista bind:mostrarCentroides />
</main>

<style>
	main {
		position: fixed;
		inset: 0;
	}

	header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 20;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 14px 20px;
		padding-top: calc(14px + env(safe-area-inset-top));
		background: var(--card);
		border-bottom: 1px solid var(--border);
		box-shadow: 0 1px 0 rgba(22, 20, 14, 0.05);
	}

	.eyebrow {
		font-size: 14px;
		font-weight: 800;
		letter-spacing: 0.03em;
		text-transform: uppercase;
		color: var(--ink);
	}

	.logo {
		height: 20px;
		width: auto;
		flex-shrink: 0;
		display: block;
	}

	@media (max-width: 640px) {
		.eyebrow {
			font-size: 12px;
		}

		.logo {
			height: 16px;
		}
	}
</style>
