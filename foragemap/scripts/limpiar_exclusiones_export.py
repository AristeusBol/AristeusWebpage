"""Limpieza de puntos de mapa_color caídos dentro de zonas de exclusión (datos/export).

Regla: ST_Covers (borde = dentro = se elimina).
Genera por cada mapa_*.csv:
  - reescritura del mismo archivo sin las filas en exclusión
  - mapa_*_cuarentena.csv con solo las removidas + columna motivo
Uso: .venv/bin/python scripts/limpiar_exclusiones_export.py
"""
import pandas as pd
import geopandas as gpd
import shapely

PARES = [
    ("datos/export/mapa_doncarlos.csv", "datos/export/zonas_doncarlos.csv"),
    ("datos/export/mapa_buenavista.csv", "datos/export/zonas_buenavista.csv"),
]


def main():
    for mapa_path, zonas_path in PARES:
        m = pd.read_csv(mapa_path)
        z = pd.read_csv(zonas_path)
        mg = gpd.GeoDataFrame(
            m, geometry=gpd.points_from_xy(m["longitud"], m["latitud"]), crs="EPSG:4326"
        )
        zg = gpd.GeoDataFrame(
            z, geometry=gpd.GeoSeries(shapely.from_wkt(z["wkt"])), crs="EPSG:4326"
        )
        drop_idx: set = set()
        for _, r in zg.iterrows():
            poly = r["geometry"]
            sel = mg[(mg["usuario_id"] == r["usuario_id"]) & (mg["potrero_id"] == r["potrero_id"])]
            inside = sel[sel.geometry.apply(lambda p: poly.covers(p))].index
            drop_idx.update(inside.tolist())
            print(f"{mapa_path}: exclusión '{r['nombre']}' potrero {r['potrero_id']}: {len(inside)} filas")
        drop_sorted = sorted(drop_idx)
        cuarentena = m.loc[drop_sorted].copy()
        cuarentena["motivo"] = "zona_exclusion"
        limpio = m.drop(index=drop_sorted)
        cuar_path = mapa_path.replace("mapa_", "mapa_cuarentena_")
        cuarentena.to_csv(cuar_path, index=False)
        limpio.to_csv(mapa_path, index=False)
        print(f"{mapa_path}: {len(m)} -> {len(limpio)} (removidas {len(drop_sorted)}), cuarentena -> {cuar_path}")


if __name__ == "__main__":
    main()
