# Registro de motores

Cada variante del motor que produce resultados se registra aquí con un ref git inmutable y un
descriptor. **Todo resultado de backtest se etiqueta con el motor que lo produjo.** Un resultado
sin etiqueta de motor no es comparable con ningún otro y no vale como medición.

| Motor | Ref | Estado | Descriptor |
|---|---|---|---|
| `faulty` | tag `engine-faulty-tomachine-902` → `b113eb7` | **congelado — preservar, no arreglar** | [FAULTY-tomachine-902.md](FAULTY-tomachine-902.md) |
| `fixed` | — | pendiente | — |

Procedencia del motor faulty y qué más llegó con él:
[ENTREGA-M2-2026-08-12-inventario.md](ENTREGA-M2-2026-08-12-inventario.md).

En qué se comporta distinto nuestro harness de backtest respecto del motor vivo, con sitio de
código y mecanismo por cada divergencia:
[DIVERGENCIAS-harness-vs-faulty.md](DIVERGENCIAS-harness-vs-faulty.md).

## Los dos hitos de paridad, antes de tocar nada

| Hito | Sustrato | Criterio |
|---|---|---|
| **P-CAP** | ticks Capitaria, ventana 902 | **bit-idéntico** contra el historial de la 902. Requisito duro: sin él no se procede. |
| **P-AVA** | ticks AVA, misma ventana | lo más par posible. Bit-idéntico es meta asintótica, no criterio de paso. |

Ambos se persisten y documentan **antes** de arreglar o modificar el motor. Son el instrumento con
el que se medirá toda mejora posterior: sin ellos, cualquier ganancia atribuida a un cambio es
indistinguible de un artefacto del harness.

Y hace falta una **tercera corrida dedicada: el motor faulty sin cierres manuales.** El desempeño
100 % autónomo de las estrategias no se puede derivar restando deals del historial — una posición
abierta ocupa el cupo de su estrategia, así que suprimir un cierre manual cambia toda la secuencia
posterior de entradas. Sólo se obtiene re-simulando.

## Por qué existe este registro

El motor que corrió en producción sobre la DEMO 2883016902 tiene un fallo estructural (D-39: abre
a precio de mercado pero hereda el SL ya trailleado del sim). La proyección plurianual de S6 y
SuperTrend **con ese fallo** es el dato de partida: dice cómo le habría ido a las estrategias
corriendo exactamente como han venido corriendo. La proyección con el motor corregido dice qué
aporta el arreglo. Sólo tienen sentido comparadas, y sólo son comparables si ambas están
etiquetadas y ambos motores están congelados.

Preservar el motor faulty no es conservadurismo: es la única forma de que el arreglo tenga un
contrafactual medible en vez de una impresión.

## Namespace de preservación

Los refs importados de otras máquinas viven en `refs/m2/*`, fuera de `refs/heads/*`. No aparecen
en `git branch`, no se pueden checkoutear ni mergear por accidente. Para inspeccionar:

```
git show engine-faulty-tomachine-902:<ruta>
git log --oneline f93e54a..engine-faulty-tomachine-902
git diff f93e54a..engine-faulty-tomachine-902 -- <ruta>
```

## Convención de etiquetado de resultados

`engine=faulty@b113eb7` · `engine=fixed@<sha>`, en el nombre del artefacto y en su manifiesto.
