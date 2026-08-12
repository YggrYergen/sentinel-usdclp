# DECISIONES DEL USER — vinculantes, fechadas, append-only

> Toda decisión del user que gobierna el programa. **Vinculante**: ningún agente puede
> contradecirla, reinterpretarla ni "mejorarla". Si una decisión parece incorrecta o entra en
> conflicto con otra: **STOP y escalar**, nunca resolver por cuenta propia.
> Append-only: una decisión superada se marca `SUPERSEDED por D-nn`, jamás se borra.

---

### D-01 · 2026-08-10 · Holdout — APROBADO
La partición propuesta queda **aprobada**: se sella (a) el trimestre más reciente del sustrato
combinado y (b) un año completo **no adyacente** de los ticks AVA (ej.: 2023 entero + may–jul 2026).
Intocados hasta la evaluación final única. *Ejecutar en T0.12 y dejar constancia aquí con las
fechas exactas una vez definidas contra el rango real descargado.*

### D-02 · 2026-08-10 · Método de descarga AVA + bloqueo
Indicación de la encargada regional de AVA (vía WhatsApp, 2026-08-07): en la plataforma instalada,
**clic derecho sobre el listado de instrumentos (Market Watch, panel izquierdo) → Symbols → Ticks →
seleccionar instrumento, ticks y fechas → Exportar**. El archivo es "sumamente pesado" (por eso no
lo envían).
**Evaluar** si es replicable programáticamente (`copy_ticks_range`), que sería preferible para
trocear 2–4 años y registrar lineage — verificar contra el terminal real de AVA.
🔴 **BLOQUEADO:** faltan las credenciales (el user tiene la clave, falta el login). Se retoma
cuando el user las provea. Charter §A.12 aplica (attach-only; credenciales no persistidas).

### D-03 · 2026-08-10 · Literatura informal — lista entregada
28 videos entregados. Descarga completada (T0.11a). **Ninguna transcripción leída.** El protocolo
de análisis, dictado por el user, está en
`research/fases/F0-preparacion/PROTOCOLO-REVISION-VIDEOS.md` y es de cumplimiento obligatorio.

### D-04 · 2026-08-10 · Limpieza de disco C: — solo propuesta
Se autoriza **generar una propuesta** cruzando **tamaño × antigüedad** (ficheros grandes que no se
han modificado ni visto hace mucho). 🔴 **PROHIBIDO BORRAR NADA.** El user revisa y **borra él
mismo, a mano**.

### D-05 · 2026-08-10 · El plan se detalla y cierra ANTES de ejecutar
Primero se detalla y sella el plan de investigación completo con todos sus artefactos,
infraestructura, trackers, reglas y prompts (el "sistema"). Solo después se ejecuta. Ninguna tarea
de investigación arranca antes de ese cierre.

### D-06 · 2026-08-10 · Ganadora = neto positivo
"Ganadora" significa **neto positivo en backtest**, NO "supera a S6/ST". La dependencia del top-K
es descriptor, no criterio de eliminación. Todas las netas positivas van a la conversación E0.

### D-07 · 2026-08-10 · Comparabilidad por encima de todo
Los resultados de los experimentos deben ser comparables entre sí, siempre. Por eso el
vol-targeting y cualquier ajuste de tamaño va **al final** del programa, cuando las estrategias
estén refinadas.

### D-08 · 2026-08-10 · Real-tick es el sustrato
Las barras M15 son irrelevantes para los veredictos de esta investigación. Se trabaja sobre
real-tick aunque consuma más cómputo.

### D-09 · 2026-08-10 · No teñir la investigación
Las opiniones del orquestador sobre qué áreas tienen más o menos probabilidad **pueden extender**
la profundidad de exploración, **nunca reducirla**. Ninguna hipótesis previa poda una grilla.
Aplica explícitamente a: indicadores de tienda (aunque parezcan correlacionados con lo existente),
familias de régimen (un representante por familia sería un error), y timeframes rápidos.

### D-10 · 2026-08-10 · Motor congelado antes de ejecutar
Toda modificación del motor exige re-verificar paridad/fidelidad (99,7 % / 99,85 %) empíricamente
antes de usarlo. Se prefiere hacer **todas** las extensiones necesarias ANTES del programa y luego
congelar: el riesgo de modificar durante la ejecución es demasiado grande.

### D-11 · 2026-08-10 · Challengers — congelados hasta el final
Nada sube a live-demo hasta terminar la investigación completa y analizar juntos, en detalle y con
honestidad, la grilla completa de netas positivas con sus pros y contras.

### D-12 · 2026-08-10 · Cuenta 902
No es cuenta de R&D y **no debe existir riesgo de confundirla o tocarla**. Sus credenciales no se
entregan salvo necesidad explícita y acotada, y jamás quedan registradas en el equipo local.
Para datos: `MT5_Tester_2` la tiene abierta y se autoriza **descargar su historial** (solo lectura).

### D-13 · 2026-08-10 · Familia F (estrategia del trader)
Se implementa y preserva la **spec literal** del trader para poder mostrársela y discutirla, **y**
se explora la familia completa de variantes, timeframes y configuraciones. El TP de 4500 (CLP)
entra como **una hipótesis entre decenas**, normalizada por lote.

### D-14 · 2026-08-10 · Routing 70/29/1 y paralelismo
Sonnet 5 high ≈70 % · Opus 5 high ≤29 % (orquestación + toda interpretación) · Fable 5 ≈1 %.
**Máximo 2 subagentes en paralelo.** A Sonnet nunca se le pide interpretar.

### D-15 · 2026-08-10 · Minimizar LLM donde haya automatización posible
Donde un script Python pueda ejecutar (colas de backtests paralelas/secuenciales, regeneraciones,
conteos), **se prefiere el script** sobre un subagente que "corre y mira". Protege de
alucinaciones, interpretaciones erróneas y costo. Requisito: la información queda registrada,
persistida y categorizada con trazabilidad absoluta.

### D-16 · 2026-08-10 · Commitear el Research OS ANTES de cualquier despacho
El sistema de gobierno (plan v4 + `research/**`) estaba **sin commitear**: HEAD era `41fdb25`
(2026-07-27), un commit que no contiene ni un solo fichero del programa. La "única fuente de verdad
del estado" vivía solo en disco, sin historia ni respaldo — el peor modo de fallo del sistema.
**Se commitea, scoped, a la rama `equipo1`, antes de despachar nada:** `research/**` +
`docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md`.
- **`data/literature/` NO entra al repo** (decisión del user, misma fecha): ni las 28
  transcripciones ni `urls.txt`. `.gitignore:33` (`data/*`) las cubre y **no se modifica**. El
  corpus queda como activo local; el LEDGER apunta a sus rutas.
- **Corrección del LEDGER:** las tres filas existentes declaran `git_sha: 41fdb25`, donde sus
  artefactos no existían. Se corrige **añadiendo filas nuevas** con `supersedes` + `reason`
  (protocolo 04 parte 3). **Jamás se edita una fila existente.**

### D-17 · 2026-08-10 · Lineage retroactivo ACOTADO
No se backfillea todo el histórico. Se registran en el LEDGER **únicamente** los artefactos
vigentes que otras tareas van a citar:
- `data/analysis/monday_audit/*.json`
- `data/analysis/realtick_bt/positions_*.csv`

Con `substrate_id=repaired-7m`, `engine_sha` **declarado desconocido** (no inventado) y
`generador=historico-pre-ledger`.
**Regla derivada, vinculante:** todo número que no tenga fila en el LEDGER queda como **no
verificado** y no se cita como base de ninguna decisión.

### D-18 · 2026-08-10 · T0.4 sale como el PRIMER RUNNER del programa
Resuelve la pregunta 6.3 del controlador: **runner, no script ad-hoc.** Pero **scaffold mínimo,
no framework**: lo justo para cumplir `protocolos/06-runners.md` — idempotente, reanudable,
fail-loud, escritura append-only al LEDGER, manifiesto declarativo. Vive en `scripts/research/`.
Consecuencia: **T0.9 se parte** en `T0.9-min` (scaffold, ahora) y `T0.9` (resto: supervisión
durable de watcher/ingesta, después). Es apenas más trabajo que un script y fija el patrón para
las ~50 tareas siguientes.

### D-19 · 2026-08-10 · Credenciales AVA entregadas — **B1 DESBLOQUEADO**
Cuenta **DEMO** de AVA: login `101744074`. El user autoriza su uso. Condiciones, las tres
vinculantes:
1. **`CUENTAS.md` es la fuente única** (charter §A.12): la cuenta AVA se registra ahí, marcada
   explícitamente como **DEMO de otro bróker**, con su propósito (descarga de histórico). El user
   autorizó escribir la password siguiendo la convención existente del fichero; `CUENTAS.md` está
   **gitignored** (`.gitignore:82`), así que no entra a git.
2. 🔴 **El guard va a rechazar la cuenta.** `scripts/analysis/realtick_bt/extract_ticks.py:34`
   tiene `SANCTIONED_DEMO = {2883015767, 2883016567}` con `REFUSE` explícito; `101744074` no está.
   **Extender ese guard es tocar código de seguridad:** requiere **autorización explícita del user**,
   va como cambio deliberado y documentado, con test, y **jamás de forma silenciosa** ni ampliando
   el guard "por conveniencia".
3. **Attach-only sigue vigente** (charter §A.12): AVA es otro bróker y necesita **su propio
   terminal MT5 instalado y logueado, abierto por el user**. Ningún script lanza terminales.

### D-20 · 2026-08-11 · B5 RETIRADO — no se amplía `SANCTIONED_DEMO`
*(Procedencia: instrucción explícita del user.)*
La ingesta de ticks de AVA se hace desde un CSV exportado a mano y no llama a la API de MT5, así
que ampliar la lista blanca `SANCTIONED_DEMO` en `extract_ticks.py:34` ya no responde a ninguna
necesidad. Principio general que queda fijado: *no se modifica código de seguridad por un
requisito que dejó de existir.* El bloqueo B5 se cierra como **RETIRADO**, no como resuelto.

### D-21 · 2026-08-11 · Modelo de costes para el sustrato AVA
*(Procedencia: criterio explícito del user.)*
Los backtests sobre datos de AVA usan **precios de AVA con un modelo de costes calibrado sobre
Capitaria** — spread, comisión y deslizamiento extrapolados profesionalmente desde los datos de
Capitaria. **El spread nativo de AVA no se usa para veredictos.** Evidencia que lo motiva: spread
medido en AVA de 0,34 (tick de 2022-01-02) y 0,45 (captura de 2026-08-11), frente al 0,60
documentado para Capitaria. Consecuencia de rol: **AVA es el sustrato de historia larga; Capitaria
es el sustrato de referencia para todo lo que toque economía real.**

### D-22 · 2026-08-11 · Las 12 modificaciones de motor quedan AUTORIZADAS (cierra B2)
*(Procedencia: aprobación explícita del user.)*
Condiciones del charter intactas y vinculantes: **R1-bis** — S6, S7 y SuperTrend vivas permanecen
**byte-idénticas**; todo cambio va sobre copias independientes (cfg deep-copiada, módulo nuevo,
banda de magic nueva); quien concluya que hay que tocar un original **PARA y escala**. Y **cada
modificación exige re-verificación de paridad antes de pasar a la siguiente**, nunca al final del
lote. Desbloquea T0.6 → T0.7 → T0.8.

### D-23 · 2026-08-11 · Baseline Largo (BL-0)
*(Procedencia: propuesta del orquestador en respuesta a una pregunta de planificación del user;
aceptada al autorizar éste la continuación. No es instrucción literal del user — regístralo así.)*
El desglose mes a mes de S6 y SuperTrend en la configuración viva (1 ficha de 0,67 cada una,
**una** posición a la vez) sobre el sustrato largo certificado se ejecuta **como primer entregable
de la fase LBT, con A6 como puerta de entrada**. Justificación: es el denominador contra el que se
mide toda mejora marginal, y es el insumo del cálculo de potencia que dimensiona la matriz de
experimentos — cálculo que debe ocurrir **antes** de diseñarla. Tres condiciones vinculantes:
**(a)** el holdout queda excluido (≈3,5 años efectivos de los 4,6); **(b)** la corrida se
instrumenta **una sola vez y rica**: persiste el flujo completo de entradas, el **MFE/MAE por
posición**, el spread en entrada y salida y la equity barra a barra, porque la mayor palanca
estadística del programa es probar K políticas de salida sobre **un** flujo de entradas y
reprocesar 3,5 años de ticks por variante mata el ritmo; **(c)** es **descriptivo, no selectivo** —
toda regla que surja de mirarlo pasa por pre-registro.

### D-24 · 2026-08-11 · A6 Pata B no exige bit-identidad
*(Procedencia: corrección de diseño del orquestador, comunicada y aceptada por el user.)*
Son dos brókers con dos flujos de ticks distintos: los precios difieren por construcción y la
bit-identidad entre feeds es inalcanzable. **Pata A** (motor sobre **los mismos** ticks de
Capitaria contra las posiciones reales de la 902) sí persigue señal idéntica y neto dentro de
99,7 % / 99,85 %. **Pata B mide transferibilidad**: mismas entradas dentro de una tolerancia
temporal declarada, y divergencia de neto bajo un umbral fijado **de antemano**. Ambos umbrales se
escriben y fechan antes de correr nada. Pedirle bit-identidad a Pata B dejaría la puerta cerrada
para siempre y atascaría el programa contra un imposible.

### D-25 · 2026-08-11 · Protocolo de revisión de videos frente al máximo de 2 subagentes en paralelo (cierra B7)
*(Procedencia: ruling del orquestador, comunicado al user y no objetado. Revocable por el user.)*
`PROTOCOLO-REVISION-VIDEOS.md` manda 2 orquestadores Sonnet, cada uno despachando ~10 subagentes
Haiku, uno por video; el charter fija un máximo de 2 subagentes en paralelo. No es un conflicto
real: **el máximo de 2 gobierna la concurrencia del *controlador* sobre agentes que tocan ficheros
del repo**, y los lectores Haiku son read-only, un fichero cada uno, sin escritura al repo.
Resolución: **como máximo 2 orquestadores Sonnet concurrentes en el nivel del controlador, y cada
orquestador procesa sus ~10 videos en tandas de ≤3 subagentes Haiku simultáneos.** Honra la
estructura que pidió el user y la restricción real de la plataforma, donde el anidamiento profundo
es poco fiable.

### D-26 · 2026-08-11 · El holdout se sella en DOS ACTOS
*(Procedencia: hallazgo de una sesión de ejecución, aceptado por el orquestador; corrige un error
de ordenación del propio orquestador.)*
D-01 define un holdout con dos mitades: el trimestre más reciente del sustrato combinado **y** un
año completo no adyacente de los ticks de AVA. La mitad de AVA **no tiene fechas** hasta conocer el
rango real efectivamente ingerido. Por tanto: **Acto 1** — sellar la mitad Capitaria inmediatamente
después de T0.4. **Acto 2** — sellar la mitad AVA inmediatamente después de T0.3. 🔴 **Ninguna
exploración, muestreo ni gráfico del sustrato AVA antes del Acto 2.** El sellado va antes de la
exploración, nunca después.

### D-27 · 2026-08-11 · Verificación de artefactos REPORT-ONLY
*(Procedencia: norma propuesta por el orquestador tras la entrega de T0.2.)*
La verificación de un artefacto report-only es **estructural, no numérica**: existencia en la ruta
declarada, secciones exigidas por el brief, cabecera de lineage, y ausencia de comandos
prohibidos. El verificador no está obligado a re-derivar cada cifra. **Consecuencia vinculante:
los números de un artefacto report-only NO son citables por ninguna tarea posterior salvo que
tengan fila propia en el `LEDGER.jsonl`.** Aplica retroactivamente a T0.2 y a la captura de
especificación del feed AVA.

### D-28 · 2026-08-11 · Separación entre autoridad de LECTURA y autoridad de ORDEN
*(Procedencia: decisión explícita del user, tomada sobre una escalación de un subagente que se
negó a resolverla por su cuenta.)*
**El problema encontrado:** `scripts/analysis/pull_account_deals.py`, que solo **lee** historial,
usaba `sentinel_engine.live.guard_cuenta.SANCTIONED_DEMO_LOGINS` como control de identidad. Esa
lista responde a una pregunta distinta —"¿puede este proceso **COLOCAR ÓRDENES** aquí?"— y
gobierna `assert_demo()` del ejecutor live. La cuenta 902 (`2883016902`) no está en ella, así que
el script abortaba antes de conectar.

**Lo que se descartó expresamente:** añadir la 902 a `SANCTIONED_DEMO_LOGINS`. Habría concedido
**autoridad de operación** a una cuenta que el charter §A.12 declara NO-R&D y de solo lectura.
Habría resuelto el síntoma creando un riesgo real y permanente en el sitio equivocado.

**Lo decidido:** separar las dos autorizaciones, tocando **únicamente** la vía de lectura.
- 🔴 `sentinel_engine/live/guard_cuenta.py` **NO se modifica**. `SANCTIONED_DEMO_LOGINS` y
  `REAL_LOGIN` quedan exactamente como estaban. **La autoridad de orden no se amplía ni en un
  login.**
- En `pull_account_deals.py`: se **mantiene** el bloqueo duro de `REAL_LOGIN` (pre y post
  conexión); se **retira** el requisito de pertenecer a `SANCTIONED_DEMO_LOGINS`; y en su lugar la
  vía de lectura gana tres controles que antes no tenía: `trade_mode == DEMO` como **gate real**
  (antes el valor solo se imprimía, nunca bloqueaba), coincidencia obligatoria e independiente de
  **login Y servidor** declarados por quien invoca, y un **test estructural** que demuestra que el
  módulo no contiene ninguna llamada capaz de escribir en la cuenta.
- **Balance neto: la vía de lectura queda MÁS estricta que antes; la autoridad de orden,
  idéntica.**

**Precedente que fija esta decisión, aplicable a todo el programa:** cuando un guard estorbe, la
pregunta correcta no es "¿lo amplío?" sino "¿está respondiendo a la pregunta que le corresponde?".
Ampliar una lista blanca de seguridad para desbloquear un caso de uso distinto es un debilitamiento
disfrazado de arreglo.

### D-29 · 2026-08-11 · La continuidad temporal es un chequeo OBLIGATORIO antes de declarar cualquier sustrato apto para veredictos
*(Procedencia: fallo de diseño detectado por el orquestador al revisar los resultados de T0.3.)*
La validación actual detecta `ask<bid`, precios ≤0 y timestamps no monótonos, pero **no detecta
que falten periodos enteros**. Un sustrato con un agujero de meses pasa hoy por bueno, y cualquier
backtest que lo cruce produce resultados silenciosamente incompletos. Queda establecido: **ningún
sustrato se declara apto sin un chequeo explícito de continuidad** que enumere los periodos
esperados, los compare con los presentes y **falle en voz alta** ante cualquier ausencia. Los
huecos legítimos (fines de semana, festivos, cierres de mercado) se declaran de antemano; lo no
declarado es un fallo, no una curiosidad.

### D-30 · 2026-08-12 · Se AUTORIZA interrogar al servidor de AVA con `copy_ticks_range` (solo lectura)
*(Procedencia: instrucción explícita del user, en respuesta a la recomendación del controlador.)*

**Lo que se autoriza:** obtener los ticks que faltan del sustrato AVA pidiéndoselos **al servidor**
vía la API Python de MT5 (`copy_ticks_range`) desde el terminal ya logueado en la demo de AVA,
en lugar de seguir exportando a mano desde la GUI.

**Por qué cambia la decisión anterior.** **D-20 no se revoca por capricho: se le cayó la premisa.**
D-20 retiró B5 y prohibió ampliar `SANCTIONED_DEMO` razonando que *"la ingesta AVA es CSV manual,
no API MT5"*, luego no existía la necesidad. Esa premisa **dejó de ser cierta** la noche del
2026-08-11, con evidencia registrada (fila B9 del TRACKER): la exportación manual **no honra el
rango pedido** — cuatro peticiones de rango devolvieron uno o dos días cada una, después de que
una idéntica en forma devolviera cuatro meses. Y está probado que **el dato existe en AVA**
(`julio del 1 al 17.csv` devolvió `2026-07-16`, un día que estaba dentro del hueco). El principio
que D-20 fijó —*no se modifica código de seguridad por un requisito que dejó de existir*— sigue
**intacto y vigente**; lo que ha cambiado es que ahora el requisito **sí existe**.

**Cómo se ejecuta — el precedente aplicable es D-28, no la ampliación de una lista blanca.**
La pregunta correcta ante el guard no es *"¿lo amplío?"* sino *"¿está respondiendo a la pregunta
que le corresponde?"*. **Leer ticks no es colocar órdenes.**
- 🔴 `sentinel_engine/live/guard_cuenta.py` **NO se toca**. `SANCTIONED_DEMO_LOGINS` y `REAL_LOGIN`
  quedan exactamente como están. **La autoridad de orden no se amplía ni en un login.**
- 🔴 `scripts/analysis/realtick_bt/extract_ticks.py:34` (`SANCTIONED_DEMO`) **tampoco se amplía**:
  ese script no interviene en esta vía.
- La vía de lectura debe exigir, como mínimo, lo mismo que ya exige la de la 902 (D-28):
  coincidencia obligatoria de **login Y servidor** declarados en el manifiesto, gate real de
  `trade_mode == DEMO`, y aborto duro fail-loud si algo no cuadra.
- **Antes de escribir código: verificar leyendo `scripts/research/runner/tasks_ticks.py` si su
  guard de identidad ya admite un login declarado en el manifiesto.** Puede que no haga falta
  tocar nada. No se asume: se lee.

**Condiciones vinculantes, sin excepción:** attach-only (charter §A.12) — ningún script lanza
terminales, los abre el user; **un solo terminal MT5 abierto** durante la extracción; **solo
lectura**, jamás una orden; credenciales de AVA **no persistidas** en el repo (`CUENTAS.md` está
gitignored); destino **`data/lake_ticks_ava/GOLD/`**, jamás `data/lake_ticks/`; y **R1-bis
intacto**.

**Alcance:** cerrar el hueco `2026-07-01`→`2026-07-15` y, si se puede, extender a
`2026-08-11`. **No** autoriza explorar, muestrear ni graficar el sustrato (charter §A.14).

### D-31 · 2026-08-12 · HOLDOUT SELLADO — fechas exactas de los dos actos
*(Procedencia: **acto 1** = aceptación explícita del user de la propuesta del controlador,
2026-08-12: "lo del holdout se acepta la propuesta". **Acto 2** = ejecución por el controlador de
la partición que D-01 ya aprobó, con su propio ejemplo literal, una vez que el rango real de AVA
quedó cerrado esta misma noche.)*

D-01 aprobó la partición y ordenó *"dejar constancia aquí con las fechas exactas una vez definidas
contra el rango real descargado"*. Queda constancia. **El holdout está SELLADO:**

| Acto | Sustrato | Tramo sellado | Fuente del rango |
|---|---|---|---|
| **1** | Capitaria `XAUUSD` | **`2026-05-12` → `2026-07-26`** | `data/lake_ticks/XAUUSD/` |
| **2** | AVA `GOLD` | **`2023-01-01` → `2023-12-31`** (año completo, no adyacente) | `data/lake_ticks_ava/GOLD/` |

**Por qué el acto 1 no es el trimestre calendario.** El "trimestre más reciente" de D-01 contiene
la ventana en que operó la 902 (`2026-07-27`→`2026-08-11`), que es **exactamente** la que A6 Pata A
necesita para medir el motor contra operaciones reales; el propio ejemplo de D-01 ("may–jul 2026")
la solapa cinco días. El corte en `2026-07-26` deja esos 16 días fuera del sello. Razón de fondo:
el holdout protege contra el sobreajuste de **selección de estrategias**, y A6 Pata A no selecciona
nada — solo comprueba que el motor reproduce operaciones ya ocurridas.

**Por qué 2023 en el acto 2.** Es el año que D-01 pone como ejemplo literal, es un año natural
completo, y no es adyacente al tramo del acto 1. Verificado en disco el 2026-08-12: el lago AVA
cubre `2022-01-02` → `2026-08-12` sin un solo día hábil ausente en 2023 (auditoría de continuidad
D-29, artefacto `04-resultados/T0.3-continuidad/continuidad-diaria-ava-2026-08-12.txt`).

🔴 **Consecuencias vinculantes desde este momento (charter §A.14):**
- Ambos tramos quedan **prohibidos**: no se abren, no se muestrean, no se grafican, no se
  backtestean. **UNA sola** evaluación final, con hipótesis pre-registradas y autorización
  explícita del user.
- **El Baseline Largo BL-0 (D-23) excluye el holdout**, tal como su condición (a) ya anticipaba:
  quedan ≈3,5 años efectivos de AVA de los 4,6 disponibles.
- A6 Pata A conserva su ventana íntegra (`2026-07-27`→`2026-08-11`), que es el objeto del sello.
- Leer **solo `t_msc`** para auditorías de continuidad **no** constituye exploración del sustrato
  y sigue permitido; leer `bid`/`ask` de un tramo sellado, no.

### D-32 · 2026-08-12 · Semántica de `maxDD` y `peak_margin` — qué miden y qué NO
*(Procedencia: dos preguntas explícitas del user sobre la primera tabla de números reales de
S6/S7/SuperTrend, con la orden de leerlo en el código y no deducirlo. Medido antes de propagar la
tabla al backtest largo, precisamente para no multiplicar el error sobre 3,5 años.)*
**Evidencia:** `04-resultados/T0.6-baseline/semantica_metricas.py` → `semantica-metricas.txt`.
Filas LEDGER `F0-INFRA-0028` (linaje retroactivo de la línea base) y `F0-INFRA-0029` (esta
auditoría). Leído en `backtest.py:391`, `:399-409`, `:412-435`.

**1 · `maxDD` es pico-a-valle del P&L CERRADO, y el simulador NO impone margen.**
Las dos hipótesis que el user planteaba como alternativas son **ambas ciertas a la vez**:
- `backtest.py:423-427` ordena las posiciones **por `t_exit`**, acumula `net1 * lot` y toma el
  máximo pico-a-valle. Es la curva de P&L realizado. **No hay saldo inicial, ni equity, ni
  flotante de las posiciones abiertas.**
- Grep sobre todo `scripts/analysis/realtick_bt/` de `equity`, `balance`, `margin_call`,
  `free_margin`, `liquidat`, `capital`: **cero ocurrencias funcionales**. `margin1`
  (`backtest.py:391`) se calcula y se **reporta**, pero ninguna apertura se rechaza por margen: no
  hay margin call ni liquidación.
🔴 **Consecuencia vinculante:** que S6 dé 73,8 MM de `maxDD` "sobre una cuenta de 50 MM" no es una
imposibilidad aritmética — **es que en el simulador no existe la cuenta**. `maxDD` y `peak_margin`
**NO son medidas de supervivencia** y quedan prohibidas como criterio para aprobar o descartar una
config. Son descriptores de excursión y de capital comprometido, nada más.
🔴 **Y el número subestima el riesgo, no lo exagera:** al excluir el flotante, `maxDD` es una
**cota inferior** del drawdown de equity. El drawdown real exige el camino intra-posición
(MFE/MAE) = **modificación de motor #11**, que aún no existe → **declarado NO EVALUABLE con la
instrumentación actual**. Se evalúa cuando #11 esté implementada e instrumentada en BL-0 (D-23 b).

**2 · S6 y S7 pican el mismo margen al céntimo porque abren las MISMAS posiciones.**
No es un tope, ni agregación a nivel de cuenta, ni un error de contabilidad cruzada — las tres
explicaciones que el user enumeró quedan descartadas por medición:
- `peak_margin` se calcula **por estrategia** (`metrics()` se invoca por `sid`), nunca agregando.
- Las **211 entradas de S6 están las 211 en S7**, idénticas en `(t_in_exec, entry_fill, side)`;
  S7 tiene 28 entradas más. Confirma empíricamente lo que el plan §7.A5 suponía: **misma señal,
  salidas distintas**. Ambas abren siempre **3 fichas F1/F2/F3 en el mismo instante y al mismo
  precio** (211 y 239 instantes de apertura, todos de 3 fichas).
- El pico cae en **ambas** en el mismo instante, `2026-02-26 00:15:00`, con las mismas 6 filas y
  los mismos dos precios (5180,66 × 3 y 5187,58 × 3). De ahí la igualdad al céntimo.

🔴 **3 · Hallazgo no buscado: la concurrencia de 6 es un artefacto del desempate.**
`backtest.py:404` ordena los eventos por `(t, -delta)`, luego **a igual timestamp las aperturas
cuentan antes que los cierres**. Un `stop_and_reverse` cierra 3 fichas y abre 3 **en el mismo
segundo**, así que ese instante se contabiliza como 6 simultáneas. **El pico de S6 y S7 ocurre
exclusivamente en uno de esos instantes de reverse** (23 y 12 instantes de solape
respectivamente), luego el pico entero lo produce el doble conteo.
- Margen **sostenido** (desempate contrario, cierres primero): **10.402.061,93** en ambas, con
  **máximo 3 simultáneas** — que es exactamente la escalera de 3 fichas. ST: 1 simultánea,
  3.438.629,09, **idéntico bajo los dos desempates** (no tiene reverses).
- **ROM corregido:** S6 **238,34 %** (no 127,03) · S7 **−106,44 %** (no −56,73) · ST **1.199,74 %**
  (sin cambio).
- 🔴 **La cifra "≈7,8 simultáneas" registrada en la bitácora del TRACKER el 2026-08-12 es
  incorrecta y queda anulada.** La concurrencia máxima medida es **3**, y es constante: la
  escalera nunca sostiene más de 3 fichas.
- **NO se corrige `backtest.py`** (R1-bis + motor congelado + instrucción explícita del user de no
  editarlo). Ninguno de los dos desempates es "el correcto" en abstracto: con cuenta *hedging*, un
  reverse ejecutado como dos órdenes sí retiene ambas patas un instante, así que el desempate del
  harness es la lectura **peor-caso instantánea**. Lo que queda **prohibido** es usar ese pico como
  denominador de ROM como si fuera capital sostenido — porque no lo es, y por eso el ROM del
  harness infla S6/S7 al revés de lo que parecería (los infla *hacia abajo*: divide por un margen
  que nunca se mantuvo).
- **Ambas cifras se reportan siempre juntas** de aquí en adelante: `peak_margin` (instantáneo,
  peor caso) y margen sostenido, con la concurrencia máxima real al lado. La divergencia entre
  ambas es un descriptor de la mecánica de reverse, no ruido.

### D-33 · 2026-08-12 · B11 se cierra por EXCLUSIÓN, no por reparación
*(Procedencia: instrucción explícita del user, 2026-08-12: "¿no podemos mejor simplemente dejar
fuera los huecos para poder avanzar más rápido?". Constituye **reducción de alcance autorizada por
escrito** en el sentido del charter §A.13 — el único que puede autorizarla es el user, y lo hizo.)*

**Qué se elimina del alcance de B11.** Sus puntos (1) y (3) tal como estaban escritos: clasificar
los huecos contra un calendario de festivos (festivo declarado vs corte de feed), y rellenarlos
desde Capitaria en el tramo de solape. **Ninguno de los dos se hará.**

**Qué se conserva, porque es condición de posibilidad de lo anterior.** Localizar los huecos: no se
puede excluir lo que no se ha ubicado. Es la parte barata (solo `t_msc`) y quedó hecha el mismo
día — artefacto `04-resultados/T0.3-continuidad/huecos_intradia_ava.py` →
`huecos-intradia-ava-2026-08-12.txt` + **`exclusiones-ava.json`**, que es la lista de intervalos
consumible por el backtest largo. Fila LEDGER `F0-DATA-AVA-0007`.

**Política que sustituye a la reparación.** Todo intervalo de `exclusiones-ava.json` se declara
**no evaluable** y se excluye del backtest largo. No se rellena, no se interpola, no se estima.

🔴 **Condición vinculante que hace honesta la exclusión — la tabla mensual lleva columna de
cobertura.** Excluir horas sin declararlo convertiría un mes mutilado en un mes aparentemente
normal con menos operaciones, y el desglose mensual de BL-0 es precisamente una comparación entre
meses. **Todo mes con horas excluidas reporta cuántas**, y ningún mes por debajo de un umbral de
cobertura declarado de antemano entra en comparaciones mes-a-mes sin la marca. Medido:
`2026-01` pierde **29,1 h de ventana operativa** (≈17 % del mes) y `2026-02` **14,0 h** (≈9 %); el
resto de meses afectados está en torno al 5 %. Sin esta columna, la exclusión sería exactamente el
tipo de degradación silenciosa que §A.13 prohíbe.

**Lo que la medición cambió respecto a lo que se temía.** El problema es **cuatro veces menor** de
lo que sugería el agregado, porque el sistema solo opera en la ventana `18:00→02:00` NY (T0.13):
de **344,1 h** de hueco total, solo **97,7 h caen dentro de la ventana**; las otras **246,4 h están
en la zona muerta y no afectan a ningún backtest**. Y el **holdout queda prácticamente intacto**:
sus 2 huecos (15,3 h) aportan **0,1 h** dentro de la ventana.

🔴 **Corrección de un número ya registrado.** La bitácora del 2026-08-12 registraba **53 huecos /
306,9 h**. Lo correcto es **56 / 344,1 h**. La diferencia son exactamente **3 huecos que cruzan
frontera de mes** (`2024-12-31→2025-01-01` 25,0 h · `2025-12-31→2026-01-01` 7,5 h ·
`2026-06-30→2026-07-01` 4,6 h): el barrido anterior procesaba cada parquet mensual de forma
aislada y no encadenaba el último tick de un mes con el primero del siguiente. 53 + 3 = 56 y
306,9 + 37,1 = 344,0 ≈ 344,1 — la discrepancia queda **completamente explicada**, y sirvió de
validación del instrumento nuevo. El tercero de esos huecos es el **artefacto de reloj ya declarado**
en B9 (julio arranca a las 04:00 porque `copy_ticks_range` interpreta datetimes naive en el reloj
del host), no un corte del feed.

### D-34 · 2026-08-12 · La ventana NY: apertura confirmada, cierre corregido, y se adopta el borde CONSERVADOR
*(Procedencia: escalación correcta del implementador de Paso 1 — el brief le ordenaba parar si la
validación divergía en los cruces de DST, y paró sin diagnosticar. El diagnóstico es del
controlador, por D-14: toda interpretación de resultados es Opus.)*
**Evidencia:** ticks de Capitaria, 28.237.850 ticks, `2026-01-01`→`2026-05-11`, holdout excluido.
Condición de estado estrecho copiada verbatim de `backtest.py:358`. Fila `F0-INFRA-0030`.

**1 · La apertura está confirmada: `18:00` hora de Nueva York.** Medida semana a semana en los tres
relojes candidatos, es el único que la mantiene estable: **NY toma 1 valor dominante** (18:00 en 16
de 20 semanas, 18:15 en 3 parciales), mientras **UTC toma 4** y **hora de servidor 6**. T0.13
acertaba, y acertaba en el borde que más importa.

**2 · El cierre NO está anclado a Nueva York — ahí T0.13 estaba incompleta.** La hora `02:00-02:59`
ET pasa de estar **fuera** a estar **dentro**: 9,5 % de ticks estrechos en ene→1-mar, 7,9 % en
16-mar→5-abr, y **99,9 % desde el 6-abr**. El salto coincide con el **fin del DST chileno
(2026-04-05)**, no con el estadounidense. En hora de servidor el cierre se estabiliza en `03:00`
desde mediados de marzo y **atraviesa el cambio de DST chileno sin moverse** — el perfil de un
horario fijado del lado del bróker, no del mercado. La ventana real es `18:00→02:00` ET hasta el
5-abr y `18:00→03:00` ET desde el 6-abr.

**3 · Decisión: se adopta `18:00→02:00` ET, el borde CONSERVADOR** (juicio del controlador dentro
del alcance; el user puede revocarlo). Razones: (a) es un **subconjunto estricto** del tiempo
operable — nunca hace operar en una hora de spread ancho, así que sesga el resultado **en contra**
del sistema y nunca a favor; (b) la alternativa (`03:00`) haría operar en una hora que está al
7,9 % de estado estrecho durante buena parte del año, metiendo coste real; (c) el sistema **vivo**
opera bajo el gate de spread, que en esa hora sencillamente no se abre — así que este borde es el
que reproduce la conducta viva.
**Consecuencia declarada:** desde el 6-abr el filtro descarta ≈1 h/día de tiempo genuinamente
operable. **No es una pérdida silenciosa: queda escrita aquí**, y la hora en disputa entra como
variante de grilla en **D3** (contexto temporal), donde se mide en vez de suponerse.

**4 · El código de Paso 1 es correcto y no se toca por esto.** Implementa el spec que se le dio; lo
que estaba incompleto era el spec. `ny_window.py` queda como está, con el borde conservador.

🔴 **PUNTO 3 SUPERSEDED por D-36 (2026-08-12, mismo día):** el user revocó el borde conservador. Los
puntos 1, 2 y 4 de esta decisión siguen vigentes.

### D-35 · 2026-08-12 · Umbrales de A6 Pata B, matriz de indicadores (B3) y puerta estadística (B4)
*(Procedencia: decisiones explícitas del user, 2026-08-12, sobre las opciones que le planteó el
controlador. Cierran B3 y B4, que estaban abiertos desde el 2026-08-10.)*

**1 · A6 Pata B — umbrales MEDIOS, fijados y fechados ANTES de correr** (lo exige D-24):

| Criterio | Umbral |
|---|---|
| Emparejado de entradas | **≥90 %** dentro de **±1 barra M15** |
| Divergencia de neto | **≤25 %** |
| Meses del mismo signo | **≥70 %** |

🔴 **Condición añadida por el user:** el gate es pasa/no-pasa, pero **la divergencia real se
reporta como número exacto** y se revisa con él en ese momento. No basta con "pasó": hay que poder
ver cuánta divergencia hubo. El informe de A6 Pata B lleva la cifra medida, no solo el veredicto.

**2 · B3 CERRADO — matriz de indicadores COMPLETA** (plan §5.2, la lista entera):
RSI · momentum(n) para varios n y TF · ATR multi-TF + percentil + pendiente · distancia a S/R y
zonas por múltiples métodos y horizontes (intradía, día anterior, 2-3 días, semana) · estados y
steps SAR · pendientes de EMAs · CHOP + pendiente · ADX · posición del precio en el rango de k días
· tick-volume · hora/día/sesión · spread vigente · proximidad a hora muerta · ventana de noticias.
*Razón registrada:* se instrumenta **una sola vez** (motor mod #11); añadir un indicador después
obliga a re-correr 3,5 años de ticks. Coste marginal ahora ≈ nulo, después enorme. Es lo que D-23
llama "instrumentar una vez y rico". **Desbloquea el motor mod #11 → A0.**

**3 · B4 CERRADO — puerta estadística, umbrales MEDIOS:**

| Criterio | Umbral |
|---|---|
| Consistencia mensual | **≥55 %** de meses positivos |
| Intervalo de confianza | **bootstrap por bloques a nivel de episodio, 95 %, que excluya 0** |
| PBO | **< 0,5** |

*Razón registrada:* exigir 65 % de meses positivos eliminaría estrategias sanas — con
trend-following la asimetría es el diseño, no un defecto, y penalizarla es el mismo error que
amputar el top-K, que el charter §A.2 ya prohíbe. Gates y descriptores no se mezclan: "ganadora =
neto positivo" (D-06) sigue siendo el criterio; esto es solo el control anti-suerte.

**4 · Higiene de ficheros — borrado autorizado.** Los tres artefactos del `2026-08-02` en
`data/analysis/2883016902/` (`open_positions.csv`, `analysis.json`, `equity_path.json`) se borran:
son de otra extracción y convivían con los de T0.5 del 11-ago, con riesgo de que un agente futuro
los leyera como si fueran T0.5. `bar_fill.py` / `test_bar_fill.py` se renombran a `.OBSOLETO`
(nunca estuvieron en git; su premisa murió al cerrarse B9, y su compañero `fidelity_compare.py`
no existe).

### D-36 · 2026-08-12 · La ventana operativa se modela POR PERIODOS medidos, no con un borde fijo
*(Procedencia: instrucción explícita del user, 2026-08-12, revocando el punto 3 de D-34:
"queremos lo que sea correcto según periodos y cambios de horario para Chile respecto al mercado".)*

**Se revoca el borde conservador fijo `18:00→02:00` ET.** En su lugar, la ventana se modela como
**calendario de periodos medido sobre el gate de Capitaria**, que es donde el estado es observable,
y se transfiere a AVA por reloj.

**Lo medido (D-34, sobre 28.237.850 ticks):**
- **Apertura: `18:00` hora de Nueva York, estable en todo el periodo.** Es el borde bien anclado.
- **Cierre: cambia una vez.** `02:00` ET hasta el `2026-04-05`; `03:00` ET desde el `2026-04-06`.
  El salto coincide con el **fin del DST chileno**. En hora de servidor el cierre también cambia una
  sola vez, de `04:00` a `03:00`, y ahí el salto coincide con el **DST estadounidense**.
  🔴 **Ninguno de los dos relojes deja el cierre constante**: cada uno lo explica con un salto
  distinto. Por eso la regla correcta es un **calendario fechado**, no un offset fijo — que es
  exactamente lo que pidió el user.

🔴 **Limitación que se declara por adelantado, no se descubre después.** Capitaria solo cubre desde
`2026-01`, así que el calendario **se mide** en 2026 y **se extrapola** a los años 2022-2025 del
sustrato de AVA, donde no hay gate observable con el que verificarlo. Esa extrapolación es una
**hipótesis declarada**, no un hecho medido, y así debe figurar en todo artefacto del backtest
largo. La apertura (18:00 ET) es la parte sólida: coincide con la apertura de Globex para el oro,
que es un ancla de mercado y no del bróker. **El cierre extrapolado es la parte frágil.**
