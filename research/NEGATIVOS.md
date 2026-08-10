# REGISTRO DE NEGATIVOS — lo que NO funcionó, con evidencia

> Un negativo bien documentado vale tanto como un positivo: evita volver a gastar presupuesto en
> lo mismo, y es lo que hace honesta la corrección estadística (el haircut de DSR cuenta **todo**
> lo intentado, no solo lo que sobrevivió).
>
> **Append-only.** Un negativo puede re-abrirse, pero **solo con causa escrita** — típicamente
> porque cambió el instrumento de medición, el sustrato, o porque el diseño original no controlaba
> una variable relevante. Al re-abrir, la entrada original **permanece**.

Formato: `<fecha> · <experimento> · <qué se probó> · <resultado> · <evidencia: ruta> · <estado>`

---

## Negativos vigentes

| Fecha | Qué se probó | Resultado | Evidencia | Estado |
|---|---|---|---|---|
| 2026-07 | **Régimen por ATR14-percentil** como gate, en la forma probada | Sharpe gateado por debajo del no-gateado | `2026-07-22-prior-experiments-audit.md` | 🔓 **Re-abierto acotado**: solo esa forma funcional quedó quemada. Nueva grilla (períodos, múltiplos, ventanas, pendiente, cruces multi-TF) con causa registrada — plan D3 |
| 2026-07 | **Take-profit fijo a-priori** (`tp_min`), todos los valores | Activamente perjudicial | `2026-07-22-prior-experiments-audit.md` §Wave-6 | 🔓 **Re-abierto (B5)**: el veredicto precede a los fixes de reloj/`reverse`/fills y nunca controló re-entradas. Además, un trailing en positivo es un TP a-posteriori: esa familia nunca estuvo quemada |
| 2026-07 | **TK-BW** tal como está | 0 posiciones: c1 (pullback<EMA8) y c4 (breakout) son geométricamente incompatibles; forzada a operar, pierde | memoria `tk-bw-structural-contradiction` | 🔒 Gated por **rediseño de entrada con múltiples alternativas**; gate de éxito = neto positivo, no "toma posiciones" |
| 2026-07 | **Fills same-bar** (look-ahead) en backtest | Colapso ~−121 % neto | `2026-07-22-prior-experiments-audit.md`; `emasar_ref.py:489-503` | 🔒 **Resuelto, no re-abrible**: `live_fill_mode=True` obligatorio |

## Eliminados por directiva (no son negativos experimentales)

| Ítem | Motivo |
|---|---|
| Cross-instrumento | Directiva del user: solo oro |
| Spread como variable de barrido | Se opera solo con spread ≤0,5; A4 mide **dentro** de esa condición |

## Resultados degradados a "direccionales" (NO concluyentes)

| Ítem | Motivo |
|---|---|
| Todo resultado de **TOKATA** (steps de SAR, ladder F1/F2/F3, PF 2,82 / 4,56, etc.) | El motor de esa época se determinó faulty (Model=1 open-prices-only + look-ahead same-bar + SL inválido bajo el mínimo del bróker). Sirven como **dirección y recomendación**, jamás como evidencia. Todo se re-corre bajo el motor honesto |
| Cifras en prosa de `b1-wait-curve.md`, `b1-robustness.md`, `long-backtest-queue.md` | Prosa anterior a la regeneración de sus JSON. **Leer siempre el JSON**, nunca la prosa |
