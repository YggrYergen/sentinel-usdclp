r"""scripts/live/verify_two_terminals.py -- PASO 5 DEL EQUIPO 3: verifica que
dos terminales MT5 pueden convivir y que `mt5.initialize(path=...)` se engancha
a CADA UNO sin ambiguedad (SENTINEL, 2026-09-24).

POR QUE EXISTE
  El equipo 3 corre dos terminales a la vez: MT5 #1 (AVA 101744074, armado) y
  MT5 #2 (segunda demo AVA, solo monitorizacion). Todo el stack asume que
  `initialize(path=<exe>, portable=<flag>)` se engancha exactamente a ESE
  terminal. Con un solo terminal abierto eso nunca se puso a prueba. Y el
  2026-07-24 ya se diagnostico el modo de fallo contrario: un desajuste del
  flag /portable hizo que initialize() NO lograra engancharse al terminal
  existente y levantara un SEGUNDO terminal propio.

  Si esta verificacion falla, el diseno de un-solo-clon no sirve y hay que
  pasar al plan B (dos clones del repo, ver el spec). Mejor saberlo el dia uno.

QUE HACE (y QUE NO)
  ESTRICTAMENTE DE SOLO LECTURA. No manda ordenes, no escribe en ninguna base,
  no arranca ni cierra terminales, no toca ficheros del repo. Solo:
    1. Cuenta los procesos terminal64.exe ANTES de tocar nada.
    2. Por cada perfil: comprueba que el exe existe y que hay un proceso
       corriendo desde ESA ruta.
    3. Se engancha con initialize(path=..., portable=...), lee account_info()
       y symbol_info(GOLD), y hace shutdown().
    4. Cuenta los procesos terminal64.exe DESPUES. Si aparecio alguno nuevo,
       initialize() levanto un terminal fantasma -> FALLO.
    5. Comprueba que los dos perfiles dieron logins DISTINTOS -- si los dos
       devuelven el mismo login, initialize() esta ignorando `path=` y ambos
       stacks escribirian sobre la misma cuenta.

  No usa guard_cuenta.assert_demo() a proposito: ese guard hard-exit(2) si el
  login no es el de ESTA maquina, y aqui inspeccionamos DOS cuentas. En su
  lugar comprobamos a mano que cada login este en SANCTIONED_DEMO_LOGINS y que
  trade_mode sea DEMO, y lo REPORTAMOS sin operar nada.

USO
    python -m scripts.live.verify_two_terminals
    python -m scripts.live.verify_two_terminals --p1 scripts/live/machine_local.json ^
                                                --p2 scripts/live/machine_local.ava2.json

SALIDA
    exit 0 = los dos terminales se distinguen correctamente -> sigue el plan.
    exit 1 = algo no cuadra; el informe dice exactamente que. NO armes nada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.live.guard_cuenta import (  # noqa: E402
    REAL_LOGIN, SANCTIONED_DEMO_LOGINS, TRADE_MODE_DEMO)
from sentinel_engine.live.machine_profile import (  # noqa: E402
    MachineProfileError, load_profile)

DEFAULT_P1 = REPO_ROOT / "scripts" / "live" / "machine_local.json"
DEFAULT_P2 = REPO_ROOT / "scripts" / "live" / "machine_local.ava2.json"
SYMBOL = "GOLD"


def _terminal_processes() -> list[dict[str, Any]]:
    """Lista de procesos terminal64.exe con su ruta de ejecutable. Usa CIM via
    PowerShell (misma tecnica que preflight_live/_portable_running, que leen
    la linea de comandos con Win32_Process)."""
    import json
    import subprocess
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
        "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] no pude enumerar procesos: {exc!r}")
        return []
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return [{"pid": d.get("ProcessId"),
             "exe": (d.get("ExecutablePath") or ""),
             "cmd": (d.get("CommandLine") or "")} for d in data]


def _probe(label: str, profile_path: Path, mt5: Any) -> dict[str, Any]:
    """Engancha a UN terminal y reporta. Devuelve un dict con el veredicto."""
    res: dict[str, Any] = {"label": label, "path": str(profile_path),
                           "ok": False, "login": None, "problems": []}
    print(f"\n{'=' * 70}\n{label}  <-  {profile_path}\n{'=' * 70}")

    if not profile_path.exists():
        res["problems"].append(f"el perfil {profile_path} no existe")
        print(f"  [FALLO] no existe {profile_path}")
        return res

    try:
        prof = load_profile(path=profile_path)
    except MachineProfileError as exc:
        res["problems"].append(f"perfil invalido: {exc}")
        print(f"  [FALLO] {exc}")
        return res

    print(f"  terminal_path : {prof.terminal_path}")
    print(f"  portable      : {prof.portable}")
    print(f"  demo_login    : {prof.demo_login}")
    print(f"  marker        : {prof.terminal_marker}")

    if not Path(prof.terminal_path).exists():
        res["problems"].append(f"el exe {prof.terminal_path} no existe en disco")
        print(f"  [FALLO] el exe no existe: {prof.terminal_path}")
        return res

    want = str(prof.terminal_path).lower()
    running = [p for p in _terminal_processes() if p["exe"].lower() == want]
    if not running:
        res["problems"].append("no hay ningun terminal64.exe corriendo desde esa ruta")
        print("  [FALLO] no hay proceso corriendo desde esa ruta exacta.")
        print("          Abre ese terminal y loguealo antes de repetir.")
        return res
    print(f"  proceso vivo  : PID {running[0]['pid']}")

    ok = (mt5.initialize(path=str(prof.terminal_path), portable=True)
          if prof.portable else mt5.initialize(path=str(prof.terminal_path)))
    if not ok:
        res["problems"].append(f"initialize fallo: {mt5.last_error()}")
        print(f"  [FALLO] initialize() fallo: {mt5.last_error()}")
        return res

    try:
        info = mt5.account_info()
        sym = mt5.symbol_info(SYMBOL)
        term = mt5.terminal_info()
    finally:
        mt5.shutdown()

    if info is None:
        res["problems"].append("account_info() devolvio None")
        print("  [FALLO] account_info() devolvio None (terminal sin sesion?)")
        return res

    res["login"] = int(info.login)
    print(f"  login leido   : {info.login}")
    print(f"  servidor      : {info.server}")
    print(f"  trade_mode    : {info.trade_mode} "
          f"({'DEMO' if info.trade_mode == TRADE_MODE_DEMO else 'NO-DEMO'})")
    print(f"  data path     : {getattr(term, 'data_path', '?')}")
    print(f"  {SYMBOL:<14}: {'presente' if sym else 'AUSENTE'}"
          + (f"  spread={sym.spread} digits={sym.digits}" if sym else ""))

    if int(info.login) != int(prof.demo_login):
        res["problems"].append(
            f"initialize(path=...) se engancho al login {info.login}, pero el "
            f"perfil dice {prof.demo_login}. path= NO esta desambiguando.")
        print(f"  [FALLO] login {info.login} != perfil {prof.demo_login}")
    if int(info.login) == REAL_LOGIN:
        res["problems"].append("ES LA CUENTA REAL -- parar de inmediato")
        print("  [FALLO GRAVE] es la cuenta REAL.")
    if int(info.login) not in SANCTIONED_DEMO_LOGINS:
        res["problems"].append(
            f"login {info.login} NO esta en SANCTIONED_DEMO_LOGINS "
            f"{sorted(SANCTIONED_DEMO_LOGINS)} -- anadelo en guard_cuenta.py "
            "(paso 7 del runbook) antes de que ningun stack lo use.")
        print(f"  [PENDIENTE] login {info.login} aun no esta sancionado.")
    if info.trade_mode != TRADE_MODE_DEMO:
        res["problems"].append(f"trade_mode={info.trade_mode}, no es DEMO")
        print("  [FALLO] no es una cuenta DEMO.")
    if sym is None:
        res["problems"].append(f"el simbolo {SYMBOL} no existe en este broker")

    res["ok"] = not res["problems"]
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Verifica que dos terminales MT5 conviven y se distinguen "
                    "por path. SOLO LECTURA: nunca manda ordenes.")
    ap.add_argument("--p1", default=str(DEFAULT_P1),
                    help=f"perfil del stack #1 (por defecto {DEFAULT_P1})")
    ap.add_argument("--p2", default=str(DEFAULT_P2),
                    help=f"perfil del stack #2 (por defecto {DEFAULT_P2})")
    args = ap.parse_args(argv)

    print("VERIFICACION DE DOS TERMINALES MT5 -- equipo 3")
    print("SOLO LECTURA: este script no manda ordenes ni arranca terminales.\n")

    try:
        import MetaTrader5 as mt5
    except Exception as exc:  # noqa: BLE001
        print(f"[FATAL] no pude importar MetaTrader5: {exc!r}")
        print("        pip install MetaTrader5")
        return 1

    before = _terminal_processes()
    print(f"terminal64.exe corriendo ANTES: {len(before)}")
    for p in before:
        print(f"   PID {p['pid']:<8} {p['exe']}")
    if len(before) < 2:
        print("\n[AVISO] hay menos de 2 terminales corriendo. Esta verificacion "
              "solo tiene sentido con los DOS abiertos y logueados.")

    r1 = _probe("STACK #1  (AVA 101744074, sera el ARMADO)", Path(args.p1), mt5)
    r2 = _probe("STACK #2  (segunda demo AVA, solo monitorizacion)", Path(args.p2), mt5)

    after = _terminal_processes()
    print(f"\n{'=' * 70}\nCONTROL DE FANTASMAS\n{'=' * 70}")
    print(f"terminal64.exe ANTES={len(before)}  DESPUES={len(after)}")
    ghosts = {p["pid"] for p in after} - {p["pid"] for p in before}
    phantom = bool(ghosts)
    if phantom:
        print(f"  [FALLO] initialize() levanto terminal(es) nuevo(s): PIDs {sorted(ghosts)}")
        print("          Suele ser un desajuste del flag `portable` en el perfil.")
    else:
        print("  OK: initialize() no levanto ningun terminal nuevo.")

    print(f"\n{'=' * 70}\nVEREDICTO\n{'=' * 70}")
    same_login = (r1["login"] is not None and r1["login"] == r2["login"])
    if same_login:
        print(f"  [FALLO CRITICO] los DOS perfiles devolvieron el mismo login "
              f"({r1['login']}). initialize(path=...) NO esta desambiguando "
              "entre terminales: el diseno de un solo clon NO es viable. "
              "Pasa al plan B del spec (dos clones).")
    for r in (r1, r2):
        estado = "OK" if r["ok"] else "CON PROBLEMAS"
        print(f"\n  {r['label']}: {estado}")
        for p in r["problems"]:
            print(f"     - {p}")

    all_ok = r1["ok"] and r2["ok"] and not phantom and not same_login
    print("\n" + ("=" * 70))
    if all_ok:
        print("RESULTADO: OK. Los dos terminales se distinguen por path.")
        print("Puedes seguir con el paso 8 del runbook.")
        return 0
    print("RESULTADO: NO OK. No armes nada todavia. Revisa los puntos de arriba.")
    print("Si el unico problema es 'login aun no esta sancionado' para el stack")
    print("#2, es lo esperado hasta completar el paso 7 del runbook.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
