// Nombre bien escrito (con tildes/eñes) de cada provincia, indexado por el
// nombre en bruto que usa el pipeline de datos: el nombre de carpeta bajo
// raw/00_bruto/<CCAA>/<PROVINCIA> (sin acentos salvo la Ñ, espacios como
// "_"), que 02_generar_geojson.py/03_limpiar_geojson.py propagan como
// nombre de archivo y que 05_edificios_afectados.py copia tal cual tanto en
// la columna PROVINCIA de cada edificio como en _resumen_afectados.csv (ver
// CLAUDE.md). Navarra no está aquí: ese pipeline todavía no genera
// provincias con ese formato de nombre (ver CLAUDE.md).
const NOMBRES_PROVINCIA = {
	ALMERIA: 'Almería',
	CADIZ: 'Cádiz',
	CORDOBA: 'Córdoba',
	GRANADA: 'Granada',
	HUELVA: 'Huelva',
	JAEN: 'Jaén',
	MALAGA: 'Málaga',
	SEVILLA: 'Sevilla',
	HUESCA: 'Huesca',
	TERUEL: 'Teruel',
	ZARAGOZA: 'Zaragoza',
	ASTURIAS: 'Asturias',
	BALEARES: 'Baleares',
	LAS_PALMAS: 'Las Palmas',
	TENERIFE: 'Santa Cruz de Tenerife',
	CANTABRIA: 'Cantabria',
	ALBACETE: 'Albacete',
	CIUDAD_REAL: 'Ciudad Real',
	CUENCA: 'Cuenca',
	GUADALAJARA: 'Guadalajara',
	TOLEDO: 'Toledo',
	AVILA: 'Ávila',
	BURGOS: 'Burgos',
	LEON: 'León',
	PALENCIA: 'Palencia',
	SALAMANCA: 'Salamanca',
	SEGOVIA: 'Segovia',
	SORIA: 'Soria',
	VALLADOLID: 'Valladolid',
	ZAMORA: 'Zamora',
	BARCELONA: 'Barcelona',
	GIRONA: 'Girona',
	LLEIDA: 'Lleida',
	TARRAGONA: 'Tarragona',
	CEUTA: 'Ceuta',
	MADRID: 'Madrid',
	ALICANTE: 'Alicante',
	CASTELLON: 'Castellón',
	VALENCIA: 'Valencia',
	BADAJOZ: 'Badajoz',
	CACERES: 'Cáceres',
	A_CORUÑA: 'A Coruña',
	LUGO: 'Lugo',
	OURENSE: 'Ourense',
	PONTEVEDRA: 'Pontevedra',
	LA_RIOJA: 'La Rioja',
	MELILLA: 'Melilla',
	MURCIA: 'Murcia'
};

// Si algún día aparece una provincia sin entrada aquí (p.ej. al incorporar
// Navarra al pipeline), se muestra igualmente en vez de romper: solo con
// los guiones bajos convertidos a espacios, como se hacía antes.
export function nombreProvincia(raw) {
	if (!raw) return raw;
	return NOMBRES_PROVINCIA[raw] ?? raw.replace(/_/g, ' ');
}
