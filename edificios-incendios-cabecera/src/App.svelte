<script>
	// Cabecera standalone, sin datos propios: reutiliza resumen.json, el
	// mismo JSON que ya genera app/scripts/prepare_data.py (generar_categorias())
	// para la app del mapa, y que queda publicado junto a esta cabecera en el
	// mismo repo (ver vite.config.js). Solo se usa el campo "categorias":
	// los residenciales se cuentan en viviendas (suma de numberOfDwellings,
	// el impacto humano real), no en edificios, y el resto de categorías de
	// uso en número de edificios — igual desglose que ya muestra el panel
	// lateral del mapa (Sidebar.svelte), reutilizado aquí en un widget
	// compacto pensado para insertarse en un artículo.
	//
	// __RESUMEN_URL__ lo inyecta vite.config.js (define): en producción
	// apunta al resumen.json que publica la app del mapa en el mismo repo;
	// en dev, a un middleware que lo sirve desde disco.
	import { onMount } from 'svelte';

	const RESUMEN_URL = __RESUMEN_URL__;

	// undefined: cargando · null: error · objeto: cargado
	let resumen = $state(undefined);

	onMount(async () => {
		try {
			const r = await fetch(RESUMEN_URL);
			if (!r.ok) throw new Error(`HTTP ${r.status}`);
			resumen = await r.json();
		} catch (e) {
			resumen = null;
		}
	});

	const viviendas = $derived(resumen?.categorias?.find((c) => c.id === 'viviendas') ?? null);
	const otrasCategorias = $derived(resumen?.categorias?.filter((c) => c.id !== 'viviendas') ?? []);

	function formatNumber(n) {
		if (n == null) return '—';
		// useGrouping: true a propósito: el agrupado "auto" de es-ES no pone
		// separador de miles por debajo de 10000 (p.ej. 5000 -> "5000").
		return n.toLocaleString('es-ES', { useGrouping: true });
	}

	function formatFecha(iso) {
		if (!iso) return '—';
		const [y, m, d] = iso.split('-');
		return `${d}/${m}/${y}`;
	}
</script>

<div class="cabecera">
	<div class="barra-top"></div>

	<div class="inner">
		<h1 class="titulo">Edificios afectados por incendios en 2026, por tipo de edificio</h1>

		{#if resumen === undefined}
			<!-- cargando -->
		{:else if resumen === null}
			<p class="error">No se pudieron cargar los datos.</p>
		{:else}
			<div class="hero">
				<span class="hero-value">{formatNumber(viviendas?.valor)}</span>
				<span class="hero-label">Viviendas afectadas por incendios en 2026</span>
			</div>

			{#if otrasCategorias.length}
				<div class="stats-grid">
					{#each otrasCategorias as cat (cat.id)}
						<div class="stat" class:stat-muted={cat.id === 'sin_clasificar'}>
							<span class="stat-value">{formatNumber(cat.valor)}</span>
							<span class="stat-label">{cat.label}</span>
						</div>
					{/each}
				</div>
			{/if}

			{#if resumen.fecha}
				<p class="actualizado">Datos actualizados a {formatFecha(resumen.fecha)}</p>
			{/if}
		{/if}
	</div>
</div>

<style>
	/* Mismos tokens de color que app.css (app/src/app.css), copiados aquí en
	   vez de importados: esta cabecera es un proyecto Vite aparte, pensado
	   para insertarse embebido en otra página que no comparte esos estilos. */
	.cabecera {
		--card: #fffdf8;
		--card-2: #e7e2d2;
		--ink: #16181a;
		--ink-muted: #6b6558;
		--fire: #ff2a01;
		--border: rgba(28, 22, 10, 0.14);
		--shadow: 0 1px 0 rgba(22, 20, 14, 0.06), 0 6px 16px rgba(22, 20, 14, 0.12);
		--font: 'Helvetica Neue', Helvetica, Arial, sans-serif;
		--font-mono: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;

		font-family: var(--font);
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: var(--shadow);
		overflow: hidden;
	}

	.barra-top {
		height: 4px;
		background: var(--fire);
	}

	.inner {
		padding: 24px 28px 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 16px;
	}

	.titulo {
		margin: 0;
		font-size: 22px;
		font-weight: 800;
		letter-spacing: -0.02em;
		color: var(--ink);
		line-height: 1.2;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}

	.hero-value {
		font-family: var(--font-mono);
		font-size: 44px;
		font-weight: 700;
		line-height: 1;
		color: var(--fire);
		font-variant-numeric: tabular-nums;
	}

	.hero-label {
		font-size: 11px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--ink-muted);
	}

	.stats-grid {
		width: 100%;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
		gap: 8px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 2px;
		padding: 10px 6px;
		border-radius: 8px;
		background: var(--card-2);
		border: 1px solid var(--border);
	}

	.stat-value {
		font-family: var(--font-mono);
		font-size: 19px;
		font-weight: 700;
		line-height: 1.1;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}

	.stat-label {
		font-size: 10.5px;
		line-height: 1.2;
		color: var(--ink-muted);
	}

	.stat-muted {
		border-style: dashed;
		background: transparent;
	}

	.stat-muted .stat-value {
		color: var(--ink-muted);
	}

	.actualizado {
		margin: 0;
		font-size: 12px;
		color: var(--ink-muted);
		font-style: italic;
	}

	.error {
		color: var(--fire);
		font-size: 13px;
		margin: 0;
	}

	@media (max-width: 480px) {
		.inner {
			padding: 16px 14px 14px;
			gap: 12px;
		}
		.titulo {
			font-size: 17px;
		}
		.hero-value {
			font-size: 32px;
		}
		.stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
</style>
