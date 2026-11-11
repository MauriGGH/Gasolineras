"""Ruta de surtido para una flota de pipas con Google OR-Tools (CVRP con ventanas de horario).

Modelo:
- Nodo 0 = terminal / base (p. ej. una TAR de Pemex). Nodos 1..n = estaciones a surtir.
- Cada pipa tiene capacidad en litros (las más comunes: 20 000 l sencilla, 31 000 y
  hasta 62 000 l full). Puede haber pipas de distintas capacidades.
- Cada estación pide `litros`, tarda `descarga_min` y opcionalmente tiene una ventana
  horaria [inicio_min, fin_min] (minutos desde la salida de la base).
- Jornada máxima por pipa (`jornada_min`).
- Objetivo: minimizar kilómetros (o minutos). Si una estación no se puede atender (no cabe
  en ninguna pipa o su ventana es imposible) se deja fuera con una penalización y se
  reporta en `no_atendidas`, en lugar de fallar todo.

La matriz viene del motor de ruteo (`tabla` de OSRM o de la red propia), así que las
distancias son por carretera. Dijkstra/A* (o CH en OSRM) resuelve cada tramo; OR-Tools
decide el orden y la asignación a pipas, que es el problema difícil (NP-duro).

Si OR-Tools no está instalado se usa la heurística de `routing.pipa` (una sola pipa).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from geo.distancia import Punto

from .pipa import Entrega, planear_surtido


@dataclass
class Pipa:
    id: str
    capacidad_l: float
    costo_fijo: float = 0.0  # penaliza usar una pipa más (en km equivalentes)


@dataclass
class Pedido:
    id: str
    punto: Punto
    litros: float
    descarga_min: float = 30.0
    ventana: tuple[float, float] | None = None  # minutos desde la salida
    datos: dict = field(default_factory=dict)  # se copia tal cual a la salida (nombre, marca...)


def _ortools_disponible() -> bool:
    try:
        import ortools  # noqa: F401
        return True
    except ImportError:
        return False


def planear_flota_surtido(
    base: Punto,
    pedidos: list[Pedido],
    pipas: list[Pipa],
    motor,
    minimizar: str = "km",  # km | minutos
    jornada_min: float = 12 * 60,
    segundos_busqueda: int = 5,
    incluir_geometria: bool = True,
) -> dict:
    """Asigna pedidos a pipas y ordena las visitas. Devuelve viajes con métricas y GeoJSON."""
    puntos = [base] + [p.punto for p in pedidos]
    t = motor.tabla(puntos)
    km, mins = t["distancia_km"], t["duracion_min"]

    if not _ortools_disponible():
        return _respaldo_heuristico(base, pedidos, pipas, km, motor, incluir_geometria)

    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    n, v = len(puntos), len(pipas)
    gestor = pywrapcp.RoutingIndexManager(n, v, 0)
    modelo = pywrapcp.RoutingModel(gestor)
    grande = 10**7

    def entero(x: float, escala: int) -> int:
        return grande if x == float("inf") else int(round(x * escala))

    # Costo de arco: metros o segundos (OR-Tools trabaja con enteros)
    matriz_costo = [[entero(km[i][j], 1000) if minimizar == "km" else entero(mins[i][j], 60) for j in range(n)] for i in range(n)]
    cb_costo = modelo.RegisterTransitCallback(
        lambda a, b: matriz_costo[gestor.IndexToNode(a)][gestor.IndexToNode(b)])
    modelo.SetArcCostEvaluatorOfAllVehicles(cb_costo)
    for k, pipa in enumerate(pipas):
        modelo.SetFixedCostOfVehicle(entero(pipa.costo_fijo, 1000 if minimizar == "km" else 60), k)

    # Capacidad
    demanda = [0] + [int(round(p.litros)) for p in pedidos]
    cb_dem = modelo.RegisterUnaryTransitCallback(lambda a: demanda[gestor.IndexToNode(a)])
    modelo.AddDimensionWithVehicleCapacity(cb_dem, 0, [int(p.capacidad_l) for p in pipas], True, "Litros")

    # Tiempo: manejo + descarga en el nodo de salida
    servicio = [0.0] + [p.descarga_min for p in pedidos]
    mat_t = [[entero(mins[i][j] + servicio[i], 1) for j in range(n)] for i in range(n)]
    cb_t = modelo.RegisterTransitCallback(lambda a, b: mat_t[gestor.IndexToNode(a)][gestor.IndexToNode(b)])
    modelo.AddDimension(cb_t, int(jornada_min), int(jornada_min), True, "Tiempo")
    dim_t = modelo.GetDimensionOrDie("Tiempo")
    for i, p in enumerate(pedidos, 1):
        if p.ventana:
            dim_t.CumulVar(gestor.NodeToIndex(i)).SetRange(int(p.ventana[0]), int(p.ventana[1]))

    # Permitir dejar pedidos fuera (con penalización alta) para que siempre haya solución
    for i in range(1, n):
        modelo.AddDisjunction([gestor.NodeToIndex(i)], grande)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = segundos_busqueda
    sol = modelo.SolveWithParameters(params)
    if sol is None:
        raise RuntimeError("OR-Tools no encontró solución")

    viajes, atendidos = [], set()
    dim_l = modelo.GetDimensionOrDie("Litros")
    for k, pipa in enumerate(pipas):
        idx = modelo.Start(k)
        nodos = []
        while not modelo.IsEnd(idx):
            nodos.append(gestor.IndexToNode(idx))
            idx = sol.Value(modelo.NextVar(idx))
        nodos.append(0)
        if len(nodos) <= 2:
            continue
        paradas = []
        for i in nodos[1:-1]:
            ped = pedidos[i - 1]
            atendidos.add(ped.id)
            ix = gestor.NodeToIndex(i)
            paradas.append({"id": ped.id, "lat": ped.punto[0], "lon": ped.punto[1], "litros": ped.litros,
                            "llegada_min": sol.Value(dim_t.CumulVar(ix)), "carga_acumulada_l": sol.Value(dim_l.CumulVar(ix)),
                            **ped.datos})
        viajes.append(_viaje(pipa.id, pipa.capacidad_l, nodos, paradas, km, mins, servicio, puntos, motor,
                             incluir_geometria))
    return _resumen(viajes, pedidos, atendidos, "ortools")


def _viaje(pipa_id, capacidad, nodos, paradas, km, mins, servicio, puntos, motor, geometria) -> dict:
    tramos = list(zip(nodos, nodos[1:]))
    viaje = {
        "pipa": pipa_id,
        "capacidad_l": capacidad,
        "litros": sum(p["litros"] for p in paradas),
        "orden": [p["id"] for p in paradas],
        "paradas": paradas,
        "distancia_km": round(sum(km[a][b] for a, b in tramos), 2),
        "duracion_min": round(sum(mins[a][b] + servicio[a] for a, b in tramos), 1),
    }
    viaje["ocupacion"] = round(viaje["litros"] / capacidad, 3) if capacidad else None
    if geometria:
        try:
            linea = motor.ruta([puntos[i] for i in nodos])["linea"]
            viaje["linea"] = [[lon, lat] for lat, lon in linea]
        except Exception as exc:  # la geometría es decorativa; no tumbar el plan
            viaje["linea_error"] = str(exc)
    return viaje


def _resumen(viajes, pedidos, atendidos, metodo) -> dict:
    features = []
    for v in viajes:
        if "linea" in v:
            features.append({"type": "Feature", "properties": {"tipo": "viaje_pipa", "pipa": v["pipa"],
                                                               "distancia_km": v["distancia_km"]},
                             "geometry": {"type": "LineString", "coordinates": v["linea"]}})
        for k, p in enumerate(v["paradas"], 1):
            features.append({"type": "Feature", "properties": {"tipo": "entrega", "pipa": v["pipa"], "orden": k, **p},
                             "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]}})
    return {
        "metodo": metodo,
        "viajes": viajes,
        "no_atendidas": [p.id for p in pedidos if p.id not in atendidos],
        "distancia_total_km": round(sum(v["distancia_km"] for v in viajes), 2),
        "litros_entregados": sum(v["litros"] for v in viajes),
        "geojson": {"type": "FeatureCollection", "features": features},
    }


def _respaldo_heuristico(base, pedidos, pipas, km, motor, geometria) -> dict:
    cap = max(p.capacidad_l for p in pipas)
    caben = [p for p in pedidos if p.litros <= cap]
    entregas = [Entrega(p.id, p.punto, p.litros) for p in caben]
    sub = [0] + [pedidos.index(p) + 1 for p in caben]
    matriz = [[km[i][j] for j in sub] for i in sub]
    por_id = {p.id: p for p in pedidos}
    viajes = []
    for k, v in enumerate(planear_surtido(base, entregas, cap, matriz)):
        nodos = [0] + [pedidos.index(por_id[i]) + 1 for i in v["orden"]] + [0]
        paradas = [{"id": i, "lat": por_id[i].punto[0], "lon": por_id[i].punto[1], "litros": por_id[i].litros,
                    **por_id[i].datos} for i in v["orden"]]
        servicio = [0.0] + [p.descarga_min for p in pedidos]
        viajes.append(_viaje(f"{pipas[0].id}-viaje{k + 1}", cap, nodos, paradas, km, km, servicio,
                             [base] + [p.punto for p in pedidos], motor, geometria))
    return _resumen(viajes, pedidos, {i for v in viajes for i in v["orden"]}, "heuristica")
