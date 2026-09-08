import argparse

import geopandas as gpd
import pandas as pd
import shapely
from sqlalchemy import text

from core.config import DATOS_DIR
from core.db import engine

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

    args = parser.parse_args()

    if args.tabla not in TABLAS_PERMITIDAS:
        print(
            f"[X] Tabla '{args.tabla}' no permitida. Elegí una de: "
            f"{', '.join(sorted(TABLAS_PERMITIDAS))}. Abortando ingesta; no se insertó nada."
        )
        return

    print(f"[*] Leyendo archivo {args.archivo}...")
    try:
        df = _leer_csv(args.archivo, args.encoding)
        if df is None:
            return
    except Exception as e:
        print(f"[X] Error crítico al leer el archivo CSV: {e}")
        return

    error_esquema = _validar_esquema(df, args.tabla)
    if error_esquema:
        print(error_esquema)
        return

    for col in ("finca", "nombre", "tipo", "origen"):
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()

    error_completitud = _validar_completitud(df)
    if error_completitud:
        print(error_completitud)
        return

    if args.tabla == "mapa_color":
        error_densidades = _validar_densidades(df)
        if error_densidades:
            print(error_densidades)
            return

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
            return
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
            return
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        gdf = gdf.drop(columns=["wkt"])
    else:
        print("[X] El CSV no contiene columnas espaciales válidas ('latitud/longitud' o 'wkt'). Abortando ingesta; no se insertó nada.")
        return

    gdf = gdf.rename_geometry("geom")
    if "id" in gdf.columns:
        gdf = gdf.drop(columns=["id"])

    if args.tabla in ("mapa_color", "zonas_exclusion"):
        error_titularidad = _validar_titularidad(gdf, args.tabla)
        if error_titularidad:
            print(error_titularidad)
            return

    if args.tabla == "mapa_color":
        error_exclusiones = _validar_exclusiones_mapa(gdf)
        if error_exclusiones:
            print(error_exclusiones)
            return

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
            return

    print(f"[*] Intentando inyectar {len(gdf)} filas a la tabla '{args.tabla}'...")
    try:
        with engine.begin() as conn:
            gdf.to_postgis(args.tabla, conn, if_exists="append", index=False, chunksize=1000)
        print("[+] ¡Ingesta completada con éxito!")
    except Exception as e:
        print(f"[X] La base de datos rechazó los datos. Verificá tipos y restricciones:\n{e}")
        return


if __name__ == "__main__":
    principal()
