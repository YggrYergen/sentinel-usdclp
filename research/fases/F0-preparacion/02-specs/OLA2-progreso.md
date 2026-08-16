# OLA2 -- bitacora de progreso (una linea por bloque cerrado, D-48)

- BLOCK A (recon): leidos CHARTER/TRACKER/DECISIONES D-45..D-60/preregistro-OLA1B/consolidado-OLA1B/catalogo-palancas/WP-345-reporte/WP-1-2-reporte/DIAG-P03-reporte/tasks_ola1.py/sustrato.py/manifiesto_ola1b.py/consolidar.py. HEAD=69bad91.
- BLOCK B.1 (plumbing P-20): `run_supertrend` gana `htf_mask` (default None, byte-identico), 5 tests nuevos, parity 4 passed. Commit `ea57198`.
- BLOCK B.2 (plumbing P-09): `_extraer_regime_de_brazos` + wiring en `ola1_paired`/`_resolver_brazos_con_progreso`, 5 tests nuevos (`test_ola2.py`), parity 4 passed. Commit `8de6480`.
- BLOCK B.3 (plumbing sizing P-16 continuo): `SizingConfig.dd_continuous`, 2 tests nuevos, parity 4 passed. Commit `816c962`.
- BLOCK B.4 (task-type sizing): `ola1_sizing` nuevo (pareado trivial por posicion, no `entry_identity`), 8 tests nuevos (`test_sizing_task.py`), parity 4 passed, `tests/research` 409 passed. Commit `490d1bf`.
- BLOCK B.5 (pre-registro OLA2): escrito y COMMITEADO antes de correr un solo brazo -- 62 arms/50 confirmatorios en 12 corridas, curacion OFAT de P-09, convenciones de unidad P-15/16/17/18, GATED list. Commit `e864e5a`.
- BLOCK B.6 (manifiesto): `manifiesto_ola2.py`, 4 tests nuevos, conteos verificados 62/50, parity 4 passed, `tests/research` 413 passed. Commit `93a2605`.
- BLOCK B.7 (fix runner CLI): `ola1_sizing` no se registraba en `runner.py` (CLI abortaba con tipo no registrado) -- import añadido, mismo patron que `tasks_ola1`. Commit `0eb7d0e`.
- BLOCK C (ejecucion): `python -m scripts.research.runner.runner <manifiesto> --on-error continue --workers 12`, foreground, 16.75s reales, 12/12 corridas ok, 0 fallidas. `_progreso.txt` 12/12 (100.0%).
- BLOCK D.1 (fix consolidador): BH-FDR se mezclaba en un solo lote pese a que el pre-registro exige 2 lotes separados (htf/regimen vs sizing) -- `consolidar.py` corregido para agrupar por `lineage.generador`, 1 test nuevo (`test_bh_fdr_se_corrige_por_lote...`), backward-compatible (fixtures viejos sin `generador` -> un solo lote implicito), parity 4 passed, `tests/research` 414 passed. Commit `1f82a02`.
- BLOCK D.2 (consolidacion real): `python -m scripts.research.ola1.consolidar research/fases/F0-preparacion/04-resultados/OLA2` -- 62 brazos, 12 corridas, 2 lotes (31 htf/regimen + 19 sizing), 0/50 confirmatorios rechazados en total (0/31 lote htf/regimen, 0/19 lote sizing).
- BLOCK A (reporte OLA1B): `OLA1B-reporte.md` escrito -- SHAs, correccion de wiring WP-5, entrada de catalogo P-34, discrepancia de formula P-15, tabla completa de tasas de emparejamiento de los 63 brazos. Commit `ed6f6a6`.
- BLOCK final: `OLA2-reporte.md` (este bloque) + verificacion final de suites.
