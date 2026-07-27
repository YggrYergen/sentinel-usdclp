# Catálogo v3 — programa exhaustivo de mejora por estrategia (salidas, re-entrada, entradas, zonas, MTF)

**Fecha: 2026-07-27 · Estado: PROPUESTO — pendiente de revisión del user.**
Origen: sesión 2026-07-27, ideación sobre el problema de giveback (posiciones que tocan
utilidad y cierran en pérdida) + directivas del user. Complementa —no reemplaza— el plan v2
(`docs/superpowers/plans/2026-07-25-experiment-matrix-implementation-plan-v2.md`) y la matriz
FINAL (`docs/superpowers/research/2026-07-22-FINAL-experiment-matrix.md`): las referencias
[→ ...] apuntan a tasks/filas de esos documentos. 🆕 = no existía ahí.

Base mecánica: informe de mecánica exacta de las tres estrategias (sesión 2026-07-27,
verificado contra `sentinel_engine/strategies/emasar_variant.py`, `emasar_ref.py`,
`_supertrend_ref.py`, `live_configs_20.py`, `scripts/live/run_live_20.py`,
`sentinel_engine/live/reconciler.py`). Hallazgos clave que fundan este catálogo:
- S6-K2P0 y S7-TPNONE comparten la señal de entrada EXACTA; difieren solo en salidas.
- S6 no tiene NINGUNA protección de utilidad; S7 lleva `be_at_r=1.0` vivo; ST no tiene nada.
- La señal S6/S7 es conjunción re-evaluada por barra SIN memoria de cierre (sin cooldown);
  ST es estado puro always-in (reapertura garantizada tras cierre sin flip).
- La trampa estructural (user): cerrar con la señal activa = partir la pérdida en dos + spread.
  → toda política de salida necesita política de re-entrada acoplada (familia C).
- El motor ya trae inertes: `be_at_r`, `f1_tp_r`/`f2_tp_r` (V-05, arma F1/F2, F3 runner nato),
  `ratchet_lock_frac`/`ratchet_atr_k` (PX-T1), `trail_arm_r`, `max_hold_bars`, `reentry_enable`
  (V-13, semántica INVERTIDA: re-entrada solo tras trail-out completo), `active_fichas`.

## 🔴 Bugs de instrumento descubiertos 2026-07-27 (bloquean todo veredicto)

1. **Pairing "reverse"**: `scripts/analysis/realtick_bt/backtest.py:164` solo empareja
   `motivo.startswith("EXIT") or motivo == "time_stop"` — los cierres `"reverse"` (~504 S6,
   ~240 S7 en 7 meses, medidos por replay) NO emiten fila en `positions_*.csv`. ~24% de los
   cierres de señal ausentes del substrato. Afecta: curva B1 (Task 16), robustez (059a5a2),
   concentración, solape a2/cap B3, correlaciones, maxDD, reporte mensual. NO afecta: el
   veredicto vivo de 50 min (origen: diagnóstico live), código vivo, R1-bis.
2. **Fallback de fills**: `resolve()` usa el tick de apertura de la barra siguiente cuando
   ningún tick cruza el nivel — 36% de los `EXIT_INITSL` de S6 tienen exit_fill en dirección
   de ganancia. Reparación: jerarquía tick → barra M1 (lake ya la tiene) → marcar-y-excluir;
   columna `fill_source`; asserts aritméticos (un stop largo no puede llenar sobre el nivel).

## Reglas del programa (directivas user 2026-07-27)

1. **Sin priors direccionales**: toda grilla incluye `off` y ambas direcciones.
2. **Exhaustividad por estrategia**: cada familia se corre para cada estrategia donde sea
   mecánicamente posible.
3. **Regla de meseta**: meseta detectada → refinar granularidad dentro (paso 0.25 o menor).
   [→ 10.2 plateau-selection, 11.1 sensitivity surfaces]
4. **Re-litigar quemados solo con causa**: TP se re-abre porque su veredicto precede a los
   fixes de reloj/reverse/fills y nunca controló re-entradas. El veredicto viejo queda en el
   registro de negativos (2.5); la nueva corrida es aditiva.
5. Veredictos = neto + robustez D170 (consistencia mensual + recorte top-K) → cola de
   backtest largo (`docs/superpowers/specs/2026-07-27-long-backtest-queue.md`, Task 2.4)
   → holdout sagrado (12.2).
6. R1-bis siempre: todo sobre copias (cfg deep-copy, banda mágica nueva); vivos intactos.
7. 🔒 Familia E (recombinación/ladder/pirámide) NO arranca hasta terminar las demás
   exploraciones; se activa solo si quedan ≥2-3 configs estadísticamente ganadoras.

## Familia A — Instrumento y medición (bloquea el resto)

| # | Qué | Detalle |
|---|---|---|
| A1 🆕 | Reparar pairing reverse + fills | regenerar CSVs, re-correr Track A completo, diff viejo-vs-nuevo documentado. Condiciona Task 2.1 de v2 |
| A2 | Mapa MFE/MAE por posición | % de perdedoras que tocó ≥{0.25,0.5,1,1.5,2}R en verde, por estrategia. Calibra familia B [→ ★ MAE/MFE de la matriz; enabler Task 2.3] |
| A3 🆕 | Economía de la reversa | ¿las patas de reverse suman o restan? ¿cuánto spread quema el ciclo? Decide E3 |
| A4 🆕 | Expectancy condicional al spread 0.50/0.60 | ya operamos con filtro accidental (cap estático 0.5 en máq1); medir qué bloquea |
| A5 | Experimento natural S6-vs-S7 | misma señal, salidas distintas: valor del BE-1R neto del churn, gratis [→ 3.2, 7.1] |

## Familia B — Salidas y protección de utilidad

- **B1 Breakeven, grid completo, las tres**: `be_at_r ∈ {off, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0}`
  para S6 Y S7 (off en S7 = testear remover el actual); ST vía wrapper (B7).
  `be_offset ∈ {0.5, 2, 5}` pips. Propiedad anti-trampa: stop-out en BE ⇒ re-entrada cuesta
  solo spread. [→ matriz fila 7, que solo tenía S7 {off,0.5,1.0,1.5,2.0} — CORREGIDA]
- **B2 Ratchet PX-T1**: `lock_frac ∈ {0.25, 0.4, 0.5, 0.6, 0.7, 0.8}` (0.6-0.8 = directiva user)
  + chandelier `ratchet_atr_k ∈ {2.0, 2.5, 3.0}` (excluyentes por diseño). [→ 5.3]
- **B3 Piso ATR del trail**: `trail_atr_floor_k ∈ {1.0, 1.5, 2.0, 2.5, 3.0}` + regla de meseta.
  [→ matriz fila 6 extendida con 3.0]
- **B4 🆕 Trailing trifásico (diseño user)**: F1 supervivencia→BE; F2 apretar hasta
  `W* = L̄·(1−WR)/WR` (umbral de suficiencia, computado del substrato reparado por estrategia;
  hoy ≈1.9·L̄ con W/L actual ≈2.2 — margen delgado); F3 runner con apriete POR INDICADOR
  (agotamiento momentum [→ 5.2], desaceleración AC [→ §4C TOKATA `AC_ModulateTrail`],
  proximidad a zona opuesta [D2]). Transiciones en R: {(1,2), (1,2.5), (1,3), (0.75,2)}.
  Riesgo declarado por el user: fase 3 sin indicador = puerta igual para ganar y perder.
- **B5 Re-exploración TP (des-quemado condicional)**: `tp_r ∈ {0.5, 0.75, 1.0, 1.5, 2.0, 3.0}`
  × por-ficha (F1 / F1+F2) × cuantizado a zona (D2) × con/sin política C acoplada.
  Argumento user: el TP que pierde sin re-entrada puede ganar con ella. [→ §1 quemado revisado]
- **B6 Time-stop + agotamiento**: [→ matriz fila 8, Task 5.2] sin cambios.
- **B7 SuperTrend, programa propio**: (a) romper always-in con MULTI-definición de plano
  (ATR-percentil EXCLUIDO, quemado): flip-count últimas K barras, ADX(14), |precio−línea|/ATR,
  Choppiness(14), pendiente LR(20) — cada una × 3 umbrales [→ §2.2 fila 3 expandida];
  (b) 🆕 cierre-a-través + buffer: SL desastre en línea ± k·ATR, salida de motor solo por
  cierre cruzando banda (mata churn mecha-toca-reabre del always-in);
  (c) 🆕 wrapper BE/ratchet (hoy ST no tiene NADA; WR 22.76%);
  (d) filas existentes: mult {2.0..3.5}, ATR period {7,10,14,21}, supresión flip cerca de zona.

## Familia C — Políticas de re-entrada 🆕 (companion obligatorio de B; alta prioridad user)

| # | Política | Grid |
|---|---|---|
| C1 | Cooldown fijo tras stop-out en pérdida | K ∈ {1,2,3,5,8} barras |
| C2 | Event-ificación: gate debe pasar por FALSO antes de re-armar | on/off × barras-en-falso {1,2} |
| C3 | Solo a mejor precio que el cierre anterior | margen {0, 0.5, 1}·ATR |
| C4 | Confirmación reforzada en re-entrada (G5 3-de-3) | on/off |
| C5 | Tamaño reducido en primera re-entrada | fracción {0.5, 0.33}, restaura tras win |
| C6 | Máx re-entradas por episodio de señal | {1, 2, 3, ∞} |
| C7 | Condicional a MFE de la pata cerrada (follow-through real) | X ∈ {0.25, 0.5, 1.0}·R |
| C8 | SAR-reset: SAR flipea en contra y de vuelta | on/off × TF del SAR |
| C9 | Bloqueo por zona consumida (rechazó el intento previo) | on/off (cruce D2) |
| C10 | Tiempo-O-distancia (K barras O alejarse Y·ATR y volver) | combinaciones C1×C3 |
| C11 | Asimétrica por tipo de cierre (post-BE libre; post-pérdida gateada) | mapa tipo→política |
| C12 | Presupuesto de pérdida por episodio (> Z·R ⇒ episodio muerto) | Z ∈ {1.5, 2, 3} |

Para ST: dialecto propio — C2 ≡ exigir cierre-confirmación tras stop-out (cruce B7b).
Inventario: `reentry_enable` V-13 existente tiene semántica invertida (solo tras trail-out
completo); documentado, no confundir.

## Familia D — Entradas, contexto, calidad de señal

- **D1 🆕 Multi-TF INFERIOR (idea user #1 + extensiones)**:
  - D1a gate binario: SAR {1m,2m,5m} alineado con dirección M15; k-de-m {1/3,2/3,3/3};
    step SAR inferior {0.02, 0.1, 0.3}.
  - D1b score graduado: nº TFs alineados como NOTA (no veto). Validar retrospectivo sobre
    substrato ANTES de usar — primera noción de strength (hipótesis lotería), costo cero.
  - D1c micro-timing: M15 arma, ejecución espera confirmación 1m/5m; SL inicial anclado en
    estructura del TF inferior ⇒ mismo stop en $ = más R ⇒ arma antes BE/ratchet/fases.
    [→ roza 8.1, va más allá]
  - D1d frescura: flip inferior reciente VS maduro — ambas direcciones, sin prior.
  - D1e variantes de indicador: misma arquitectura con SuperTrend inferior o AO/AC en 5m.
  - D1f índice de coherencia 1m→H1 (integra Task 4.2): gate + score sizing (6.1) + feature
    meta-label (9.1).
- **D2 Zonas de compra/venta — máximo depth (idea user #2; [→ Eje 2 §3 FOCO] expandido)**:
  - Métodos: swings fractales (fuerza N-barras) · pivotes floor-trader S1-S3/R1-R3
    (formalización de "primeras 3-4 zonas") · H/L de día/semana/sesión previos · números
    redondos oro (00/50/25) · perfil volumen-tick HVN/LVN · opening range / initial balance ·
    bordes de gaps de reapertura (detector de reaperturas YA construido: `session_clock.py`) ·
    extremos Donchian · score de confluencia entre métodos.
  - Firmeza: toques ≥{1,2,3} × decay recencia (Osler 2000) × tamaño de mechas de rechazo × edad.
  - Usos (cada uno experimento): permiso de entrada espacio ≥ α·R, α∈{1,1.5,2} — ACOPLADO al
    armado del BE (síntesis user: espacio suficiente = espacio para armar la protección) ·
    ancla del SL inicial [→ Task 15 / cola entrada 3] · cuantización de TP (B5) · supresión
    flip ST (B7) · apriete fase 3 (B4) · bloqueo re-entrada (C9).
  - Unidades de distancia: R, ATR, múltiplos de spread — la unidad correcta es un hallazgo.
- **D3 Contexto temporal/régimen**: [→ 4.3] hora/día, asimetría L/S, spread-regime (A4).

## Familia E — Estructura y recombinación 🔒 (fase tardía, gateada)

- E1 Escalera de fichas diferenciada (hoy F1/F2/F3 son clones que cierran juntos — verificado).
- E2 S6+S7 como UNA estrategia de 6 fichas (señal idéntica, corr 0.76). [→ 7.1 lo sugerirá]
- E3 `stop_and_reverse` {on, off} como lever de grilla (decidido por A3). 🆕 no estaba en matriz.
- E4 Piramidación [→ 5.1 ⭐] — requiere la información de casi todo el plan.

## Correcciones a la matriz FINAL que este catálogo arrastra

1. Grilla de espera post-apertura en minutos → BARRAS (degeneración probada, Task 16 c402976).
2. `be_at_r`: añadir S6 y ST-wrapper; incluir off para S7.
3. Añadir filas: familia C completa, `stop_and_reverse` on/off, granularidades B2/B3.
4. TP: de "quemado" a "re-validar post-bugs con re-entrada controlada" (veredicto viejo
   permanece en el registro de negativos).
5. Task 2.1 (promover real-tick a scoring path) condicionada a A1.
6. Puerta estadística §8 incorpora D170 (neto + consistencia mensual + top-K).

## Secuencia

A1 → {A2, A3, A4, A5} en paralelo → grillas B/C/D por estrategia (screening in-sample sobre
substrato reparado) → D170 → cola de backtest largo → holdout. Familia E al final, gateada.
Rieles: presupuesto §C, registro de negativos 2.5, walk-forward purgado 12.1, holdout 12.2,
kill criteria 13.3, plateau 10.2, Monte Carlo 11.2.
