import argparse
import sys
import warnings
from datetime import date

from sqlalchemy import text

from core.db import engine
from motor_analitico.negocio import calcular_stock_potrero
from repositorios import calculos

warnings.filterwarnings("ignore")


def principal():
    parser = argparse.ArgumentParser(description="Calculadora de Stock Forrajero con Persistencia Directa")
    parser.add_argument("--potrero", type=int, required=True, help="ID del potrero a analizar")
    parser.add_argument("--usuario", type=int, default=None, help="ID del usuario dueño (opcional, se deriva del potrero si no se provee)")
    parser.add_argument("--fecha", type=str, default=None, help="Fecha YYYY-MM-DD a calcular (por defecto: la más reciente con datos)")
    parser.add_argument("--guardar", action="store_true", help="Guarda el resultado histórico en la base de datos")
    args = parser.parse_args()

    fecha_obj = None
    if args.fecha:
        try:
            fecha_obj = date.fromisoformat(args.fecha)
        except ValueError:
            print(f"[X] Fecha inválida '{args.fecha}'. Usá formato YYYY-MM-DD.")
            return 1

    usuario_id = args.usuario
    if usuario_id is None:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT usuario_id FROM potreros_base WHERE id=:pid"), {"pid": args.potrero}).fetchone()
            if res:
                usuario_id = res.usuario_id

    resultado = calcular_stock_potrero(engine, args.potrero, usuario_id, fecha=fecha_obj)
    if resultado is None:
        if usuario_id is not None:
            with engine.connect() as conn:
                existe = conn.execute(text("SELECT 1 FROM potreros_base WHERE id=:pid"), {"pid": args.potrero}).fetchone()
                pertenece = conn.execute(text("SELECT 1 FROM potreros_base WHERE id=:pid AND usuario_id=:uid"), {"pid": args.potrero, "uid": usuario_id}).fetchone() if usuario_id else None
                if existe and not pertenece:
                    print(f"[X] Potrero ID {args.potrero} no pertenece al usuario {usuario_id}. Acceso denegado.")
                    return 1
        print(f"[!] No se encuentran datos de mapa_color para el potrero ID {args.potrero} (o potrero no existe).")
        return 1

    if args.guardar:
        try:
            with engine.begin() as conn:
                calculos.upsert_calculo(
                    conn,
                    args.potrero,
                    resultado["finca"],
                    resultado["fecha"],
                    resultado["area_neta_ha"],
                    resultado["masa_total_potrero_verde_kg"],
                    resultado["masa_total_potrero_muerta_kg"],
                    resultado["masa_total_potrero_total_kg"],
                    usuario_id=resultado.get("usuario_id", usuario_id),
                )
        except Exception as e:
            print(f"[X] Error guardando el cálculo: {e}")
            return 1

    nombre_potrero = resultado["nombre"]
    area_neta_ha = resultado["area_neta_ha"]
    area_neta_m2 = resultado["area_neta_m2"]
    densidad_promedio_verde_g_m2 = resultado["densidad_promedio_verde_g_m2"]
    densidad_promedio_muerta_g_m2 = resultado["densidad_promedio_muerta_g_m2"]
    densidad_promedio_total_g_m2 = resultado["densidad_promedio_total_g_m2"]
    masa_total_potrero_verde_kg = resultado["masa_total_potrero_verde_kg"]
    masa_total_potrero_muerta_kg = resultado["masa_total_potrero_muerta_kg"]
    masa_total_potrero_total_kg = resultado["masa_total_potrero_total_kg"]

    print("\n" + "=" * 50)
    print(f" INVENTARIO FORRAJERO - {nombre_potrero.upper()} (Usuario {resultado.get('usuario_id','?')})")
    print("=" * 50)
    print(f" Área Neta Productiva: {area_neta_ha:.2f} ha ({area_neta_m2:,.0f} m²)".replace(",", "."))
    print("-" * 50)
    print(f" DENSIDAD PROMEDIO (g/m²):")
    print(f"  Verde:  {densidad_promedio_verde_g_m2:,.1f} g/m²".replace(",", "."))
    print(f"  Muerta: {densidad_promedio_muerta_g_m2:,.1f} g/m²".replace(",", "."))
    print(f"  Total:  {densidad_promedio_total_g_m2:,.1f} g/m²".replace(",", "."))
    print("-" * 50)
    print(" STOCK REAL DISPONIBLE (masa total del potrero):")
    print(f"  MS Verde Total:  {masa_total_potrero_verde_kg:,.0f} kg".replace(",", "."))
    print(f"  MS Muerta Total: {masa_total_potrero_muerta_kg:,.0f} kg".replace(",", "."))
    print(f"  MASA ABSOLUTA:   {masa_total_potrero_total_kg:,.0f} kg".replace(",", "."))
    print("-" * 50)

    if args.guardar:
        print(f" [💾] Guardado en DB -> Potrero ID '{args.potrero}' (Usuario {resultado.get('usuario_id','?')})")
        print(f"      Área: {area_neta_ha:.2f} ha | Total: {masa_total_potrero_total_kg:,.0f} kg".replace(",", "."))
    else:
        print(" [!] Modo solo lectura. Usá --guardar para registrar en DB.")
    print("=" * 50 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
