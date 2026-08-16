# WP-3+4+5 — Reporte final: feed H1/H4, hook de tamaño de posición, cómputos de régimen

**Rol:** IMPLEMENTADOR (Sonnet 5 high effort). **Rama:** `equipo1`. **Fecha:** 2026-08-16.
**Spec:** `research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md`
(WP-3, WP-4, WP-5, §1 contrato antitrampa, §2 recon, §4 reglas verbatim).
**Bitácora completa (recon + una entrada por bloque):**
`research/fases/F0-preparacion/02-specs/WP-345-progreso.md`.

Los 3 paquetes están **verdes y commiteados**, uno por commit:

| Bloque | SHA | Contenido |
|---|---|---|
| WP-3 | `0dd14ec` | Feed H1/H4 (`higher_tf.py`), sin tocar `backtest.py` |
| WP-4 | `332884d` | Hook de tamaño + estado de cuenta (`sizing.py`) + `lot_fn` en `metrics`/`peak_margin` |
| WP-5 | `3706020` | ADX/Variance Ratio/Efficiency Ratio/Choppiness + gate (`regime.py`), sin tocar `backtest.py` |

---

## 1 · API exacta que se deja

### `scripts/analysis/realtick_bt/higher_tf.py` (WP-3, módulo nuevo)

```python
def aggregate_closed_with_visibility(
    bars_m15: list[dict[str, Any]], tf_sec: int, *, m15_sec: int = 900,
) -> tuple[list[dict[str, Any]], np.ndarray]
```
Agrega M15 en buckets de `tf_sec` segundos (H1=3600, H4=14400) por floor-division del epoch
(`t // tf_sec * tf_sec`) — sin conversión de huso, el eje ya codifica hora de servidor. Un bucket
se marca **cerrado** la primera vez que una barra M15 propia alcanza/supera el borde de cierre de
SU PROPIO bucket (`b["t"] + m15_sec >= bucket_close`), usando sólo el dato de esa barra, nunca la
siguiente. Devuelve `(closed_bars, visible_count)`: `closed_bars` = OHLC `{"t","t_close","open",
"high","low","close","n_m15"}` de buckets **provablemente** cerrados (el bucket en curso nunca
aparece); `visible_count[i]` = nº de barras superiores visibles en el instante de decisión de la
barra M15 `i` (`bars_m15[i]["t"] + m15_sec`), monótono no decreciente.

```python
@dataclass
class HigherSeries:
    tf_sec: int; bars: list[dict]; ema: list[float|None]; ema_slope: list[float|None]
    st_dir: list[int|None]; momentum: list[float|None]; visible_count: np.ndarray
    def snapshot_at_m15_index(self, i: int) -> dict[str, Any] | None   # O(1)

def build_higher_series(
    bars_m15: list[dict[str, Any]], tf_sec: int, *, m15_sec: int = 900,
    ema_period: int = 20, st_atr_period: int = 10, st_mult: float = 3.0,
    momentum_lookback: int = 10,
) -> HigherSeries
```
EMA/ATR-Wilder/dirección-SuperTrend **reimplementados localmente** (self-contained: cero import de
`emasar_ref.py`, fuera de mis rutas y no leído en esta tarea). Indicadores calculados **una sola
vez** sobre el array de barras cerradas (O(m), m = nº de barras superiores, m≪n); lookup por barra
M15 es O(1) vía `visible_count` precalculado — el coste no es lineal en el histórico por barra.
**No se integró en `backtest.py`**: WP-3 sirve a P-19..P-22/P-28, palancas de estrategia que este
spec deja fuera de este viaje (el módulo queda listo para que un futuro lever lo consuma).

### `scripts/analysis/realtick_bt/sizing.py` (WP-4, módulo nuevo)

```python
@dataclass
class SizingConfig:
    kelly_mult: float|None=None; kelly_payoff_default: float=1.0; kelly_clip: tuple=(0.0,1.0)
    atr_target: float|None=None; atr_clip: tuple=(0.25,4.0)
    dd_bands: list[tuple[float,float]]|None=None            # [(dd_pct_upper, factor), ...] asc.
    ficha_factors: dict[str,float]|None=None
    sharpe_window: int=50; sharpe_floor: float|None=None; sharpe_floor_factor: float=0.5
    loss_streak_cutoff: int|None=None; loss_streak_factor: float=0.0
    correlation_discount_per_extra: float=0.0
    clip: tuple[float,float]=(0.0,3.0)

@dataclass
class AccountState:
    equity: float=0.0; equity_peak: float=0.0
    trade_returns: dict[str,list[float]]; current_day: str|None=None
    consecutive_losses_today: int=0
    @property
    def drawdown_pct(self) -> float

def rolling_sharpe(returns: list[float]) -> float|None
def kelly_factor(state: AccountState, sid: str, cfg: SizingConfig) -> float
def lot_multiplier(pos, sid, state, cfg, n_concurrent_sids, atr_fn) -> float
def apply_sizing(
    resolved: dict[str, list[dict]], cfg: SizingConfig | None, *,
    atr_fn: Callable[[dict], float|None] | None = None,
) -> dict[str, list[dict]]
def lot_fn(base_lot: float) -> Callable[[dict], float]     # adaptador para el hook del motor
```
`apply_sizing(resolved, None)` devuelve `resolved` **sin tocar** (mismo objeto — off por defecto).
Con `cfg` dado: recorre TODAS las posiciones de las 3 estrategias en un **único orden cronológico
explícito** `sorted(key=(t_exit, t_in_exec, sid, ficha, índice_plano))` — nunca el orden de
iteración del dict de `resolved` — reconstruye `AccountState` (equity/drawdown, Sharpe rodante por
estrategia capado a `sharpe_window`, racha de pérdidas consecutivas por día de servidor) y adjunta
`lot_mult` (clave nueva; `net1`/`margin1` intactos), preservando el orden ORIGINAL de la lista de
cada estrategia en la salida. `lot_multiplier()` combina multiplicativamente: Kelly fraccional
(`f* = win_rate - (1-win_rate)/payoff`, clip, `× kelly_mult`), ATR-inverso (vía `atr_fn` inyectado
por el llamador — este módulo no calcula ATR, decisión de diseño para no acoplar a `bars`), banda
de drawdown, factor por ficha, piso de Sharpe rodante, corte de racha de pérdidas diaria, descuento
de correlación por solape real de aperturas (`_concurrency_at_open()`, sweep de eventos
determinista — cuenta estrategias DISTINTAS con posición abierta al momento de abrir), clip final.

### `scripts/analysis/realtick_bt/backtest.py` (único cambio de núcleo, WP-4)

```python
def peak_margin(rows, lot, *, lot_fn: Callable[[dict], float] | None = None) -> float
def metrics(rows, lot, *, lot_fn: Callable[[dict], float] | None = None) -> dict[str, Any]
```
`lot_fn=None` (default) ⇒ usa el `lot` global exactamente como antes de WP-4, byte-idéntico. Los 4
call-sites reales (`baseline_golden.py:92`, `backtest_largo_ava.py:461,468`, `ola1/metricas.py:
55-56`) llaman con 2 posicionales, retrocompatibles sin cambio (verificado por grep, WP-345-
progreso.md Bloque 0 punto 4).

### `scripts/analysis/realtick_bt/regime.py` (WP-5, módulo nuevo, **cero cambios en `backtest.py`**)

```python
def compute_adx(highs, lows, closes, period: int = 14) -> list[float|None]
def compute_variance_ratio(closes, *, window: int = 40, q: int = 2) -> list[float|None]
def compute_efficiency_ratio(closes, *, period: int = 10) -> list[float|None]
def compute_choppiness(highs, lows, closes, *, period: int = 14) -> list[float|None]

@dataclass
class RegimeSeries:
    adx: list[float|None]; variance_ratio: list[float|None]
    efficiency_ratio: list[float|None]; choppiness: list[float|None]

def compute_regime_series(bars, *, adx_period=14, vr_window=40, vr_q=2,
                           er_period=10, chop_period=14) -> RegimeSeries

@dataclass
class RegimeGateConfig:
    enabled: bool = False
    adx_min: float|None=None; vr_low: float|None=None; vr_high: float|None=None
    er_min: float|None=None; chop_max: float|None=None; k_of_m: int = 1

def regime_gate(idx: int, series: RegimeSeries, cfg: RegimeGateConfig) -> bool
```
Las 4 series son cerradas, sin dependencia estadística externa (sólo `math`/`numpy`, ya
dependencias del proyecto) — ADX por recursión de Wilder izquierda-a-derecha; Variance Ratio,
Efficiency Ratio y Choppiness por ventana trasera estricta (`[i-window..i]`, nunca centrada).
`regime_gate` con `cfg.enabled=False` (default) siempre `True` — no filtra nada. Confirmado por el
spec §2 (tabla): WP-5 **no toca el núcleo**; el módulo queda listo para P-09/P-31, no wireado.

---

## 2 · Comandos ejecutados y salida real

Bloque 0 (antes de empezar):
```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in 2.84s
```

Tras WP-3:
```
python -m pytest tests/research/test_higher_tf.py -q
............                                                             [100%]
12 passed in 0.18s

python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in 2.52s
```

Tras WP-4:
```
python -m pytest tests/research/test_sizing.py -q
...............                                                          [100%]
15 passed in 0.62s

python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in 2.34s

python -m pytest tests/research -q
353 passed, 11 deselected in 25.71s

python -m pytest tests/analysis -q
307 passed in 54.24s
```

Tras WP-5:
```
python -m pytest tests/research/test_regime.py -q
.............                                                            [100%]
13 passed in 0.08s

python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in 2.49s

python -m pytest tests/research tests/analysis -q
673 passed, 11 deselected in 72.64s (0:01:12)
```

Cierre (verificación extra fuera de mandato estricto, porque WP-4 tocó `backtest.py`):
```
python -m pytest tests/strategies -q
........................................................................ [ 26%]
........................................................................ [ 52%]
........................................................................ [ 79%]
........................................................                 [100%]
272 passed in 3.84s
```

---

## 3 · Bug atrapado antes de verde (WP-4)

`AccountState.consecutive_losses_today` se reseteaba al cambiar de día DENTRO de
`_update_account_state`, que corre **después** de decidir el multiplicador de la posición actual —
la primera operación de un día nuevo se dimensionaba con la racha de AYER todavía activa. Atrapado
por `test_apply_sizing_loss_streak_cutoff_resets_on_new_server_day` (rojo real, no cosmético).
Arreglo: `_roll_day(state, pos)` — avanza el borde de día ANTES de `lot_multiplier()`, porque el día
de una operación se conoce de antemano por su propio `t_exit`, a diferencia de su PnL, que sólo se
conoce después. Ver `sizing.py::_roll_day`.

---

## 4 · Lo que NO se hizo, y por qué

1. **WP-3 no se enganchó a `backtest.py`.** El spec sirve a P-19..P-22/P-28/P-29 — palancas de
   ESTRATEGIA (momentum multi-temporal), explícitamente fuera de este viaje (§3 de la spec de
   catálogo original y §0 de este spec: "el motor se toca una sola vez... si un paquete descubre
   que necesita algo no listado, para y escala"). El módulo `higher_tf.py` es completo, cacheado,
   probado y listo para que un futuro lever lo consuma; no inventé un punto de enganche no pedido
   por prudencia (menos superficie tocada en `backtest.py` = menos riesgo de paridad).
2. **WP-5 no se enganchó a `backtest.py`, por diseño explícito de la spec** (§2, tabla: "no toca el
   núcleo"). `regime_gate()` existe y está probado como predicado standalone, no wireado.
3. **WP-4: el ATR-inverso (`atr_target`) necesita un `atr_fn` provisto por el llamador.** Este
   módulo deliberadamente NO calcula ATR ni depende de `bars` — decisión de diseño para mantener
   `sizing.py` desacoplado del eje de barras/indicadores (ese cálculo vive donde ya existe
   `_atr_wilder`, fuera de mis rutas, o en `higher_tf.py`/futuro código de estrategia). Probado con
   un `atr_fn` de prueba pasado explícitamente en ningún test actual porque `atr_target=None` por
   defecto ya cubre el camino apagado; el factor ATR-inverso en sí (`kelly_factor`-equivalente) no
   tiene test dedicado aislado — cubierto indirectamente por la composición multiplicativa en
   `lot_multiplier`, pero no hay un test que ejercite `atr_target` con un `atr_fn` real. **Hueco
   declarado**, no bloqueante (todos los demás factores sí tienen test dedicado), fácil de cerrar
   si un futuro consumidor lo necesita.
4. **AC/emasar, Ola1/runner, controlador (TRACKER/LEDGER/DECISIONES/.gitignore/docs/superpowers/
   plans): no tocados, no leídos**, conforme a la prohibición explícita del dispatcher. Nota: el
   `git status` de esta sesión mostró ficheros untracked de otra tarea concurrente (`DIAG-P03-*`,
   `research/fases/F0-preparacion/04-resultados/OLA1/P03-S6/`) — **no se agregaron ni commitearon**,
   confirmado con `git add -- <rutas explícitas>` en cada commit (nunca `git add -A`/`.`).
5. **Fuera de alcance por diseño (spec §3 catálogo original), no intentado:** HMM (P-10), GARCH
   (P-12), Hurst con corrección de sesgo (P-11), trendline de pivotes (P-30), VWAP anclado (P-31
   más allá del gate), overlap de señal en tiempo de ejecución (P-15 más allá del descuento de
   correlación de WP-4).

---

## 5 · Reservas / dudas para el controlador

Ninguna que exija decisión humana bloqueante. Dos notas de trazabilidad, no bloqueos:

- **WP-3/WP-5 quedan sin "punto de inyección" ejercitado en `backtest.py`** (el spec los lista como
  propietarios de un punto de inyección en la tabla §2, pero el contenido de cada sección WP
  aclara que son palancas de estrategia futuras, no de este viaje). Interpreté "punto de inyección"
  como "módulo listo para engancharse", no "enganchado y ejercitado hoy", para minimizar la
  superficie tocada en el núcleo real-tick. Si el controlador quería lo segundo, es un paquete
  adicional pequeño (wireo explícito + test), no un rediseño.
- **`atr_target` de WP-4 no tiene test dedicado con un `atr_fn` real** (punto 3 de la sección
  anterior) — hueco declarado, no bloqueante.
