# MACHINE-2 — Despliegue FIXED4 (shadow-only) — 2026-07-19

> **Directiva D114 (user, 2026-07-19):** machine-2 **NUNCA** arma los live-4 sin corregir.
> Machine-2 opera **SOLO** el roster corregido FIXED4 (`--configs shadow`, magics 721010–40).
> Prohibido en machine-2: `SUPERVISOR_CONFIGS=live` y `SUPERVISOR_CONFIGS=live+shadow`.

## Qué es FIXED4

Los mismos 4 configs live (V11-M2, V13-M2, V15-M2, V15-M15) con las correcciones de honestidad
(catálogo IV.H, commits `056bdef` + `75ad350`):
`ac_modulate=False`, `live_fill_mode=True` (open_state reporta el SL server-side real),
`trail_atr_floor_k=1.5` (el trail vive sobre el stops_level de $0.50 de Capitaria).
IDs con sufijo `-F`; magics **721011..721043** (banda disjunta de los live 7201xx/7200xx).

## Verificación local ya realizada en machine-1 (gate D114 — CUMPLIDO)

- **Backtest (A1-V, verificador independiente, 5/5 PASS):** idempotencia (3 pares de hashes iguales);
  byte-identidad clásica (hash `afd8aad5…`, 2967 eventos exit); open_state honesto == nivel server de
  barra previa ≠ f.sl clásico (6 posiciones, barras t=1780413600/1780438200); suite 6/6.
- **Live (ciclo real 2026-07-20T02:20Z, DEMO 2883015767, mercado abierto):**
  `connected + guard OK: DEMO login 2883015767 (dry_run=True, 8 configs)`; los 4 `-F` ciclaron sin
  errores; magics shadow `721021/22/23` en acciones would-OPEN espejando la señal live
  (`720131-33`, mismo sl=3979.49); ciclo completo 1.6 s; `executor stopped cleanly`.
- **Suite:** gate completo 265 passed (parity dorada intacta). Reviews: A1/A2 Approved, 0 hallazgos bloqueantes.

## Pasos en machine-2 (orden estricto)

### 1. Pull

```powershell
cd D:\FOREX
git fetch origin; git checkout alvaro; git pull origin alvaro
git log --oneline -6   # deben aparecer: 75ad350 (FIXED4), 056bdef (sim honesto)
```

### 2. Kit de evidencia (si aún no se corrió) — diagnóstico zero-positions

Ejecutar el kit de `docs/DIAGNOSTIC_REPORT_MACHINE2_ZERO_POSITIONS_2026-07-18.md` §5 y aplicar su
matriz de decisión. **Las causas de plataforma bloquean FIXED4 igual que bloqueaban los live-4** —
deben quedar despejadas ANTES de armar nada:
- AutoTrading **ON** en el terminal (si estaba OFF: retcode 10027 en el audit log).
- `scripts/live/machine_local.json` presente y correcto para esta máquina (sin él: defaults de
  máquina-1 → exit 3 en loop).
- Sin archivo STOP; preflight `python -m scripts.live.preflight_live` en verde.
- Terminal MT5 portable DEMO **2883015767** abierto a mano (ATTACH-ONLY: ningún script lo lanza).

### 3. Armar SOLO shadow (FIXED4)

```powershell
# En la MISMA consola que lanzará el watchdog:
$env:SUPERVISOR_CONFIGS = "shadow"
# Persistente para futuros arranques (nuevas consolas):
setx SUPERVISOR_CONFIGS shadow
# Lanzar el stack canónico:
powershell -ExecutionPolicy Bypass -File scripts\live\watchdog_local.ps1
```

El supervisor armará el executor como:
`python -m scripts.live.run_live_20 --arm --confirm-account 2883015767 --configs shadow` (4 configs FIXED4).

### 4. Verificar

```powershell
# 4 configs shadow resueltos (NO 8, NO live):
Select-String -Path scripts\live\run_live_20.audit.log -Pattern "4 configs" | Select-Object -Last 3
# IDs -F ciclando:
Select-String -Path scripts\live\run_live_20.audit.log -Pattern "\[V1[135]-M(2|15)-F\]" | Select-Object -Last 8
# Magics FIXED4 y fills:
Select-String -Path scripts\live\run_live_20.audit.log -Pattern "magic=7210" | Select-Object -Last 10
Select-String -Path scripts\live\run_live_20.audit.log -Pattern "SENT OPEN.*retcode=10009" | Select-Object -Last 5
```

Éxito = ciclos con `guard OK`, ids `-F`, y (cuando haya señal) `[SENT OPEN] … magic=7210xx -> retcode=10009`.
Si aparece `retcode=10027` → AutoTrading OFF (volver al paso 2).

### 5. Rollback

**Detener el stack** (cerrar watchdog + supervisor + executor). En machine-2 **no hay roster
alternativo válido** (D114 prohíbe `live`). No borrar nada; reportar el motivo al equipo 1.

---

## Bloque copy-paste para la sesión de Claude Code en machine-2

```
Context: SENTINEL repo D:\FOREX, branch alvaro. Directive D114: this machine (machine-2) must ONLY
arm the corrected FIXED4 roster (--configs shadow, magics 721010-40). NEVER set SUPERVISOR_CONFIGS
to "live" or "live+shadow" here. Safety (Capa 4): DEMO 2883015767 is the only tradable account
(ATTACH-ONLY, the human opens the MT5 terminal); REAL accounts are READ-ONLY, never operate.

Do, in order:
1. git fetch origin && git checkout alvaro && git pull origin alvaro. Verify commits 056bdef and
   75ad350 are present (git log --oneline -6).
2. Follow docs/MACHINE2_FIXED4_DEPLOY_2026-07-19.md steps 2-4: run the evidence kit of
   DIAGNOSTIC_REPORT_MACHINE2_ZERO_POSITIONS_2026-07-18.md §5 first, clear any platform cause
   (AutoTrading ON, machine_local.json for THIS machine, no STOP file, preflight green, portable
   DEMO terminal open by the human), then set SUPERVISOR_CONFIGS=shadow (both $env: and setx) and
   start scripts\live\watchdog_local.ps1.
3. Verify per step 4 greps: "4 configs", [V*-F] ids cycling, magic=7210xx, and on first signal a
   [SENT OPEN] ... retcode=10009. If 10027 appears, AutoTrading is OFF — fix and recheck.
4. Report back to team 1: the step-4 grep outputs + any deviation. Rollback = stop the stack
   (there is no valid alternative roster on this machine).
```
