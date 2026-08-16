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

Bloque 2 -- paired_harness.run_paired_arms(pares="todos"|"contra_control", brazo_control):
cambio aditivo, default "todos" byte-identico. 21 tests de test_harness_pareado.py siguen
verdes sin tocarlos; 2 tests nuevos en test_ola1.py (coincide con "todos" en los pares
compartidos + ValueError si falta el control). Parity gate 4 passed. VERDE.

Bloque 3 -- metricas.py: metricas_de_brazo() con las 20 claves del brief (net_lote1, R,
en-R, racha de perdidas, sharpe x2, n_por_reason, overlay de coste D-54/D-59). COSTE_CLP
verificado = 21071.25. 3 tests nuevos (coste sintetico + n=0 + datos reales S6, slow).
Parity gate 4 passed. VERDE.

Bloque 4 -- pareado.py: pareado_vs_control() con dedup de identidad (primera por t_exit,
n_identidades_duplicadas contado), tasa de emparejamiento + degradado_a_1B (D-56, umbral 0.90),
diffs pareados + media_diff_en_R, bootstrap por bloques vectorizado (dia servidor, B=10000,
seed 20260816). 5 tests nuevos (IC de diferencia cero, vectorizado==ingenuo, reproducible,
no-evaluable, duplicadas). Parity gate 4 passed. VERDE.
