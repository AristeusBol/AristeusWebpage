"""Serialización y armado de trayectorias de pastoreo."""

from datetime import date, timedelta

from dominio.constantes import CATEGORIAS_RODEO
from dominio.stock import consumo_diario


def vigente_hoy(row, hoy: date) -> bool:
    return row.fecha_entrada <= hoy and (row.fecha_salida is None or row.fecha_salida >= hoy)


def consolidar_dias(dias, inicio: date):
    """Convierte los 7 días (cada uno con su lista de parcelas) en tramos continuos.

    Cada día puede tener varias parcelas: se comen en ese orden dentro del día.
    Una misma parcela en días seguidos (sin otra en medio) se fusiona en un solo
    stay [entrada, salida]. Devuelve lista de (parcela_id, fecha_entrada, fecha_salida).
    """
    pasos: list[tuple[int, date, date]] = []
    for i, dia in enumerate(dias):
        for pid in dia:
            if pasos and pasos[-1][0] == pid:
                ultimo_fin = (pasos[-1][2] - inicio).days
                if i == ultimo_fin + 1:
                    pasos[-1] = (pid, pasos[-1][1], inicio + timedelta(days=i))
                elif i == ultimo_fin:
                    continue  # misma parcela repetida el mismo día → ignorar
                else:
                    pasos.append((pid, inicio + timedelta(days=i), inicio + timedelta(days=i)))
            else:
                pasos.append((pid, inicio + timedelta(days=i), inicio + timedelta(days=i)))
    return pasos


def trayectoria_bloque(inicio: date, etapas: list) -> dict:
    """Bloque de una trayectoria: ventana de 7 días desde su inicio + etapas."""
    return {
        "inicio": inicio.isoformat(),
        "dias": [(inicio + timedelta(days=i)).isoformat() for i in range(7)],
        "etapas": etapas,
    }


def fila_asignacion(r) -> dict:
    return {
        "id": r.asignacion_id,
        "rodeo_id": int(r.rodeo_id),
        "rodeo": r.rodeo,
        "categoria": r.categoria,
        "categoria_label": CATEGORIAS_RODEO.get(r.categoria, {}).get("label", r.categoria),
        "cabezas": int(r.cabezas),
        "peso_prom_kg": float(r.peso_prom_kg),
        "consumo_pct": float(r.consumo_pct),
        "consumo_diario_ms_kg": consumo_diario(r.cabezas, r.peso_prom_kg, r.consumo_pct),
        "parcela_id": int(r.parcela_id),
        "parcela": r.parcela,
        "estado_parcela": r.estado,
        "potrero_id": int(r.potrero_id),
        "potrero": r.potrero,
        "finca": r.finca,
        "fecha_entrada": r.fecha_entrada.isoformat(),
        "fecha_salida": r.fecha_salida.isoformat() if r.fecha_salida else None,
        "notas": r.notas,
    }


def construir_trayectoria(rows, lotes, fin, hoy: date) -> dict:
    """Agrupa asignaciones por lote y trayectoria, calculando etapas y estados."""
    marcadas: dict[tuple[int, date], object] = {
        (int(f.rodeo_id), f.trayectoria_inicio): f.finalizada_en for f in fin
    }
    por_rodeo: dict[int, list] = {}
    for r in rows:
        por_rodeo.setdefault(int(r.rodeo_id), []).append(r)

    trayectoria = []
    for lote in lotes:
        by_grupo: dict[date, list] = {}
        for r in por_rodeo.get(int(lote.id), []):
            entrada = r.fecha_entrada
            salida = r.fecha_salida
            if salida is not None and salida < hoy:
                estado_etapa = "cerrada"
            elif entrada <= hoy and (salida is None or salida >= hoy):
                estado_etapa = "vigente"
            else:
                estado_etapa = "programada"
            fila = fila_asignacion(r)
            fila["trayectoria_inicio"] = r.trayectoria_inicio
            fila["estado_etapa"] = estado_etapa
            fila["dias_planificados"] = (salida - entrada).days + 1 if salida else None
            fila["dias_transcurridos"] = (hoy - entrada).days + 1 if entrada <= hoy else None
            by_grupo.setdefault(r.trayectoria_inicio, []).append(fila)

        trayectorias: list[dict] = []
        for inicio, etapas in by_grupo.items():
            trayectorias.append(trayectoria_bloque(inicio, etapas))
        for t in trayectorias:
            t["finalizada"] = False
            t["finalizada_en"] = None
            marca = marcadas.get((int(lote.id), date.fromisoformat(t["inicio"])))
            if marca is not None:
                t["finalizada"] = True
                t["finalizada_en"] = marca.isoformat()
        trayectorias.sort(key=lambda t: t["inicio"], reverse=True)
        trayectoria.append({
            "rodeo_id": int(lote.id),
            "rodeo": lote.nombre,
            "color": lote.color,
            "cabezas": int(lote.cabezas),
            "peso_prom_kg": float(lote.peso_prom_kg),
            "consumo_pct": float(lote.consumo_pct),
            "consumo_diario_ms_kg": consumo_diario(lote.cabezas, lote.peso_prom_kg, lote.consumo_pct),
            "trayectorias": trayectorias,
        })
    return {"trayectoria": trayectoria}
