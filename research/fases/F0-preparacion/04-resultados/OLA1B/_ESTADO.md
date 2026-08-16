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


# OLA1 -- estado de la corrida

git_sha (momento de correr): cae0475b6bc813d2dbe86c14e2a13e0c9eea5235
iniciado: 2026-08-16T13:32:57  finalizado: 2026-08-16T13:32:57
corridas ok: 4 -- P02-S6, P02-S7, P03FLOOR-S6, P34-S6
corridas fallidas: 0 -- (ninguna)
BH-FDR alpha=0.05: confirmatorio 0/39; total 0/59; 0 sin p_bootstrap.
