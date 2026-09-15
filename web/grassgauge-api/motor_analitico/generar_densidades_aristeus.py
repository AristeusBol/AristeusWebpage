import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter
from scipy.stats import norm

DATOS = Path(__file__).resolve().parents[1] / "datos"
MAP_COLOR = DATOS / "mapa_color.csv"
MAPA_ARISTEUS = DATOS / "mapa_aristeus_20260914.csv"
RNG_SEED = 20260914
CORR_VERDE_MUERTA = 0.74
SIGMA_M = 60.0
PASO_M = 10.0
N_DONANTES = 9


def cargar_donantes(ruta):
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    donantes = {}
    for pid, sub in df.groupby("potrero_id"):
        verde = sub["densidad_verde_g_m2"].to_numpy(float)
        muerta = sub["densidad_muerta_g_m2"].to_numpy(float)
        donantes[int(pid)] = (np.sort(verde), np.sort(muerta))
    return donantes


def _quantile_map(u, ordenado):
    n = len(ordenado)
    probs = (np.arange(n) + 0.5) / n
    p = norm.cdf(u)
    p = np.clip(p, probs[0], probs[-1])
    return np.interp(p, probs, ordenado)


def _campo_suave(lon, lat, rng, lat0, lon0):
    x = (lon - lon0) * 111111.0 * np.cos(np.deg2rad(lat0))
    y = (lat - lat0) * 111111.0
    xi = np.rint((x - x.min()) / PASO_M).astype(int)
    yi = np.rint((y - y.min()) / PASO_M).astype(int)
    z = rng.standard_normal((yi.max() + 1, xi.max() + 1))
    w = gaussian_filter(z, sigma=SIGMA_M / PASO_M, mode="reflect")
    w -= w.mean()
    w /= w.std()
    return w[yi, xi]


def smokear(df, donantes, seed):
    rng = np.random.default_rng(seed)
    a = np.sqrt(CORR_VERDE_MUERTA)
    b = np.sqrt(1.0 - a * a)
    verde = np.empty(len(df), dtype=float)
    muerta = np.empty(len(df), dtype=float)
    for pid, sub in df.groupby("potrero_id", sort=True):
        idx = sub.index
        lat0, lon0 = float(sub["latitud"].mean()), float(sub["longitud"].mean())
        lon = sub["longitud"].to_numpy(float)
        lat = sub["latitud"].to_numpy(float)

        comun = _campo_suave(lon, lat, rng, lat0, lon0)
        sp1 = _campo_suave(lon, lat, rng, lat0, lon0)
        sp2 = _campo_suave(lon, lat, rng, lat0, lon0)
        u_verde = a * comun + b * sp1
        u_muerta = a * comun + b * sp2

        donante_v, donante_m = donantes[(int(pid) - 1) % N_DONANTES + 1]
        verde[idx] = np.rint(_quantile_map(u_verde, donante_v))
        muerta[idx] = np.rint(_quantile_map(u_muerta, donante_m))
    return verde.astype(int), muerta.astype(int)


def verificar(df):
    problemas = []
    for col in ("densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2"):
        if df[col].isna().any():
            problemas.append(f"vacíos en {col}")
        if (df[col] < 0).any():
            problemas.append(f"negativos en {col}")
    dif = (df["densidad_total_g_m2"] - df["densidad_verde_g_m2"] - df["densidad_muerta_g_m2"]).abs()
    if dif.max() != 0:
        problemas.append(f"total != verde+muerta en {int((dif != 0).sum())} filas")
    return problemas


def principal():
    parser = argparse.ArgumentParser(description="Genera densidades sintéticas para el mapa de Aristeus")
    parser.add_argument("--entrada", type=Path, default=MAPA_ARISTEUS)
    parser.add_argument("--salida", type=Path, default=MAPA_ARISTEUS)
    parser.add_argument("--semilla", type=int, default=RNG_SEED)
    args = parser.parse_args()

    donantes = cargar_donantes(MAP_COLOR)
    df = pd.read_csv(args.entrada, encoding="utf-8-sig")
    verde, muerta = smokear(df, donantes, args.semilla)
    df["densidad_verde_g_m2"] = verde
    df["densidad_muerta_g_m2"] = muerta
    df["densidad_total_g_m2"] = verde + muerta

    problemas = verificar(df)
    if problemas:
        print("[X] Verificación fallida:")
        for p in problemas:
            print("   -", p)
        return 1

    df.to_csv(args.salida, index=False, encoding="utf-8")
    print(f"[+] {len(df)} filas con densidad en {args.salida}")

    print("\nStats globales (comparables con Don Carlos):")
    st = df[["densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2"]].describe()
    print(st.loc[["min", "mean", "std", "max"]].to_string())
    print("corr verde-muerta:", round(df["densidad_verde_g_m2"].corr(df["densidad_muerta_g_m2"]), 3))

    print("\nStats por potrero (verde/media | muerta/media | n):")
    agg = df.groupby("potrero_id")[["densidad_verde_g_m2", "densidad_muerta_g_m2"]].agg(["mean", "std"])
    resumen = df.groupby("potrero_id").size().rename("n").to_frame()
    resumen["verde_mean"] = agg["densidad_verde_g_m2"]["mean"]
    resumen["verde_std"] = agg["densidad_verde_g_m2"]["std"]
    resumen["muerta_mean"] = agg["densidad_muerta_g_m2"]["mean"]
    resumen["muerta_std"] = agg["densidad_muerta_g_m2"]["std"]
    print(resumen.head(10).round(1).to_string())
    print(f"...\ntotal potreros: {len(resumen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())