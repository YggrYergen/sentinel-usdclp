# Observaciones — fase F0-preparacion

> Backlog local. NO crea tareas (charter §A.10). Se revisa en la frontera de fase.
> Formato: `<fecha> · <quién> · <observación> · <origen>`


- **2026-08-15** · controlador · **`reconciler.py:41` fija `MAX_VOLUME = 0.10` y el sistema vivo opera 0,67 lotes.** Al cerrar B13 quedó claro que la desalineación no era «config viva desconocida» sino que el repo está desalineado respecto al vivo. La ruta `reconciler.py:254-258` rechazaría una orden de 0,67. No bloquea T0.7 (que no envía órdenes) pero es deuda real. · Origen: cierre de B13.
- **2026-08-15** · controlador · **`ticks.first_at()` (`backtest.py:130-139`) es búsqueda hacia adelante SIN COTA y lo usa también el harness vivo** (`backtest.py:353` y `:383`), no sólo la réplica. El look-ahead medido en `F0-A6-BORDE-0001` se localizó en `ciclos.py:161`, pero **nadie ha comprobado si el harness tiene el mismo defecto en sus dos llamadas**. Si lo tiene, contamina todo backtest largo ya corrido. · Origen: ADDENDUM III.
- **2026-08-15** · controlador · **La segunda población de la cola (16 casos `OPEN_SKIPPED_SL_CROSSED`) queda censada y NO explicada.** Catorce con la réplica tarde, desvíos de precio ±0,9, y el nivel de stop deseado registrado en cada rechazo. · Origen: `F0-A6-BORDE-0001` pregunta 6.
- **2026-08-15** · controlador · **Un test que busque look-ahead no existe en la suite.** El veredicto de los fills same-bar (−121 % neto) se cerró con una regla (`live_fill_mode=True`) y el mismo error de clase reapareció en un módulo escrito después. Una regla no lo previene; un test que compare el timestamp del tick usado contra el instante de decisión, sí. · Origen: ADDENDUM III §M.
- **2026-08-15** · controlador · **La prosa del TRACKER llegó a citar «137 emparejadas» donde el artefacto dice 135**, y el error lo introdujo el controlador y se propagó al estado en una línea y a un brief. Lo detectó un agente aplicando la regla «gana el artefacto». Sugiere que el estado en una línea necesita que sus cifras salgan de los JSON, no de la memoria de quien lo escribe. · Origen: `F0-A6-NETO-0001`.
