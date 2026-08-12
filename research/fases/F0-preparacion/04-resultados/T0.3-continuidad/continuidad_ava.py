"""Auditoria de continuidad DIARIA del lago de ticks (D-29).

Report-only: no escribe nada, no toca el lago. Enumera los dias presentes en
cada parquet mensual y localiza los huecos interiores.

Los timestamps del lago son epoch-ms zero-offset que decodifican con
utcfromtimestamp() al reloj de SERVIDOR del broker (no UTC real).
"""
import sys
import datetime as dt
import pathlib

import numpy as np
import pyarrow.parquet as pq

lago = pathlib.Path(sys.argv[1])
ficheros = sorted(lago.glob("*.parquet"))

dias_presentes = set()
print(f"{'mes':8s} {'ticks':>12s}  {'primer tick':19s}  {'ultimo tick':19s}  {'dias':>4s}")
print("-" * 74)
for f in ficheros:
    t = pq.read_table(f, columns=["t_msc"])["t_msc"].to_numpy()
    dias_epoch = np.unique(t // 86_400_000)
    dias_presentes.update(int(d) for d in dias_epoch)
    fmt = lambda x: dt.datetime.utcfromtimestamp(x / 1000).strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"{f.stem:8s} {len(t):12,d}  {fmt(t.min()):19s}  {fmt(t.max()):19s}  {len(dias_epoch):4d}"
    )
    del t

# --- huecos interiores, en dias de calendario ---
orden = sorted(dias_presentes)
d0 = dt.date(1970, 1, 1)
print("\n=== HUECOS INTERIORES (> 1 dia natural entre dos dias con ticks) ===")
print(f"{'desde (ultimo con ticks)':26s} {'hasta (siguiente con ticks)':27s} {'dias sin ticks':>14s}  clase")
print("-" * 90)
total_habiles_perdidos = 0
for a, b in zip(orden, orden[1:]):
    hueco = b - a - 1
    if hueco <= 0:
        continue
    fa, fb = d0 + dt.timedelta(days=a), d0 + dt.timedelta(days=b)
    faltantes = [fa + dt.timedelta(days=i) for i in range(1, b - a)]
    habiles = [d for d in faltantes if d.weekday() < 5]  # lun-vie
    # Un fin de semana normal deja sin ticks el sabado y casi todo el domingo.
    if not habiles:
        clase = "fin de semana (legitimo)"
    elif len(habiles) == 1:
        clase = f"1 dia habil: {habiles[0]} ({habiles[0].strftime('%A')}) -- festivo?"
        total_habiles_perdidos += 1
    else:
        clase = f"*** {len(habiles)} DIAS HABILES *** {habiles[0]} .. {habiles[-1]}"
        total_habiles_perdidos += len(habiles)
    print(f"{str(fa):26s} {str(fb):27s} {hueco:14d}  {clase}")

print(f"\nTotal de dias habiles (lun-vie) sin un solo tick: {total_habiles_perdidos}")
print(f"Rango cubierto: {d0 + dt.timedelta(days=orden[0])} .. {d0 + dt.timedelta(days=orden[-1])}")
print(f"Dias de calendario con ticks: {len(orden)}")
