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
