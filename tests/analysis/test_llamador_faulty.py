"""tests/analysis/test_llamador_faulty.py -- Componente D de la réplica del
motor faulty: el LLAMADOR de P-CAP (`correr_p_cap`), que une A + B + C.

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§4-bis (ADDENDUM 2026-08-13 -- Componente D).

Orden de trabajo (brief §4): 1) acotado y carga, 2) cableado de una
estrategia sobre un tramo corto, 3) la segunda estrategia, 4) la corrida
completa (NO se ejecuta en este fichero de tests -- es un script aparte,
foreground, medido una sola vez).

R1-bis: nada aquí modifica A/B/C, backtest.py ni ningún módulo de
sentinel_engine/**. Se importan y se llaman.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.analysis.realtick_bt.faulty import llamador as L
from scripts.analysis.realtick_bt.faulty.ciclos import correr_ciclos
from scripts.analysis.realtick_bt.faulty.config_faulty import kwargs_de
from scripts.analysis.realtick_bt.faulty.estado_por_barra import (
    estado_por_barra,
    estado_por_barra_supertrend,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------- 0. estático
def test_llamador_no_importa_live_configs_20():
    """D.3: prohibido importar `_GOLIVE_M15`, `CONFIGS_TOMACHINE` o cualquier
    símbolo de `sentinel_engine.strategies.live_configs_20` en llamador.py.
    Las kwargs SIEMPRE salen de config_faulty (Componente C)."""
    fuente = (
        _REPO_ROOT / "scripts" / "analysis" / "realtick_bt" / "faulty" / "llamador.py"
    ).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            assert "live_configs_20" not in nodo.module, (
                f"llamador.py importa de {nodo.module!r} -- prohibido por D.3"
            )
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                assert "live_configs_20" not in alias.name, (
                    f"llamador.py importa {alias.name!r} -- prohibido por D.3"
                )


def test_grafia_strategy_id_coincide_con_verdad_de_terreno():
    """§5 trampa: la grafía de strategy_id debe ser EXACTAMENTE la de
    verdad_terreno_902.csv, o el comparador no empareja nada."""
    verdad = pd.read_csv(_REPO_ROOT / "data" / "analysis" / "p_cap" / "verdad_terreno_902.csv")
    esperado = set(verdad["strategy_id"].unique())
    assert set(L.STRATEGY_ID_DE_CONFIG.values()) == esperado
    assert L.STRATEGY_ID_DE_CONFIG["S6-K2P0"] == "SAR::S6-K2P0"
    assert (
        L.STRATEGY_ID_DE_CONFIG["SuperTrend-p14x3-M15"]
        == "SuperTrend::SuperTrend-p14x3-M15"
    )


def test_ventana_902_t1_es_el_ultimo_cierre_real_de_verdad_de_terreno():
    """RONDA DE CORRECCIÓN 1 (2026-08-13): añadido tras el hallazgo de que
    VENTANA_902[1] traía un t1 con dígitos transpuestos (1785409304 en vez
    de 1786431669), que truncaba la ventana a 2,67 de sus 14,5 días (250
    velas en vez de 970) SIN que ningún test lo detectara.

    `test_idx_desde_idx_hasta_ventana_902_valores_medidos` (más abajo) NO
    podía atrapar ese error: compara `idx_desde_idx_hasta(bar_times, t0, t1)`
    contra una fórmula recalculada con el MISMO `t0`/`t1` que trae
    `L.VENTANA_902` -- es una prueba de que la función implementa bien la
    fórmula de acotado, no de que `VENTANA_902` sea la ventana correcta. Con
    el t1 malo, esa comparación pasaba igual de verde que con el t1 bueno
    (ambos lados usan el mismo t1 erróneo): un acotado que no distingue 250
    velas de 970 no estaba midiendo si LA VENTANA es correcta.

    Este test sí lo hace: ata `VENTANA_902[1]` a una fuente de verdad
    independiente del propio código de `llamador.py` -- el último
    `t_close_epoch` real de `verdad_terreno_902.csv` (D.2: "último cierre").
    Si alguien vuelve a transcribir mal el epoch, este test revienta antes
    de correr nada.

    `VENTANA_902[0]` (t0, conexión del ejecutor) NO se valida aquí: no es
    derivable de `verdad_terreno_902.csv` -- la primera posición real abre
    ~60 s DESPUÉS de t0 por el retcode=10027 documentado en D.6, así que
    "primer t_open_epoch menos t0" no es una identidad, es un desfase
    conocido y declarado, no chequeable por igualdad."""
    verdad = pd.read_csv(_REPO_ROOT / "data" / "analysis" / "p_cap" / "verdad_terreno_902.csv")
    assert L.VENTANA_902[1] == verdad["t_close_epoch"].max()


# --------------------------------------------------------- 1. acotado y carga
def test_load_bars_nativas_falla_ruidosamente_si_no_existe(tmp_path):
    """D.1: si el fichero de nativas no existe, reventar con un mensaje que
    diga qué script lo regenera -- NUNCA caer en silencio a las derivadas."""
    ruta_falsa = tmp_path / "no_existe_XAUUSD_M15_nativas.parquet"
    with pytest.raises(FileNotFoundError) as exc:
        L.load_bars_nativas(ruta_falsa)
    assert "barras_nativas_vs_derivadas.py" in str(exc.value)


def test_load_bars_nativas_mismo_esquema_que_backtest_load_bars():
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    assert len(bars) > 0
    b0 = bars[0]
    assert set(b0.keys()) == {"t", "open", "high", "low", "close", "volume"}
    assert isinstance(b0["t"], int)


def test_idx_desde_idx_hasta_ventana_902_valores_medidos():
    """Pin de los valores reales medidos independientemente contra
    XAUUSD_M15_nativas.parquet para VENTANA_902 (idx_desde=13740,
    idx_hasta=14709, 970 velas) -- no tautológico: la fórmula de este test se
    escribe fresca, no se reutiliza el código de idx_desde_idx_hasta.

    RONDA DE CORRECCIÓN 1 (2026-08-13): VENTANA_902[1] pasó de 1785409304
    (t1 erróneo, dígitos transpuestos -- truncaba la ventana a 2,67 de sus
    14,5 días, 250 velas) a 1786431669 (último t_close_epoch real de
    verdad_terreno_902.csv, 970 velas). Este test pinea el valor CORRECTO
    contra `L.VENTANA_902` -- si la constante volviera a desviarse, este test
    lo distingue (250 != 970), que es justo lo que un pin de acotado debe
    hacer."""
    df = pd.read_parquet(L.BARS_NATIVAS)
    bar_times = df["t"].to_numpy(dtype=float)
    bar_closes = bar_times + 900.0
    t0, t1 = L.VENTANA_902
    idx_desde_esperado = int(np.searchsorted(bar_closes, t0, side="right")) - 1
    idx_hasta_esperado = int(np.searchsorted(bar_closes, t1, side="right")) - 1

    idx_desde, idx_hasta = L.idx_desde_idx_hasta(bar_times, t0, t1)
    assert (idx_desde, idx_hasta) == (idx_desde_esperado, idx_hasta_esperado)
    assert idx_desde == 13740
    assert idx_hasta == 14709

    # boundary: bar_closes[idx_desde] <= t0, y (si existe) bar_closes[idx_desde+1] > t0
    assert bar_closes[idx_desde] <= t0
    if idx_desde + 1 < len(bar_closes):
        assert bar_closes[idx_desde + 1] > t0
    assert bar_closes[idx_hasta] <= t1
    if idx_hasta + 1 < len(bar_closes):
        assert bar_closes[idx_hasta + 1] > t1


def test_estados_fuera_de_acotado_revienta_no_silencioso():
    """D.4: si correr_ciclos pide estados[i] y ese elemento es None (fuera de
    [idx_desde, idx_hasta] o no calculado), debe REVENTAR -- nunca tratarse
    como 'sin ficha deseada'."""
    bar_times = np.array([0.0, 900.0, 1800.0])
    estados = [None, {"open": {"F1": {"side": "L", "sl": 1000.0, "entry": 2000.0}}}, None]
    envueltos = L._EstadosParaCiclos(estados)

    class _FakeTicks:
        def first_at(self, t_sec):
            return (t_sec, 2000.0, 2000.30)

        def range(self, t0, t1):
            return np.array([]), np.array([]), np.array([])

    with pytest.raises(L._EstadosFueraDeAcotado):
        correr_ciclos(envueltos, bar_times, _FakeTicks(), t0=900.0, t1=915.0)


def test_estados_para_ciclos_desenvuelve_open_y_pasa_dentro_del_acotado():
    """Dentro del acotado, _EstadosParaCiclos debe desenvolver el snapshot
    {"open": {...}} de estado_por_barra al dict plano que correr_ciclos
    consume (verificado contra el propio Componente A, no sintetizado)."""
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    kwargs = kwargs_de("S6-K2P0")
    estados = estado_por_barra(bars, kwargs, window=10_000, idx_desde=13740, idx_hasta=13741)
    envueltos = L._EstadosParaCiclos(estados)
    assert envueltos[13740] == estados[13740]["open"]
    assert envueltos[13741] == estados[13741]["open"]
    with pytest.raises(L._EstadosFueraDeAcotado):
        envueltos[13739]


# ------------------------------------------------------------- 2. cableado S6
def test_cableado_s6_tramo_corto_produce_esquema_d5():
    """Cableado de A + B + C para S6-K2P0 sobre un tramo corto (21 velas
    reales, en torno al abrir de la ventana 902, donde el Comp. A ya midió
    ficha activa F1 short) -- comprueba el esquema D.5 de posiciones/eventos,
    no cuenta específica (eso es la corrida completa)."""
    idx_desde, idx_hasta = 13740, 13760
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    ticks = L._TicksCapitaria(L.LAKE_TICKS_CAPITARIA)

    t0 = bar_times[idx_desde] + 900.0  # cierre de la primera vela del tramo
    t1 = bar_times[idx_hasta] + 900.0

    posiciones, eventos = L._correr_estrategia(
        config_id="S6-K2P0",
        strategy_id=L.STRATEGY_ID_DE_CONFIG["S6-K2P0"],
        bars=bars, bar_times=bar_times, ticks=ticks,
        t0=t0, t1=t1, window=10_000, stops_level=0.50,
        max_spread_open=0.50, cycle_sec=15.0,
        idx_desde=idx_desde, idx_hasta=idx_hasta,
    )

    assert isinstance(posiciones, list)
    assert isinstance(eventos, list)
    tipos_validos = {
        "OPEN", "MODIFY", "CLOSE", "SPREAD_GATE_SKIP", "TIME_GATE_SKIP",
        "OPEN_SKIPPED_SL_CROSSED", "SL_CLAMPED", "FALLBACK_CLOSE_INVALID_SL",
        "NOOP",
    }
    motivos_validos = {"SL", "CLOSE_RECONCILER", "FIN_VENTANA", "FALLBACK_CLOSE_INVALID_SL"}
    for e in eventos:
        assert e["tipo"] in tipos_validos
        assert e["strategy_id"] == "SAR::S6-K2P0"
        assert "t" in e and "detalle" in e
    for p in posiciones:
        assert p["strategy_id"] == "SAR::S6-K2P0"
        assert p["motivo_cierre"] in motivos_validos
        for campo in ("t_open", "precio_open", "side", "sl_open_deseado",
                      "sl_open_enviado", "clamp_aplicado", "t_close",
                      "precio_close", "motivo_cierre"):
            assert campo in p
    # el tramo elegido tiene ficha F1 activa en el Comp. A (medido arriba,
    # fuera de este test) -- debe producir al menos un evento.
    assert len(eventos) > 0


# --------------------------------------------------------- 3. cableado ST
def test_cableado_supertrend_tramo_corto_produce_esquema_d5():
    idx_desde, idx_hasta = 13740, 13760
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    ticks = L._TicksCapitaria(L.LAKE_TICKS_CAPITARIA)

    t0 = bar_times[idx_desde] + 900.0
    t1 = bar_times[idx_hasta] + 900.0

    posiciones, eventos = L._correr_estrategia(
        config_id="SuperTrend-p14x3-M15",
        strategy_id=L.STRATEGY_ID_DE_CONFIG["SuperTrend-p14x3-M15"],
        bars=bars, bar_times=bar_times, ticks=ticks,
        t0=t0, t1=t1, window=10_000, stops_level=0.50,
        max_spread_open=0.50, cycle_sec=15.0,
        idx_desde=idx_desde, idx_hasta=idx_hasta,
    )
    assert isinstance(posiciones, list)
    assert isinstance(eventos, list)
    for e in eventos:
        assert e["strategy_id"] == "SuperTrend::SuperTrend-p14x3-M15"
    for p in posiciones:
        assert p["strategy_id"] == "SuperTrend::SuperTrend-p14x3-M15"


# -------------------------------------------------------- artefactos (D.5)
def test_correr_p_cap_tramo_corto_escribe_artefactos_con_esquema_d5(tmp_path):
    """Corrida chica de correr_p_cap (tramo corto de la ventana 902, NO la
    corrida completa) para probar la escritura de artefactos con el esquema
    D.5 -- CSV de posiciones, CSV de eventos, JSON de métricas con lineage."""
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    t0 = bar_times[13740] + 900.0
    t1 = bar_times[13760] + 900.0

    out_dir = tmp_path / "replica"
    metricas = L.correr_p_cap(
        bars_path=L.BARS_NATIVAS,
        ticks_root=L.LAKE_TICKS_CAPITARIA,
        t0=t0, t1=t1,
        stops_level=0.50,
        out_dir=out_dir,
    )

    assert (out_dir / "posiciones_replica.csv").exists()
    assert (out_dir / "eventos_replica.csv").exists()
    assert (out_dir / "metricas_p_cap.json").exists()

    pos_df = pd.read_csv(out_dir / "posiciones_replica.csv")
    ev_df = pd.read_csv(out_dir / "eventos_replica.csv")
    if len(pos_df):
        for col in ("strategy_id", "t_open", "t_open_servidor", "precio_open",
                    "side", "sl_open_deseado", "sl_open_enviado",
                    "clamp_aplicado", "t_close", "t_close_servidor",
                    "precio_close", "motivo_cierre"):
            assert col in pos_df.columns
    if len(ev_df):
        for col in ("strategy_id", "t", "tipo", "detalle"):
            assert col in ev_df.columns

    with open(out_dir / "metricas_p_cap.json", encoding="utf-8") as f:
        m = json.load(f)
    assert m == metricas
    assert set(m["posiciones_por_estrategia"].keys()) == set(L.STRATEGY_ID_DE_CONFIG.values())
    assert m["lineage"]["engine_sha"] == "b113eb7"
    assert m["lineage"]["substrate_id"] == "capitaria-ticks + XAUUSD_M15_nativas"
    assert m["lineage"]["experimento"] == "T0.7-P-CAP"
    assert "tiempo_calculo_seg" in m


# --------------------------------------------------------- D-46: instantes
# `_correr_estrategia` / `correr_p_cap` aceptan un parámetro opcional
# `instantes` (aditivo, D-46) que se reenvía a `correr_ciclos`. No decide
# CÓMO derivar la lista de instantes reales (eso está bloqueado, escalado al
# controlador) -- sólo prueba que el cableado reenvía lo que se le pase.


def test_correr_estrategia_instantes_none_equivale_a_no_pasarlo():
    idx_desde, idx_hasta = 13740, 13760
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    ticks = L._TicksCapitaria(L.LAKE_TICKS_CAPITARIA)
    t0 = bar_times[idx_desde] + 900.0
    t1 = bar_times[idx_hasta] + 900.0

    kwargs_comunes = dict(
        config_id="S6-K2P0", strategy_id=L.STRATEGY_ID_DE_CONFIG["S6-K2P0"],
        bars=bars, bar_times=bar_times, ticks=ticks,
        t0=t0, t1=t1, window=10_000, stops_level=0.50,
        max_spread_open=0.50, cycle_sec=15.0,
        idx_desde=idx_desde, idx_hasta=idx_hasta,
    )

    sin_param = L._correr_estrategia(**kwargs_comunes)
    con_none = L._correr_estrategia(**kwargs_comunes, instantes=None)
    assert sin_param == con_none


def test_correr_estrategia_instantes_reenviado_a_correr_ciclos():
    """El parámetro `instantes` de `_correr_estrategia` debe llegar intacto a
    `correr_ciclos`: pasar la rejilla sintética reconstruida a mano como
    `instantes` debe dar el MISMO resultado que no pasar nada (instantes=None,
    que usa esa misma rejilla internamente) -- prueba de cableado, no
    redecide cómo derivar la lista real."""
    idx_desde, idx_hasta = 13740, 13760
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    ticks = L._TicksCapitaria(L.LAKE_TICKS_CAPITARIA)
    t0 = bar_times[idx_desde] + 900.0
    t1 = bar_times[idx_hasta] + 900.0
    cycle_sec = 15.0

    rejilla = []
    t = t0
    while t < t1:
        rejilla.append(t)
        t += cycle_sec

    kwargs_comunes = dict(
        config_id="S6-K2P0", strategy_id=L.STRATEGY_ID_DE_CONFIG["S6-K2P0"],
        bars=bars, bar_times=bar_times, ticks=ticks,
        t0=t0, t1=t1, window=10_000, stops_level=0.50,
        max_spread_open=0.50, cycle_sec=cycle_sec,
        idx_desde=idx_desde, idx_hasta=idx_hasta,
    )

    con_rejilla_explicita = L._correr_estrategia(**kwargs_comunes, instantes=rejilla)
    con_none = L._correr_estrategia(**kwargs_comunes, instantes=None)
    assert con_rejilla_explicita == con_none
    # y el tramo elegido produce señal real (mismo tramo que los tests de
    # cableado de arriba)
    assert len(con_none[1]) > 0


def test_correr_p_cap_instantes_none_por_defecto_preserva_comportamiento(tmp_path):
    """`correr_p_cap` sin `instantes` (ni pasarlo) debe seguir escribiendo los
    mismos artefactos que antes de D-46 -- ninguna regresión de contrato."""
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    t0 = bar_times[13740] + 900.0
    t1 = bar_times[13760] + 900.0

    out_dir = tmp_path / "replica"
    metricas = L.correr_p_cap(
        bars_path=L.BARS_NATIVAS, ticks_root=L.LAKE_TICKS_CAPITARIA,
        t0=t0, t1=t1, stops_level=0.50, out_dir=out_dir,
    )
    assert "posiciones_por_estrategia" in metricas
    assert (out_dir / "posiciones_replica.csv").exists()


# ------------------------------------------------- D-46 RULING: reloj reconstruido
# El controlador corrigió el encargo original tras ver la medición de cobertura:
# los instantes del log NO son la lista de ciclos (el log registra EVENTOS, no
# ciclos -- todo evento deja rastro, así que un hueco significa "miró y no
# hizo nada", no "no miró"). Se reconstruye el RELOJ: cada epoch real es un
# ANCLA de fase; entre dos anclas el reloj avanza por su cuenta a la cadencia
# medida, y se RE-ANCLA al llegar a la siguiente -- el último paso de relleno
# antes de una ancla es más corto que la cadencia (correcto, no un defecto).
# La réplica sigue libre de decidir QUÉ hacer en cada ciclo (ancla o
# relleno); sólo hereda CUÁNDO mira.


def test_construir_instantes_sin_anclas_es_rejilla_pura():
    """Sin ninguna ancla dentro de [t0, t1), t0 se convierte en la única
    ancla (arranque del reloj) y el resto es relleno puro a `cadencia` --
    debe coincidir exactamente con la rejilla sintética de siempre."""
    instantes, es_ancla = L.construir_instantes_ancla_relleno(
        anclas=[], t0=900.0, t1=960.0, cadencia=15.0
    )
    assert instantes == [900.0, 915.0, 930.0, 945.0]
    assert es_ancla == [True, False, False, False]


def test_construir_instantes_reancla_en_cada_epoch_real():
    """Con anclas=[900, 940] (t0=900 coincide con la primera ancla) y
    cadencia=15: 900 -> 915 -> 930 (relleno, el siguiente paso a 945 se
    pasaría de la ancla 940) -> 940 (RE-ANCLA, paso corto de 10s, no 15) ->
    955 -> 970 (relleno hasta t1=980)."""
    instantes, es_ancla = L.construir_instantes_ancla_relleno(
        anclas=[900.0, 940.0], t0=900.0, t1=980.0, cadencia=15.0
    )
    assert instantes == [900.0, 915.0, 930.0, 940.0, 955.0, 970.0]
    assert es_ancla == [True, False, False, True, False, False]
    # el paso de re-ancla (930 -> 940) es más corto que la cadencia (10 < 15)
    assert instantes[3] - instantes[2] == 10.0


def test_construir_instantes_anclas_fuera_de_ventana_se_descartan_t0_siempre_ancla():
    """Anclas < t0 o >= t1 se ignoran; t0 sigue siendo la ancla de arranque
    aunque no venga del log."""
    instantes, es_ancla = L.construir_instantes_ancla_relleno(
        anclas=[500.0, 900.0, 2000.0], t0=900.0, t1=1000.0, cadencia=15.0
    )
    assert instantes[0] == 900.0
    assert es_ancla[0] is True
    assert all(t0_ <= i < 1000.0 for i, t0_ in [(i, 900.0) for i in instantes])
    assert 2000.0 not in instantes
    # una sola ancla real (900) -- el resto es relleno puro hasta t1=1000
    assert sum(es_ancla) == 1


def test_construir_instantes_cuenta_anclas_y_relleno_es_exhaustiva():
    """Todo elemento de `instantes` es o ancla o relleno, nunca ambos ni
    ninguno -- invariante básico de las dos listas paralelas."""
    instantes, es_ancla = L.construir_instantes_ancla_relleno(
        anclas=[905.0, 933.0, 950.0], t0=900.0, t1=1000.0, cadencia=15.77
    )
    assert len(instantes) == len(es_ancla)
    assert instantes == sorted(instantes)
    # las 3 anclas reales + t0 (arranque, no coincide con ninguna ancla real
    # porque la primera es 905 != 900) deben aparecer con es_ancla=True
    anclas_en_salida = [i for i, a in zip(instantes, es_ancla) if a]
    assert anclas_en_salida == [900.0, 905.0, 933.0, 950.0]


def test_correr_p_cap_reloj_reconstruido_reenvia_instantes_y_anota_metadatos(tmp_path):
    """`correr_p_cap_reloj_reconstruido` debe: 1) construir los instantes a
    partir de un CSV de eventos con columna `epoch`, 2) correr `correr_p_cap`
    con esos instantes, 3) anotar en las métricas devueltas (y en el JSON en
    disco) cuántas anclas y cuánto relleno se usaron."""
    bars = L.load_bars_nativas(L.BARS_NATIVAS)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    t0 = bar_times[13740] + 900.0
    t1 = bar_times[13760] + 900.0

    eventos_csv = tmp_path / "eventos_fake.csv"
    # dos anclas reales dentro del tramo, cadencia de relleno de sobra
    anclas_reales = [t0, t0 + 47.0]
    pd.DataFrame({"epoch": anclas_reales}).to_csv(eventos_csv, index=False)

    out_dir = tmp_path / "replica"
    metricas = L.correr_p_cap_reloj_reconstruido(
        cadencia_relleno=15.77,
        eventos_path=eventos_csv,
        t0=t0, t1=t1,
        bars_path=L.BARS_NATIVAS, ticks_root=L.LAKE_TICKS_CAPITARIA,
        stops_level=0.50, out_dir=out_dir,
    )
    assert "reloj_reconstruido" in metricas
    rr = metricas["reloj_reconstruido"]
    assert rr["cadencia_relleno"] == 15.77
    assert rr["n_anclas_usadas"] == 2
    assert rr["n_relleno"] >= 0
    assert rr["n_instantes_total"] == rr["n_anclas_usadas"] + rr["n_relleno"]

    with open(out_dir / "metricas_p_cap.json", encoding="utf-8") as f:
        m_disco = json.load(f)
    assert m_disco["reloj_reconstruido"] == rr
