# PROTOCOLO 03 — VERIFICACIÓN Y ANTI-DRIFT

> El riesgo dominante de un programa agéntico de semanas no es equivocarse: es **creer que algo
> se hizo cuando no se hizo**, o **aceptar un resultado que en realidad no soporta la conclusión**.
> Este protocolo existe para que eso sea estructuralmente imposible, no solo "desaconsejado".

---

## 1 · Definición de HECHO

Una tarea está `[x]` cuando, y solo cuando, existen las **tres**:

1. **Artefacto en la ruta esperada** — el fichero existe, tiene contenido y es del tipo esperado.
2. **Fila en `LEDGER.jsonl`** con lineage completo (charter §A.9).
3. **Evidencia de ejecución** — la salida REAL de los comandos/tests, pegada en el reporte.

**Nunca** cuenta como "hecho": la afirmación de un agente, un resumen en prosa, un "debería
funcionar", un test escrito pero no ejecutado, o un artefacto que nadie abrió.

## 2 · Verificador ≠ implementador

Quien implementa **no** valida su propio trabajo como cerrado. La verificación la hace el
controlador (u otro agente) comprobando las tres condiciones de arriba **contra los artefactos
crudos**, no contra el reporte.

**Auditoría aleatoria:** el controlador (Opus) toma periódicamente un reporte de Sonnet al azar y
lo contrasta contra los artefactos. Un reporte que no cuadre invalida la tarea y dispara revisión
de las tareas vecinas del mismo agente.

## 3 · STOP y escalar — casos obligatorios

Se detiene el trabajo y se escala al user, **sin intentar arreglarlo por cuenta propia**, cuando:

- El spec parece incorrecto, incompleto o contradictorio.
- Hay que tocar un fichero de estrategia **viva** (charter §A.11 — R1-bis).
- Un número no cuadra con lo registrado y no hay explicación documentada.
- Un test falla por una razón que no estaba prevista en el spec.
- Una decisión del user (`DECISIONES.md`) parece bloquear la tarea o entrar en conflicto con otra.
- Aparece una anomalía en los datos (huecos, duplicados, valores imposibles, fills en dirección
  de ganancia en un stop, etc.).
- La tarea resulta ser más grande de lo especificado.

**Prohibido**: "aceptar" un error de resultado o de método, reducir el alcance, simplificar el
trabajo para que quepa, o marcar `[!]` y seguir con otra cosa sin avisar.

## 4 · Interpretación en cuarentena

Los datos y las conclusiones viven en ficheros distintos:
- `04-resultados/` — solo números, con tags. **Cero conclusiones.**
- `05-analisis/` — memos de Opus. Es el único lugar donde se interpreta.

Un artefacto de datos que contenga una conclusión está mal formado y se corrige.

## 5 · Cadena de custodia de los números

- Todo número que aparezca en cualquier documento debe poder rastrearse en <1 minuto al
  experimento del LEDGER que lo produjo.
- **La prosa envejece; los artefactos no.** Si un documento en prosa cita una cifra, se re-lee el
  artefacto de origen antes de usarla. (Precedente real: tres documentos del repo siguieron
  imprimiendo cifras del sustrato roto después de que sus JSON fueran regenerados.)
- Registro **aditivo**: jamás se borra ni se muta una fila de resultados. Lo superado se marca.

## 6 · Checklist de cierre de tarea (lo corre el verificador)

- [ ] ¿Existe el artefacto en la ruta exacta? (comprobado, no asumido)
- [ ] ¿Tiene la fila del LEDGER con lineage completo?
- [ ] ¿El reporte incluye salida real de comandos, no parafraseada?
- [ ] ¿Los tests corrieron en foreground y están en verde?
- [ ] ¿El commit está scoped solo a las rutas de la tarea?
- [ ] ¿No se tocó ningún fichero vivo ni compartido sin autorización?
- [ ] ¿El TRACKER quedó actualizado (solo la fila de esa tarea)?
- [ ] Si es investigación: ¿el reporte está libre de interpretaciones?

## 7 · Checklist de cierre de FASE (además de lo anterior)

- [ ] Todas las tareas de la fase en `[x]` verificado.
- [ ] Revisión de código batcheada de la fase (`superpowers:requesting-code-review`).
- [ ] Memo de análisis de la fase escrito por Opus.
- [ ] Backlog de la fase revisado: qué se promueve a tarea (con enmienda) y qué queda.
- [ ] Criterio de cierre de la fase, escrito en su `00-README.md`, cumplido y evidenciado.
- [ ] Handoff del brain actualizado.
