r"""scripts/research/ola1/secundarias.py -- OLA1-EXEC Bloque 5.

Las tres metricas secundarias, definidas ejecutablemente en E-04 SS4.
Impleméntadas literalmente, sin ajuste posterior (charter SS A.10, D-58).
"""
from __future__ import annotations

from typing import Any

from scripts.research.ola1.pareado import _mapa_identidad

REFLIP_VENTANA_S = 2700.0  # 3 barras M15 (E-04 SS4, P-03).


def secundaria_p02(sid: str, posiciones_brazo: list[dict[str, Any]],
                    posiciones_control: list[dict[str, Any]]) -> dict[str, Any]:
    """P-02 -- buena poda o upside amputado, sobre el subconjunto casado con
    el control, mirando solo las posiciones que el BRAZO cerro con
    reason == 'time_stop'."""
    mapa_brazo, _ = _mapa_identidad(sid, posiciones_brazo)
    mapa_control, _ = _mapa_identidad(sid, posiciones_control)
    casadas = set(mapa_brazo) & set(mapa_control)

    cerradas_ts = [(mapa_brazo[i], mapa_control[i]) for i in casadas
                   if mapa_brazo[i]["reason"] == "time_stop"]
    n_cerradas_por_time_stop = len(cerradas_ts)

    podadas_n = 0
    podadas_suma = 0.0
    amputadas_n = 0
    amputadas_suma = 0.0
    for pb, pc in cerradas_ts:
        delta = pb["net1"] - pc["net1"]
        if pc["net1"] < 0 and delta > 0:
            podadas_n += 1
            podadas_suma += delta
        elif pc["net1"] > 0 and delta < 0:
            amputadas_n += 1
            amputadas_suma += delta

    nets_ts = [pb["net1"] for pb, _ in cerradas_ts]
    net_medio_time_stop_lote1 = (sum(nets_ts) / len(nets_ts)) if nets_ts else None
    wr_time_stop = (100.0 * sum(1 for x in nets_ts if x > 0) / len(nets_ts)) if nets_ts else None

    return {
        "n_cerradas_por_time_stop": n_cerradas_por_time_stop,
        "podadas_perdedoras": {"n": podadas_n, "suma_delta": podadas_suma},
        "amputadas_ganadoras": {"n": amputadas_n, "suma_delta": amputadas_suma},
        "net_medio_time_stop_lote1": net_medio_time_stop_lote1,
        "wr_time_stop": wr_time_stop,
    }


def secundaria_p03(sid: str, posiciones_brazo: list[dict[str, Any]]) -> dict[str, Any]:
    """P-03 -- coste de whipsaw. Re-flip = par de posiciones consecutivas en
    el tiempo donde la segunda abre en sentido contrario dentro de 3 barras
    M15 (2700 s) desde el cierre de la primera. Falso si la segunda termina
    con net1 < 0. Para la escalera, se aplica POR FICHA (tres fichas de la
    misma senal se solapan en el tiempo)."""
    if sid == "SuperTrend-p14x3-M15":
        grupos: dict[Any, list[dict[str, Any]]] = {"_": list(posiciones_brazo)}
    else:
        grupos = {}
        for p in posiciones_brazo:
            grupos.setdefault(p.get("ficha"), []).append(p)

    n_reflips = 0
    n_reflips_falsos = 0
    for grupo in grupos.values():
        ordenado = sorted(grupo, key=lambda p: p["t_exit"])
        for a, b in zip(ordenado, ordenado[1:]):
            delta_t = b["t_in_exec"] - a["t_exit"]
            if 0 <= delta_t <= REFLIP_VENTANA_S and b["side"] != a["side"]:
                n_reflips += 1
                if b["net1"] < 0:
                    n_reflips_falsos += 1

    pct_reflip_falso = (n_reflips_falsos / n_reflips) if n_reflips else None
    return {"n_reflips": n_reflips, "n_reflips_falsos": n_reflips_falsos,
            "pct_reflip_falso": pct_reflip_falso}


def secundaria_p08(sid: str, posiciones_brazo: list[dict[str, Any]],
                    posiciones_control: list[dict[str, Any]]) -> dict[str, Any]:
    """P-08 -- los dos lados, obligatorio: descomposicion exhaustiva sobre
    las casadas en salvadas / mismo_stop_peor_fill / otros, que debe sumar
    EXACTAMENTE la diferencia total (assert, tolerancia 1e-6)."""
    mapa_brazo, _ = _mapa_identidad(sid, posiciones_brazo)
    mapa_control, _ = _mapa_identidad(sid, posiciones_control)
    casadas = sorted(set(mapa_brazo) & set(mapa_control), key=repr)

    salvadas_n = 0
    salvadas_suma = 0.0
    mismo_n = 0
    mismo_suma = 0.0
    otros_n = 0
    otros_suma = 0.0
    suma_diff_total = 0.0
    for ident in casadas:
        pb = mapa_brazo[ident]
        pc = mapa_control[ident]
        delta = pb["net1"] - pc["net1"]
        suma_diff_total += delta
        if pc["reason"] == "EXIT_STLINE" and pb["reason"] != "EXIT_STLINE":
            salvadas_n += 1
            salvadas_suma += delta
        elif pc["reason"] == "EXIT_STLINE" and pb["reason"] == "EXIT_STLINE":
            mismo_n += 1
            mismo_suma += delta
        else:
            otros_n += 1
            otros_suma += delta

    suma_cubos = salvadas_suma + mismo_suma + otros_suma
    assert abs(suma_cubos - suma_diff_total) < 1e-6, (
        f"{sid}: descomposicion P-08 no suma la diferencia total -- "
        f"cubos={suma_cubos} diff_total={suma_diff_total}"
    )
    return {
        "salvadas": {"n": salvadas_n, "suma_delta": salvadas_suma},
        "mismo_stop_peor_fill": {"n": mismo_n, "suma_delta": mismo_suma},
        "otros": {"n": otros_n, "suma_delta": otros_suma},
    }
