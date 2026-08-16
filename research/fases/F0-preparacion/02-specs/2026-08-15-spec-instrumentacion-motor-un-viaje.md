# SPEC — Instrumentación del motor en un solo viaje

**Fecha:** 2026-08-15 · **Autor:** controlador (Opus) · **Rama:** `equipo1`
**Manda:** D-52 (instrumentación total de una pasada) · **Insumo:** `05-analisis/2026-08-15-catalogo-palancas-y-requisitos-motor.md` (commit `0198002`)

---

## 0 · Por qué existe este documento

El catálogo consolidó 33 palancas y dedujo de ellas los requisitos de motor, deduplicados. Este
documento los convierte en **paquetes de trabajo despachables**, con contratos, criterios de
aceptación y particiones de fichero que permiten paralelizar sin que dos agentes se pisen.

**La regla que gobierna todo:** el motor se toca **una sola vez**. Cada retorno posterior se paga
dos veces — cuota de implementación y re-corrida de todo lo ya medido. Si un paquete descubre que
necesita algo no listado aquí, **para y escala**; no lo añade por su cuenta ni lo deja para después.

**Invariante de comportamiento.** Toda la instrumentación es **aditiva y apagada por defecto**. Con
los parámetros nuevos sin especificar, el motor debe producir resultados **byte-idénticos** a los de
hoy. Ese invariante lo protege la puerta de paridad, y es la razón por la que la puerta se
re-congela ANTES de empezar estos paquetes (D-55).

---

## 1 · El riesgo que ha costado dinero tres veces, y cómo se ataca aquí

Este programa ha sufrido **look-ahead** (usar información del futuro para decidir el presente) en
tres ocasiones distintas y documentadas:

1. Fills en la misma barra — costaron −121 %, quemados en `NEGATIVOS.md`.
2. `first_at()` sin cota devolvía ticks de hasta 21 horas después del instante de decisión
   (`f3dda1a`); inflaba el conteo de posiciones entre un 2 y un 3 %.
3. `ciclos.py` comparaba el reloj reconstruido en vez del tick real contra la ventana bloqueada
   (`492556b`); movía cinco posiciones 45 minutos.

**Dos de los paquetes de este spec son fábricas naturales de look-ahead:** el feed de temporalidad
superior (WP-3) y los cómputos de régimen (WP-5). Una barra de 4 horas que se está formando NO
existe todavía para una decisión de las 15:15. Un indicador calculado sobre la serie completa y
luego indexado por fecha ve el futuro entero.

**Contrato antitrampa, obligatorio en WP-3 y WP-5 y verificado por test:**

> Toda serie derivada expone su valor en el instante `t` usando **exclusivamente** observaciones con
> marca de tiempo **estrictamente anterior o igual a `t`**, y en el caso de barras agregadas,
> exclusivamente barras **ya cerradas** en `t`. El test que lo demuestra debe construirse cortando
> la serie en `t`, recalculando sobre el prefijo, y exigiendo igualdad con el valor que el motor
> entrega en `t` sobre la serie completa. Si difieren, hay look-ahead.

Ese test es condición de HECHO. Un paquete sin él no se acepta, por muy verde que esté el resto.

---

## 2 · Paquetes de trabajo, y cómo se reparten sin colisión

El charter §C prohíbe dos agentes sobre los mismos ficheros, ni siquiera lectura de un fichero que
otro edita. La partición siguiente lo respeta.

| WP | Qué hace | Ficheros que posee | Puede correr con |
|---|---|---|---|
| WP-1 | Harness pareado + parámetros existentes expuestos | harness nuevo + bucle de posición | — (posee el núcleo) |
| WP-2 | Instrumentación de camino de posición | mismo bucle de posición | **fusionado con WP-1** |
| WP-3 | Feed de temporalidad superior H1/H4 | módulo nuevo + punto de inyección | WP-5 |
| WP-4 | Hook de tamaño de posición + estado de cuenta | módulo nuevo + punto de emisión de orden | WP-5 |
| WP-5 | Cómputos de régimen (4 series) + gate | módulo nuevo, sin tocar el núcleo | WP-3, WP-4 |

**Orden de despacho recomendado:** WP-1+2 primero y solo (posee el núcleo). Después WP-3 y WP-5 en
paralelo. Después WP-4. WP-5 puede adelantarse si hace falta, porque no toca el núcleo.

**Recon obligatorio.** Este spec fija **contratos**, no números de línea. Todo paquete arranca
produciendo una nota de reconocimiento de diez líneas que confirma dónde vive de verdad cada cosa
que va a tocar. **Donde este spec y el código difieran, gana el código** — y corregir al controlador
es lo esperado, no una molestia.

---

## WP-1+2 · Harness pareado y camino de posición

**Sirve a:** P-01 a P-08, P-24 parcial, P-26, P-27, P-30 — y es el habilitador de la Ola 1 entera.

### 1.1 Harness pareado (mod #1 del plan)

El contrato es simple de enunciar y es la pieza más valiosa de todo el spec:

> Dado un conjunto de entradas producido por una estrategia, ejecutar **K políticas de salida
> distintas sobre exactamente las mismas entradas**, y devolver K resultados alineados posición a
> posición.

Por qué importa tanto: el simulador tiene hoy un **17,6 % de divergencia** contra la realidad, con
sesgo de **signo opuesto** entre S6 y SuperTrend. Ese sesgo desplaza el nivel absoluto, pero al
comparar K políticas sobre el mismo flujo de entradas **se cancela en la resta**. Es lo único que
permite concluir algo con rigor hoy, antes de reparar el neto.

Requisitos:
- Las entradas se calculan **una sola vez** y se reutilizan para las K políticas. No re-simular la
  entrada por política: eso reintroduce varianza y multiplica el coste.
- Una política de salida es un objeto con una interfaz estable que recibe el estado de la posición
  y de la barra y devuelve «mantener» o «cerrar a este precio por esta razón».
- La salida por defecto (la actual de cada estrategia) debe ser **una política más**, y correrla
  sola tiene que reproducir el resultado de hoy exactamente. Ése es el test de no-regresión.
- Resultado alineado por identificador de entrada, para que la comparación sea pareada de verdad.

### 1.2 Parámetros que dejan de estar fijos

| Parámetro | Estado | Palancas |
|---|---|---|
| Multiplicador ATR de SuperTrend | ya existe, falta exponerlo al harness | P-05 |
| Período ATR de SuperTrend | ya existe, falta exponerlo | P-05, P-07 |
| `max_hold_bars` (stop temporal) | ya existe, deshabilitado en S6/S7 | P-02 |
| Umbral y ventana de desaceleración de AC | **hoy fijo en el código**, hay que sacarlo a parámetro | P-03 |
| Offset de SL por deslizamiento esperado | **nuevo** | P-08 |

⚠️ **P-02 arrastra un confound conocido de 64 barras** que el catálogo documenta. Léelo antes de
diseñar su grilla; no lo redescubras.

### 1.3 Instrumentación de camino (mod #11)

Registrar, por posición y a lo largo de su vida:
- **MFE y MAE** (mejor y peor excursión desde la entrada) en el tiempo, no solo su valor final.
- **Snapshot del contexto de entrada**: el estado de los indicadores en el momento de abrir. Es la
  materia prima de P-01 (stop por confianza) y P-04 (stop por recuperación).
- **Barras transcurridas** desde la entrada.
- **Spread vigente en el instante de decisión.** Hoy no se registra por operación, y es un agujero
  conocido: el spread de este bróker es **bimodal 0,50 / 0,60**, no fijo, y sin este dato no se
  puede separar coste de ejecución de calidad de señal.

Formato: columnar, una fila por posición y muestra. Debe poder unirse al historial de posiciones por
identificador sin ambigüedad.

### 1.4 Criterios de aceptación

- Correr el harness con **solo** la política por defecto reproduce los conteos actuales **exactos**.
- Correr K políticas produce K resultados con **idéntico conjunto de entradas** — verificado por
  test comparando los identificadores de entrada, no por inspección.
- Con todos los parámetros nuevos sin especificar, el resultado es byte-idéntico al de hoy.
- La instrumentación no altera ninguna decisión: correr con y sin ella da el mismo resultado.

---

## WP-3 · Feed de temporalidad superior (H1 / H4)

**Sirve a:** P-19, P-20, P-21, P-22, P-28, P-29 parcial — seis palancas, el bloque de momentum
multi-temporal completo. Hoy **ninguna** de las dos estrategias mira nada por encima de 15 minutos.

**Es el hueco más repetido del catálogo y no estaba en la lista de 12 modificaciones**: el mod #5 del
plan cubre temporalidad *inferior*, no superior.

Contrato:
- Agregar barras M15 a H1 y H4 respetando el borde de sesión del bróker. Los timestamps son **hora
  de servidor (UTC−4)** y está **prohibida toda conversión de zona**. Esta regla ya costó dinero.
- En el instante `t`, solo son visibles las barras superiores **ya cerradas**. La barra de 4 horas
  en curso **no existe** para esa decisión.
- Exponer, sobre la serie superior: EMA(20) y su pendiente, dirección de SuperTrend, y un indicador
  de momento. Lo suficiente para P-19 a P-22 y P-28.
- El coste de recalcular no puede ser lineal en el histórico por cada barra. Cachear por barra
  superior cerrada.

**Aceptación:** el test antitrampa de §1 sobre las series H1 y H4, más un test explícito de que la
barra superior en curso nunca es visible. Sin esos dos, el paquete no está hecho.

---

## WP-4 · Hook de tamaño de posición y estado de cuenta

**Sirve a:** P-13 a P-18 — seis palancas, el bloque de sizing completo. **Hoy el motor no tiene
ningún mecanismo para escalar el volumen de una orden según estadística.** Tampoco estaba en la
lista de 12.

Contrato — un multiplicador de lote calculado por posición, parametrizable por:
- **Kelly fraccional** (0,25× a 0,5×). No es una preferencia: la literatura lo condiciona a que la
  variante principal de S6 tiene calidad estadística ≈ 0 en nuestras propias mediciones, y Kelly
  completo sobre una señal débil es peligroso.
- **ATR inverso** (objetivo de volatilidad constante).
- **Tramo de drawdown corriente.**
- **Índice de ficha** (S6 opera tres «fichas» por señal).
- **Sharpe rodante** sobre las últimas 50 operaciones cerradas.
- **Descuento por correlación**: S6, S7 y SuperTrend comparten entre el **60 % y el 77 %** de sus
  señales. Tratarlas como independientes infla el riesgo real.

Estado agregado de cuenta que hay que llevar y que hoy no existe (solo hay estado por posición):
pico de equity y drawdown corriente; Sharpe rodante por estrategia; contador de pérdidas
consecutivas por día (evento discreto, distinto del anterior).

**Aceptación:** con multiplicador fijo en 1,0, resultado byte-idéntico al de hoy. El estado de
cuenta se reconstruye determinísticamente y no depende del orden de iteración.

---

## WP-5 · Cómputos de régimen

**Sirve a:** P-09, y habilita P-31. **No toca el núcleo** — es un módulo nuevo más un gate booleano.

Cuatro series, todas de fórmula cerrada y **sin dependencia estadística externa**:
ADX · Variance Ratio · Efficiency Ratio · Choppiness Index.

Nota que conviene tener presente al interpretar después: la literatura marca **ADX y Choppiness como
débiles, casi folklore**, y señala el Variance Ratio como la opción con respaldo real. Se implementan
las cuatro igual, porque el valor está en el filtro compuesto «k de m» de P-09 y en poder demostrar
con números que las populares no funcionan — un negativo bien medido es un resultado legítimo.

**Gate de régimen** como condición booleana de entrada, apagado por defecto.

**Aceptación:** test antitrampa de §1 sobre las cuatro series. Con el gate apagado, resultado
byte-idéntico al de hoy.

---

## 3 · Lo que este spec deja fuera a propósito

Estos requisitos del catálogo **no** se implementan en este viaje. No es olvido, es economía: cada
uno tiene dependencia externa o coste alto, y ninguno bloquea la Ola 1 ni la Ola 2.

| Requisito | Palanca | Por qué se difiere |
|---|---|---|
| HMM de régimen (2-4 estados) | P-10 | Dependencia externa (`hmmlearn`), esfuerzo alto |
| GARCH(1,1) en ventana rodante | P-12 | Dependencia estadística, no trivial en el motor actual |
| Exponente de Hurst con corrección de sesgo | P-11 | Riesgo real de implementarlo mal con R/S ingenuo |
| Trendline de pivotes sin intersección | P-30 | Búsqueda combinatoria, mucho más cara que una banda |
| VWAP anclado | P-31 | Sin grilla numérica de origen; exige calibración propia |
| Overlap de señal entre estrategias en tiempo de ejecución | P-15 | Hoy se mide fuera de línea; sirve así para empezar |

Quedan como **pendiente declarado con recomendación**, según permite el charter §11.

---

## 4 · Reglas que van verbatim en todo brief derivado

- **R1-bis:** los S6 / S7 / SuperTrend vivos se preservan **byte-idénticos**. Todo cambio va sobre
  copias. Quien crea que hay que tocar un original: **para y escala**.
- Rama `equipo1`. Nunca `master` ni `alvaro`. Sin force-push, sin rebase, sin amend.
- Todos los timestamps son **hora de servidor del bróker (UTC−4)**. **Prohibida toda conversión de
  zona.**
- `pandas` convierte `None` en `NaN` y los filtros `is not None` no lo ven — usar `pd.isna()`.
- El spread de Capitaria es **bimodal 0,50 / 0,60**, no fijo.
- La cadencia de 15,77 s es **medida, no elegida**: con 15,0 el total pasa de 157 a 167 posiciones.
- La verdad de terreno tiene **resolución de segundo entero** (D-46).
- **No re-congelar** `tests/research/test_baseline_parity.py`. Es del controlador (D-55).
- Pytest **siempre en primer plano**, suites dirigidas. Nunca la suite completa: hay 13 rojos
  conocidos por fuga de variables de entorno del host vivo.
- Respaldo `<nombre>.bak-<timestamp>` antes de regenerar cualquier artefacto.
- `scripts/analysis/a6_pata_a/` está **sin trackear**: `git add` sobre el directorio lo incorpora
  entero. Añadir por ruta explícita.
- Método obligatorio: TDD (rojo → mínimo → verde → commit) y verificación antes de declarar nada
  terminado. Commit de **cada** incremento verde — cuatro agentes han muerto por límite de sesión en
  este programa.
- Disciplina de salida (D-48): **un** fichero de reporte por tarea, bitácora de una línea por
  bloque, y mensaje final corto — estado, SHAs, una línea de tests, y solo las dudas que exijan
  decisión humana.
