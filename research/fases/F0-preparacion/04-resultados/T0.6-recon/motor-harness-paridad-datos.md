# T0.6-recon — Harness de backtest, paridad, datos y costes

**Fecha de captura:** 2026-08-11
**Rol:** investigador report-only (Sonnet 5), rama `equipo1`. Cero interpretación, cero recomendación.
**Rama git:** `equipo1`. No se ejecutó ningún comando git (prohibido para este rol).
**Pytest:** no se ejecutó ninguna suite (prohibido para este rol); los comandos de suite dirigida se citan pero no se corrieron.

## Comandos ejecutados (Bash, solo lectura)

```
find scripts/analysis/realtick_bt -maxdepth 2 -type f | sort
find "D:/FOREX/data/lake_ticks_ava" -maxdepth 3 2>/dev/null | head -50
find "D:/FOREX/tests/analysis" -maxdepth 1 -type f | sort
mkdir -p "D:/FOREX/research/fases/F0-preparacion/04-resultados/T0.6-recon"
```

Salida real del primer comando:

```
scripts/analysis/realtick_bt/__pycache__/backtest.cpython-311.pyc
scripts/analysis/realtick_bt/__pycache__/bar_fill.cpython-311.pyc
scripts/analysis/realtick_bt/backtest.py
scripts/analysis/realtick_bt/bar_fill.py
scripts/analysis/realtick_bt/extract_bars.py
scripts/analysis/realtick_bt/extract_ticks.py
```

Salida real del tercer comando:

```
D:/FOREX/tests/analysis/__init__.py
D:/FOREX/tests/analysis/test_b1_robustness.py
D:/FOREX/tests/analysis/test_b1_wait_curve.py
D:/FOREX/tests/analysis/test_bar_fill.py
D:/FOREX/tests/analysis/test_monday_audit.py
D:/FOREX/tests/analysis/test_pull_account_deals.py
D:/FOREX/tests/analysis/test_realtick_pairing.py
D:/FOREX/tests/analysis/test_realtick_sl_attribution.py
D:/FOREX/tests/analysis/test_session_clock.py
```

El resto de la evidencia se obtuvo con `Read`/`Grep`/`Glob` (sin comando de shell) sobre los ficheros citados abajo — no se leyó, muestreó ni graficó ningún contenido de ticks (solo se listaron nombres de fichero en `data/lake_ticks_ava/GOLD/` y se leyó código fuente).

---

## 1. Harness de backtest real-tick

**Ubicación:** `scripts/analysis/realtick_bt/` (4 módulos `.py`, sin subpaquetes):
- `scripts/analysis/realtick_bt/backtest.py` — módulo principal, con `main()` como punto de entrada (`scripts/analysis/realtick_bt/backtest.py:637-700`, invocado vía `if __name__ == "__main__": raise SystemExit(main())` en la línea 699-700).
- `scripts/analysis/realtick_bt/bar_fill.py` — resolutor de fills SOLO-BARRA (compañero experimental de `resolve()`, no un punto de entrada independiente; no tiene `main()`).
- `scripts/analysis/realtick_bt/extract_bars.py` — extractor de barras M15 (Componente 1b), con su propio `main()` (`extract_bars.py:40-69`).
- `scripts/analysis/realtick_bt/extract_ticks.py` — extractor de ticks reales (Componente 1), con su propio `main()` (`extract_ticks.py:46-96`).

**`main()` de `backtest.py` no acepta argumentos de CLI** (no hay `argparse`/`sys.argv` en el fichero). Es un script de ejecución fija:
```python
# scripts/analysis/realtick_bt/backtest.py:637-644
def main() -> int:
    bars = load_bars()
    ticks = Ticks()
    print(f"bars: {len(bars)}  {datetime.utcfromtimestamp(bars[0]['t'])} .. {datetime.utcfromtimestamp(bars[-1]['t'])}")
    resolved = build_all(ticks, bars)
    emit_report(resolved)
```
Comando de invocación real (no se ejecutó en esta corrida): `python -m scripts.analysis.realtick_bt.backtest` (o `python scripts/analysis/realtick_bt/backtest.py`, ya que el módulo hace `sys.path.insert(0, str(ROOT))` con `ROOT = Path(r"D:\FOREX")`, `backtest.py:38-39`).

**Cómo se le dice qué estrategia correr:** NO por argumento — está cableado por una constante de módulo:
```python
# scripts/analysis/realtick_bt/backtest.py:71
STRATS = ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"]
```
S6/S7 toman sus kwargs del roster graduado go-live: `_GL = {c["id"]: c["kwargs"] for c in _GOLIVE_M15}` (`backtest.py:70`), importado de `sentinel_engine.strategies.live_configs_20._GOLIVE_M15` (`backtest.py:41`). El driver `build_all()` despacha por nombre: si `sid == "SuperTrend-p14x3-M15"` llama a `run_supertrend(bars, ticks)`; en cualquier otro caso llama a `run_ladder(_GL[sid], bars)` (`backtest.py:444-459`, concretamente la rama en `backtest.py:448-452`). No hay mecanismo para pasar una estrategia arbitraria sin editar `STRATS`/`_GL` en el código fuente.

**Firmas de las funciones núcleo del harness:**
```python
# backtest.py:75
def load_bars() -> list[dict[str, Any]]

# backtest.py:221
def run_ladder(kwargs: dict[str, Any], bars: list[dict[str, Any]]) -> list[dict[str, Any]]

# backtest.py:288
def run_supertrend(bars: list[dict[str, Any]], ticks: Ticks) -> list[dict[str, Any]]

# backtest.py:336
def resolve(pos: dict[str, Any], ticks: Ticks, bar_times: np.ndarray) -> dict[str, Any] | None

# backtest.py:399
def peak_margin(rows: list[dict[str, Any]], lot: float) -> float

# backtest.py:412
def metrics(rows: list[dict[str, Any]], lot: float) -> dict[str, Any]

# backtest.py:444
def build_all(ticks: Ticks, bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]

# backtest.py:503
def emit_report(resolved: dict[str, list[dict[str, Any]]]) -> None

# backtest.py:637
def main() -> int
```

Constantes de módulo relevantes (`backtest.py:45-71`): `BAR_SEC = 900`, `MAX_RETRY_BARS = 1`, `USDCLP = 936.50`, `LEVERAGE = 100.0`, `CONTRACT = 100.0`, `SYMBOL = "XAUUSD"`, `TICKDIR = ROOT / "data" / "lake_ticks" / "XAUUSD"`, `BARS_PATH = TICKDIR / "_bars_M15.parquet"`, `LEVEL_EXITS = {"EXIT_INITSL", "EXIT_SL_RAISED", "EXIT_TRAIL", "EXIT_TP", "EXIT_STLINE"}`, `TOL = 1e-6`.

**Pipeline documentado en el docstring del módulo** (`backtest.py:1-27`, "approach C"): (2) SEÑAL/NIVEL vía `simular_variant` (S6/S7, motor intacto) o SuperTrend vendorizado always-in (ST); (3) FILL RESOLVER camina ticks reales; (4) SPREAD GATE mantiene solo entradas con spread real de tick == 0.5; (5) MÉTRICAS por estrategia × mes.

---

## 2. Cómo consume ticks

**Función que lee los parquet del lago de ticks:** método privado `Ticks._load` de la clase `Ticks` (`backtest.py:83-97`, concretamente `_load` en líneas 88-97):
```python
# backtest.py:88-97
def _load(self, ym: str):
    if ym not in self._m:
        p = TICKDIR / f"{ym}.parquet"
        if not p.exists():
            self._m[ym] = (np.array([]), np.array([]), np.array([]))
        else:
            df = pd.read_parquet(p)
            self._m[ym] = (df.t_msc.to_numpy() / 1000.0,
                           df.bid.to_numpy(), df.ask.to_numpy())
    return self._m[ym]
```
**Esquema de columnas esperado** (leído tal cual del parquet, sin renombrar): `t_msc` (epoch milisegundos, `int64` en el fichero fuente — ver `extract_ticks.py:158-162` / `tasks_ticks_csv.py:158-162`), `bid` (`float64`), `ask` (`float64`). `_load` convierte `t_msc` a segundos dividiendo por 1000.0 (queda `float64` en memoria, eje temporal compartido con las barras).

**Cómo itera:** `Ticks` es un store por-mes cacheado en `self._m: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]` (`backtest.py:86`). Dos métodos públicos de acceso:
```python
# backtest.py:130-139
def first_at(self, t_sec: float):
    """First tick with t >= t_sec (spills across month files as needed)."""
    for ym in self._candidates(t_sec):
        ta, bid, ask = self._load(ym)
        if not len(ta):
            continue
        i = int(np.searchsorted(ta, t_sec, "left"))
        if i < len(ta):
            return float(ta[i]), float(bid[i]), float(ask[i])
    return None

# backtest.py:141-158
def range(self, t0: float, t1: float):
    """All ticks in [t0, t1) (spans <=2 months)."""
    ...
```
La iteración usa `np.searchsorted` sobre arrays ordenados (no un loop tick-a-tick de Python) — busca por posición y devuelve slices/valores puntuales.

**Ruteo de meses (`_candidates`, `backtest.py:113-128`):** el nombre del fichero `<YYYYMM>.parquet` NO coincide exactamente con el mes-servidor porque el extractor bucketiza en la hora del host de extracción, no la hora servidor (ver §7 más abajo y `extract_ticks.py:7-18`). Por eso `_candidates(t_sec)` siempre prueba `[mes-1, mes, mes+1]` en vez de asumir que el fichero `<ym>` contiene exactamente el mes servidor `<ym>`.

**Barras:** `load_bars()` (`backtest.py:75-79`) lee `BARS_PATH` (`data/lake_ticks/XAUUSD/_bars_M15.parquet`) con `pd.read_parquet` y reconstruye una lista de dicts `{"t": int, "open": float, "high": float, "low": float, "close": float, "volume": int}` desde columnas `t,o,h,l,c,v` (esquema fijado por `extract_bars.py:55-60`, ver §7).

**Convención de reloj (documentada extensamente en el docstring del módulo, `backtest.py:15-26`):** todo epoch en el eje barras/ticks es un epoch MT5, que YA codifica la hora del servidor del bróker (server = UTC−4). La única forma correcta de volver a datetime es `datetime.utcfromtimestamp()` (offset cero); `datetime.fromtimestamp()` es INCORRECTO aquí porque reaplica el offset local del host (Chile, con DST variable). Aplicado consistentemente en `Ticks._ym` (`backtest.py:100-102`), `ym_of` (`backtest.py:438-440`), y en `emit_report`/`main` (múltiples sitios anotados con el comentario `# server wall clock`).

---

## 3. Suite golden / paridad

**Ubicación:** `tests/golden/` (paquete completo: `__init__.py`, `generate_fixtures.py`, `fake_feed.py`, `capture_engine.py`, `capture_golden.py`, `test_parity.py`, `test_golden_determinism.py`, más `fixtures/` con CSVs sintéticos y 3 JSON golden).

**IMPORTANTE — alcance de este golden:** cubre el motor de SCORING `sentinel_engine.engine.Engine` (SentinelCore / MacroScorer / TechnicalScorer / levels_engine, instrumentos `usdclp`/`gold`/`nasdaq`), **NO** el motor de estrategias de trading `emasar_variant.simular_variant` / SuperTrend que usa `scripts/analysis/realtick_bt/backtest.py`. No se encontró ningún fichero `tests/golden/fixtures/*.json` ni test de paridad dedicado a `simular_variant` o al harness real-tick — ver "no evaluable" al final de esta sección.

**Qué compara `test_parity.py` exactamente** (`tests/golden/test_parity.py:95-106`):
```python
INSTRUMENTS = ["usdclp", "gold", "nasdaq"]
FLOAT_TOL = 1e-9

@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_parity_against_golden(instrument):
    actual = _clean(capture_engine(instrument, FakeFeed()))
    fixture_path = FIXTURES_DIR / f"{instrument}.json"
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert_recursive_equal(actual, expected)
```
`assert_recursive_equal` (`tests/golden/test_parity.py:37-92`) compara recursivamente dicts (mismas keys), listas (misma longitud, elemento a elemento), booleanos (tipo exacto, nunca `1==True` implícito para tipos distintos), numéricos no-booleanos con tolerancia `FLOAT_TOL = 1e-9` (`abs(actual-expected) <= FLOAT_TOL`), y el resto (int/str/enum/None) con igualdad exacta de tipo y valor.

**Fichero de referencia:** `tests/golden/fixtures/<instrument>.json` (3 ficheros: `usdclp.json`, `gold.json`, `nasdaq.json`, en `tests/golden/fixtures/`).

**Cómo se regenera:** ejecutando `capture_engine.py` como script (`tests/golden/capture_engine.py:63-68`):
```python
if __name__ == "__main__":
    from tests.golden.fake_feed import FakeFeed
    for instrument in ("usdclp", "gold", "nasdaq"):
        path = write_golden(instrument, FakeFeed())
        print(f"Wrote {path}")
```
Comando: `python -m tests.golden.capture_engine`. `write_golden` (`tests/golden/capture_engine.py:55-60`) escribe el JSON canónico vía `to_canonical_json` (importado sin modificar de `capture_golden.py:76-80`: `json.dumps(cleaned, sort_keys=True, ensure_ascii=False, indent=2)`, con `_clean` redondeando floats a 6 decimales, `capture_golden.py:45-73`). El docstring del test (`tests/golden/test_parity.py:12-16`) advierte explícitamente: si el test se pone rojo, regenerar el golden requiere "review/sign-off", nunca aflojar la tolerancia.

**`test_golden_determinism.py`** (`tests/golden/test_golden_determinism.py:17-25`): corre `capture_engine` dos veces sobre el mismo fixture y exige JSON canónico byte-idéntico (`json_1 == json_2`).

**Nombres de test exactos:**
- `tests/golden/test_parity.py::test_parity_against_golden[usdclp]` / `[gold]` / `[nasdaq]`
- `tests/golden/test_golden_determinism.py::test_capture_is_deterministic[usdclp]` / `[gold]` / `[nasdaq]`

**Comando de suite dirigida** (no ejecutado por este rol; solo se cita): `pytest tests/golden -q` (o dirigido a un fichero: `pytest tests/golden/test_parity.py -q`).

**Firma de `capture_engine`:**
```python
# tests/golden/capture_engine.py:41-52
ENGINE_WARMUP_TICKS = 34

def capture_engine(instrument: str, feed) -> dict:
    cfg = load_instrument(instrument)
    engine = Engine(cfg, feed)
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(feed)
    snap = engine.step()
    return snap.to_dict()
```

**No evaluable:** no existe (búsqueda `Grep` sobre `tests/` completo, patrón `simular_variant|realtick_bt|fidelity_compare`) ninguna suite golden/paridad dedicada al motor de estrategias trading (`simular_variant`) ni al harness `realtick_bt`. Lo más cercano en ese dominio son los tests de comportamiento puntual `tests/analysis/test_realtick_pairing.py` y `tests/analysis/test_realtick_sl_attribution.py` (ver §9) y `tests/strategies/test_emasar_variant.py` / `tests/strategies/test_configs_golive.py` (no abiertos en detalle en esta corrida — fuera del listado de "Found 23 files" solo se confirmó su existencia por `Grep` de nombres de fichero, no se leyó su contenido). También referenciado pero **no encontrado en disco**: `fidelity_compare.py`, citado por el docstring de `bar_fill.py:16,34` como el módulo que mide la deriva bar-only vs tick-real; `Grep` de `fidelity_compare` en todo el repo solo encontró la referencia dentro de `bar_fill.py` mismo, ningún fichero de ese nombre existe.

---

## 4. Modelo de costes

Existen **dos** implementaciones de modelo de costes en el repo, en dos harnesses distintos, con parámetros distintos. Ninguna aplica comisión ni slippage explícito además del spread — ambas asumen spread flat/real y comisión=0.

### 4.1 `scripts/analysis/realtick_bt/backtest.py` (harness real-tick, ticks reales)

Constantes (`backtest.py:48-51`): `USDCLP = 936.50`, `LEVERAGE = 100.0`, `CONTRACT = 100.0` (oz por 1.0 lote), `SYMBOL = "XAUUSD"`.

Spread: NO es un parámetro fijo — se lee del tick real (`ask - bid`) y se aplica una PUERTA de spread ("SPREAD GATE") que solo acepta entradas cuyo spread real de tick sea `0.5 ± 0.05`:
```python
# backtest.py:357-359
sp = eask - ebid
if abs(sp - 0.5) <= 0.05:
    entry = (tc, ebid, eask, round(sp, 3)); delay_bars = bi - lo; break
```
Comisión: **0** (documentado en el docstring del módulo, `backtest.py:11`: "commission=0 (Capitaria embeds it in the spread)"; no hay parámetro de comisión en el código — no se resta nada del pnl).
Swap: **0** (`backtest.py:11`: "swap=0 (short holds)"; ídem, sin parámetro ni resta en el código).
Slippage: no hay parámetro de slippage explícito; el "slippage" que se modela es la resolución de nivel intra-barra contra ticks reales (`level_slip`, `backtest.py:381` / `backtest.py:392-395`), que puede desviar el fill del nivel teórico del motor pero no es un parámetro configurable, es un efecto emergente de caminar los ticks reales.
PnL: `net1 = diff * CONTRACT * USDCLP` (por 1.0 lote, en CLP) — `backtest.py:390`; `margin1 = CONTRACT * entry_fill * USDCLP / LEVERAGE` — `backtest.py:391`.
Sizing de reporte: `LOT_GRID = 0.67` y `LOT_VAL = 0.01` (`backtest.py:465-466`), aplicados como multiplicadores sobre `net1`/`margin1` (invariante de escala) en `metrics()` (`backtest.py:412-435`) y `emit_report()`.

### 4.2 `scripts/report/gen_variant_batch1.py` (harness "liga honesta" a barras M15, distinto del anterior)

```python
# scripts/report/gen_variant_batch1.py:45-48
SYMBOL = "XAUUSD"
SPREAD = 0.5  # Capitaria/MT5 real spread, flat, applied at fill.
LOT = 0.10
CONTRACT_SIZE = 100.0  # XAUUSD: $100 per $1 move per 1.00 lot.
```
Aquí el spread SÍ es una constante FIJA de 0.5 (no leída de tick real — este harness corre sobre barras, no ticks), aplicada así:
```python
# gen_variant_batch1.py:130-142
def _entry_fill(side: str, bid_price: float) -> float:
    """Long entries buy at ASK; short entries sell at BID."""
    return bid_price + SPREAD if side == "L" else bid_price

def _exit_fill(side: str, bid_price: float) -> float:
    """Long exits SELL at BID (no adj); short exits BUY BACK at ASK."""
    return bid_price if side == "L" else bid_price + SPREAD

def _pnl(side: str, px_in: float, px_out: float, volume: float = LOT) -> float:
    diff = (px_out - px_in) if side == "LONG" else (px_in - px_out)
    return round(diff * volume * CONTRACT_SIZE, 2)
```
Sin comisión ni swap ni slippage explícitos (no hay parámetros para ninguno de los dos en este módulo). `scripts/report/gen_mfe_capture.py` reusa exactamente estas constantes/funciones vía `importlib` (`gen_mfe_capture.py:96-108`, `_B1.SYMBOL`/`_B1.SPREAD`/`_B1.LOT`/`_B1.CONTRACT_SIZE`/`_B1._entry_fill`/`_B1._exit_fill`/`_B1._pnl`), etiquetando el artefacto de salida con `"cost_model": "flat0.5"` (`gen_mfe_capture.py:269`).

### 4.3 `scripts/analysis/realtick_bt/bar_fill.py` (resolutor bar-only, spread sintetizado)

```python
# bar_fill.py:160
FIXED_SPREAD = 0.5
```
Aquí el spread es una ASUNCIÓN FIJA explícita (no leída de tick, no leída de barra — sintetizada): "we ASSUME the live gate's target spread (0.5) holds on every single candidate bar" (`bar_fill.py:52-56`). El lado ask se sintetiza como `bid + 0.5` para SHORT (`bar_fill.py:74-75`, `199-200`).

**No evaluable:** ningún módulo de los tres trae un parámetro nombrado `commission=` o `slippage=` distinto de cero — no hay "no evaluable" real aquí más allá de eso; la ausencia está confirmada por lectura directa de las tres fuentes, no es una laguna de búsqueda.

---

## 5. Instrumentación existente

### 5.1 CSV de salida por posición (`emit_report`, `backtest.py:503-519`)

Columnas literales del `pd.DataFrame` escrito a `data/analysis/realtick_bt/positions_<sid>.csv`:
```python
# backtest.py:508-518
{
    "side": r["side"], "ficha": r["ficha"], "reason": r["reason"],
    "t_in": datetime.utcfromtimestamp(r["t_in_exec"]).isoformat(),
    "t_out": datetime.utcfromtimestamp(r["t_exit"]).isoformat(),
    "entry_fill": r["entry_fill"], "exit_fill": r["exit_fill"],
    "spread": r["spread"], "entry_delay_bars": r["entry_delay_bars"],
    "net_067lot_clp": round(r["net1"] * LOT_GRID, 2),
    "month": ym_of(r["t_in_exec"]),
}
```
Es decir: `side, ficha, reason, t_in, t_out, entry_fill, exit_fill, spread, entry_delay_bars, net_067lot_clp, month`.

### 5.2 Dict interno completo por posición resuelta (antes del recorte de columnas del CSV)

Producido por `resolve()` (`backtest.py:392-395`) — superset de campos que SÍ existe en memoria pero NO todos llegan al CSV:
```
side_l, side, ficha, t_in, t_out, entry_bid, exit_bid, reason, same_bar,
spread, band, entry_fill, exit_fill, t_in_exec, entry_delay_bars,
t_exit, net1, margin1, level_slip
```
(`side_l`/`t_in`/`t_out`/`entry_bid`/`exit_bid`/`reason`/`same_bar` vienen de `run_ladder`/`run_supertrend`, ver `backtest.py:257-258`, `276-281`, `325-329`; el resto los añade `resolve`.) `bar_fill.resolve_bars()` añade además `ambiguous` y `ambiguous_pessimistic` (`bar_fill.py:237-241`) — no presentes en el resolutor de ticks reales.

### 5.3 No hay JSON de salida por posición en `backtest.py`/`bar_fill.py` — solo el reporte Markdown agregado

`emit_report()` (`backtest.py:503-634`) escribe (a) los CSV por-posición descritos arriba y (b) un único Markdown (`docs/REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md`, ruta fija en `REPORT_MD = ROOT / "docs" / "REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md"`, `backtest.py:464`) con tablas agregadas mensuales (`Mes, Ops, Neto CLP, WR%, PF, maxDD CLP, RoM%`, ver `_grid_table`, `backtest.py:486-500`). No hay un JSON por posición emitido por este harness.

### 5.4 Sí existe un JSON por posición en OTRO módulo: `gen_mfe_capture.py`

```python
# scripts/report/gen_mfe_capture.py:204-219
{
    "side": ..., "ficha": ..., "exit_reason": ...,
    "entry_bar_idx": ..., "exit_bar_idx": ...,
    "entry": ..., "px_out": ...,
    "booked": ..., "mfe": ..., "mae": ...,
    "mfe_capture": ..., "giveback_price": ..., "giveback_usd": ...,
    "pnl_usd": ...,
}
```
Agregado en un artefacto (`_artifact`, `gen_mfe_capture.py:265-274`) con campos de cabecera `report, report_only, cost_model, lot, contract_size, symbol, configs` y escrito a JSON (`write_json`, `gen_mfe_capture.py:277-286`) + Markdown (`write_markdown`, `gen_mfe_capture.py:293-317`). Este es un módulo report-only INDEPENDIENTE del harness `realtick_bt` (usa barras del lago `data/lake`, no ticks reales, y reusa `simular_variant`/`sim_positions` directamente).

### 5.5 Estado grabado DURANTE la posición (no solo apertura/cierre)

- **`return_state=True` de `simular_variant`** (`sentinel_engine/strategies/emasar_variant.py:1441-1462`): expone un snapshot `open_state` de las fichas AÚN ABIERTAS tras procesar la ÚLTIMA barra de `bars`, con `{"side", "entry", "sl", "max_fav"}` por ficha (`emasar_variant.py:1456-1462`). **Esto NO es una traza histórica por-barra durante toda la vida de la posición** — es un snapshot puntual del estado al final del array de barras pasado, pensado para el reconciler en vivo (comparar el SL server-side deseado). Documentado explícitamente en el propio código (`emasar_variant.py:1442-1449`: "the still-open fichas AFTER processing the last bar... Only the reconciler passes return_state=True").
- **`f.max_fav` internamente** (`_Ficha.__slots__`, `sentinel_engine/strategies/emasar_ref.py:255`, actualizado en múltiples puntos de `emasar_variant.py`, p. ej. líneas 502-508, 808-815, 862-874, 924-931, 973, 1018) SÍ se actualiza bar a bar dentro del loop de simulación (`emasar_variant.py:704` en adelante), pero es estado interno de la función — no se emite como evento ni se expone salvo en el snapshot final descrito arriba.
- **`gen_mfe_capture.py` NO usa ese estado interno**: su propio docstring (`gen_mfe_capture.py:36-40`) dice explícitamente que `simular_variant` no expone `max_fav` por-ficha en su propio momento de salida, así que MFE/MAE se RECALCULAN post-hoc a partir de los highs/lows de las barras en el rango `[entry_bar_idx, exit_bar_idx]` (`ficha_metrics`, `gen_mfe_capture.py:150-219`, especialmente líneas 168-178) — no es una traza capturada en vivo durante la simulación, es una reconstrucción determinista fuera de banda.

**Conclusión de hecho (no interpretación):** no se encontró, en el harness `realtick_bt` ni en `emasar_variant.simular_variant`, ningún mecanismo que grabe una traza por-barra o por-tick del estado de una posición (equity flotante, distancia a SL, R acumulado, etc.) a lo largo de TODA su vida y la persista como artefacto. Lo que existe es: (a) snapshot puntual de fin-de-array (`return_state`), y (b) reconstrucción post-hoc span-bounded desde OHLC (`gen_mfe_capture.py`).

---

## 6. Inyección de eventos — forzar cierre en un timestamp dado

**No existe tal mecanismo**, ni en `simular_variant` ni en el harness `realtick_bt`. Búsqueda `Grep` (`force_close|forced_close|manual_close|inject.*close|close_at_timestamp`, case-insensitive, todo el repo) no encontró ningún hit en código de motor o harness (los 2 hits reales están en `scripts/llm_format_eval.py` y un spec doc no relacionados).

**Punto exacto del código donde se decide el cierre** (única fuente de verdad, todo interno, sin gancho exógeno):
- El bucle principal de `simular_variant` empieza en `sentinel_engine/strategies/emasar_variant.py:704` (`for i in range(n): bar = bars[i]; ...`). La sección "1) exits for open fichas" arranca en la línea 714-719 y de ahí en adelante evalúa, por ficha abierta, en este orden documentado (ver docstrings inline citados en el propio fichero): take-profit por R (`EXIT_TP`, líneas 746-781), SL inicial (`EXIT_INITSL`, líneas 785-798), trailing (`EXIT_TRAIL`, múltiples bloques 832-1044 según modo: pips/range/AC-modulado/ratchet/breakeven), `time_stop` (línea 1075), y `stop_and_reverse` (motivo `"reverse"`, descrito en el docstring líneas 374-387). Todos estos son cálculos DETERMINISTAS sobre el `bar` actual (`bar["high"]`/`bar["low"]`/`bar["close"]`) — no hay parámetro ni kwarg que permita inyectar "cierra la ficha X en el timestamp Y al precio Z" desde fuera.
- En la capa del harness (`backtest.py`), `run_ladder()` (`backtest.py:221-285`) solo CONSUME el stream de eventos ya emitido por `simular_variant` — no genera ni modifica cierres, solo empareja ENTRY→EXIT. `resolve()` (`backtest.py:336-395`) decide el PRECIO/TIMESTAMP DE FILL de un cierre ya decidido por el motor (caminando ticks reales para hallar el primer cruce de nivel), pero tampoco puede forzar un cierre en un instante arbitrario no producido por el motor.

**Implicación de hecho (no recomendación):** replicar un "cierre manual" (p. ej. una posición cerrada a mano en MT5 fuera del flujo algorítmico) requeriría, tal como está el código hoy, o bien (a) truncar el array `bars` pasado a `simular_variant` en el índice deseado (afecta la señal completa desde ahí, no solo el cierre), o (b) post-procesar la lista de posiciones devuelta por `run_ladder`/`run_supertrend` fuera de estas funciones. Ninguna de las dos vías existe hoy como función invocable.

---

## 7. Lectura de datos multi-timeframe

**Dentro del harness `realtick_bt`: las barras M15 NO se construyen a partir de ticks.** Se descargan directamente del API de MT5 vía `copy_rates_range` (agregación hecha por el bróker/terminal, no por este repo):
```python
# scripts/analysis/realtick_bt/extract_bars.py:50-51
rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M15, START, END)
```
Salida: columnas `t, o, h, l, c, v` (`extract_bars.py:55-60`), persistidas en `data/lake_ticks/XAUUSD/_bars_M15.parquet` (`OUT`, `extract_bars.py:31`). Ventana fija `START = datetime(2026, 1, 1)`, `END = datetime(2026, 7, 25)` (`extract_bars.py:32-33`). Guardas de identidad: `SANCTIONED_DEMO = {2883015767, 2883016567}`, `REAL_LOGIN = 2883011573` (`extract_bars.py:27-28`), con un self-check textual que aborta si el propio fichero fuente contiene la cadena `order_send` (`extract_bars.py:24-25`).

`load_bars()` en `backtest.py` (§1/§2 arriba) solo LEE ese parquet ya agregado; no hay ningún paso de agregación tick→M15 en el harness real-tick.

**Fuera del harness real-tick, sí existe agregación bar→bar (no tick→bar) en el servicio del dashboard:**
```python
# sentinel_engine/service/bars.py:31-44
def _resample_from_m1(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    rule = f"{int(minutes)}min"
    agg = m1.resample(rule, label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    })
    return agg.dropna(subset=["open", "high", "low", "close"])
```
`NATIVE_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "D": 1440}`, `RESAMPLE_TF_MINUTES = {"M2": 2, "M10": 10}` (`sentinel_engine/service/bars.py:22-23`) — M2/M10 se resamplean desde M1 nativo del lago; el resto son timeframes nativos ya almacenados. `load_tf_frame()` (`bars.py:47-55`) despacha entre lectura directa (`sentinel_engine.lake.store.read_bars`) y resample según si el tf está en el diccionario nativo o el de resample. Esto pertenece al servicio `/api/bars` del dashboard (`sentinel_engine/service/`), NO al harness de backtest `realtick_bt` — es una ruta de código distinta, citada aquí porque el punto 7 del brief pregunta por construcción multi-timeframe en general.

**No evaluable:** no se encontró, en ningún módulo del repo (búsqueda `Grep` case-insensitive `resample|ticks_to_bars|aggregate.*bar|bars_from_ticks` sobre todo el repo), código que agregue ticks crudos (bid/ask por tick) directamente a velas OHLC dentro de este proyecto — toda construcción de barras M15/M1 pasa por el API `copy_rates_range` de MT5 (agregación hecha por el bróker) o por resample bar→bar de un M1 ya agregado.

---

## 8. Adaptador de brókers — Capitaria vs AVA

**Símbolos:** Capitaria usa `"XAUUSD"` (constante `SYMBOL` en `extract_ticks.py:37`, `extract_bars.py:30`, `backtest.py:51`); AVA usa `"GOLD"` (constante `SYMBOL` en `scripts/research/runner/tasks_ticks_csv.py`, ver docstring líneas 5-6: "the broker AVA -- symbol `GOLD` (not `XAUUSD`)"). Confirmado en captura en vivo del feed AVA (`research/fases/F0-preparacion/04-resultados/T0.3-ava/especificacion-feed.md`, no reinterpretado aquí, solo citado como evidencia ya existente de otro agente): `symbol_info.GOLD.description = '1 Lot= 100 Troy Oz'`, `path = 'CFD-Metals\\GOLD'`, `trade_contract_size = 100.0` (mismo contract size que Capitaria, contrastado en esa misma nota contra la cita de Capitaria `trade_contract_size=100`, spread Capitaria=0.60 fijo/`spread_float=False` vs AVA≈0.45 observado/`spread_float=True`).

**Rutas cableadas — lagos físicamente separados, nunca mezclados:**
- Capitaria: `TICKDIR = ROOT / "data" / "lake_ticks" / "XAUUSD"` (`backtest.py:52`; mismo patrón en `extract_ticks.py:38`: `OUT = Path(r"D:\FOREX\data\lake_ticks\XAUUSD")`).
- AVA: `data/lake_ticks_ava/GOLD/` — confirmado por listado de directorio real (52 ficheros `<YYYYMM>.parquet`, `202201.parquet` .. `202512.parquet`) y por el propio código del ingestor: el docstring de `tasks_ticks_csv.py:41-48` dice literalmente "the SAME physical terminal on this machine serves Capitaria some sessions and AVA others, so mixing the two substrates would silently contaminate `data/lake_ticks/XAUUSD/`".

**Guarda de código que impide la mezcla (`assert_destino_seguro`, `scripts/research/runner/tasks_ticks_csv.py:181-197`):**
```python
LAKE_TICKS_PARTS = ("data", "lake_ticks")

def assert_destino_seguro(destino: Path) -> None:
    """Abort if `destino` resolves anywhere inside data/lake_ticks/."""
    parts = Path(destino).resolve().parts
    for i in range(len(parts) - 1):
        if parts[i] == LAKE_TICKS_PARTS[0] and parts[i + 1] == LAKE_TICKS_PARTS[1]:
            raise TicksCsvDestinoError(
                f"destino {destino} cae dentro de data/lake_ticks/ -- PROHIBIDO: "
                "mezclaria ticks AVA con el lago Capitaria que alimenta A6. "
                "usa un lago separado, p.ej. data/lake_ticks_ava/GOLD/"
            )
```
Este check compara componentes de ruta consecutivos exactos `("data","lake_ticks")`, por lo que NO confunde `lake_ticks_ava` (componente distinto) con `lake_ticks` — comentario explícito en el docstring de la función (`tasks_ticks_csv.py:187-189`).

**Task-types del runner que alimentan cada lago:**
- `ticks_mt5` (Capitaria, API MT5 en vivo vía `copy_ticks_range`): `scripts/research/runner/tasks_ticks.py:159-338`, registrado `register("ticks_mt5", ticks_mt5)` (línea 338). Firma: `ticks_mt5(params: dict, out_dir: Path, *, provider=mt5, terminal_check=terminal64_running) -> dict`. `params` requiere `symbol, desde, hasta, destino, logins_sancionados, login_prohibido, expected_login, expected_server` (`tasks_ticks.py:175-183`).
- `ticks_csv_mt5` (AVA, CSV exportado a mano desde la UI del terminal, NUNCA vía API MT5 — el propio módulo se autoprohíbe importar el paquete `MetaTrader5`, `tasks_ticks_csv.py:143-152`): `scripts/research/runner/tasks_ticks_csv.py:253-455`, registrado `register("ticks_csv_mt5", ticks_csv_mt5)` (línea 455). Firma: `ticks_csv_mt5(params: dict, out_dir: Path) -> dict`, `params` requiere `csv_path, destino` (`tasks_ticks_csv.py:256-262`), `destino` SIN valor por defecto en ningún sitio del módulo (docstring líneas 46-48).

**Logins/servidores sancionados distintos por bróker** (constantes en cada extractor Capitaria): `SANCTIONED_DEMO = {2883015767, 2883016567}`, `REAL_LOGIN = 2883011573` (`extract_ticks.py:34-35`, `extract_bars.py:27-28`). El bróker AVA usa credenciales/servidor distintos, verificados en la captura ya citada: login `101744074`, server `'Ava-Demo 1-MT5'`, company `'Ava Trade Ltd.'` — no hay constante equivalente en el harness `realtick_bt` porque ese harness (§1) solo lee de `data/lake_ticks/XAUUSD/` (Capitaria); no consume `lake_ticks_ava` en absoluto hoy.

**No evaluable:** no se encontró (en el código del harness `realtick_bt` ni en `scripts/research/runner/`) ningún adaptador que permita a `backtest.py` correr contra el sustrato AVA (`lake_ticks_ava/GOLD/`) sin modificar el código — `TICKDIR`/`SYMBOL` están cableados a Capitaria/XAUUSD (`backtest.py:51-52`), y no hay parámetro para seleccionar el bróker/símbolo en `main()`.

---

## 9. Tests existentes del harness y del modelo de costes

**Directorio `tests/analysis/`** (listado real, ver comando ejecutado arriba): `__init__.py`, `test_b1_robustness.py`, `test_b1_wait_curve.py`, `test_bar_fill.py`, `test_monday_audit.py`, `test_pull_account_deals.py`, `test_realtick_pairing.py`, `test_realtick_sl_attribution.py`, `test_session_clock.py`.

**Tests directamente sobre el harness `realtick_bt`:**

1. `tests/analysis/test_realtick_pairing.py` — cubre el emparejamiento `run_ladder()` de eventos `"reverse"` (stop-and-reverse) en filas de posición, y dos asserts de membresía de `LEVEL_EXITS`. Nombres de test exactos:
   - `test_reverse_not_in_level_exits` (línea 37)
   - `test_exit_sl_raised_in_level_exits` (línea 45)
   - `test_exit_sl_raised_resolves_via_intrabar_tick_not_bar_close` (línea 82) — pin del fill/timestamp exacto que produce `resolve()` para un `EXIT_SL_RAISED` vía tick real.
   - `test_reverse_emits_one_row_per_open_ficha` (línea 112)
   - `test_reverse_leaves_no_orphaned_ficha_in_open_pos` (línea 133)
   - `test_new_entry_same_bar_as_reverse_pairs_with_its_own_close` (línea 153)
   Usa un stub `_FakeTicks` (líneas 59-79) con `.first_at`/`.range`, mismo contrato que `backtest.Ticks`.

2. `tests/analysis/test_realtick_sl_attribution.py` — cubre la reclasificación `EXIT_INITSL` → `EXIT_SL_RAISED` de `run_ladder()` cuando el nivel emitido no coincide con la fórmula genuina de SL inicial recomputada (`_sl_inicial_genuine`, `backtest.py:162-218`).

3. `tests/analysis/test_bar_fill.py` — cubre `bar_fill.resolve_bars()` (el resolutor bar-only, §4.3). Nombres de test exactos:
   - `test_clean_long_level_exit_fills_at_level` (línea 28)
   - `test_short_level_exit_uses_synthesized_ask_range` (línea 58)
   - `test_ambiguous_both_levels_in_range_overrides_tp_pessimistically` (línea 82)
   - `test_ambiguous_stop_type_reason_is_not_overridden` (línea 106)
   - `test_bar_close_exit_uses_next_bar_open` (línea 130)
   - `test_bar_close_exit_short_side_adds_spread` (línea 154)
   - `test_same_bar_position_never_opens` (línea 173)
   - `test_missing_next_bar_drops_position` (línea 191)
   - `test_entry_delay_bars_always_zero_under_fixed_spread_assumption` (línea 205)

**Comando de suite dirigida** (no ejecutado por este rol, solo citado): `pytest tests/analysis -q` (suite completa del directorio) o dirigido a un fichero, p. ej. `pytest tests/analysis/test_bar_fill.py tests/analysis/test_realtick_pairing.py tests/analysis/test_realtick_sl_attribution.py -q`.

**Tests del modelo de costes (`_entry_fill`/`_exit_fill`/`_pnl`/`SPREAD`/`LOT`/`CONTRACT_SIZE` de `gen_variant_batch1.py`):** no se encontró, en el listado de `tests/analysis/` ni en el `Grep` original de 23 ficheros que referencian `simular_variant`/`realtick_bt`/`fidelity_compare`, ningún fichero de test cuyo nombre indique cobertura directa de esas funciones de `gen_variant_batch1.py` (p. ej. `test_gen_variant_batch1.py` no aparece en ningún listado obtenido). `tests/report/test_gen_mfe_capture.py` SÍ existe (confirmado por `Grep` de nombres de fichero) y ejercita `gen_mfe_capture.py`, que consume esas mismas primitivas de costo vía `importlib` (§4.2) — pero no se abrió su contenido en esta corrida para confirmar qué aserciones concretas hace sobre el costo en sí (ver "no evaluable" abajo).

**No evaluable:** no se abrió el contenido de `tests/report/test_gen_mfe_capture.py`, `tests/strategies/test_emasar_variant.py`, `tests/strategies/test_configs_golive.py`, `tests/strategies/test_supertrend_golive.py`, `tests/scripts/test_check_live_sim_parity.py` ni `tests/scripts/test_check_dryrun_intent_parity.py` en esta corrida (solo se confirmó su existencia por nombre vía `Grep`) — por restricción de alcance/tiempo de esta tarea, no por imposibilidad técnica. Si el plan de implementación necesita sus aserciones exactas, requiere una lectura dedicada de esos ficheros no cubierta aquí.

---

## Resumen de lo NO evaluable (consolidado)

1. §3 — No existe suite golden/paridad para `simular_variant`/`realtick_bt`; el único golden del repo (`tests/golden/`) cubre el motor de scoring `Engine`, un sistema distinto. `fidelity_compare.py`, citado por `bar_fill.py`, no existe en disco.
2. §4 — Confirmado por lectura directa (no una laguna): ningún módulo de costes trae comisión/slippage distintos de cero.
3. §7 — No hay agregación tick→bar dentro de este repo; toda barra M15 viene de `copy_rates_range` (MT5) o de resample bar→bar de M1 ya agregado.
4. §8 — El harness `realtick_bt` no tiene ningún parámetro/adaptador para correr contra el sustrato AVA; está cableado a Capitaria/XAUUSD.
5. §9 — No se abrió el contenido de 6 ficheros de test cuya existencia sí se confirmó por nombre (`test_gen_mfe_capture.py`, `test_emasar_variant.py`, `test_configs_golive.py`, `test_supertrend_golive.py`, `test_check_live_sim_parity.py`, `test_check_dryrun_intent_parity.py`) — restricción de alcance de esta corrida, no imposibilidad.
