🔴 PRE-INTERPRETACION -- DATOS SIN LEER
Este fichero contiene resultados crudos de la Ola 1. NO contiene interpretacion, ni lectura,
ni veredicto, ni recomendacion (charter SS A.4).
Ninguna interpretacion de estos datos es valida hasta haber sido discutida en profundidad con
el humano y aprobada por el (directiva del user, 2026-08-16). Lo que el controlador escriba
antes de esa conversacion es PROPUESTA DE LECTURA y vive en un fichero aparte.
Estado del resultado: piloto-instrumento (D-57) -- el congelado del motor no esta firmado.

UNIDAD de `net_lote1`: CLP (peso chileno) por 1.0 lote, NO USD -- confirmado leyendo
`scripts/analysis/realtick_bt/backtest.py:520` (`net1 = diff * CONTRACT * USDCLP`) y su
docstring de cabecera (linea 12: "Net in CLP (USDCLP=936.50)"). Las magnitudes de decenas de
millones que se ven en `net_lote1` son CLP, no USD (dividir por ~936.5 para una lectura
aproximada en USD).

🟡 UN NETO ABSOLUTO NO ES UNA CIFRA DE FIAR POR SI SOLA. El simulador diverge 3.28% del
neto real (D-54/T0.7-M-H, tras modelar el deslizamiento de los stops) y el sesgo tiene SIGNO
OPUESTO por estrategia (penaliza a S6, favorece a SuperTrend -- N-xx 2026-08-15 en NEGATIVOS.md).
Lo que sobrevive a esa divergencia es la DIFERENCIA PAREADA contra el control (misma entrada,
mismo simulador, el sesgo se cancela en la resta) -- NUNCA el nivel absoluto. Las columnas
`net_positivo`/`diff_positivo` de abajo marcan un HECHO (el signo del numero), no un veredicto:
priorizar SIEMPRE `diff_positivo` (columna `media_diff`) sobre `net_positivo` al leer esta tabla.


# OLA1 -- consolidado (62 brazos en 12 corridas)

BH-FDR alpha=0.05 (agregado de 2 lote(s), NUNCA mezclados entre si -- ver desglose por lote abajo): confirmatorio 0/50 rechazados; total 0/50 rechazados; 0 brazos sin p_bootstrap (fuera del denominador de BH).

- lote `runner:tasks_ola1.ola1_paired`: confirmatorio 0/31 rechazados; total 0/31 rechazados.
- lote `runner:tasks_sizing.ola1_sizing`: confirmatorio 0/19 rechazados; total 0/19 rechazados.

Corridas presentes: P09-S6, P19-S6, P19-S7, P20-ST, P21-S6, P28-S6, P28-S7, SIZING-P13, SIZING-P15, SIZING-P16, SIZING-P17, SIZING-P18.
Corridas faltantes: (ninguna).

## P09-S6 (13 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: k2-baseline, k2-adx25, k2-chop38, k2-er050, k2-vr095, k2-vr105, k3-baseline, k3-adx25, k3-chop38, k3-er050, k3-vr095, k3-vr105, control

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| k2-baseline | False | True | 420 | 67,981,471.50 | True | 0.67 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k2-adx25 | False | True | 330 | 136,718,698.50 | True | 0.53 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k2-chop38 | False | True | 168 | 40,928,796.00 | True | 0.27 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k2-er050 | False | True | 411 | 75,092,316.00 | True | 0.66 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k2-vr095 | False | True | 426 | 80,317,986.00 | True | 0.68 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k2-vr105 | False | True | 417 | 58,221,268.50 | True | 0.67 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k3-baseline | False | True | 144 | 37,827,108.00 | True | 0.23 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k3-adx25 | False | True | 87 | 33,360,003.00 | True | 0.14 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k3-chop38 | False | True | 42 | 25,653,544.50 | True | 0.07 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k3-er050 | False | True | 114 | 40,439,943.00 | True | 0.18 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k3-vr095 | False | True | 180 | 9,577,585.50 | True | 0.29 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| k3-vr105 | False | True | 129 | 49,708,483.50 | True | 0.21 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| control | True | False | 624 | 40,246,087.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |

## P19-S6 (5 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: default, p10, p15, p20

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | False | 624 | 40,246,087.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| p10 | False | True | 324 | 40,858,558.50 | True | 0.49 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p15 | False | True | 312 | 9,552,300.00 | True | 0.47 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p20 | False | True | 306 | 13,631,694.00 | True | 0.47 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p30 | False | True | 309 | -28,583,853.00 | False | 0.48 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## P19-S7 (5 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: (ninguno)

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | False | 708 | -13,929,501.00 | False | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| p10 | False | True | 369 | -45,881,944.50 | False | 0.50 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p15 | False | True | 363 | -48,742,015.50 | False | 0.49 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p20 | False | True | 348 | -33,846,046.50 | False | 0.48 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p30 | False | True | 351 | -40,265,754.00 | False | 0.49 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## P20-ST (2 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: default, h4st

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | False | 153 | 61,425,035.00 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| h4st | False | True | 153 | 61,425,035.00 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## P21-S6 (3 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: default

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | False | 624 | 40,246,087.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| emaslope | False | True | 378 | -52,984,360.50 | False | 0.56 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| momentum | False | True | 432 | -17,775,706.50 | False | 0.50 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## P28-S6 (5 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: default

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | False | 624 | 40,246,087.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| p10 | False | True | 417 | -30,620,740.50 | False | 0.57 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p15 | False | True | 393 | -39,150,382.50 | False | 0.57 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p20 | False | True | 378 | -52,984,360.50 | False | 0.56 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p30 | False | True | 351 | -18,059,466.00 | False | 0.50 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## P28-S7 (5 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: (ninguno)

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | False | 708 | -13,929,501.00 | False | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| p10 | False | True | 462 | -50,770,474.50 | False | 0.60 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p15 | False | True | 438 | -45,055,951.50 | False | 0.58 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p20 | False | True | 426 | -58,979,833.50 | False | 0.58 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| p30 | False | True | 399 | -30,440,932.50 | False | 0.53 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## SIZING-P13 (4 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: alpha0.25, alpha0.50, alpha1.00, neutral

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alpha0.25 | False | True | 1485 | 2,050,334.34 | True | 1.00 | -57,704.57 | False | -383,306.22 | 229,832.35 | 0.71 | False | False |
| alpha0.50 | False | True | 1485 | 4,100,668.68 | True | 1.00 | -56,323.87 | False | -375,298.38 | 225,462.16 | 0.71 | False | False |
| alpha1.00 | False | True | 1485 | 8,201,337.37 | True | 1.00 | -53,562.48 | False | -359,110.09 | 217,833.13 | 0.71 | False | False |
| neutral | True | False | 1485 | 87,741,621.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |

## SIZING-P15 (4 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: disc0.70, disc0.77, disc0.85, neutral

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| disc0.70 | False | True | 1485 | 27,772,582.33 | True | 1.00 | -40,383.19 | False | -167,812.06 | 74,597.34 | 0.51 | False | False |
| disc0.77 | False | True | 1485 | 25,094,903.65 | True | 1.00 | -42,186.34 | False | -175,558.09 | 78,415.10 | 0.51 | False | False |
| disc0.85 | False | True | 1485 | 22,338,868.84 | True | 1.00 | -44,042.26 | False | -183,608.72 | 81,838.24 | 0.51 | False | False |
| neutral | True | False | 1485 | 87,741,621.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |

## SIZING-P16 (3 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: continuous, ladder
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: continuous, ladder, neutral

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| continuous | False | True | 1485 | 110,239,649.27 | True | 1.00 | 15,150.19 | True | -201,753.82 | 209,221.35 | 0.88 | False | False |
| ladder | False | True | 1485 | 101,382,680.50 | True | 1.00 | 9,185.90 | True | -206,565.59 | 202,577.25 | 0.93 | False | False |
| neutral | True | False | 1485 | 87,741,621.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |

## SIZING-P17 (3 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: asym-front
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: asym-back, asym-front, neutral

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| asym-back | False | True | 1485 | 81,599,118.00 | True | 1.00 | -4,136.37 | False | -12,404.58 | 2,443.88 | 0.25 | False | False |
| asym-front | False | True | 1485 | 100,026,628.50 | True | 1.00 | 8,272.73 | True | -4,887.77 | 24,809.15 | 0.25 | False | False |
| neutral | True | False | 1485 | 87,741,621.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |

## SIZING-P18 (10 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: sh0.3-r20, sh0.3-r30, sh0.3-r50, sh0.5-r20, sh0.5-r30, sh0.5-r50, sh0.7-r20, sh0.7-r30, sh0.7-r50, neutral

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sh0.3-r20 | False | True | 1485 | 5,755,167.10 | True | 1.00 | -55,209.73 | False | -316,266.23 | 171,402.25 | 0.66 | False | False |
| sh0.3-r30 | False | True | 1485 | 16,003,473.90 | True | 1.00 | -48,308.52 | False | -276,732.95 | 149,976.97 | 0.66 | False | False |
| sh0.3-r50 | False | True | 1485 | 36,500,087.50 | True | 1.00 | -34,506.08 | False | -197,666.39 | 107,126.41 | 0.66 | False | False |
| sh0.5-r20 | False | True | 1485 | 26,214,320.70 | True | 1.00 | -41,432.53 | False | -306,340.96 | 192,349.95 | 0.74 | False | False |
| sh0.5-r30 | False | True | 1485 | 33,905,233.30 | True | 1.00 | -36,253.46 | False | -268,048.34 | 168,306.20 | 0.74 | False | False |
| sh0.5-r50 | False | True | 1485 | 49,287,058.50 | True | 1.00 | -25,895.33 | False | -191,463.10 | 120,218.72 | 0.74 | False | False |
| sh0.7-r20 | False | True | 1485 | 25,524,307.50 | True | 1.00 | -41,897.18 | False | -307,784.38 | 192,540.81 | 0.74 | False | False |
| sh0.7-r30 | False | True | 1485 | 33,301,471.75 | True | 1.00 | -36,660.03 | False | -269,311.33 | 168,473.21 | 0.74 | False | False |
| sh0.7-r50 | False | True | 1485 | 48,855,800.25 | True | 1.00 | -26,185.74 | False | -192,365.24 | 120,338.01 | 0.74 | False | False |
| neutral | True | False | 1485 | 87,741,621.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
