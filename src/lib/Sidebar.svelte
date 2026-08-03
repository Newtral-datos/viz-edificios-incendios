<script>
	import { nombreProvincia } from './provincias.js';

	let {
		resumen = null,
		periodoHistorico = null,
		vista = $bindable('actual'),
		mostrarCentroides = $bindable(true)
	} = $props();

	// Solo tiene efecto en móvil: en escritorio el tirador no es clicable.
	let collapsed = $state(false);
	let provinciasExpandido = $state(false);

	// Etiqueta de la pestaña "histórico": usa el rango real en cuanto
	// resumen_historico.json ha cargado (periodoHistorico llega siempre,
	// independientemente de qué pestaña esté activa, ver App.svelte); antes
	// de eso, o si --historico no se ha ejecutado nunca, se queda en un
	// rótulo genérico en vez de bloquear el render de las pestañas.
	const historicoTabLabel = $derived(
		periodoHistorico ? `${periodoHistorico.anio_inicio}–${periodoHistorico.anio_fin}` : 'Histórico'
	);

	// "en 2026" / "entre 2016 y 2025": reutilizado en el hero y en la nota
	// final. Con la vista histórica activa pero resumen.periodo todavía sin
	// cargar (fetch en curso) cae al genérico "histórico" en vez de mostrar
	// un rango a medias.
	const periodoLabel = $derived(
		vista === 'historico'
			? resumen?.periodo
				? `entre ${resumen.periodo.anio_inicio} y ${resumen.periodo.anio_fin}`
				: 'en el histórico'
			: 'en 2026'
	);

	function formatNumber(n) {
		if (n == null) return '—';
		// useGrouping: true a propósito: el agrupado "auto" de es-ES no pone
		// separador de miles por debajo de 10000 (p.ej. 5000 -> "5000"), y
		// aquí interesa el punto desde 1000 (p.ej. "5.000").
		return n.toLocaleString('es-ES', { useGrouping: true });
	}

	function formatFecha(iso) {
		if (!iso) return '—';
		const [y, m, d] = iso.split('-');
		return `${d}/${m}/${y}`;
	}

	// Provincias más afectadas: cada una trae sus viviendas y edificios
	// afectados ya segregados (ver 05_edificios_afectados.py), así que una
	// provincia con muchas viviendas afectadas pero 0 edificios "de otro
	// tipo" no debe quedar fuera solo por tener 0 en la otra columna.
	const provincias = $derived(
		resumen?.provincias?.filter((p) => p.num_viviendas_afectadas > 0 || p.num_edificios_afectados > 0) ?? []
	);
	const provinciasVisibles = $derived(provinciasExpandido ? provincias : provincias.slice(0, 6));

	function provinciaValor(p) {
		const partes = [];
		if (p.num_viviendas_afectadas > 0) partes.push(`${formatNumber(p.num_viviendas_afectadas)} viv.`);
		if (p.num_edificios_afectados > 0) partes.push(`${formatNumber(p.num_edificios_afectados)} ed.`);
		return partes.join(' | ');
	}

	// Un edificio residencial de 15 viviendas no es lo mismo que uno
	// agrícola: en vez de un único total "edificios afectados", se separa
	// la cifra que importa de verdad (viviendas, la de impacto humano) del
	// resto de categorías, contadas en número de edificios. Ver
	// generar_categorias() en app/scripts/prepare_data.py.
	const viviendas = $derived(resumen?.categorias?.find((c) => c.id === 'viviendas') ?? null);
	const otrasCategorias = $derived(resumen?.categorias?.filter((c) => c.id !== 'viviendas') ?? []);
</script>

<div class="panel" class:collapsed>
	<button
		type="button"
		class="handle-row"
		aria-expanded={!collapsed}
		onclick={() => (collapsed = !collapsed)}
	>
		<span class="handle" aria-hidden="true"></span>
		<span class="handle-summary">
			{formatNumber(viviendas?.valor)} viviendas afectadas
		</span>
		<svg class="handle-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
			<path d="m6 9 6 6 6-6"/>
		</svg>
	</button>

	<div class="panel-body">
		<div class="tabs" role="tablist" aria-label="Periodo">
			<button
				type="button"
				role="tab"
				aria-selected={vista === 'actual'}
				class:active={vista === 'actual'}
				onclick={() => (vista = 'actual')}
			>
				2026
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={vista === 'historico'}
				class:active={vista === 'historico'}
				onclick={() => (vista = 'historico')}
			>
				{historicoTabLabel}
			</button>
		</div>

		<div class="hero">
			<span class="hero-value">{formatNumber(viviendas?.valor)}</span>
			<span class="hero-label">Viviendas afectadas por incendios {periodoLabel}</span>
			<button
				type="button"
				class="centroides-toggle"
				class:active={mostrarCentroides}
				role="switch"
				aria-checked={mostrarCentroides}
				title="Mostrar/ocultar los puntos de edificio a poco zoom en el mapa"
				onclick={() => (mostrarCentroides = !mostrarCentroides)}
			>
				<span class="centroides-toggle-label">Puntos en el mapa</span>
				<span class="centroides-toggle-track"><span class="centroides-toggle-thumb"></span></span>
			</button>
		</div>

		{#if otrasCategorias.length}
			<div class="stats-block">
				<span class="table-title">Por tipo de edificio</span>
				<div class="stats-grid">
					{#each otrasCategorias as cat (cat.id)}
						<div class="stat" class:stat-muted={cat.id === 'sin_clasificar'}>
							<span class="stat-value">{formatNumber(cat.valor)}</span>
							<span class="stat-label">{cat.label}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		{#if provincias.length}
			<div class="table">
				<span class="table-title">Provincias más afectadas</span>
				<ul>
					{#each provinciasVisibles as p (p.ccaa + p.provincia)}
						<li>
							<span class="table-name">{nombreProvincia(p.provincia)}</span>
							<span class="table-val">{provinciaValor(p)}</span>
						</li>
					{/each}
				</ul>
				{#if provincias.length > 6}
					<button type="button" class="table-toggle" onclick={() => (provinciasExpandido = !provinciasExpandido)}>
						{provinciasExpandido ? 'Ver menos' : `Ver las ${provincias.length} provincias`}
					</button>
				{/if}
			</div>
		{/if}

		<p class="note">
			<i>Edificios del Catastro dentro del perímetro de un incendio iniciado
			{periodoLabel}. Los residenciales se cuentan en viviendas, no en edificios.<br>
			<b>
				{#if resumen?.fecha}
					{vista === 'historico'
						? `Datos generados el ${formatFecha(resumen.fecha)}.`
						: `Datos actualizados a ${formatFecha(resumen.fecha)}.`}
				{/if}
			</b></i>
		</p>
	</div>
</div>

<style>
	.panel {
		position: absolute;
		top: 76px;
		left: 16px;
		z-index: 10;
		width: 300px;
		max-height: calc(100vh - 96px);
		overflow-y: auto;
		padding: 16px;
		border-radius: 12px;
		border: 1px solid var(--border);
		background: var(--card);
		box-shadow: var(--shadow);
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.panel-body {
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
		gap: 16px;
	}

	.handle-row {
		display: none;
	}

	/* ── Pestañas temporada actual / histórico ── */
	.tabs {
		display: flex;
		flex-shrink: 0;
		gap: 2px;
		padding: 3px;
		border-radius: 9px;
		background: var(--card-2);
		border: 1px solid var(--border);
	}

	.tabs button {
		flex: 1;
		padding: 6px 4px;
		font-family: var(--font-mono);
		font-size: 12px;
		font-weight: 600;
		color: var(--ink-muted);
		background: transparent;
		border: none;
		border-radius: 6px;
		cursor: pointer;
	}

	.tabs button.active {
		color: var(--ink);
		background: var(--card);
		box-shadow: var(--shadow);
	}

	/* ── Cifra principal ── */
	.hero {
		position: relative;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 2px;
		padding: 14px 16px;
		border-radius: 10px;
		background: linear-gradient(150deg, rgba(255, 42, 1, 0.09), rgba(255, 42, 1, 0.02));
		border: 1px solid rgba(255, 42, 1, 0.16);
	}

	.hero-value {
		font-family: var(--font-mono);
		font-size: 34px;
		font-weight: 600;
		line-height: 1;
		color: var(--fire);
	}

	.hero-label {
		margin-top: 4px;
		font-size: 11px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--ink-muted);
	}

	/* ── Interruptor de los puntos de centroide (ver MapView), dentro de la
	   caja de viviendas para que quede junto a la estadística que ilustra en
	   el mapa, en vez de perdido como control aparte encima del mapa. ── */
	.centroides-toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		width: 100%;
		margin-top: 10px;
		padding: 10px 0 0;
		border: none;
		border-top: 1px solid rgba(255, 42, 1, 0.16);
		background: transparent;
		cursor: pointer;
	}

	.centroides-toggle-label {
		font-size: 10.5px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--ink-muted);
	}

	.centroides-toggle.active .centroides-toggle-label {
		color: var(--ink);
	}

	.centroides-toggle-track {
		position: relative;
		flex-shrink: 0;
		width: 30px;
		height: 17px;
		border-radius: 999px;
		background: var(--card-2);
		border: 1px solid var(--border);
		transition: background-color 0.15s ease, border-color 0.15s ease;
	}

	.centroides-toggle-thumb {
		position: absolute;
		top: 1px;
		left: 1px;
		width: 13px;
		height: 13px;
		border-radius: 50%;
		background: var(--card);
		box-shadow: 0 1px 2px rgba(22, 20, 14, 0.3);
		transition: transform 0.15s ease;
	}

	.centroides-toggle.active .centroides-toggle-track {
		background: var(--teal-deep);
		border-color: var(--teal-deep);
	}

	.centroides-toggle.active .centroides-toggle-thumb {
		transform: translateX(13px);
	}

	.table-title {
		font-size: 11px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		text-align: center;
		color: var(--ink-muted);
	}

	/* ── Categorías (tipo de edificio) ── */
	.stats-block {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 6px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 1px;
		padding: 8px 6px;
		border-radius: 8px;
		background: var(--card-2);
		border: 1px solid var(--border);
	}

	.stat-value {
		font-family: var(--font-mono);
		font-size: 17px;
		font-weight: 700;
		line-height: 1.1;
		color: var(--ink);
	}

	.stat-label {
		font-size: 10px;
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

	/* ── Tabla de provincias ── */
	.table {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.table ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid var(--border);
	}

	.table li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 6px 10px;
		background: var(--card);
	}

	.table li:nth-child(even) {
		background: var(--card-2);
	}

	.table-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 12px;
		color: var(--ink);
	}

	.table-val {
		flex-shrink: 0;
		font-family: var(--font-mono);
		font-size: 12.5px;
		font-weight: 600;
		color: var(--ink);
	}

	.table-toggle {
		align-self: center;
		padding: 4px 10px;
		font-family: var(--font);
		font-size: 11px;
		font-weight: 700;
		color: var(--teal-deep);
		background: transparent;
		border: none;
		cursor: pointer;
	}

	.note {
		margin: 0;
		font-size: 11px;
		line-height: 1.45;
		text-align: center;
		color: var(--ink-muted);
	}

	@media (max-width: 640px) {
		.panel {
			top: auto;
			bottom: 0;
			left: 0;
			right: 0;
			width: auto;
			max-height: min(75vh, 420px);
			gap: 6px;
			border-radius: 16px 16px 0 0;
			padding: 4px 12px calc(10px + env(safe-area-inset-bottom));
			box-shadow: 0 -8px 24px rgba(22, 20, 14, 0.16);
		}

		.panel-body {
			gap: 10px;
			overflow: hidden;
			transition: max-height 0.25s ease, opacity 0.2s ease;
			max-height: 600px;
			opacity: 1;
		}

		.panel.collapsed {
			max-height: none;
		}

		.panel.collapsed .panel-body {
			max-height: 0;
			opacity: 0;
		}

		.handle-row {
			display: flex;
			align-items: center;
			gap: 8px;
			width: 100%;
			padding: 6px 2px;
			background: none;
			border: none;
			cursor: pointer;
			-webkit-tap-highlight-color: transparent;
		}

		.handle {
			flex-shrink: 0;
			width: 32px;
			height: 4px;
			border-radius: 2px;
			background: var(--card-2);
			border: 1px solid var(--border);
		}

		.handle-summary {
			flex: 1;
			min-width: 0;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
			text-align: left;
			font-family: var(--font-mono);
			font-size: 12.5px;
			font-weight: 600;
			color: var(--ink);
			opacity: 0;
			transition: opacity 0.15s ease;
		}

		.handle-chevron {
			flex-shrink: 0;
			width: 16px;
			height: 16px;
			color: var(--ink-muted);
			transform: rotate(180deg);
			transition: transform 0.25s ease;
		}

		.panel.collapsed .handle-summary {
			opacity: 1;
		}

		.panel.collapsed .handle-chevron {
			transform: rotate(0deg);
		}

		.hero {
			padding: 8px 14px;
		}

		.hero-value {
			font-size: 24px;
		}

		/* Más columnas: la hoja móvil es todo el ancho de la pantalla, más
		   que el panel fijo de escritorio, y así caben las 6 categorías en
		   2 filas en vez de 3 (menos alto en una hoja con espacio limitado). */
		.stats-grid {
			grid-template-columns: repeat(3, 1fr);
			gap: 5px;
		}

		.stat {
			padding: 6px 4px;
		}

		.stat-value {
			font-size: 14.5px;
		}

		.stat-label {
			font-size: 9px;
		}

		.note {
			display: none;
		}
	}
</style>
