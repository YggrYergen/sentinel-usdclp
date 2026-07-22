# Desempeño de estrategias en vivo — desde el lunes 08:30 (Chile) hasta ahora

> Cuenta: **DEMO 2883015767** (Capitaria-All, moneda **CLP**). Read-only, sin
> órdenes. Generado 2026-07-21 ~09:27 hora Chile.

## Desfase horario (verificado, no asumido)
- Tick fresco XAUUSD: server-wall `2026-07-21 09:26:40`; UTC real `13:26:40`
  ⇒ **reloj del server = UTC−4**.
- Hora local de la máquina = `09:26:40` = **idéntica al server** ⇒ el server MT5
  marca **la misma hora que Chile** (el "corrimiento" es respecto a UTC: 4 horas).
- Por lo tanto **"lunes 2026-07-20 08:30 Chile" = server-wall 2026-07-20 08:30**.
- **Ventana usada:** `2026-07-20 08:30:00` → `2026-07-21 09:27:43` (hora Chile/server).
  Validado cruzando timestamps de deals reales (caen dentro).

## Qué está corriendo AHORA (procesos)
- **Único ejecutor armado activo:** `run_live_20 --configs tk-momentum --arm`
  (PID 18116, desde 09:11 hoy). Es **TK-Momentum-5-8-short** y va **plano, 0
  trades** todavía.
- **NO hay** ningún otro ejecutor armado ni supervisor corriendo ahora.
- Las bandas **720xxx (classic)** y **724xxx (go-live)** que aparecen abajo son
  de ejecutores que **corrieron antes en la ventana y ya se detuvieron**,
  dejando posiciones abiertas. Es decir: hubo actividad de esos rosters el
  lunes/hoy, pero ya no están vivos.

## ⚠️ Lo que MÁS movió la plata: operaciones MANUALES (magic 0) — NO es una estrategia
El lunes entre **14:00 y 14:26** hay 4 operaciones **sin magic**, de **1.5 lotes**
(150× el tamaño de los EAs, que usan 0.01), sin comentario → **manuales / no-EA**:

| Hora (Chile) | Lado | Vol | Resultado |
|---|---|---|---|
| 14:04:45 (cierre) | — | 1.5 | +12.602 |
| 14:17:50 (cierre) | venta | 1.5 | **−405.149** |
| 14:23:06 (cierre) | venta | 1.5 | **−707.960** |
| 14:26:22 (cierre) | venta | 1.5 | −109.348 |

**Total sin-magic en la ventana ≈ −1.186.249 CLP.** Esto **domina** cualquier
resultado de los EAs y hay que mirarlo aparte: no es ninguna de las estrategias
automáticas. (Conviene confirmar quién/qué generó estas 1.5-lote.)

## Métricas por estrategia (trades CERRADOS reales, CLP, con costos incluidos)

Los EAs operan **XAUUSD a 0.01 lote**. Todo es *plata realizada* (profit + swap +
comisión). Las variantes S*/V11 son el **roster go-live (banda 724xxx)**.

| Estrategia (magic base) | Trades (L/S) | Net CLP | WR | PF | maxDD | avg | mejor / peor |
|---|---|---|---|---|---|---|---|
| S6-K2P0 (724010) | 29 (6/23) | **−50.365** | 27.6% | 0.45 | 69.719 | −1.737 | +7.554 / −12.626 |
| S7-TPNONE (724020) | 21 (9/12) | **−38.618** | 33.3% | 0.38 | 50.495 | −1.839 | +3.978 / −9.271 |
| V11-M2 (724060) | 117 (57/60) | **−44.844** | 31.6% | 0.52 | 71.592 | −383 | +3.650 / −3.551 |
| S6-K1P5 (724030) | 9 (6/3) | −12.703 | 33.3% | 0.41 | 21.438 | −1.411 | +4.428 / −4.855 |
| S7-TP1P0 (724040) | 6 (3/3) | −14.658 | 33.3% | 0.02 | 14.909 | −2.443 | +158 / −4.929 |
| S7-TPNONE-F2 (724050) | 4 (2/2) | −10.400 | 0.0% | 0.00 | 10.400 | −2.600 | −140 / −4.929 |
| SuperTrend-p14x3-M15 (724070) | 4 (0/4) | −6.794 | 25.0% | 0.49 | 13.225 | −1.698 | +6.431 / −11.104 |
| **TOTAL EAs (cerrados)** | **190** | **≈ −178.382** | ~31% | <0.6 | — | — | — |
| TK-Momentum-5-8-short (999999999) | 0 | 0 | — | — | — | — | (corre, plano) |

**Todas las variantes go-live cerraron en rojo** en la ventana. WR ~25–33% y PF
< 0.6 en todas (pierden más de lo que ganan por trade). V11-M2 es la más activa
(M2, 117 trades) por ser timeframe corto.

## Posiciones ABIERTAS ahora (no-realizado, aparte de lo anterior)
Dejadas por ejecutores ya detenidos; el libro abierto va **en verde**:

| Estrategia | Abiertas | No-realizado CLP |
|---|---|---|
| SuperTrend-p14x3-M15 (go-live, 724071) | 1 (largo) | **+24.661** |
| V11-M2 (classic, 720201-203) | 3 (cortos) | +17.117 |
| V13-M2 (classic, 720161-163) | 3 (cortos) | +16.894 |
| V15-M2 (classic, 720031-033) | 3 (cortos) | +17.061 |

Total no-realizado ≈ **+75.733 CLP** (equity 59.690.227 > balance 59.632.239 lo
refleja). *El classic (720xxx) no cerró ningún trade en la ventana: solo abrió
estas 9 posiciones que siguen vivas.*

## Resumen honesto (moneda CLP)
- **Manual/sin-magic:** ≈ **−1,19 MM CLP** (4 trades de 1.5 lotes el lunes). El
  verdadero mover de la cuenta. No es estrategia automática.
- **EAs go-live cerrados:** ≈ **−178 K CLP** en 190 trades, todas las variantes
  negativas. WR bajo, PF < 0.6.
- **Libro abierto:** ≈ **+76 K CLP** no-realizado (SuperTrend + classic).
- **TK-Momentum:** 0 trades (recién armada, plana).
- **Caveats:** muestras chicas por variante (salvo V11-M2); todo a 0.01 lote
  (montos diminutos vs. la cuenta de ~59,6 MM CLP); resultados en la moneda de la
  cuenta (CLP); estos EAs NO son edges probados (in-sample, sub-significativos) —
  es forward-test de observación.

---

# Cómo funciona EXACTAMENTE cada estrategia (en simple)

### 1. Variantes S6/S7 — "M15 V-15 SAR" (go-live, motor `simular_variant`)
Operan **oro (XAUUSD)** en velas de **15 minutos**, a 0.01 lote, en **ambas
direcciones** (compra y venta). Cómo decide:
- **Entrada:** mira dos medias exponenciales (rápida 8, lenta 20) + un indicador
  de tendencia llamado **SAR** + osciladores de momentum. Solo entra **a favor de
  la tendencia**: si las medias están ordenadas al alza y el SAR es alcista →
  puede **comprar**; ordenadas a la baja y SAR bajista → puede **vender**. Exige
  que varias condiciones (orden de medias, pendiente, SAR, confirmación) coincidan.
- **Manejo de la posición ("escalera de 3 fichas"):** abre hasta **3 sub-posiciones
  (F1, F2, F3)**, cada una con su **stop que se va arrastrando** (trailing) a
  distinta distancia. Empieza con un stop inicial basado en volatilidad (rango).
- **Salida:** cada ficha sale cuando su trailing la alcanza. Las variantes se
  diferencian en detalles finos: **K2P0/K1P5** = distancia del "piso" del trailing
  (2.0 vs 1.5 × ATR); **TPNONE** = sin objetivo de ganancia fijo (deja correr con
  break-even a +1R); **TP1P0** = toma parcial a 1R; **F2** = solo 2 fichas.
- En resumen: **seguidora de tendencia con salida por trailing**. En la ventana
  todas perdieron (mercado choppy en M15).

### 2. V11-M2 (go-live y classic, motor `simular_variant`)
Igual lógica que las S6/S7 pero en velas de **2 minutos** (mucho más rápida → más
trades) y con **bloqueo de ciertas horas** del server (0,6,16,18,23) donde no abre
nuevas. Por ser M2 hace decenas de trades al día (117 en la ventana).

### 3. V13-M2 / V15-M2 (classic, motor `simular_variant`)
Mismas familias en **M2**, con re-entradas (V13) o SAR adaptativo a volatilidad
(V15). En la ventana solo dejaron **posiciones abiertas** (cortos), hoy en verde.

### 4. SuperTrend-p14x3-M15 (go-live, motor `supertrend_always_in`)
Oro, **15 minutos**, **siempre en mercado** con **una sola posición**: está
**largo** cuando el precio está por encima de la línea SuperTrend(14, 3.0), y
**corto** cuando está por debajo; **se da vuelta** (cierra y abre al revés) cuando
el precio cruza la línea. La línea SuperTrend es su **stop** (va subiendo/bajando
con la tendencia). Simple: "sigue la tendencia, sin quedarse nunca afuera". Cerró
4 trades en rojo pero su posición abierta actual (larga) va **+24.661**.

### 5. TK-Momentum-5-8-short (motor `tk_momentum`, la NUEVA — corre ahora)
Oro, velas de **10 minutos**, 0.01 lote, **ambas direcciones**, **una sola
posición**, magic **999999999**:
- **Permiso por medias simples:** si SMA5 < SMA8 → solo **ventas**; si SMA5 > SMA8
  → solo **compras**.
- **Entrada por momentum:** usa Momentum de 2 periodos (oscila en torno a 100).
  Vende cuando el momentum **cruza hacia abajo el 100** (estando en régimen
  bajista); compra cuando **cruza hacia arriba el 100** (régimen alcista).
- **Salida:** cuando el momentum **vuelve a cruzar el 100** en sentido contrario,
  **o** si toca un **trailing stop de 3.0 USD** (lo que pase primero).
- Recién armada hoy 09:11; **aún no toma posición** porque no ha habido un cruce
  nuevo del 100 (es "sin señal ahora", no una falla — verificado en backtest que
  dispara ~13 veces/día).

---

# Pros y contras EMPÍRICOS por estrategia (con consecuencias)

> Basado en los trades reales de la ventana (no en teoría). Todas las variantes
> go-live cerraron negativas: son sistemas de **baja tasa de acierto** (WR
> 25–33%) que dependen de **pocos ganadores grandes**; en esta ventana *choppy*
> los ganadores no aparecieron y el PF quedó < 0.6.

### Observación transversal (afecta a las 5 variantes S*)
- **Empírico:** S6-K2P0 + S7-TPNONE solos = **−89 K** de los −178 K. Las cinco S*
  son **casi-clones** (60–77% de solape de señal): abren lo mismo y **pierden
  juntas**.
- **Consecuencia:** correr las 7 (no el roster *dedup*) **re-concentra el riesgo**
  — un mismo *whipsaw* se multiplica por 5. El drawdown conjunto es mucho mayor
  que el de una sola.

### S6-K2P0 (724010) — trail ancho (2.0×ATR)
- **Fuerte:** el mayor ganador individual de las S* (**+7.554**); el trail ancho
  deja **correr** al ganador cuando hay tendencia.
- **Débil:** peor net (**−50.365**) y **peor drawdown (69.719)**; sesgo corto
  fuerte (23S/6L) justo donde los cortos sangraron; el trail ancho = **mayor
  devolución** por pérdida (peor −12.626).
- **Consecuencia:** en régimen lateral/reversivo **devuelve mucho** antes de
  parar; la concentración en cortos amplificó la pérdida.

### S7-TPNONE (724020) — sin TP, break-even a +1R
- **Fuerte:** filosofía "deja correr"; capturó algún ganador decente (+3.978).
- **Débil:** net −38.618, PF 0.38; el break-even a +1R **corta muchos trades
  justo en cero** en *chop*, mientras los perdedores llegan completos (−9.271).
- **Consecuencia:** **asimetría** — recortas ganadores a BE pero comes perdedores
  enteros.

### S7-TP1P0 (724040) — toma parcial a 1R
- **Fuerte:** el TP temprano debería subir el WR.
- **Débil:** **PF 0.02** (catastrófico), mejor trade **+158**. El TP **capa** al
  ganador en +158 mientras el perdedor corre completo (−4.929).
- **Consecuencia:** confirma **empíricamente** que el TP es el *lever* más dañino
  del proyecto: destruye la estructura de pago de un seguidor de tendencia
  (necesita colas grandes, y el TP las corta).

### S7-TPNONE-F2 (724050) — solo 2 fichas
- **Fuerte:** menos fichas = menos exposición por señal, menor riesgo bruto.
- **Débil:** **WR 0% (0/4)**, net −10.400 (muestra chica).
- **Consecuencia:** bajar fichas **no arregla** el problema; solo hay menos tiros,
  igual de rojos en esta ventana.

### S6-K1P5 (724030) — trail apretado (1.5×ATR)
- **Fuerte:** menor devolución por pérdida (peor −4.855 vs −12.626 de K2P0); DD
  más bajo (21.438).
- **Débil:** net −12.703, PF 0.41; el trail apretado **stopea prematuramente** con
  el ruido normal.
- **Consecuencia:** menos pérdidas catastróficas, pero **muerte por mil cortes**.

### V11-M2 (724060 go-live / 720xxx classic) — M2, rápida
- **Fuerte:** la más **balanceada** L/S (57/60), menor pérdida promedio (−383),
  mejor PF entre las perdedoras (0.52), y **más trades = más informativa**; el
  bloqueo horario evita algunas horas malas; su versión classic tiene 3 cortos
  **abiertos en verde** ahora.
- **Débil:** net −44.844 por **volumen** de trades (117), cada uno pagando spread.
- **Consecuencia:** en M2 el **costo (spread) domina**: 117× spread se come
  cualquier borde fino. El edge, si existe, es más delgado que el costo.

### SuperTrend-p14x3-M15 (724070) — siempre-en-mercado
- **Fuerte:** la **única con un ganador grande vivo** (+24.661 no-realizado);
  "siempre dentro" ⇒ **nunca se pierde** una tendencia real (ganador +6.431).
- **Débil:** 4 cerrados todos cortos, net −6.794, WR 25%; sin filtro de "quedarse
  afuera", **come todos los whipsaws** en lateral (peor −11.104).
- **Consecuencia:** **excelente en tendencia, malo en *chop***; su P&L es
  **binario/grumoso** (pocas grandes jugadas deciden todo). Su largo abierto es
  justamente el pago del "siempre-en-mercado" cuando por fin llega la tendencia.

### TK-Momentum-5-8-short (999999999) — la nueva, corre ahora
- **Fuerte (del backtest 0.01-lote):** simétrica L/S; el **lado largo fue
  net-positivo** (PF 1.79 bruto) — mostró un borde bruto real; reacciona rápido
  (10 min, momentum).
- **Débil:** el **lado corto fue negativo** (PF 0.88); el backtest **bruto**
  (+$74) se vuelve **negativo tras spread** (~0.6 ida-vuelta × ~13 trades/día);
  los flips de momentum generan muchos stops rápidos; **0 trades vivos aún**.
- **Consecuencia:** borde delgado concentrado en el **lado largo**; su prueba real
  es **sobrevivir a los costos** en vivo. Todavía sin evidencia en vivo.

### Classic V13-M2 / V15-M2 / V11-M2 (720xxx, 9 cortos abiertos)
- **Fuerte:** **+51 K no-realizado** — los cortos agarraron la última pata bajista
  del oro; dejarlos correr capturó el movimiento.
- **Débil:** **0 trades cerrados** (no hay con qué juzgarlas aún); lo no-realizado
  puede evaporarse.
- **⚠️ Consecuencia OPERATIVA CRÍTICA:** **ningún ejecutor está vivo gestionando
  estas 9 posiciones ni la de SuperTrend** (solo corre tk-momentum). Sus stops
  quedaron **estáticos** en el último nivel seteado; nadie está arrastrando el
  trailing. Si el oro se da vuelta, esas ganancias no se protegen solas. **Hay que
  decidir: relanzar su ejecutor, cerrarlas a mano, o dejarlas conscientes del
  riesgo.**

### Manual (magic 0) — NO es estrategia
- **Débil:** 4 trades **manuales de 1.5 lotes** (150× el tamaño de los EAs) el
  lunes → **−1,19 MM CLP**.
- **Consecuencia:** el **mayor riesgo real de la cuenta es el trading manual con
  sizing grande**, no los EAs (que mueven montos diminutos a 0.01). Conviene
  confirmar quién las hizo y si fue intencional.
