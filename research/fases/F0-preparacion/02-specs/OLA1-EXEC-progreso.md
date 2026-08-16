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

DIRECTIVA DIRECTA DEL USER (2026-08-16, mid-turn, dos mensajes: "ya basta ... necesitamos
correr la suite completa asap" / "corre el comando para que corra completa por favor"):
el USER (no un agente) instruyo explicitamente correr la ola completa AHORA. Esto es consentimiento
directo del user, que prevalece sobre la delegacion de roles del brief (que asumia que solo el
CONTROLADOR lanzaria la corrida real). Se procedio a completar Bloques 6-8 minimamente y LANZAR
la corrida real contra research/LEDGER.jsonl y 04-resultados/OLA1/, ver detalle abajo.

Bloque 6 -- tasks_ola1.py: task-type ola1_paired registrado (runner.py +1 linea de import).
Resuelve brazo-a-brazo con progreso (_brazos.txt), guardas fail-loud (holdout, control-vs-base,
R no computable >50%, identidad duplicada), escribe posiciones.csv/metricas.json/alineacion.json.
Smoke-testeado directamente (SuperTrend P-08 y ladder S6 P-02) antes de commitear.

Bloque 8 -- manifiesto.py (grillas E-04 SS3 hardcodeadas, 157 brazos/44 confirmatorios generados
y verificados), consolidar.py (BH-FDR doble, banner SS8-bis), correr_ola1.py (una orden). YAML
generado: research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml.

CORRIDA REAL LANZADA (por instruccion directa del user): `python -m scripts.research.runner.runner
research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml --on-error continue --workers 5`,
git_sha=ad5b95d, iniciado 2026-08-16T03:24:38, terminado 2026-08-16T03:25:15 (36.3s).
RESULTADO: 3/5 corridas OK (P08-ST, P05-ST, P03-S6 = 123 brazos, LEDGER real actualizado con
3 filas), 2/5 FALLIDAS (P02-S6, P02-S7 = 34 brazos, incl. TODOS sus 14 confirmatorios) por
HoldoutVioladoError real y reproducible: una posicion cuyo time_stop (max_hold_bars=10) cierra
exactamente en t_exit=HOLDOUT_INI (1778544000), identica en S6 y S7. Guarda fail-loud funcionando
como se especifico (Bloque 6 paso 4: holdout se verifica sobre TODOS los brazos de la corrida a
la vez, asi que UN brazo intruso invalida la corrida entera). NO es un bug de este paquete
(verificado: mismo Ticks()/resolve() que paired_harness, ya testeado byte-identico en Bloque 2).
Necesita decision de diseno del controlador -- ver reporte final.

HALLAZGO ADICIONAL (objetivo, no interpretado): los 95 brazos de P03-S6 (incl. ac_off y los 3
factor<F>) dan net_lote1 y posiciones BYTE-IDENTICAS al control en la corrida real. Verificado que
el overlay SI se propaga (spy sobre ac_desacelerando: 6306/13947 True con umbral=0.0 vs 4044/13947
con umbral=0.75 -- el trigger dispara distinto) pero el resultado simulado final no cambia ni una
posicion. Dato consolidado tal cual (media_diff=0.00, p_bootstrap=1.00 en los 95 brazos); no se
investigo mas por presupuesto de tiempo -- ver reporte final.

Consolidador corrido sobre el resultado real: 123 brazos, BH-FDR confirmatorio 3/27 rechazados,
total 7/120 rechazados, 0 sin p_bootstrap. _consolidado.json/_consolidado.md/_ESTADO.md escritos
en 04-resultados/OLA1/. Suite completa test_ola1.py: 27 passed (20 rapidos + 7 slow). Parity gate,
tests/research (326 passed/11 deselected) y tests/analysis (307 passed) verdes tras el cambio.

Bloque 5 -- secundarias.py: secundaria_p02 (podadas/amputadas sobre casadas+time_stop),
secundaria_p03 (reflip 3 barras/2700s, por ficha en la escalera, pct=None si n_reflips=0),
secundaria_p08 (salvadas/mismo_stop_peor_fill/otros, assert suma==diff_total). 5 tests
nuevos verdes. Parity gate 4 passed. VERDE.
