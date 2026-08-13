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

### D-37 · 2026-08-12 · El calendario se agrupa por la tupla (DST Chile, DST Nueva York)
*(Procedencia: **ruling del controlador**, no instrucción del user — comunicado a él y
**revocable por él**, mismo estatus que D-25. Cierra el pendiente que D-36 dejó abierto.)*

**El problema.** Agrupar periodos por igualdad exacta del `cierre_ny` medido en crudo produce
**11 periodos en 7 meses**. Eso no es un horario de bróker: es ruido de medición, por dos vías.
- **Jitter de ±15 min** por cruzar el 50 % a resolución de 15 minutos: semanas sueltas miden
  `02:15`/`03:15` donde el valor estructural es `02:00`/`03:00`.
- **Una semana con medición contaminada:** `2026-03-08`, la del DST estadounidense, mide `03:00`
  aislada entre semanas que miden `02:00` a ambos lados. En D-34 esa misma semana salía al
  **63,5 %** de tasa estrecha, por debajo de cualquier umbral limpio.

Aplicar esos 11 periodos habría **codificado ruido como señal**.

**La regla.** La clave de agrupamiento es la tupla **`(es_verano_chile, es_verano_ny)`**, derivada
en ambos componentes del `utcoffset()` de `zoneinfo` — **nunca de una fecha de transición
hardcodeada**, para que la lógica siga siendo correcta si el script se re-corre en otro año.
- El **DST de Chile** gobierna `cierre_ny`, que es el campo que consume el backtest.
- El **DST de Nueva York** gobierna la **proyección** de la ventana sobre UTC y hora de servidor.
  🔴 Omitirlo fue un error real, detectado por el controlador al verificar el JSON crudo: con clave
  solo-Chile, el primer periodo publicaba `UTC 07:00` para 14 semanas de las cuales **5
  contradecían ese valor** (`06:00` desde el DST estadounidense). Degradación silenciosa, §A.13.
- Dentro de cada periodo, los bordes se resuelven por **moda**, con desempate a la **hora en
  punto** frente al jitter de 15 min. Las semanas discrepantes no se descartan: se **declaran** en
  `n_semanas_bordes_discrepantes`.
- **`bordes_por_semana` se conserva SIN canonicalizar**, como registro crudo para auditoría.

**Resultado: 4 periodos**, con `cierre_ny` = `02:00` · `02:00` · `03:00` · `03:15`. Siguen siendo
**dos valores estructurales** del cierre NY, que es la señal que D-36 pedía. Los dos cortes de más
no son cambios de ventana: uno es el cambio de proyección de reloj del `2026-03-08`, y el otro es
**el hueco del holdout sellado** (`2026-05-12`→`2026-07-26`), que fragmenta por diseño — no se
afirma continuidad sobre territorio no medido.

🟠 **Residuo declarado, no resuelto.** El periodo 4 publica `03:15` (moda de 2 semanas sobre 3) y el
periodo 3 resuelve un **empate exacto 3-3** entre `03:00` y `03:15`. Desde el `2026-04-26` la
mayoría de semanas mide `03:15`: puede ser un **corrimiento real del cierre**, no jitter. Es
**inmaterial para el backtest** —`ventana_calendario._hora()` consume hora entera y ambos dan `3`—
pero queda anotado por si **A6 Pata B** lo hace visible.

### D-38 · 2026-08-12 · Los ticks que el overlay estrecharía son NO EVALUABLES
*(Procedencia: **instrucción explícita del user**, 2026-08-12, resolviendo una ambigüedad de D-21
que un subagente había intentado reinterpretar por su cuenta: "correcta interpretación D-21 como
no evaluables".)*

**El problema.** D-21 manda sustituir la anchura nativa de AVA por la calibrada sobre Capitaria, y
afirma que el overlay **siempre ensancha** — premisa apoyada en que el spread de AVA (0,34-0,45)
es más angosto que el de Capitaria (0,50-0,60). **Esa premisa es falsa parte del tiempo.** Existen
ticks de AVA cuyo spread nativo ya supera al calibrado; sustituir ahí la anchura **estrecharía**,
que es exactamente el fallo que D-21 existe para impedir.

**La regla.** Esos ticks **no se estrechan y no se conservan crudos: se declaran NO EVALUABLES y
se retiran** del store que ve el simulador. El fill usa el siguiente tick evaluable. Comparación
`nativo > calibrado` **estricta**: la igualdad no estrecha, luego es evaluable. Se cuentan por mes
y se declaran en el artefacto (`ticks_no_evaluables_d38`) — excluir sin declarar viola §A.13.

🔴 **La magnitud desmiente la estimación que motivó la duda, y es la cifra más importante de este
paso.** Un subagente había medido "~0,016 %" **sobre un solo mes de 2022** y generalizado. Medido
sobre el sustrato entero: **16.549.795 ticks retirados**, y **concentrados en el tiempo de forma
extrema**:

| Año | Ticks retirados |
|---|---:|
| 2022 | 14.059 |
| 2024 | 125.105 |
| 2025 | 5.941.924 |
| 2026 | 10.468.707 |

No son outliers dispersos: es un **cambio de régimen en el feed de AVA a partir de 2025**. En
`2026-02` se retiran 2,70 M de ticks; en `2022-10`, 73. La premisa de D-21 se sostiene en
2022-2024 y **se rompe en 2025-2026** — justo el tramo donde vive el solape con Capitaria que
A6 Pata B necesita.

🔴 **Consecuencia medida, no estimada.** Con la regla anterior (estrechar) frente a la regla del
user (retirar), el mismo backtest da:

| Estrategia | Estrechando (rechazado) | No evaluables (D-38) | Δ |
|---|---:|---:|---:|
| S6-K2P0 | 117.399.340 | **84.913.485** | −28 % |
| SuperTrend | 168.624.139 | **19.380.203** | **−88 %** |

La sensibilidad de SuperTrend a esta única decisión es tal que **ninguna cifra suya es citable sin
declarar qué regla se aplicó**. La razón está localizada: sus dos meses grandes eran `2026-01` y
`2026-02`, que son también los dos meses con más ticks retirados.

🟠 **Tercera vía no elegida, anotada para poder revocar con criterio.** Existe una lectura
intermedia —aplicar `max(nativo, calibrado)`, es decir ensanchar siempre y no retirar nunca— que
también respeta "el overlay nunca estrecha" y además **cobra** el coste real en vez de saltárselo.
Retirar el tick no paga el spread ancho: lo omite. El user eligió "no evaluables"; queda escrito
que la alternativa existe y que el cambio es de una línea más una corrida de 3,5 minutos.

#### D-38 · ADENDA de corrección · 2026-08-12 · «AVA se encareció» era una lectura ERRÓNEA
*(Motivo: objeción del user — "los de AVA promocionan spread más bajo que Capitaria y son de los
más grandes del mundo, no van a mentir en algo con consecuencias legales". Tenía razón; la
comprobé y me obliga a corregir el cuerpo de D-38 arriba.)*

**Medido en ventana, meses fuera del holdout, los dos feeds a la vez:**

| Mes | Feed | p10 | p50 | p75 | p90 | p99 | media |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-04 | AVA | 0,450 | **0,450** | 0,490 | 0,590 | 1,260 | **0,5066** |
| 2026-04 | Capitaria | 0,500 | **0,500** | 0,500 | 0,500 | 0,600 | **0,5071** |
| 2026-08 | AVA | 0,320 | **0,450** | 0,560 | 0,730 | 1,190 | **0,5049** |
| 2026-08 | Capitaria | 0,500 | **0,500** | 0,500 | 0,500 | 0,600 | **0,5018** |

🟢 **AVA no es más caro: en media son prácticamente idénticos** (0,5066 vs 0,5071 · 0,5049 vs
0,5018), y **en mediana AVA es MEJOR** (0,45 vs 0,50), con un p10 muy superior (0,32 vs 0,50). **La
promesa comercial de AVA se sostiene en el dato.** Lo que difiere es la **forma**, no el nivel.

🔴 **Y ahí está el hallazgo real, que es más incómodo que el anterior.** Capitaria es
**degenerada**: `p10 = p50 = p75 = p90 = 0,500` y `p99 = 0,600`. Eso no es el spread de un
mercado, es una **función escalón fijada por el bróker** — coherente con la bimodalidad 0,50/0,60
ya medida. AVA sí tiene una distribución real. Y en 2022/2024 el feed de AVA también era
degenerado (`p50 = p75 = p90 = 0,34` y `0,27`): **lo que cambió en 2025 no es el precio de AVA,
es la granularidad con que su feed reporta el spread.**

🔴 **Consecuencia sobre D-21 que hay que asumir.** La premisa de D-21 —AVA sistemáticamente más
angosto, luego el overlay siempre ensancha— **no se sostiene en 2026**: son equivalentes en media.
El overlay no está «encareciendo AVA hasta el coste real»: está **sustituyendo una distribución de
costes realista por el escalón plano de Capitaria**, y con D-38 además **retira justo la cola** —
es decir, los momentos en que operar de verdad costaba caro. **Eso hace el backtest OPTIMISTA, no
conservador.** Refuerza la tercera vía anotada al final de D-38 (`max(nativo, calibrado)`), que
cobra la cola en vez de omitirla. Queda para decisión del user; no se aplica nada por iniciativa
propia.

### D-39 · 2026-08-12 · El fallo de paridad de ENTRADAS es consecuencia del de SALIDAS
*(Procedencia: hallazgo de la sesión de ejecución del 2026-08-12, verificado de forma independiente
en el repo de máquina 1 y corroborado después por la entrega de máquina 2. No es instrucción del
user. **Se registra con retraso**: las sesiones anteriores lo citaban como «D-39» pero nunca llegó
a escribirse en este ledger — el ledger terminaba en D-38.)*

El ejecutor **abre a precio de mercado pero hereda el SL ya trailleado del sim**.
`reconciler.py:296-299` emite la acción `OPEN` con `sl=d["sl"]` (el SL **actual**, ya arrastrado por
el trail) y `price_ref=d["entry"]`, declarado en `reconciler.py:60` como *«sim entry/stop reference
(for logs)»*; `run_live_20.py:786` manda la orden con `price = tick.ask/bid`. **`price_ref` no se
usa nunca.**

Consecuencia: cuando la señal del sim es de hace varias barras y el precio ya corrió a favor, la
posición viva nace con el stop a un pelo en vez de a los ~17,5 USD del SL inicial. De ahí las
salidas agrupadas en −1,00 USD (= ancho exacto del trail plano) y las duraciones de segundos:
mediana **169 s**, **41,7 %** bajo el minuto, cuenta plana el **68 %** del tiempo y re-entrando sin
parar.

La ruta está en la base compartida `origin/alvaro` y los 10 commits locales de máquina 2 no la
tocan: **no es divergencia máquina-1-vs-máquina-2, es divergencia ejecutor-vs-backtest**, y nuestro
repo la tiene igual. Huella en el audit log de la ventana: 943 `OPEN_SKIPPED_SL_CROSSED`, 441
`MODIFY`, 35 `SL_CLAMPED`, y **solo 3 `CLOSE`** ⇒ prácticamente todas las salidas las hizo el
bróker por SL.

**Esto invierte la causalidad que se venía asumiendo.** No son dos fallos de paridad: el de
entradas es consecuencia del de salidas, porque con `active_fichas=1` y concurrencia 1 cada salida
prematura reabre la ventana de entrada.

### D-40 · 2026-08-12 · El motor faulty se PRESERVA como ref inmutable, y todo resultado se etiqueta con su motor
*(Procedencia: instrucción explícita del user — «es definitivamente necesario para continuar el
proceso con la rigurosidad requerida para que los resultados sean transferibles y sustentados en
datos reales, repetibles y proyectables». **Revierte** la instrucción anterior de «no integrar
rama, no traer bundle», por motivo de rigor: sin la copia byte-exacta, el motor faulty sería «uno
que creemos equivalente», y eso no sostiene una proyección de años.)*

El motor que operó la DEMO 2883016902 queda congelado en el tag `engine-faulty-tomachine-902`
(`b113eb7`), importado a `refs/m2/*` para que no se pueda checkoutear ni mergear por accidente.
Descriptor en `research/motores/FAULTY-tomachine-902.md`.

Tres reglas vinculantes: **(a)** ese ref se preserva, **no se arregla** — los arreglos van sobre un
motor separado `engine=fixed`; **(b)** todo resultado de backtest se etiqueta con su motor
(`engine=faulty@b113eb7` / `engine=fixed@<sha>`), y un resultado sin etiqueta no es comparable y no
vale; **(c)** R1-bis sigue intacto por encima de esto.

Secuencia acordada: preservar → modelar la ruta faulty en el harness → **certificar con A6** →
backtest largo faulty → arreglar → backtest largo fixed → perillas. La corrección de orden sobre la
propuesta original del user (que ponía A6 al final) es que **A6 es el certificado del backtest
faulty**, no un trámite pendiente: sin él se proyectan años de un motor que sólo *creemos* haber
replicado. Aceptada.

### D-41 · 2026-08-12 · `equipo1` es exclusiva del equipo local de R&D
*(Procedencia: aclaración explícita del user.)*
La máquina 2 no usa `equipo1`. Commit y push sobre esa rama son libres y no requieren coordinación.
Deja sin efecto la cautela de «intercambio bidireccional» anotada al importar el bundle.

### D-42 · 2026-08-12 · Los 8 meses de Capitaria son un límite del bróker, no nuestro
*(Procedencia: aclaración explícita del user.)*
El lake de ticks de Capitaria cubre sólo 2026-01 → 2026-08 porque **Capitaria no quiso o no pudo
compartir más** — no es un tope de nuestra descarga ni algo que quede por intentar. **AVA sí los
tenía y los compartió, con ayuda exhaustiva cuando hizo falta.** Cierra esa línea de indagación.

Refuerza el reparto de roles de D-21: AVA es el sustrato de historia larga (2022-01 → 2026-08,
~4,7 años) y **el backtest largo corre sobre AVA**, sin alternativa. Capitaria sigue siendo la
referencia de economía real, con la salvedad de que su spread es un escalón degenerado
(p25=p50=0,500 · p75=p99=0,600) frente a la distribución real de AVA.

### D-43 · 2026-08-12 · El objetivo es REPLICAR, no proyectar — y los cierres manuales se simulan
*(Procedencia: instrucción explícita del user.)*

El fin del ejercicio no es estimar cómo le habría ido a las estrategias: es **reproducir sobre
sustrato AVA las mismas señales y prácticamente las mismas salidas** que las estrategias obtuvieron
corriendo en Capitaria. Se intentó repetidamente en backtests real-tick y **falló todas las veces**,
porque se desconocían las particularidades de la implementación hoy identificada como faulty. Con
el motor faulty preservado y sus logs, la réplica pasa a ser alcanzable. La estructura de medición
ya existe: es **D-24** (Pata A = mismos ticks de Capitaria, persigue señal idéntica; Pata B =
transferibilidad a AVA).

**Los cierres manuales se simulan** (condicionado por el user a «de ser posible»), y la razón no es
el PnL: es reproducir las **ventanas de disponibilidad para tomar posición**. Con `active_fichas=1`
y concurrencia máxima 1 por estrategia, una posición abierta **bloquea toda señal posterior**; un
cierre manual libera la estrategia antes de tiempo y le abre una entrada que el sim nunca tiene.

🔴 **Esto no corrige un confusor: lo da vuelta.** Los 11 cierres manuales se descartaron con
«atacan sólo el 7 %». Ese 7 % era **11 de 151 por CUENTA**, arrastrado después como si fuera
participación en el neto. Es el mismo error de clase que el de `SPREAD_GATE_SKIP`: contar eventos y
hablar de magnitudes.

Medido sobre `deals_raw` de la entrega de máquina 2 (ventana canónica 2026-07-27 18:53:30 →
2026-08-11 01:15:04; reproduce exactamente 118 SL · 21 expert · 11 manuales · 1 TP = 151 cierres, y
su neto total cuadra al peso con la LEDGER F0-INFRA-0025):

| | NETO (= LEDGER) | **Sin cierres manuales** | Aporte manual |
|---|---:|---:|---:|
| `SAR::S6-K2P0` | +9.272.144,35 | **+3.009.841,01** | +6.262.303,34 · 3 cierres · **68 %** de su neto |
| `SuperTrend::SuperTrend-p14x3-M15` | +5.930.966,98 | **−16.223.085,46** | +22.154.052,44 · 8 cierres · **374 %** de su neto |
| **Cuenta** | **+15.203.111,33** | **−13.213.244,45** | **+28.416.355,78** |

**Los 11 cierres manuales no aportan el 7 % del neto: aportan la totalidad de la rentabilidad.**
Sin ellos la cuenta pierde 13,2 M CLP. **SuperTrend no es una estrategia ganadora — es
catastróficamente perdedora y el operador la rescató**; sus 58 salidas por SL suman −17,38 M. S6
sigue siendo ganadora pero vale un tercio de lo que aparentaba.

**Consecuencia sobre las cifras de la LEDGER:** los +9.272.144 y +5.930.966 registrados por
estrategia **incluyen los cierres manuales** y por tanto no miden a las estrategias. Toda
comparación de paridad de neto contra esas cifras estaba comparando contra el desempeño de un
humano. Hay que declarar cuál de los dos objetivos se persigue:

- **Neto de estrategia** (sólo salidas automáticas): objetivo +3,01 M / −16,22 M.
- **Neto de operación** (incluye discrecionales): objetivo +9,27 M / +5,93 M, y exige reproducir
  los cierres manuales por marca temporal — no es modelable, es replay.

Esto **refuerza y no contradice** el criterio ya fijado por el user («que el operador aporte el neto
no es crítica al plan: automatizar ese criterio es el objetivo»): ahora está cuantificado, y da a
Familia B su cifra objetivo — la política de salida que se busque debe recuperar del orden de
+28,4 M CLP que las salidas automáticas dejan sobre la mesa. Los 11 cierres quedan como **datos
etiquetados** para esa familia.

### D-38 · ADENDA 2 · 2026-08-12 · La tercera vía no debe decidirse todavía
*(Procedencia: recomendación del orquestador a raíz de D-39 + D-43. **No es decisión tomada** — la
elección entre estrechar, no evaluar y `max(nativo, calibrado)` sigue siendo del user.)*

El overlay de costes de D-21 existe para que AVA reproduzca la economía de Capitaria, y se calibró
**contra una brecha observada** entre backtest y operativa real. D-39 y `active_fichas` muestran que
**buena parte de esa brecha era del motor, no de los costes**. Calibrar un modelo de costes para
cerrar una brecha causada por un fallo de ejecución produce un modelo de costes equivocado — y
explica por qué las réplicas previas fallaban de forma inconsistente: se depuraba una brecha de dos
variables con una sola medición, y el overlay absorbía el error del motor.

**Recomendación: no fijar `max(nativo, calibrado)` antes de haber replicado el motor faulty.**
Decidirlo ahora hornea la contaminación en el modelo de costes. Se re-deriva después, con el motor
ya fiel y con la ventana viva —donde existen **ambos** feeds a la vez— como base empírica del
traspaso, en vez de por extrapolación.

### D-44 · 2026-08-13 · Correcciones del user sobre el catálogo de divergencias y la franja horaria
*(Procedencia: instrucciones explícitas del user, 2026-08-13. **Aditivo**: corrige y extiende
D-39…D-43 y el catálogo `research/motores/DIVERGENCIAS-harness-vs-faulty.md`. Nada se elimina.)*

**🔴 RETRACTADO — la «ventana de Londres» era una mala interpretación del orquestador.**
La sesión previa observó que los cierres manuales caían entre las 03:00 y las 10:00 de servidor y
concluyó que esa franja era la propicia. **Es falso, y el user aporta el dato que lo refuta:** la
hora de los cierres manuales **no tiene valor métrico**: un operador se conectó a monitorear **al
azar** a esas horas. Las posiciones que ganaron dinero **se abrieron mucho antes** y simplemente
lograron sobrevivir hasta que alguien miró la pantalla. Las posiciones abiertas requieren
supervisión constante, que no existió. **La distribución horaria de los cierres manuales es ruido
de disponibilidad humana, no señal de mercado.** No usarla para nada. Queda como confusor muerto.

**Corrección de husos.** El reloj del servidor **coincide con la hora local de Chile**: la primera
apertura de cada día cae a las **18:45 servidor = 18:45 local**, confirmado experiencialmente por el
user y por `deals_raw`. Lo que estaba mal era la atribución de mercado: **18:00 local es la apertura
del mercado ASIÁTICO**, no Londres (error de usuario, reconocido y corregido). La franja que el bot
operó fue **18:00 → 03:00 ≈ 9 h ≈ 37 % del día**.

**El objetivo real a extrapolar** no es «Londres» ni una hora concreta: es que las estrategias
abran posiciones en el **~40 % del día con mayor volatilidad y volumen**. Esa es la filosofía que se
transfiere al motor corregido sobre AVA. Cuál es ese 40 % en cada época **se mide sobre los ticks**,
no se deduce de tablas de husos horarios — el offset del servidor de AVA no está verificado y puede
no haber sido constante en 4 años.

**Correcciones al catálogo de divergencias, por entrada:**

- **D1** — confirmada. Se preserva y se etiqueta donde corresponda para no perderla dentro de la
  ejecución del plan.
- **D2** — el reintento indefinido va en el **motor corregido/extendido**, no como fin en sí mismo.
  Objetivo: que el sistema alcance a **reaccionar a variaciones grandes e inesperadas**. Tasa de
  refresco **ideal 1 s, aceptable 2–4 s**. Restricción dura: **no debe degradar la velocidad de los
  backtests** — correr volúmenes grandes tiene que seguir siendo eficiente sin perder calidad ni
  paridad.
- **D3** — 🔴 **redacción corregida**: no es «una ficha por posición», es **una POSICIÓN por
  ESTRATEGIA**.
- **D4** — las re-entradas **se preservan y se comentan**: el plan de investigación las explorará
  más adelante. Pero para P-CAP y P-AVA **se reproduce lo que realmente ocurrió** en el historial de
  S6 y ST, **derivado del dato, no de la percepción** — el propio user marca su recuerdo («creo que
  era sólo una posición por estrategia») como posiblemente equivocado. **Verificar contra
  `deals_raw`, no asumir.**
- **D5** — aceptada como conjetura natural.
- **D6** — correcta. Para P-CAP/P-AVA la ventana bloqueada 18:00–18:45 se reproduce **verbatim**.
- **D7** — se preserva tal cual para P-CAP/P-AVA. Para el **motor corregido** el objetivo es que el
  trailing siga el precio y sus indicadores **en vivo**: si una estrategia debe apretar el stop ante
  una variación, que pueda hacerlo a la velocidad correcta, **sin el lag de esperar el cierre de
  vela**.
- **D8** — lo importante es corregir que cierre una entrada recién abierta con un SL incorrecto.
  🟡 **Cuestión abierta, anotada como tal:** la re-entrada inmediata tras un cierre por SL **no ha
  sido trabajada formalmente**. Puede ser **motivo de pérdida, motivo de utilidad, o ruido sin
  dirección clara de beneficio**. Queda **INDETERMINADA** y pendiente de estudio; no se asume signo.
- **D9** — confirmada.
- **D10** — confirmada.

**Sobre el plan:** aceptado tal como se presentó (réplica → P-CAP → P-AVA → corrida sin manuales →
recién entonces corregir/extender). Debe quedar registrado de forma que **sobreviva a los cambios de
sesión** y se integre **sin destruir información previa ni otros pasos ya detallados**: sólo
extender y corregir. **Prohibido eliminar.**

### D-45 · 2026-08-13 · La verificación dura del SL de entrada en P-CAP se DEFIERE, y se anota lo que se prefería
*(Procedencia: decisión explícita del user, 2026-08-13, ante la disyuntiva planteada por el
controlador tras T0.6-B.)*

**El hecho que fuerza la decisión.** El log del ejecutor imprime `[SENT OPEN]` **sin el SL**; el SL
sólo queda escrito cuando hubo un clamp. Por eso el SL realmente enviado es recuperable en
**61 de 152 aperturas**, y las otras **91 son NO EVALUABLES** (T0.6-B, pregunta 10). No es un fallo
de la extracción: el dato no existe en la fuente.

**Lo que el user prefiere** —y se registra como tal, no como lo que se hará ahora— es la opción
exigente: que el SL derivado por la réplica **case en esas 61 como condición de paso** de P-CAP, y
aceptar ese acierto como validación indirecta de las 91 restantes. Su razón: los resultados del
backtest largo con el motor faulty son **los más representativos para proyectar cómo están
funcionando hoy las estrategias en vivo**, así que conviene la vara más alta.

**Lo que se hace, y por qué.** Queda **diferida**. Pesa más completar la investigación entera cuanto
antes que apurar un backtest puntual, y no se compromete el cronograma a un debug profundo si el SL
no casa a la primera. Se revisa **al terminar el plan**, o antes si alguna etapa lo requiere o se
beneficiaría en gran medida.

**Matiz del controlador, aceptado dentro de la misma decisión:** la comparación sobre las 61
aperturas con dato **sí se mide y se reporta** en P-CAP como métrica informativa — el dato ya está
extraído y medirlo es barato—, pero **sin poder de bloqueo**. Así no se pierde la señal y no se
hipoteca el calendario.

**Consecuencia sobre el criterio de paso de P-CAP:** la paridad bit-idéntica se declara sobre
**precio de entrada, instante de entrada, instante y precio de salida, razón de cierre y resultado**.
El SL de entrada queda fuera del criterio de paso y dentro del reporte. Anotado en
`research/BACKLOG.md` para su revisión posterior.
