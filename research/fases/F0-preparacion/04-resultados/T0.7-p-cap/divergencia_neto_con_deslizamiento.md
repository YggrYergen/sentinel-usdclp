# divergencia_neto_con_deslizamiento -- T0.7-M-H (D-54)

Comando: `python scripts/analysis/realtick_bt/faulty/divergencia_neto.py --coste-deslizamiento`

Fecha: 2026-08-16 · git_sha: `fc3773b0055d3e628fe52a78916863aa5efe1db5` · run_id: `T0.7-M-H-DIVNETO-DESLIZ-0001`

REPORT-ONLY. Sin interpretación, sin veredicto. `T0.7-M-A` (precio de cierre contra el nivel del stop) queda diferida por D-54 y NO se corre aquí: parte del desvío medido en `fill_vs_cotizacion.py:69-77` es artefacto del método (la referencia es la cotización al PRINCIPIO del segundo, y un stop se dispara durante un movimiento en contra), no dinero perdido.

## 1 · Calibración del coste (Bloque 1)

Columna usada: `delta_vigente (fill_vs_cotizacion.csv)`. Stop: reason_name == 'SL' (cierres por stop server-side, n=119). Mercado: reason_name == 'EXPERT' (cierres a mercado del ejecutor, n=21).

| spread | n (stop) | mediana|delta| (stop) | coste = stop - mercado |
|---|---|---|---|
| 0.5 | 110 | 0.255000 | 0.225000 |
| 0.6 | 9 | 0.270000 | 0.240000 |

mediana|delta| (mercado, n=21): 0.030000

spread dominante (fallback, spread no recuperable por posición en réplica): 0.5
coste aplicado a la réplica: 0.225000

El spread por operación no se registra ni en posiciones_replica.csv ni en comparacion_p_cap.csv (columnas verificadas, ninguna contiene 'spread'); no es recuperable por posición para NINGUNA de las filas de la réplica. Se usa el modo dominante entre los propios cierres por stop de fill_vs_cotizacion.csv (0.5) para el 100% de los cierres por stop de la réplica.

### Discrepancia vs D-54

mediana|delta_vigente| en reason_name=='EXPERT' (n=21) recalculada por este código = 0.03 (redondeado), NO 0.053. La MEDIA aritmética de la misma serie SI da 0.0529 (~0.053) -- coincide con la cifra citada por D-54, que por tanto parece una media, no una mediana, pese a que el propio texto de D-54 dice 'mediana'. El Bloque 1 del brief especifica la fórmula con 'mediana', así que gana la mediana recalculada (0.03) según instrucción explícita del brief ('si no coinciden, gana tu recálculo').

| cifra | D-54 | recálculo (este código) |
|---|---|---|
| mediana stop spread 0.50 | 0.255 | 0.25500000000010914 |
| n stop spread 0.50 | 110 | 110 |
| mediana stop spread 0.60 | 0.27 | 0.2700000000004365 |
| n stop spread 0.60 | 9 | 9 |
| mediana mercado | 0.053 | 0.0299999999997453 |
| n mercado | 21 | 21 |
| coste spread 0.50 | 0.202 | 0.22500000000036385 |
| coste spread 0.60 | 0.217 | 0.24000000000069122 |

## 2 · Los tres números del Bloque 3

### (1) Divergencia global (población a, USD)

antes: 16.715984 %
después (coste sólo en stops): 3.279174 %

### (2) Sesgo por posición por estrategia (diff_abs / n, población a, USD)

antes: {'SAR::S6-K2P0': -5.131012658227628, 'SuperTrend::SuperTrend-p14x3-M15': 45.21890909091182}
después (coste sólo en stops): {'SAR::S6-K2P0': -16.580379746853737, 'SuperTrend::SuperTrend-p14x3-M15': 31.24027272725282}
cociente antes: 8.812862509392346
cociente después (stops only): 1.884171122991373

### (3) Frecuencia y peso de los cierres por stop por estrategia (población a)

| estrategia | n_total | real n_stop | real % | real USD stop | réplica n_stop | réplica % | réplica USD stop |
|---|---|---|---|---|---|---|---|
| SAR::S6-K2P0 | 79 | 58 | 73.42 | 1965.11 | 60 | 75.95 | 1335.98 |
| SuperTrend::SuperTrend-p14x3-M15 | 55 | 55 | 100.00 | -16483.34 | 51 | 92.73 | -14906.83 |

## 3 · Control -- coste uniforme a TODAS las posiciones de la réplica

coste aplicado a TODAS las posiciones de la réplica por igual (no sólo a los cierres por stop), para separar 'el coste importa' de 'el coste importa de forma asimétrica entre estrategias'.

cociente antes (sin coste): 8.812862509392346
cociente después, coste sólo en stops: 1.884171122991373
cociente después, coste uniforme (control): 1.491828674994759
diff_por_posicion, coste uniforme: {'SAR::S6-K2P0': -20.206012658252003, 'SuperTrend::SuperTrend-p14x3-M15': 30.143909090887412}
