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


# OLA1 -- consolidado (63 brazos en 4 corridas)

BH-FDR alpha=0.05: confirmatorio 0/39 rechazados; total 0/59 rechazados; 0 brazos sin p_bootstrap (fuera del denominador de BH).

Corridas presentes: P02-S6, P02-S7, P03FLOOR-S6, P34-S6.
Corridas faltantes: (ninguna).

## P02-S6 (17 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: mhb15, mhb20, mhb48
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: default, mhb15, mhb20, mhb25, mhb30, mhb40, mhb48, mhb56, mhb64, mhb80, mhb96, mhb128

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | True | 615 | 42,937,588.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| mhb4 | False | False | 849 | -47,216,457.00 | False | 1.00 | -145,735.93 | False | -451,440.21 | 121,839.32 | 0.33 | n/a | False |
| mhb6 | False | False | 774 | -58,387,029.00 | False | 0.99 | -143,464.42 | False | -512,253.39 | 159,751.18 | 0.40 | n/a | False |
| mhb8 | False | False | 723 | -43,125,825.00 | False | 1.00 | -116,980.27 | False | -394,031.17 | 99,593.02 | 0.35 | n/a | False |
| mhb10 | False | True | 693 | -66,267,676.50 | False | 1.00 | -169,488.23 | False | -397,158.87 | 6,788.02 | 0.06 | False | False |
| mhb12 | False | False | 666 | -32,387,916.00 | False | 1.00 | -136,920.87 | False | -336,356.41 | 18,743.72 | 0.09 | n/a | False |
| mhb15 | False | True | 636 | 77,376,439.50 | True | 1.00 | 24,983.99 | True | -174,635.21 | 183,441.57 | 0.73 | False | False |
| mhb20 | False | True | 630 | 62,955,276.00 | True | 1.00 | 35,861.10 | True | -52,316.31 | 127,967.99 | 0.41 | False | False |
| mhb25 | False | False | 621 | 48,657,730.50 | True | 1.00 | -6,045.93 | False | -59,525.29 | 29,154.45 | 0.89 | n/a | False |
| mhb30 | False | True | 618 | 31,559,113.50 | True | 1.00 | -12,087.70 | False | -49,361.32 | 9,634.53 | 0.67 | False | False |
| mhb40 | False | False | 615 | 42,547,068.00 | True | 1.00 | -634.99 | False | -2,044.61 | 0.00 | 0.73 | n/a | False |
| mhb48 | False | True | 615 | 47,508,645.00 | True | 1.00 | 7,432.61 | True | 0.00 | 23,932.23 | 0.73 | False | False |
| mhb56 | False | False | 615 | 42,937,588.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb64 | False | True | 615 | 42,937,588.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| mhb80 | False | False | 615 | 42,937,588.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb96 | False | False | 615 | 42,937,588.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb128 | False | False | 615 | 42,937,588.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |

## P02-S7 (17 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: mhb20, mhb30
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: (ninguno)

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | True | 696 | -9,650,632.50 | False | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| mhb4 | False | False | 858 | -34,259,043.00 | False | 1.00 | -51,089.93 | False | -268,014.18 | 141,867.36 | 0.63 | n/a | False |
| mhb6 | False | False | 795 | -63,283,987.50 | False | 0.99 | -63,368.48 | False | -250,984.37 | 97,545.07 | 0.49 | n/a | False |
| mhb8 | False | False | 750 | -28,325,379.00 | False | 1.00 | -45,137.69 | False | -180,566.35 | 69,421.97 | 0.50 | n/a | False |
| mhb10 | False | True | 735 | -45,187,998.00 | False | 1.00 | -97,618.02 | False | -220,095.59 | 2,091.39 | 0.06 | False | False |
| mhb12 | False | False | 720 | -44,923,905.00 | False | 1.00 | -79,432.96 | False | -177,505.47 | 722.08 | 0.05 | n/a | False |
| mhb15 | False | True | 705 | -4,585,104.00 | False | 1.00 | -3,641.05 | False | -53,393.24 | 36,270.53 | 0.94 | False | False |
| mhb20 | False | True | 702 | -9,361,254.00 | False | 1.00 | 7,253.84 | True | -34,712.38 | 57,748.01 | 0.80 | False | False |
| mhb25 | False | False | 699 | -13,311,411.00 | False | 1.00 | -2,849.87 | False | -12,236.87 | 4,022.56 | 0.55 | n/a | False |
| mhb30 | False | True | 696 | -7,197,939.00 | False | 1.00 | 3,523.98 | True | 0.00 | 11,302.74 | 0.74 | False | False |
| mhb40 | False | False | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb48 | False | True | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| mhb56 | False | False | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb64 | False | True | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| mhb80 | False | False | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb96 | False | False | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |
| mhb128 | False | False | 696 | -9,650,632.50 | False | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | n/a | False |

## P03FLOOR-S6 (20 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: relief0.00-u0, relief0.00-u25, relief0.00-u50, relief0.00-u75, relief0.25-u0, relief0.25-u25, relief0.25-u50, relief0.25-u75, relief0.50-u0, relief0.50-u25, relief0.50-u50, relief0.50-u75, relief0.75-u0, relief0.75-u25, relief0.75-u50, relief0.75-u75, relief1.00-u0, relief1.00-u25, relief1.00-u50, relief1.00-u75

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| relief0.00-u0 | False | True | 891 | 35,469,937.50 | True | 1.00 | -33,151.20 | False | -351,461.14 | 243,231.05 | 0.84 | False | False |
| relief0.00-u25 | False | True | 855 | 44,817,144.00 | True | 1.00 | -36,919.71 | False | -347,158.87 | 234,059.32 | 0.81 | False | False |
| relief0.00-u50 | False | True | 834 | 36,840,973.50 | True | 1.00 | -57,248.06 | False | -353,501.48 | 207,381.61 | 0.69 | False | False |
| relief0.00-u75 | False | True | 813 | 23,641,942.50 | True | 1.00 | -72,142.17 | False | -416,384.12 | 218,430.30 | 0.67 | False | False |
| relief0.25-u0 | False | True | 846 | 21,894,433.50 | True | 1.00 | -38,495.55 | False | -344,191.97 | 224,635.74 | 0.80 | False | False |
| relief0.25-u25 | False | True | 828 | 35,026,036.50 | True | 1.00 | -41,242.02 | False | -341,618.82 | 220,544.37 | 0.79 | False | False |
| relief0.25-u50 | False | True | 813 | 34,388,280.00 | True | 1.00 | -44,988.02 | False | -327,653.75 | 204,422.45 | 0.76 | False | False |
| relief0.25-u75 | False | True | 786 | 34,348,947.00 | True | 1.00 | -24,027.79 | False | -348,382.68 | 240,991.27 | 0.91 | False | False |
| relief0.50-u0 | False | True | 780 | 34,096,092.00 | True | 1.00 | -31,949.06 | False | -302,932.04 | 195,121.56 | 0.83 | False | False |
| relief0.50-u25 | False | True | 765 | 52,975,932.00 | True | 1.00 | -42,664.78 | False | -316,406.93 | 187,356.34 | 0.76 | False | False |
| relief0.50-u50 | False | True | 756 | 45,612,232.50 | True | 1.00 | -43,709.34 | False | -301,015.20 | 176,686.78 | 0.73 | False | False |
| relief0.50-u75 | False | True | 738 | 24,462,316.50 | True | 1.00 | -68,246.87 | False | -377,201.21 | 176,315.55 | 0.65 | False | False |
| relief0.75-u0 | False | True | 678 | 20,734,110.00 | True | 1.00 | -45,784.94 | False | -304,069.98 | 143,986.82 | 0.74 | False | False |
| relief0.75-u25 | False | True | 675 | 26,965,581.00 | True | 1.00 | -28,765.86 | False | -284,500.61 | 158,442.59 | 0.86 | False | False |
| relief0.75-u50 | False | True | 675 | 8,063,265.00 | True | 1.00 | -57,572.24 | False | -312,027.05 | 129,877.67 | 0.66 | False | False |
| relief0.75-u75 | False | True | 672 | 5,175,099.00 | True | 1.00 | -58,864.43 | False | -343,314.17 | 141,795.57 | 0.69 | False | False |
| relief1.00-u0 | True | True | 624 | 40,246,087.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| relief1.00-u25 | False | True | 624 | 40,246,087.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| relief1.00-u50 | False | True | 624 | 40,246,087.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |
| relief1.00-u75 | False | True | 624 | 40,246,087.50 | True | 1.00 | 0.00 | False | 0.00 | 0.00 | 1.00 | False | False |

## P34-S6 (9 brazos)

- Brazos con `media_diff` (pareado vs. control) POSITIVO: (ninguno)
- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: default, floork1.75

| brazo | control | confirmatorio | n | net_lote1 | net_positivo | tasa_emparejamiento | media_diff | diff_positivo | ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | True | True | 624 | 40,246,087.50 | True | n/a | n/a | n/a (control) | n/a | n/a | n/a | n/a | n/a |
| floork0.00 | False | True | 1074 | -72,752,002.50 | False | 0.97 | -189,098.45 | False | -619,507.77 | 181,957.44 | 0.34 | False | False |
| floork0.25 | False | True | 1020 | -78,185,575.50 | False | 0.97 | -207,325.26 | False | -637,195.70 | 163,680.91 | 0.29 | False | False |
| floork0.50 | False | True | 999 | -90,780,564.00 | False | 0.99 | -167,792.61 | False | -569,324.72 | 170,160.58 | 0.37 | False | False |
| floork0.75 | False | True | 936 | -105,274,774.50 | False | 1.00 | -190,946.95 | False | -564,339.07 | 119,702.64 | 0.26 | False | False |
| floork1.00 | False | True | 876 | -149,268,735.00 | False | 1.00 | -242,368.90 | False | -597,671.74 | 56,228.45 | 0.11 | False | False |
| floork1.25 | False | True | 783 | -53,549,070.00 | False | 1.00 | -149,871.52 | False | -494,174.70 | 131,566.00 | 0.34 | False | False |
| floork1.50 | False | True | 708 | -15,721,962.00 | False | 1.00 | -55,424.59 | False | -365,640.37 | 181,021.81 | 0.72 | False | False |
| floork1.75 | False | True | 678 | 16,050,673.50 | True | 1.00 | -36,924.21 | False | -293,211.91 | 127,525.58 | 0.81 | False | False |
