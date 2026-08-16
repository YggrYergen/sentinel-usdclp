# OLA1-EXEC -- bitacora de progreso (una linea por bloque, escrita al cerrar cada bloque)

Bloque 0 -- linea de partida: `pytest test_baseline_parity.py -m slow -q` -> 4 passed;
`tests/research` -> 306 passed, 4 deselected; `tests/analysis` -> 307 passed;
`git rev-parse HEAD` -> 25a5d838f4b7cfbf56fd385a991842e49bb5eed4; sustrato: 8334 barras,
{'S6-K2P0': 624, 'S7-TPNONE': 708, 'SuperTrend-p14x3-M15': 153} -- coincide con el esperado. VERDE.

CONTRADICCION DETECTADA (no bloqueante para bloques 0-9, bloqueante para "correr la ola"):
el prompt de despacho de este agente pide lanzar la corrida completa de 157 brazos y escribir
LEDGER real; el brief cerrado (`OLA1-EXEC-brief-paquete-de-ejecucion.md`, SS9, en rojo, repetido
dos veces) y D-58 dicen literalmente "TU NO CORRES LA OLA. La corrida completa la lanza el
CONTROLADOR." y prohiben escribir en `research/LEDGER.jsonl`. Sigo el brief (documento que manda,
segun el propio prompt de despacho): construyo, pruebo con manifiestos de humo/tmp_path/ledger
temporal, y NO lanzo la corrida completa ni toco el LEDGER real. Declarado en el reporte final.

Bloque 1 -- sustrato.py + riesgo.py: cargar_barras/verificar_holdout/verificar_control_contra_linea_base
y r_por_posicion (escalera via bt._sl_inicial_genuine, SuperTrend via bt._atr_wilder+bt.supertrend).
9 tests nuevos en tests/research/test_ola1.py (3 rapidos + 6 slow, datos reales del sustrato),
todos verdes. Parity gate 4 passed antes y despues. VERDE.
