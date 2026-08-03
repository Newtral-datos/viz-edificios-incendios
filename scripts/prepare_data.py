"""
Genera los datos que consume la app Svelte (app/public/data/) a partir de las
salidas del pipeline principal del repo. No es un paso numerado de
scripts/: vive en app/scripts porque solo prepara datos para esta app, no
para el análisis de "edificios calcinados" en sí.

Genera, para la temporada en curso (siempre) y para el histórico
2016..año_actual-1 (si ya se ha calculado, ver más abajo), tres archivos
cada uno en app/public/data/:

  - edificios_afectados(_historico).pmtiles: data/03_pmtiles/edificios_afectados.pmtiles
    (o data/03_pmtiles_historico/edificios_afectados_historico.pmtiles, salida
    de scripts/06_generar_pmtiles.py o de scripts/edificios_historicos.py
    para la variante histórica, capa "edificios_afectados", huellas reales
    de los edificios) fusionado con una capa de puntos generada aquí mismo
    ("edificios_centroides": el centroide de cada edificio de
    data/02_edificios_afectados(_historico)/*.geojson, teselada hasta
    EDIFICIOS_CENTROIDES_MAXZOOM). El polígono es sub-píxel a escala de toda
    España, así que sin el centroide los edificios serían invisibles hasta
    hacer mucho zoom; MapView.svelte dibuja el punto a opacidad plena por
    debajo de EDIFICIOS_MINZOOM (donde arranca el polígono real) y
    desvanecido en el tramo de solape entre EDIFICIOS_MINZOOM y
    EDIFICIOS_CENTROIDES_MAXZOOM, así que la tesela de centroides tiene que
    llegar hasta ese mismo zoom o el punto desaparecería de golpe en cuanto
    se acabaran sus teselas, sin que el desvanecido del estilo tuviera nada
    que animar. La fusión la hace `tile-join` (viene con tippecanoe), sin
    volver a teselar el polígono. Requiere haber corrido antes scripts/05_edificios_afectados.py
    + scripts/06_generar_pmtiles.py (o PIPELINE_EDIFICIOS_AFECTADOS.py, que
    encadena los dos) para la temporada actual, y scripts/edificios_historicos.py
    para la variante histórica.

  - incendios(_historico).pmtiles: perímetros de incendios, convertidos a
    pmtiles con tippecanoe (capa "incendios"). Se leen del mismo geojson
    diario del panel de incendios que usa scripts/05_edificios_afectados.py
    y scripts/edificios_historicos.py
    (PANEL_INCENDIOS/<año>/datos_limpios/incendios_<DD_MM_YYYY>.geojson,
    fuera de este repo, con el histórico completo dentro de ese mismo
    archivo), filtrando por AÑO == año actual para la temporada en curso, o
    por el rango 2016..año_actual-1 para la variante histórica. Se
    convierte a pmtiles (y no se sirve el geojson tal cual) porque el
    archivo diario completo pesa 140MB+ y cargarlo entero en el navegador no
    es viable.

  - resumen(_historico).json: total de viviendas y de edificios afectados,
    desglose por CCAA/provincia —cada una con sus propias viviendas y
    edificios afectados por separado, ya segregados en el propio CSV (ver
    generar_resumen())— (leído de
    data/02_edificios_afectados(_historico)/_resumen_afectados.csv, salida
    de scripts/05_edificios_afectados.py o de
    scripts/edificios_historicos.py para la variante histórica) y desglose
    por categoría de uso (leído directamente de
    data/02_edificios_afectados(_historico)/*.geojson: la residencial se
    cuenta en viviendas —suma de numberOfDwellings—, no en edificios, y el
    resto de categorías en número de edificios, ver generar_categorias()),
    más la fecha de generación. La variante histórica añade un campo
    "periodo" ({anio_inicio, anio_fin}) que la app usa para rotular el
    rango de años sin hardcodearlo en el frontend.

La variante histórica es un cálculo pesado (cruza ~5x más incendios que la
temporada en curso contra los mismos edificios de Catastro) que en la
práctica solo hace falta generar una vez: los incendios de años ya cerrados
no cambian. Por eso, sin --historico, este script solo la genera si
data/02_edificios_afectados_historico/ ya existe (si no, la omite con un
aviso, no falla) y si los archivos históricos de public/data/ todavía no
existen (si ya están generados, los deja tal cual). --historico (flag de
este script, no de scripts/edificios_historicos.py) fuerza la regeneración
aunque ya existan, para cuando se recalcule scripts/edificios_historicos.py
a propósito.

Uso:
  python3 app/scripts/prepare_data.py               # actual siempre + histórico solo si falta
  python3 app/scripts/prepare_data.py --historico    # fuerza también la regeneración del histórico
"""

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
import warnings
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

APP_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = APP_DIR.parent
PUBLIC_DATA_DIR = APP_DIR / "public" / "data"

EDIFICIOS_AFECTADOS_DIR = ROOT_DIR / "data" / "02_edificios_afectados"
EDIFICIOS_PMTILES_SRC = ROOT_DIR / "data" / "03_pmtiles" / "edificios_afectados.pmtiles"
EDIFICIOS_PMTILES_DEST = PUBLIC_DATA_DIR / "edificios_afectados.pmtiles"
RESUMEN_CSV = EDIFICIOS_AFECTADOS_DIR / "_resumen_afectados.csv"
RESUMEN_JSON_DEST = PUBLIC_DATA_DIR / "resumen.json"
INCENDIOS_PMTILES_DEST = PUBLIC_DATA_DIR / "incendios.pmtiles"

EDIFICIOS_AFECTADOS_DIR_HISTORICO = ROOT_DIR / "data" / "02_edificios_afectados_historico"
EDIFICIOS_PMTILES_SRC_HISTORICO = ROOT_DIR / "data" / "03_pmtiles_historico" / "edificios_afectados_historico.pmtiles"
EDIFICIOS_PMTILES_DEST_HISTORICO = PUBLIC_DATA_DIR / "edificios_afectados_historico.pmtiles"
RESUMEN_CSV_HISTORICO = EDIFICIOS_AFECTADOS_DIR_HISTORICO / "_resumen_afectados.csv"
RESUMEN_JSON_DEST_HISTORICO = PUBLIC_DATA_DIR / "resumen_historico.json"
INCENDIOS_PMTILES_DEST_HISTORICO = PUBLIC_DATA_DIR / "incendios_historico.pmtiles"

# Primer año con datos en el panel de incendios (ver CLAUDE.md). Duplicada
# con comentario en scripts/05_edificios_afectados.py, que necesita el mismo
# límite para calcular qué edificios están en el histórico.
ANIO_HISTORICO_MIN = 2016

# Debe coincidir con EDIFICIOS_MINZOOM en src/lib/MapView.svelte: es el zoom
# a partir del cual se dibuja la huella real del edificio (el polígono) y a
# partir del cual el estilo empieza a desvanecer la capa de puntos de
# centroide que genera generar_edificios() de abajo, para que los edificios
# se puedan ver a escala de toda España, donde el polígono es sub-píxel.
EDIFICIOS_MINZOOM = 9

# Debe coincidir con EDIFICIOS_CENTROIDES_MAXZOOM en src/lib/MapView.svelte,
# y con el maxzoom real con el que scripts/06_generar_pmtiles.py tesela el
# polígono (14, fijo por ahora) — no puede ser mayor: la tesela de
# centroides tiene que llegar como mínimo hasta aquí (ver el "-z" de
# tippecanoe en generar_edificios(), el tramo de solape del desvanecido del
# estilo con el polígono, que ya se dibuja desde EDIFICIOS_MINZOOM), pero si
# fuera más allá del maxzoom del polígono, tile-join generaría teselas
# propias en esos zooms de más que solo tendrían el punto (el polígono no
# llega tan lejos), y al existir esa tesela MapLibre ya no haría "overzoom"
# reutilizando la última tesela del polígono que sí lo tiene: el edificio
# real desaparecería justo en el tramo final del desvanecido.
EDIFICIOS_CENTROIDES_MAXZOOM = 14

# Mismas 6 categorías de currentUse que USOS en src/lib/MapView.svelte
# (deben ir a la par). "1_residential" no está aquí: se trata aparte, en
# viviendas y no en edificios (ver generar_resumen() más abajo).
CATEGORIAS_USO = {
    "2_agriculture": ("agrario", "Agrario"),
    "3_industrial": ("industrial", "Industrial"),
    "4_3_publicServices": ("servicios_publicos", "Servicios públicos"),
    "4_2_retail": ("comercial", "Comercial"),
    "4_1_office": ("oficinas", "Oficinas"),
}

HOY = date.today()
INCENDIOS_PATH = (
    Path("/Users/miguel.ros/Desktop/PANELES/PANEL_INCENDIOS")
    / HOY.strftime("%Y")
    / "datos_limpios"
    / f"incendios_{HOY.strftime('%d_%m_%Y')}.geojson"
)
COLUMNAS_INCENDIO = ["geometry", "PROVINCE", "COMMUNE", "FECHA_INCENDIO", "HECTAREAS"]

# El geojson diario del panel de incendios viene de Copernicus EFFIS y trae
# España y Portugal mezclados (su propio pipeline, PANEL_INCENDIOS.py,
# descarga ambos países por separado y los concatena). Se queda con COUNTRY
# == "ES" para filtrar Portugal.
ZOOM_MIN = 2
# Igual que el de scripts/06_generar_pmtiles.py. Se probó a 18: el archivo
# pasaba de 18MB a 93MB sin ganancia real de detalle, porque a partir de z16
# tippecanoe ya conserva casi toda la densidad de vértices del origen
# (comprobado decodificando teselas sueltas) — la mejora de calidad real
# viene de --no-tiny-polygon-reduction-at-maximum-zoom y
# --simplify-only-low-zooms de abajo, no de subir el zoom máximo.
ZOOM_MAX = 14


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def generar_edificios(pmtiles_src: Path, edificios_afectados_dir: Path, pmtiles_dest: Path, historico: bool = False):
    script_hint = "scripts/edificios_historicos.py" if historico else "scripts/05_edificios_afectados.py + scripts/06_generar_pmtiles.py (o PIPELINE_EDIFICIOS_AFECTADOS.py)"
    if not pmtiles_src.exists():
        raise SystemExit(f"No se encuentra {pmtiles_src}. Ejecuta antes {script_hint}.")
    if not shutil.which("tippecanoe"):
        raise SystemExit("tippecanoe no está instalado o no está en el PATH.")
    if not shutil.which("tile-join"):
        raise SystemExit("tile-join no está instalado o no está en el PATH (viene con tippecanoe).")

    geojson_paths = sorted(edificios_afectados_dir.glob("*.geojson"))
    if not geojson_paths:
        raise SystemExit(f"No hay ningún geojson en {edificios_afectados_dir}. Ejecuta antes {script_hint}.")

    print(f"Calculando centroides de {len(geojson_paths)} CCAA...")
    # Solo geometría (columns=[]): el punto es puramente decorativo, para
    # poder "ver" los edificios a escala de toda España antes de que su
    # huella real sea visible como polígono, así que no hace falta cargar ni
    # conservar sus atributos. geopandas avisa de que el centroide en un CRS
    # geográfico (grados) no es exacto; no importa aquí, ya que el punto
    # sirve solo de referencia visual aproximada, no para medir nada.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        centroides = gpd.GeoDataFrame(
            geometry=pd.concat(
                [gpd.read_file(p, columns=[]).geometry.centroid for p in geojson_paths],
                ignore_index=True,
            ),
            crs="EPSG:4326",
        )
    print(f"{len(centroides)} centroides")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        centroides_geojson = tmp_dir / "centroides.geojson"
        centroides.to_file(centroides_geojson, driver="GeoJSON")

        centroides_pmtiles = tmp_dir / "centroides.pmtiles"
        subprocess.run(
            [
                "tippecanoe",
                "-o", str(centroides_pmtiles),
                "-f",
                "-l", "edificios_centroides",
                "-Z", str(ZOOM_MIN),
                "-z", str(EDIFICIOS_CENTROIDES_MAXZOOM),
                # Por defecto tippecanoe va soltando puntos en los zooms
                # bajos para no saturar la tesela (pensado para densidades
                # enormes tipo OSM); aquí cada punto es un edificio afectado
                # real y no sobran, así que -r1 desactiva ese descarte y se
                # ven todos a cualquier zoom, incluidos los que están solos.
                "-r1",
                str(centroides_geojson),
            ],
            check=True,
        )

        # tile-join combina las dos capas (polígonos + centroides) en un
        # único pmtiles sin volver a teselar nada: cada una conserva su
        # propio rango de zoom (avisa por consola de que no coinciden, pero
        # no es un error). El polígono ya viene teselado de
        # scripts/06_generar_pmtiles.py.
        subprocess.run(
            [
                "tile-join",
                "-o", str(pmtiles_dest),
                "-f",
                str(pmtiles_src),
                str(centroides_pmtiles),
            ],
            check=True,
        )

    print(f"-> {pmtiles_dest} ({human_size(pmtiles_dest.stat().st_size)})")


def generar_incendios(pmtiles_dest: Path, anios: set[str], etiqueta: str):
    if not INCENDIOS_PATH.exists():
        raise SystemExit(f"No se encuentra el geojson de incendios de hoy: {INCENDIOS_PATH}")
    if not shutil.which("tippecanoe"):
        raise SystemExit("tippecanoe no está instalado o no está en el PATH.")

    print(f"Cargando incendios de {INCENDIOS_PATH}...")
    incendios = gpd.read_file(INCENDIOS_PATH)
    if "COUNTRY" not in incendios.columns:
        raise SystemExit(
            f"{INCENDIOS_PATH} no tiene columna COUNTRY (venía de una versión "
            "anterior de PANEL_INCENDIOS.py, que la eliminaba). Vuelve a "
            "ejecutar PANEL_INCENDIOS.py para regenerar el geojson de hoy con "
            "COUNTRY incluido."
        )
    incendios = incendios[incendios["COUNTRY"] == "ES"]
    incendios = incendios[incendios["AÑO"].isin(anios)][COLUMNAS_INCENDIO]
    print(f"{len(incendios)} incendios de {etiqueta} (España)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_geojson = Path(tmp) / "incendios.geojson"
        incendios.to_file(tmp_geojson, driver="GeoJSON")
        peso_geojson = tmp_geojson.stat().st_size

        subprocess.run(
            [
                "tippecanoe",
                "-o", str(pmtiles_dest),
                "-f",
                "-l", "incendios",
                "-Z", str(ZOOM_MIN),
                "-z", str(ZOOM_MAX),
                # Los incendios son pocos (unos miles) y ya están recortados a
                # las columnas mínimas, así que no hay problema de tamaño en
                # sacrificar algo de compresión a cambio de conservar la
                # forma real del perímetro: sin reducir los polígonos
                # pequeños a un cuadrado en el zoom máximo, con la mínima
                # simplificación de líneas/polígonos en los niveles bajos de
                # zoom, y sin ninguna simplificación en el zoom máximo (los
                # perímetros de origen llegan a tener más de 10.000 vértices;
                # sin --simplify-only-low-zooms tippecanoe los recorta
                # igualmente en el zoom máximo, que es donde más se nota).
                "--no-tiny-polygon-reduction-at-maximum-zoom",
                "--simplification=2",
                "--simplify-only-low-zooms",
                str(tmp_geojson),
            ],
            check=True,
        )

    peso_pmtiles = pmtiles_dest.stat().st_size
    print(f"-> {pmtiles_dest} ({human_size(peso_geojson)} -> {human_size(peso_pmtiles)})")


def generar_categorias(edificios_afectados_dir: Path, historico: bool = False):
    # No todos los edificios afectados cuentan igual: un residencial de 15
    # viviendas no es lo mismo que un agrícola. En vez de un único total
    # "edificios afectados", se desglosa por categoría de uso; los
    # residenciales se cuentan en viviendas (suma de numberOfDwellings, la
    # cifra que refleja el impacto humano real), no en número de edificios,
    # y el resto de categorías se cuentan en edificios.
    script_hint = "scripts/edificios_historicos.py" if historico else "scripts/05_edificios_afectados.py"
    geojson_paths = sorted(edificios_afectados_dir.glob("*.geojson"))
    if not geojson_paths:
        raise SystemExit(f"No hay ningún geojson en {edificios_afectados_dir}. Ejecuta antes {script_hint}.")

    edificios = pd.concat(
        [
            gpd.read_file(p, columns=["currentUse", "numberOfDwellings"], read_geometry=False)
            for p in geojson_paths
        ],
        ignore_index=True,
    )

    categorias = [
        {
            "id": "viviendas",
            "label": "Viviendas",
            "valor": int(
                edificios.loc[edificios["currentUse"] == "1_residential", "numberOfDwellings"].sum()
            ),
            "unidad": "viviendas",
        }
    ]

    resto = [
        {
            "id": id_,
            "label": label,
            "valor": int((edificios["currentUse"] == codigo).sum()),
            "unidad": "edificios",
        }
        for codigo, (id_, label) in CATEGORIAS_USO.items()
    ]
    categorias += sorted(resto, key=lambda c: -c["valor"])

    # Edificios sin currentUse registrado en el dato de Catastro: se cuentan
    # aparte (no son una categoría real) para no perderlos del recuento sin
    # fingir que están clasificados.
    sin_clasificar = int(edificios["currentUse"].isna().sum())
    if sin_clasificar:
        categorias.append(
            {"id": "sin_clasificar", "label": "Sin uso registrado", "valor": sin_clasificar, "unidad": "edificios"}
        )

    return categorias


def generar_resumen(
    resumen_csv: Path,
    edificios_afectados_dir: Path,
    json_dest: Path,
    historico: bool = False,
    periodo: dict | None = None,
):
    script_hint = "scripts/edificios_historicos.py" if historico else "scripts/05_edificios_afectados.py"
    if not resumen_csv.exists():
        raise SystemExit(f"No se encuentra {resumen_csv}. Ejecuta antes {script_hint}.")

    # El CSV ya segrega viviendas de edificios (ver script_hint): un
    # residencial de 15 viviendas no es lo mismo que un agrícola, así que se
    # mantienen como dos columnas separadas también aquí en vez de sumarlas
    # en un único total — se ordena por la suma de ambas solo a efectos de
    # ranking ("provincias más afectadas"), no como una cifra que se exponga.
    with open(resumen_csv, newline="") as f:
        filas = [
            {
                "ccaa": fila["ccaa"],
                "provincia": fila["provincia"],
                "num_viviendas_afectadas": int(fila["num_viviendas_afectadas"]),
                "num_edificios_afectados": int(fila["num_edificios_afectados"]),
            }
            for fila in csv.DictReader(f)
        ]

    resumen = {
        "fecha": HOY.isoformat(),
        "total_viviendas_afectadas": sum(fila["num_viviendas_afectadas"] for fila in filas),
        "total_edificios_afectados": sum(fila["num_edificios_afectados"] for fila in filas),
        "categorias": generar_categorias(edificios_afectados_dir, historico=historico),
        "provincias": sorted(
            filas,
            key=lambda fila: -(fila["num_viviendas_afectadas"] + fila["num_edificios_afectados"]),
        ),
    }
    if periodo is not None:
        resumen["periodo"] = periodo

    json_dest.write_text(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(
        f"-> {json_dest} "
        f"({resumen['total_viviendas_afectadas']} viviendas y {resumen['total_edificios_afectados']} edificios afectados, {len(filas)} provincias)"
    )


def main():
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--historico",
        action="store_true",
        help=(
            "Fuerza la regeneración de los archivos históricos "
            "(edificios_afectados_historico.pmtiles, incendios_historico.pmtiles, "
            "resumen_historico.json) aunque ya estén al día. Por defecto solo se "
            "regeneran si data/02_edificios_afectados_historico/_resumen_afectados.csv "
            "(la fuente) es más reciente que ellos, o si todavía no existen."
        ),
    )
    args = parser.parse_args()

    generar_edificios(EDIFICIOS_PMTILES_SRC, EDIFICIOS_AFECTADOS_DIR, EDIFICIOS_PMTILES_DEST)
    generar_incendios(INCENDIOS_PMTILES_DEST, anios={HOY.strftime("%Y")}, etiqueta=HOY.strftime("%Y"))
    generar_resumen(RESUMEN_CSV, EDIFICIOS_AFECTADOS_DIR, RESUMEN_JSON_DEST)

    if not EDIFICIOS_AFECTADOS_DIR_HISTORICO.exists():
        print(
            f"\nAviso: no se encuentra {EDIFICIOS_AFECTADOS_DIR_HISTORICO} — se omite la "
            "generación de datos históricos. Ejecuta antes scripts/edificios_historicos.py."
        )
        return

    # "Ya generado" se decide por fecha de modificación, no solo por
    # existencia: RESUMEN_CSV_HISTORICO es lo último que escribe
    # scripts/edificios_historicos.py en cada ejecución (después de todos los
    # geojson por CCAA), así que su mtime es una buena marca de "cuándo se
    # calculó por última vez el histórico". Si es más reciente que el pmtiles
    # ya publicado, la fuente cambió desde la última vez que se generaron los
    # archivos de la app (p.ej. se completaron más CCAA) y hay que
    # refrescarlos — comparar solo existencia dejaba servido un histórico
    # obsoleto sin avisar.
    historico_desactualizado = RESUMEN_CSV_HISTORICO.exists() and (
        not EDIFICIOS_PMTILES_DEST_HISTORICO.exists()
        or RESUMEN_CSV_HISTORICO.stat().st_mtime > EDIFICIOS_PMTILES_DEST_HISTORICO.stat().st_mtime
    )
    if not args.historico and not historico_desactualizado:
        print(
            f"\n{EDIFICIOS_PMTILES_DEST_HISTORICO.name} ya está al día — se omite la "
            "regeneración de los datos históricos (usa --historico para forzarla igualmente)."
        )
        return

    anio_max_historico = HOY.year - 1
    anios_historico = {str(a) for a in range(ANIO_HISTORICO_MIN, HOY.year)}
    etiqueta_historico = f"{ANIO_HISTORICO_MIN}-{anio_max_historico}"

    print(f"\nGenerando datos históricos ({etiqueta_historico})...")
    generar_edificios(
        EDIFICIOS_PMTILES_SRC_HISTORICO,
        EDIFICIOS_AFECTADOS_DIR_HISTORICO,
        EDIFICIOS_PMTILES_DEST_HISTORICO,
        historico=True,
    )
    generar_incendios(INCENDIOS_PMTILES_DEST_HISTORICO, anios=anios_historico, etiqueta=etiqueta_historico)
    generar_resumen(
        RESUMEN_CSV_HISTORICO,
        EDIFICIOS_AFECTADOS_DIR_HISTORICO,
        RESUMEN_JSON_DEST_HISTORICO,
        historico=True,
        periodo={"anio_inicio": ANIO_HISTORICO_MIN, "anio_fin": anio_max_historico},
    )


if __name__ == "__main__":
    main()
