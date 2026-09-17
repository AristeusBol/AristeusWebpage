import argparse
import sys
from datetime import date

import geopandas as gpd
import pandas as pd
import shapely
from sqlalchemy import text

from core.config import DATOS_DIR
from core.db import engine
from motor_analitico.negocio import calcular_stock_potrero
from repositorios import calculos

TABLAS_PERMITIDAS = {"mapa_color", "potreros_base", "zonas_exclusion"}

ESQUEMA_CSV = {
    "mapa_color": [
        ["usuario_id", "potrero_id", "finca", "fecha", "latitud", "longitud", "densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2", "origen"],
        ["usuario_id", "potrero_id", "finca", "fecha", "wkt", "densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2", "origen"],
    ],
    "potreros_base": [
        ["usuario_id", "nombre", "finca", "wkt"],
    ],
    "zonas_exclusion": [
        ["usuario_id", "potrero_id", "finca", "nombre", "tipo", "wkt"],
    ],
}


def _validar_esquema(df, tabla):
    if "id" in df.columns:
        df.drop(columns=["id"], inplace=True)
    cols = [str(c).strip() for c in df.columns]
    df.columns = cols
    cols_set = set(cols)
    esperados_lista = ESQUEMA_CSV[tabla]

    for esperadas in esperados_lista:
        if cols_set == set(esperadas):
            return None

    mejor = max(esperados_lista, key=lambda e: len(cols_set & set(e)))
    faltantes = sorted(set(mejor) - cols_set)
    sobrantes = sorted(cols_set - set(mejor))
    msg = f"[X] Columnas no coinciden con tabla '{tabla}'. Abortando ingesta; no se insertó nada."
    if faltantes:
        msg += f"\n    Faltan: {', '.join(faltantes)}"
    if sobrantes:
        msg += f"\n    Sobran: {', '.join(sobrantes)}"
    msg += f"\n    Esperadas: {', '.join(sorted(mejor))}"
    msg += f"\n    Recibidas: {', '.join(sorted(cols))}"
    if len(esperados_lista) > 1:
        msg += "\n    Variantes permitidas:"
        for v in esperados_lista:
            msg += f"\n      - {', '.join(v)}"
    return msg


def _validar_completitud(df):
    if len(df) == 0:
        return "[X] CSV vacío (0 filas). Abortando ingesta; no se insertó nada."

    mask_vacias = pd.DataFrame(False, index=df.index, columns=df.columns)
    for col in df.columns:
        serie = df[col]
        vacia = serie.isna()
        str_stripped = serie.astype(str).str.strip()
        vacia = vacia | (str_stripped == "") | (str_stripped.str.lower() == "nan")
        mask_vacias[col] = vacia

    filas_incompletas = mask_vacias.any(axis=1)
    if filas_incompletas.any():
        n = int(filas_incompletas.sum())
        cols_con_vacios = [c for c in df.columns if mask_vacias[c].any()]
        ejemplos_idx = df[filas_incompletas].index.tolist()[:3]
        filas_csv = [i + 2 for i in ejemplos_idx]
        msg = f"[X] CSV incompleto: {n} filas con celdas vacías. Abortando ingesta; no se insertó nada."
        msg += f"\n    Columnas con vacíos: {', '.join(cols_con_vacios)}"
        msg += f"\n    Filas ejemplo (nro. fila CSV): {filas_csv}"
        return msg
    return None


def _validar_titularidad(gdf, tabla):
    if tabla not in ("mapa_color", "zonas_exclusion"):
        return None
    if "usuario_id" not in gdf.columns or "potrero_id" not in gdf.columns:
        return None
    try:
        with engine.connect() as conn:
            for potrero_id in gdf["potrero_id"].unique():
                try:
                    pid_int = int(str(potrero_id).strip())
                except (ValueError, TypeError):
                    return f"[X] potrero_id '{potrero_id}' no es numérico. Abortando ingesta; no se insertó nada."
                res = conn.execute(text("SELECT usuario_id, finca FROM potreros_base WHERE id=:pid"), {"pid": pid_int}).fetchone()
                if not res:
                    return f"[X] Potrero ID {pid_int} no existe en potreros_base. Abortando ingesta; no se insertó nada.\n    Creá el potrero primero o corregí el potrero_id."
                owner = int(res.usuario_id)
                subset = gdf[gdf["potrero_id"] == potrero_id]
                fincas_csv = {str(v).strip() for v in subset["finca"].unique()}
                if fincas_csv != {res.finca.strip()}:
                    return (
                        f"[X] Finca del CSV {sorted(fincas_csv)} no coincide con la del potrero {pid_int} ('{res.finca}'). "
                        "Abortando ingesta; no se insertó nada."
                    )
                for uid in subset["usuario_id"].unique():
                    try:
                        uid_int = int(str(uid).strip())
                    except (ValueError, TypeError):
                        return f"[X] usuario_id '{uid}' no es numérico para potrero {pid_int}. Abortando."
                    if uid_int != owner:
                        return (
                            f"[X] Violación de titularidad: CSV indica usuario_id={uid_int} para potrero_id={pid_int} "
                            f"pero el potrero pertenece a usuario_id={owner}. Abortando ingesta; no se insertó nada."
                        )
                    existe = conn.execute(text("SELECT 1 FROM usuarios WHERE id=:uid"), {"uid": uid_int}).fetchone()
                    if not existe:
                        return f"[X] usuario_id={uid_int} no existe en tabla usuarios. Abortando."
        return None
    except Exception as e:
        return f"[X] Error validando titularidad: {e}. Abortando."


COLUMNAS_DENSIDAD = ("densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2")


def _validar_exclusiones_mapa(gdf):
    """Rechaza puntos de mapa_color caídos dentro de una zona de exclusión existente.

    Regla ST_Covers (borde = dentro). All-or-nothing como el resto de validaciones.
    """
    try:
        with engine.connect() as conn:
            for (uid, pid), sub in gdf.groupby(["usuario_id", "potrero_id"]):
                try:
                    uid_int, pid_int = int(str(uid).strip()), int(str(pid).strip())
                except (ValueError, TypeError):
                    continue
                res = conn.execute(
                    text("""
                        SELECT COUNT(*) AS n FROM zonas_exclusion
                        WHERE usuario_id = :uid AND potrero_id = :pid
                    """),
                    {"uid": uid_int, "pid": pid_int},
                ).fetchone()
                if not res or not res.n:
                    continue
                geoms = sub.geometry.tolist()
                wkt_list = [g.wkt for g in geoms]
                dentro = conn.execute(
                    text("""
                        SELECT COUNT(*) AS n FROM (
                          SELECT ST_GeomFromText(g, 4326) AS geom
                          FROM unnest(CAST(:wkts AS text[])) AS g
                        ) p
                        JOIN zonas_exclusion z ON z.usuario_id = :uid AND z.potrero_id = :pid
                        WHERE ST_Covers(z.geom, p.geom)
                    """),
                    {"wkts": wkt_list, "uid": uid_int, "pid": pid_int},
                ).fetchone()
                n = int(dentro.n or 0)
                if n > 0:
                    return (
                        f"[X] {n} punto(s) de mapa_color caen dentro de una zona de exclusión "
                        f"(usuario_id={uid_int}, potrero_id={pid_int}). Abortando ingesta; no se insertó nada."
                        "\n    Eliminá esas filas del CSV o ajustá la exclusión."
                    )
        return None
    except Exception as e:
        return f"[X] Error validando exclusiones: {e}. Abortando."


def _validar_densidades(df):
    if not any(c in df.columns for c in COLUMNAS_DENSIDAD):
        return None
    numericas = {}
    for col in COLUMNAS_DENSIDAD:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.isna().any():
            filas = df[vals.isna()].index.tolist()[:3]
            return f"[X] Columna '{col}' con valores no numéricos (filas CSV {[i + 2 for i in filas]}). Abortando ingesta; no se insertó nada."
        if (vals < 0).any():
            filas = df[vals < 0].index.tolist()[:3]
            return f"[X] Columna '{col}' con densidades negativas (filas CSV {[i + 2 for i in filas]}). Abortando ingesta; no se insertó nada."
        numericas[col] = vals
    suma = numericas["densidad_verde_g_m2"] + numericas["densidad_muerta_g_m2"]
    dif = (numericas["densidad_total_g_m2"] - suma).abs() / suma.where(suma != 0, 1).abs()
    if (dif > 0.05).any():
        filas = df[dif > 0.05].index.tolist()[:3]
        return f"[X] densidad_total incoherente con verde+muerta (>5%, filas CSV {[i + 2 for i in filas]}). Abortando ingesta; no se insertó nada."
    return None


def _validar_potreros_unicos(gdf):
    clave = ["usuario_id", "finca", "nombre"]
    norm = gdf[clave].astype(str).apply(lambda s: s.str.strip())
    dup = norm[norm.duplicated(keep=False)]
    if not dup.empty:
        ejemplos = dup.drop_duplicates().head(3).to_dict("records")
        return f"[X] Potreros duplicados en el CSV (usuario_id, finca, nombre): {ejemplos}. Abortando ingesta; no se insertó nada."
    try:
        with engine.connect() as conn:
            for _, r in norm.drop_duplicates().iterrows():
                try:
                    uid_int = int(r["usuario_id"])
                except (ValueError, TypeError):
                    return f"[X] usuario_id '{r['usuario_id']}' no es numérico. Abortando ingesta; no se insertó nada."
                existe = conn.execute(
                    text("SELECT 1 FROM potreros_base WHERE usuario_id = :uid AND finca = :finca AND nombre = :nombre"),
                    {"uid": uid_int, "finca": r["finca"], "nombre": r["nombre"]},
                ).fetchone()
                if existe:
                    return (
                        f"[X] Potrero ya existe (usuario_id={uid_int}, finca='{r['finca']}', nombre='{r['nombre']}'). "
                        "Abortando ingesta; no se insertó nada."
                    )
    except Exception as e:
        return f"[X] Error validando potreros existentes: {e}. Abortando."
    return None


GEOMETRIA_ESPERADA = {
    "mapa_color": {"Point"},
    "potreros_base": {"Polygon", "MultiPolygon"},
    "zonas_exclusion": {"Polygon", "MultiPolygon"},
}


def _validar_tipos_geometria(gdf, tabla):
    """Rechaza geometrías de tipo inesperado (ej. POINT en potreros_base).

    Sin esto, el error lo da PostGIS con un mensaje genérico.
    """
    esperados = GEOMETRIA_ESPERADA[tabla]
    tipos = {g.geom_type for g in gdf.geometry if g is not None}
    inesperados = tipos - esperados
    if inesperados:
        return (
            f"[X] Tipos de geometría inesperados en '{tabla}': {sorted(inesperados)}. "
            f"Esperados: {sorted(esperados)}. Abortando ingesta; no se insertó nada."
        )
    return None


def _validar_rangos_coords(gdf):
    """Rechaza puntos con coordenadas imposibles (lon -180..180, lat -90..90).

    Solo aplica a geometrías Point (mapa_color); los polígonos se validan
    por tipo y por PostGIS.
    """
    try:
        if not ((gdf.geometry.geom_type == "Point").all()):
            return None
        lon = gdf.geometry.x
        lat = gdf.geometry.y
    except Exception:
        return None
    if ((lon < -180) | (lon > 180) | (lat < -90) | (lat > 90)).any():
        n = int(((lon < -180) | (lon > 180) | (lat < -90) | (lat > 90)).sum())
        return (
            f"[X] {n} filas con coordenadas fuera de rango "
            "(lon -180..180, lat -90..90). Abortando ingesta; no se insertó nada."
        )
    return None


def _leer_csv(ruta, encoding):
    if encoding:
        return pd.read_csv(ruta, encoding=encoding)
    try:
        return pd.read_csv(ruta, encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        print("[X] El archivo no está codificado en UTF-8 y aborto la ingesta.")
        print(f"    Detalle: {e}")
        print("    ¿El CSV viene de Excel con otro encoding? Forzá el formato con --encoding (por ej. --encoding latin-1).")
        return None


def _grupos_mapa(gdf):
    """Grupos (usuario_id, potrero_id, fecha) presentes en el lote ingerido."""
    grupos = []
    for (uid, pid, fecha), _sub in gdf.groupby(["usuario_id", "potrero_id", "fecha"]):
        try:
            uid_int, pid_int = int(str(uid).strip()), int(str(pid).strip())
        except (ValueError, TypeError):
            continue
        if isinstance(fecha, date):
            f = fecha
        else:
            try:
                f = date.fromisoformat(str(fecha).strip())
            except ValueError:
                continue
        grupos.append((uid_int, pid_int, f))
    return grupos


def _calcular_grupos(gdf):
    """Calcula y guarda el stock de cada grupo del lote (best-effort).

    Retorna (ok, fallos): cantidad de grupos guardados y lista de
    (uid, pid, fecha, motivo) para los que no se pudo calcular.
    """
    ok, fallos = 0, []
    for uid, pid, fecha in _grupos_mapa(gdf):
        try:
            res = calcular_stock_potrero(engine, pid, uid, fecha=fecha)
        except Exception as e:
            fallos.append((uid, pid, fecha.isoformat(), str(e)))
            continue
        if res is None:
            fallos.append((uid, pid, fecha.isoformat(), "sin puntos válidos"))
            continue
        try:
            with engine.begin() as conn:
                calculos.upsert_calculo(
                    conn,
                    pid,
                    res["finca"],
                    res["fecha"],
                    res["area_neta_ha"],
                    res["masa_total_potrero_verde_kg"],
                    res["masa_total_potrero_muerta_kg"],
                    res["masa_total_potrero_total_kg"],
                    usuario_id=res.get("usuario_id", uid),
                )
            ok += 1
        except Exception as e:
            fallos.append((uid, pid, fecha.isoformat(), f"error guardando: {e}"))
    return ok, fallos


def principal():
    parser = argparse.ArgumentParser(description="Ingesta simple: sube CSV solo si está completo y columnas coinciden")
    parser.add_argument(
        "--archivo",
        type=str,
        default=str(DATOS_DIR / "mapa_color.csv"),
        help="Ruta al archivo CSV (por defecto: datos/mapa_color.csv)",
    )
    parser.add_argument("--tabla", required=True, help="Tabla destino en PostGIS")
    parser.add_argument(
        "--encoding",
        type=str,
        default=None,
        help="Fuerza la codificación del CSV (por defecto: UTF-8)",
    )
    parser.add_argument(
        "--sin-calcular",
        action="store_true",
        help="Solo para mapa_color: no calcula ni guarda el stock tras ingerir",
    )

    args = parser.parse_args()

    if args.tabla not in TABLAS_PERMITIDAS:
        print(
            f"[X] Tabla '{args.tabla}' no permitida. Elegí una de: "
            f"{', '.join(sorted(TABLAS_PERMITIDAS))}. Abortando ingesta; no se insertó nada."
        )
        return 1

    print(f"[*] Leyendo archivo {args.archivo}...")
    try:
        df = _leer_csv(args.archivo, args.encoding)
        if df is None:
            return 1
    except Exception as e:
        print(f"[X] Error crítico al leer el archivo CSV: {e}")
        return 1

    error_esquema = _validar_esquema(df, args.tabla)
    if error_esquema:
        print(error_esquema)
        return 1

    for col in ("finca", "nombre", "tipo", "origen"):
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()

    error_completitud = _validar_completitud(df)
    if error_completitud:
        print(error_completitud)
        return 1

    if args.tabla == "mapa_color":
        error_densidades = _validar_densidades(df)
        if error_densidades:
            print(error_densidades)
            return 1

    if "latitud" in df.columns and "longitud" in df.columns:
        lat = pd.to_numeric(df["latitud"], errors="coerce")
        lon = pd.to_numeric(df["longitud"], errors="coerce")
        invalidas = lat.isna() | lon.isna()
        if invalidas.any():
            n = int(invalidas.sum())
            print(
                f"[X] {n} filas sin coordenadas válidas (latitud/longitud faltante o no numérica). "
                "Abortando ingesta; no se insertó nada."
            )
            print("    ¿Tu CSV usa coma decimal (ej. 32,0401)? Convertila a punto antes.")
            return 1
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(lon, lat),
            crs="EPSG:4326",
        )
        gdf = gdf.drop(columns=["latitud", "longitud"])
    elif "wkt" in df.columns:
        geometry = shapely.from_wkt(df["wkt"].fillna("").astype(str), on_invalid="ignore")
        invalidas = geometry.isna()
        if invalidas.any():
            n = int(invalidas.sum())
            print(f"[X] {n} filas con WKT inválido o vacío. Abortando ingesta; no se insertó nada.")
            return 1
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        gdf = gdf.drop(columns=["wkt"])
    else:
        print("[X] El CSV no contiene columnas espaciales válidas ('latitud/longitud' o 'wkt'). Abortando ingesta; no se insertó nada.")
        return 1

    gdf = gdf.rename_geometry("geom")
    if "id" in gdf.columns:
        gdf = gdf.drop(columns=["id"])

    error_tipos = _validar_tipos_geometria(gdf, args.tabla)
    if error_tipos:
        print(error_tipos)
        return 1

    error_rangos = _validar_rangos_coords(gdf)
    if error_rangos:
        print(error_rangos)
        return 1

    if args.tabla in ("mapa_color", "zonas_exclusion"):
        error_titularidad = _validar_titularidad(gdf, args.tabla)
        if error_titularidad:
            print(error_titularidad)
            return 1

    if args.tabla == "mapa_color":
        error_exclusiones = _validar_exclusiones_mapa(gdf)
        if error_exclusiones:
            print(error_exclusiones)
            return 1

    if args.tabla == "zonas_exclusion":
        try:
            with engine.connect() as conn:
                for _, r in gdf.iterrows():
                    try:
                        uid_int, pid_int = int(str(r["usuario_id"]).strip()), int(str(r["potrero_id"]).strip())
                    except (ValueError, TypeError):
                        continue
                    n = conn.execute(
                        text("""
                            SELECT COUNT(*) AS n FROM mapa_color m
                            WHERE m.usuario_id = :uid AND m.potrero_id = :pid
                              AND ST_Covers(ST_GeomFromText(:wkt, 4326), m.geom)
                        """),
                        {"uid": uid_int, "pid": pid_int, "wkt": r.geometry.wkt},
                    ).fetchone()
                    if n and n.n:
                        print(f"[!] Aviso: la exclusión '{r.get('nombre', '?')}' (potrero {pid_int}) "
                              f"cubre {int(n.n)} punto(s) existentes de mapa_color. "
                              f"Esos puntos ya no se usan en tiles/cálculos/histograma.")
        except Exception as e:
            print(f"[!] No se pudo verificar solape con mapa_color: {e}")

    if args.tabla == "potreros_base":
        error_unicos = _validar_potreros_unicos(gdf)
        if error_unicos:
            print(error_unicos)
            return 1

    print(f"[*] Intentando inyectar {len(gdf)} filas a la tabla '{args.tabla}'...")
    try:
        with engine.begin() as conn:
            gdf.to_postgis(args.tabla, conn, if_exists="append", index=False, chunksize=1000)
        print("[+] ¡Ingesta completada con éxito!")
    except Exception as e:
        print(f"[X] La base de datos rechazó los datos. Verificá tipos y restricciones:\n{e}")
        return 1

    # Potreros y exclusiones son fijos: nada que calcular. El mapa dispara
    # el cálculo+guardado de cada grupo (usuario, potrero, fecha) ingerido.
    if args.tabla == "mapa_color" and not args.sin_calcular:
        print("[*] Calculando stock de los grupos ingeridos...")
        ok, fallos = _calcular_grupos(gdf)
        for uid, pid, fecha, motivo in fallos:
            print(f"[X] Sin cálculo potrero {pid} (usuario {uid}, fecha {fecha}): {motivo}")
        if fallos:
            print(f"[!] Ingesta OK, cálculos {ok} OK / {len(fallos)} con fallo. "
                  "Revisá y re-corré calcular_kilos_reales.py para esos grupos.")
            return 1
        print(f"[+] Stock calculado y guardado para {ok} grupo(s).")

    return 0


if __name__ == "__main__":
    sys.exit(principal())
