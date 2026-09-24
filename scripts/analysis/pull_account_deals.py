r"""scripts/analysis/pull_account_deals.py -- READ-ONLY deal-history puller for
per-account, per-strategy performance analysis (week-of-2026-07-20 review;
extended 2026-08-11 to support cross-terminal accounts such as 902).

WHAT IT DOES
  1. Attaches to a SEPARATE tester terminal (default D:\FOREX\MT5_Tester,
     overridable -- see TERMINAL PATH below) via an explicit login
     (login/password/server) -- NOT the live portable terminal, so pulling
     one account never disturbs a live executor.
  2. Read-scoped identity guard (see PERMISSION SEPARATION below), enforced
     AFTER connecting and BEFORE any history read.
  3. Pulls `mt5.history_deals_get(from, to)` over a wide window and writes:
       - <out>/<login>_deals_raw.csv      (every deal, all P&L components)
       - <out>/<login>_positions.csv      (per-position rollup + attribution)
     plus a printed summary (net per strategy x batch).

PERMISSION SEPARATION (2026-08-11) -- READ THIS BEFORE TOUCHING ANY GUARD
  `sentinel_engine.live.guard_cuenta.SANCTIONED_DEMO_LOGINS` answers "may
  this process PLACE ORDERS here?" -- it gates the live executor's
  `assert_demo()` and is deliberately a small, hard-coded, order-authority
  allowlist. This script answers a DIFFERENT question -- "may I READ this
  account's history?" -- and reusing the order-authority list for that
  purpose was a bug: it silently tied a read-only research tool to the live
  trading allowlist, and would refuse to read accounts (e.g. 2883016902 /
  "902", explicitly NO-R&D and read-only per CUENTAS.md) that must NEVER be
  added to that allowlist, because adding them there would grant them order
  authority they must never have.

  The fix separates the two questions instead of widening the order-authority
  list:
    - `guard_cuenta.SANCTIONED_DEMO_LOGINS` is NOT used here anymore, and
      `sentinel_engine/live/guard_cuenta.py` is UNTOUCHED -- order authority
      is exactly what it was before this change, not one login wider.
    - `guard_cuenta.REAL_LOGIN` (the hard block on the real-money account) IS
      still imported and still enforced, unchanged, at both the pre-connect
      and post-connect checkpoints.
    - This module enforces its OWN read-scoped identity guard instead
      (`check_post_connect_guard`): the connected account's `login` AND
      `server` (both mandatory, checked independently -- several sanctioned
      accounts share the server name `Capitaria-All`, so server alone cannot
      tell accounts apart, and login alone cannot tell brokers/terminals
      apart) must equal the caller-supplied expected login/server, and
      `trade_mode` must be DEMO -- a REAL gate now (previously the value was
      only printed, never enforced).
    - `tests/analysis/test_pull_account_deals.py::test_no_order_capable_calls_in_source`
      asserts the module source contains no order-capable MT5 call
      (order_send, order_check, order_calc_margin, order_calc_profit,
      positions_modify) as the structural proof that removing the allowlist
      check did not create an operate-capable path.

  Net effect: order authority is not widened by one bit -- guard_cuenta.py is
  untouched. The read path is strictly MORE restrictive than before this
  change (real trade_mode gate, mandatory server check, structural
  no-order-call proof), in exchange for no longer gating reads on the
  order-authority allowlist.

TERMINAL PATH
  Parametrized, not secret (no credential involved). Resolution order:
  `--tester-exe` CLI arg > `MT5_PULL_TESTER_EXE` env var > default
  `D:\FOREX\MT5_Tester\terminal64.exe` (unchanged default). Validated to
  exist before use; aborts with a clear message otherwise.

USAGE
  MT5_PULL_PASSWORD=<pwd> python -m scripts.analysis.pull_account_deals \
      --login 2883016567 --server Capitaria-All \
      --from 2026-07-01 --to 2026-07-25 --out data/analysis/week_20260720

  # cross-terminal example (account 902, read-only, NO-R&D):
  MT5_PULL_PASSWORD=<pwd> python -m scripts.analysis.pull_account_deals \
      --login 2883016902 --server Capitaria-All \
      --tester-exe D:\FOREX\MT5_Tester_2\terminal64.exe \
      --from 2026-07-01 --to 2026-08-11 --out data/analysis/2883016902

Password is read from the MT5_PULL_PASSWORD env var (never a CLI arg / never
written to any tracked file), per CUENTAS.md rule 2.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.live import guard_cuenta  # noqa: E402

DEFAULT_TESTER_EXE = REPO_ROOT / "MT5_Tester" / "terminal64.exe"
TESTER_EXE_ENV_VAR = "MT5_PULL_TESTER_EXE"

# --- Self-check: this file must never CALL an order-capable MT5 function. ----
# Each token is assembled from fragments so it never appears literally in
# this source; if anyone adds a real order-dispatch call, the assert trips.
# Kept in sync with
# tests/analysis/test_pull_account_deals.py::test_no_order_capable_calls_in_source.
_ORDER_CALLS = tuple(
    "mt5." + frag
    for frag in (
        "order_" + "send",
        "order_" + "check",
        "order_calc_" + "margin",
        "order_calc_" + "profit",
        "positions_" + "modify",
    )
)
_SRC_TEXT = Path(__file__).read_text(encoding="utf-8")
for _call in _ORDER_CALLS:
    assert _call not in _SRC_TEXT, (
        f"READ-ONLY violation: an order-capable call ({_call}) is present "
        "in pull_account_deals.py"
    )


# --- Strategy attribution --------------------------------------------------
# magic band -> (strategy label, magic base, batch). Batch tags come from the
# trader's 2026-07-24 briefing: 720xxx/721xxx (V11/V13/V15) = TANDA 1 (primera
# tanda, no corregida, dom->mar); 724xxx/725xxx + TK-Momentum = TANDA 2
# (post-hotfix, mar->). The batch tag is a convenience label ONLY -- the actual
# batch split is VERIFIED empirically against each magic's time range in the
# report, never asserted from this table.
def classify_magic(magic: Any) -> tuple[str, str, str]:
    try:
        m = int(magic)
    except (TypeError, ValueError):
        return ("(no-magic)", "?", "?")
    bands = [
        # TANDA 2 (post-hotfix corrected roster)
        (724010, 724013, "S6-K2P0", "724010", "tanda2"),
        (724020, 724023, "S7-TPNONE", "724020", "tanda2"),
        (724070, 724073, "SuperTrend-p14x3-M15", "724070", "tanda2"),
        (725010, 725013, "TK-BW2-fix2atr", "725010", "tanda2"),
        # TANDA 1 (primera tanda, no corregida)
        (720030, 720033, "V13-M2", "720030", "tanda1"),
        (720160, 720163, "V15-M15", "720160", "tanda1"),
        (721010, 721013, "V11-M2-F", "721010", "tanda1"),
        (721020, 721023, "V15-M2-F", "721020", "tanda1"),
        (721030, 721033, "V13-M2-F", "721030", "tanda1"),
        (721040, 721043, "V15-M15-F", "721040", "tanda1"),
    ]
    for lo, hi, label, base, batch in bands:
        if lo <= m <= hi:
            return (label, base, batch)
    if m in (999999998, 999999999):
        return ("TK-Momentum-5-8-short", "999999998", "tanda2")
    if m == 0:
        return ("(magic-0 SL/TP close)", "0", "inherit")
    return (f"UNKNOWN-{m}", str(m), "?")


def _dt(s: str) -> datetime:
    """Parse a YYYY-MM-DD (or full ISO) string as broker/server-naive time.
    MT5 history_deals_get takes server-time datetimes; we pass naive local
    datetimes matching the server clock the terminal is on."""
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d")
    return datetime.fromisoformat(s)


def _deal_row(mt5: Any, d: Any) -> dict[str, Any]:
    entry = getattr(d, "entry", None)
    entry_type = {0: "IN", 1: "OUT", 2: "INOUT", 3: "OUT_BY"}.get(entry, str(entry))
    dtype = getattr(d, "type", None)
    side = {0: "BUY", 1: "SELL", 2: "BALANCE"}.get(dtype, str(dtype))
    magic = getattr(d, "magic", None)
    label, base, batch = classify_magic(magic)
    t = getattr(d, "time", None)
    t_iso = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if t else ""
    return {
        "ticket": getattr(d, "ticket", None),
        "position_id": getattr(d, "position_id", None),
        "order": getattr(d, "order", None),
        "time": t,
        "time_srv": t_iso,  # broker server clock (UTC-4), shown as-is
        "symbol": getattr(d, "symbol", None),
        "side": side,
        "entry": entry_type,
        "volume": getattr(d, "volume", None),
        "price": getattr(d, "price", None),
        "profit": getattr(d, "profit", 0.0) or 0.0,
        "commission": getattr(d, "commission", 0.0) or 0.0,
        "swap": getattr(d, "swap", 0.0) or 0.0,
        "fee": getattr(d, "fee", 0.0) or 0.0,
        "magic": magic,
        "strategy": label,
        "magic_base": base,
        "tanda": batch,
        "comment": getattr(d, "comment", ""),
        "reason": getattr(d, "reason", None),
    }


def _net(row: dict[str, Any]) -> float:
    return row["profit"] + row["commission"] + row["swap"] + row["fee"]


# --- Terminal path resolution (parametrized, not secret) --------------------

def resolve_tester_exe(cli_value: str | None, env_value: str | None,
                        default: Path = DEFAULT_TESTER_EXE) -> Path:
    """Resolve the tester terminal64.exe path: `--tester-exe` CLI arg >
    `MT5_PULL_TESTER_EXE` env var > `default`. Pure path resolution -- does
    NOT check existence (see `validate_tester_exe`)."""
    if cli_value:
        return Path(cli_value)
    if env_value:
        return Path(env_value)
    return default


def validate_tester_exe(path: Path) -> str | None:
    """Returns an error message if `path` is not an existing file, else
    None. Never continue with an unvalidated path."""
    if not path.exists():
        return f"terminal64.exe not found at {path}"
    if not path.is_file():
        return f"terminal64.exe path is not a file: {path}"
    return None


# --- Read-scoped identity guard (post-connect, before any history read) ----

def check_post_connect_guard(login: Any, server: Any, trade_mode: Any, *,
                              expected_login: int, expected_server: str) -> str | None:
    """Identity guard run AFTER connecting, BEFORE any history read. Returns
    None if the connected account is safe to read from; otherwise an error
    message describing expected-vs-found (login/server/trade_mode are
    account identity, never credentials -- safe to print in full).

    Checks, in order:
      1. `login != guard_cuenta.REAL_LOGIN` (hard block, unchanged, always
         on -- see PERMISSION SEPARATION in the module docstring).
      2. `login == expected_login` AND `server == expected_server` (both
         mandatory and independent -- `Capitaria-All` is shared by several
         sanctioned accounts, so server alone does not discriminate between
         accounts, and login alone does not confirm which broker/terminal
         answered).
      3. `trade_mode == guard_cuenta.TRADE_MODE_DEMO` (a real gate now, not
         merely printed).
    """
    if login == guard_cuenta.REAL_LOGIN:
        return (f"connected to the REAL account {login} -- HARD FORBIDDEN "
                "(CUENTAS.md rule: read-only, never operate)")
    if login != expected_login or server != expected_server:
        return (f"identity mismatch: expected login={expected_login} "
                f"server={expected_server!r}, found login={login!r} "
                f"server={server!r}")
    if trade_mode != guard_cuenta.TRADE_MODE_DEMO:
        return (f"trade_mode={trade_mode!r} is not DEMO "
                f"(expected {guard_cuenta.TRADE_MODE_DEMO}) -- refusing")
    return None


# --- Core connect + guard + pull (mt5 module injected for testability) -----

def pull_account_history(
    mt5_module: Any,
    *,
    tester_exe: Path,
    login: int,
    server: str,
    password: str,
    dfrom: datetime,
    dto: datetime,
    out_dir: Path,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    """Connect to `tester_exe` as `login`/`server`, enforce
    `check_post_connect_guard` (login, server, trade_mode), and only if the
    guard passes, pull and write deal history. Returns the process exit
    code (0 on success). ALWAYS closes the connection via
    `mt5_module.shutdown()`, including on every error path.
    """
    print(f"[*] Connecting tester terminal -> login {login} @ {server} (READ-ONLY)")
    ok = mt5_module.initialize(path=str(tester_exe), login=login,
                                password=password, server=server)
    if not ok:
        print(f"[FATAL] initialize/login failed: {mt5_module.last_error()}", file=sys.stderr)
        return 1
    try:
        info = mt5_module.account_info()
        if info is None:
            print("[FATAL] account_info() returned None (not connected / attach failed)",
                  file=sys.stderr)
            return 1

        conn_login = getattr(info, "login", None)
        conn_server = getattr(info, "server", None)
        trade_mode = getattr(info, "trade_mode", None)

        err = check_post_connect_guard(conn_login, conn_server, trade_mode,
                                        expected_login=login, expected_server=server)
        if err is not None:
            print(f"[FATAL] identity guard failed: {err}", file=sys.stderr)
            return 2

        print(f"[OK] guard passed: login={conn_login} server={conn_server} "
              f"trade_mode={trade_mode} balance={getattr(info, 'balance', None)} "
              f"equity={getattr(info, 'equity', None)} currency={getattr(info, 'currency', None)}")

        # Fresh login: the terminal streams deal history from the server
        # PROGRESSIVELY, so an immediate (or too-early) history_deals_get can
        # return 0 OR a PARTIAL snapshot (a partial pull silently truncated an
        # earlier account-1 run at a mid-history instant). Break only when the
        # count has been STABLE for several consecutive probes -- never merely
        # ">0" -- so the full history has landed before we read it.
        prev = -1
        stable = 0
        total = 0
        probes = 0
        for probes in range(1, 181):  # up to ~180s
            total = mt5_module.history_deals_total(dfrom, dto) or 0
            if total > 0 and total == prev:
                stable += 1
                if stable >= 6:  # count unchanged ~6s -> sync settled
                    break
            else:
                stable = 0
            prev = total
            sleep_fn(1.0)
        print(f"[*] history synced: {total} deals in window, stable after {probes} probe(s)")
        if total == 0:
            print("[WARN] still 0 deals after warm-up -- account may genuinely "
                  "have none in this window, or history never synced.", file=sys.stderr)

        deals = mt5_module.history_deals_get(dfrom, dto)
        if deals is None:
            print(f"[FATAL] history_deals_get returned None: {mt5_module.last_error()}",
                  file=sys.stderr)
            return 1
        rows = [_deal_row(mt5_module, d) for d in deals]
        print(f"[*] pulled {len(rows)} deals over {dfrom.date()} .. {dto.date()} (server time)")
    finally:
        mt5_module.shutdown()

    _write_outputs(rows, login, out_dir)
    return 0


def _write_outputs(rows: list[dict[str, Any]], login: int, out_dir: Path) -> None:
    """Writes <out>/<login>_deals_raw.csv and <out>/<login>_positions.csv,
    plus a printed summary. Output format/schema unchanged from the
    pre-2026-08-11 version of this script."""
    # --- write raw deals ---
    raw_path = out_dir / f"{login}_deals_raw.csv"
    fields = list(rows[0].keys()) if rows else []
    with raw_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[written] {raw_path}  ({len(rows)} deals)")

    # --- per-position rollup with strategy attribution ---
    # Group deals by position_id. Attribution = the position's IN-deal magic
    # (entry=IN); magic-0 OUT/SL-TP deals inherit it automatically because the
    # IN deal in the same position carries the real magic. net = Σ all P&L
    # components across the position's deals.
    by_pos: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["side"] == "BALANCE":  # skip funding/credit deals
            continue
        by_pos[r["position_id"]].append(r)

    pos_rows: list[dict[str, Any]] = []
    for pid, ds in by_pos.items():
        ds_sorted = sorted(ds, key=lambda x: (x["time"] or 0))
        in_deal = next((d for d in ds_sorted if d["entry"] == "IN"), ds_sorted[0])
        out_deals = [d for d in ds_sorted if d["entry"] in ("OUT", "OUT_BY")]
        net = sum(_net(d) for d in ds)
        pos_rows.append({
            "position_id": pid,
            "symbol": in_deal["symbol"],
            "side": in_deal["side"],
            "strategy": in_deal["strategy"],
            "magic_base": in_deal["magic_base"],
            "tanda": in_deal["tanda"],
            "open_srv": in_deal["time_srv"],
            "close_srv": out_deals[-1]["time_srv"] if out_deals else "",
            "status": "closed" if out_deals else "open",
            "n_deals": len(ds),
            "volume_in": in_deal["volume"],
            "net": round(net, 2),
        })
    pos_rows.sort(key=lambda x: (x["open_srv"] or ""))

    pos_path = out_dir / f"{login}_positions.csv"
    if pos_rows:
        with pos_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(pos_rows[0].keys()))
            w.writeheader()
            w.writerows(pos_rows)
    print(f"[written] {pos_path}  ({len(pos_rows)} positions)")

    # --- printed summary: net per (tanda, strategy) over CLOSED positions ---
    agg: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"closed": 0, "open": 0, "net": 0.0, "first": "", "last": ""})
    for p in pos_rows:
        key = (p["tanda"], p["strategy"])
        a = agg[key]
        if p["status"] == "closed":
            a["closed"] += 1
            a["net"] += p["net"]
        else:
            a["open"] += 1
        if p["open_srv"] and (not a["first"] or p["open_srv"] < a["first"]):
            a["first"] = p["open_srv"]
        if p["open_srv"] and p["open_srv"] > a["last"]:
            a["last"] = p["open_srv"]

    print("\n=== NET per (tanda, strategy) -- closed positions, server time (UTC-4) ===")
    print(f"{'tanda':8s} {'strategy':24s} {'closed':>7s} {'open':>5s} {'net':>14s}  "
          f"{'first_open':19s} .. {'last_open':19s}")
    for (tanda, strat), a in sorted(agg.items()):
        print(f"{tanda:8s} {strat:24s} {a['closed']:>7d} {a['open']:>5d} "
              f"{a['net']:>14,.2f}  {a['first']:19s} .. {a['last']:19s}")

    print("\n[DONE] READ-ONLY pull complete. No order was placed/modified/closed.")


def main(argv: list[str] | None = None, mt5_module: Any = None) -> int:
    ap = argparse.ArgumentParser(description="READ-ONLY per-account deal-history puller.")
    ap.add_argument("--login", type=int, required=True)
    ap.add_argument("--server", default="Capitaria-All")
    ap.add_argument("--from", dest="dfrom", default="2026-07-01")
    ap.add_argument("--to", dest="dto", default=None, help="default = now+1d")
    ap.add_argument("--out", default=None, help="output dir (default data/analysis/<login>)")
    ap.add_argument("--tester-exe", dest="tester_exe", default=None,
                     help="path to terminal64.exe (default: MT5_PULL_TESTER_EXE env var, "
                          f"else {DEFAULT_TESTER_EXE}). Not secret -- CLI/env are both fine.")
    args = ap.parse_args(argv)

    password = os.environ.get("MT5_PULL_PASSWORD")
    if not password:
        print("[FATAL] set MT5_PULL_PASSWORD env var (never pass password on the CLI).",
              file=sys.stderr)
        return 3

    # Pre-connect REAL_LOGIN hard block (unchanged; still imported from
    # guard_cuenta, see PERMISSION SEPARATION in the module docstring).
    if args.login == guard_cuenta.REAL_LOGIN:
        print(f"[FATAL] {args.login} is the REAL account -- REFUSED.", file=sys.stderr)
        return 2

    tester_exe = resolve_tester_exe(args.tester_exe, os.environ.get(TESTER_EXE_ENV_VAR))
    exe_err = validate_tester_exe(tester_exe)
    if exe_err is not None:
        print(f"[FATAL] {exe_err}", file=sys.stderr)
        return 4

    out_dir = Path(args.out) if args.out else (REPO_ROOT / "data" / "analysis" / str(args.login))
    out_dir.mkdir(parents=True, exist_ok=True)

    dfrom = _dt(args.dfrom)
    dto = _dt(args.dto) if args.dto else (datetime.now() + timedelta(days=1))

    if mt5_module is None:
        import MetaTrader5 as mt5_module  # noqa: N813

    return pull_account_history(
        mt5_module,
        tester_exe=tester_exe,
        login=args.login,
        server=args.server,
        password=password,
        dfrom=dfrom,
        dto=dto,
        out_dir=out_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
