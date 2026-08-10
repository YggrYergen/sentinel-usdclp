# ESTRUCTURA ESTÁNDAR DE UNA FASE

> Todas las fases usan la misma estructura. Un agente que aprendió a moverse en una fase sabe
> moverse en todas. El formato es el de una tesis: cada área tiene su sub-índice, sus hipótesis,
> sus resultados, sus observaciones y su cierre; el conjunto forma "el libro" del programa.

```
fases/<ID>-<nombre>/
  00-README.md         objetivo, entradas, salidas, criterio de cierre, dependencias
  01-hipotesis/        pre-registros — SE ESCRIBEN ANTES DE CORRER. Uno por experimento
  02-specs/            specs cerradas para implementadores
  03-runs/             manifiestos declarativos (los ejecuta un runner, no un LLM)
  04-resultados/       capa máquina: JSON/parquet/CSV con tags de lineage. CERO conclusiones
  05-analisis/         memos de interpretación. SOLO Opus. Separados de los datos
  06-observaciones.md  backlog local: ideas que NO crean tareas
```

## Fases del programa

| ID | Nombre | Gate de entrada |
|---|---|---|
| `F0-preparacion` | Datos, motor congelado, fidelidad, Research OS, literatura, holdout | — (fase actual) |
| `A0-autopsia` | Autopsia de posiciones (dossiers, indicadores, episodios, lateralidad) | F0 cerrada + motor mod #11 |
| `S0-screening` | Screening retrospectivo de features con reglas pre-fijadas | A0 cerrada |
| `GR-grillas` | Ola de grillas B · C · D · LS · F · G · H | S0 cerrada |
| `LBT-backtest-largo` | Backtest largo real-tick sobre AVA | Puerta D170' + T0.3 |
| `E-recombinacion` | Recombinación y ensambles (🔒 tras checkpoint E0 conversado) | E0 con OK del user |
| `HO-holdout` | Holdout sagrado — UNA sola pasada | Autorización explícita del user |

## Plantilla de `00-README.md`

```markdown
# FASE <ID> — <nombre>

## Objetivo
<una frase: qué produce esta fase que las siguientes necesitan>

## Gate de entrada
<qué debe estar `[x]` antes de empezar>

## Entradas
<artefactos y datos que consume, con rutas>

## Salidas
<artefactos que produce, con rutas — esto es lo que se verifica al cerrar>

## Criterio de cierre (verificable)
- [ ] <condición objetiva 1>
- [ ] <condición objetiva 2>
- [ ] Revisión de código batcheada de la fase
- [ ] Memo de análisis escrito (Opus)
- [ ] Backlog revisado: qué se promueve (con enmienda) y qué queda
- [ ] TRACKER y LEDGER actualizados

## Riesgos conocidos de esta fase
<lo que puede salir mal y cómo se detecta>
```

## Plantilla de pre-registro (`01-hipotesis/<exp>.md`)

```markdown
# PRE-REGISTRO — <experimento-id>
**Fecha:** <antes de correr, siempre>   **Autor:** <Opus>

## Hipótesis
<afirmación falseable, en una frase>

## Grilla exacta
<parámetros y niveles — congelados a partir de aquí>

## Sustrato
substrate_id: <valor del vocabulario controlado>

## Métrica de decisión
<qué se mide, exactamente>

## Regla de decisión (pre-fijada)
<qué resultado hace que esto avance, y qué resultado lo manda al registro de negativos.
 Se escribe ANTES de ver un solo número. Esto es lo que hace falseable al experimento>

## Qué NO podrá concluirse con este diseño
<explícito — evita sobre-lectura posterior>
```
