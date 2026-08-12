# Registro de motores

Cada variante del motor que produce resultados se registra aquí con un ref git inmutable y un
descriptor. **Todo resultado de backtest se etiqueta con el motor que lo produjo.** Un resultado
sin etiqueta de motor no es comparable con ningún otro y no vale como medición.

| Motor | Ref | Estado | Descriptor |
|---|---|---|---|
| `faulty` | tag `engine-faulty-tomachine-902` → `b113eb7` | **congelado — preservar, no arreglar** | [FAULTY-tomachine-902.md](FAULTY-tomachine-902.md) |
| `fixed` | — | pendiente | — |

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
