"""sentinel_engine.live.reconciler -- pure recompute-and-reconcile core for the
guarded live executor (SENTINEL, 2026-07-13). ORDER-CAPABLE ADJACENT: this
module decides WHAT to do; it never talks to MT5 or sends anything. The daemon
(`scripts/live/run_live_20.py`) executes the returned actions (dry-run logs
them, --arm sends them), always behind `guard_cuenta.assert_demo`.

DESIGN (parity-by-construction)
-------------------------------
The sim (`simular_variant`) is close-driven: on each newly CLOSED bar it yields
the exact set of open fichas (F1/F2/F3), their side, entry price and CURRENT
stop -- obtained via `simular_variant(..., return_state=True)`. Per the TOKATA
per-ficha magic convention, ficha FN of a config lives at `base_magic + N`
(F1=+1, F2=+2, F3=+3). We diff that DESIRED state against the ACTUAL MT5
positions filtered to `[base+1 .. base+3]`, one position per ficha slot, and
emit:
  - OPEN   : a desired ficha has no live position (market order, that side).
  - CLOSE  : a live position exists whose ficha slot is NOT desired (orphan).
  - MODIFY : a desired ficha IS open but its live SL differs from the sim's
             current SL by more than `sl_tol` (position modify / trailing).
  - NOOP   : desired == actual within tolerance.

Fills happen at the next tick AFTER bar close (the sim is close-driven); the
shadow-parity checker already tolerates spread + 1 tick, so this is expected,
not a divergence.

SAFETY CAPS (enforced HERE, re-checked by the daemon):
  - `MAX_VOLUME` per ficha = 0.10; any computed volume above it -> the OPEN
    action is REJECTED (kind REJECT_VOLUME), never silently clamped.
  - `MAX_FICHAS_PER_CONFIG` = 3, `MAX_FICHAS_TOTAL` = 60: OPENs beyond the cap
    are REJECTED (kind REJECT_CAP).
  - Kill-switch: when `kill_switch=True`, OPEN actions are suppressed
    (converted to SUPPRESSED_OPEN, logged, not sent); CLOSE and MODIFY of
    EXISTING positions still proceed (we never abandon risk management), and
    all logging continues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_VOLUME = 0.10
MAX_FICHAS_PER_CONFIG = 3
MAX_FICHAS_TOTAL = 60
FICHA_TAGS = ("F1", "F2", "F3")
FICHA_OFFSET = {"F1": 1, "F2": 2, "F3": 3}
# sim exit events carry lado already as "L"/"S"; keep a permissive normalizer.
_SIDE_NORM_L = {"L": "L", "S": "S", "LONG": "L", "SHORT": "S", "BUY": "L", "SELL": "S"}


@dataclass
class Action:
    kind: str            # OPEN | CLOSE | MODIFY | NOOP | REJECT_VOLUME |
                         # REJECT_CAP | SUPPRESSED_OPEN | SAME_BAR_EXIT_FALLBACK |
                         # MISSING_SL_ALARM
    config_id: str
    magic: int           # the per-ficha magic (base + offset)
    ficha: str           # F1/F2/F3
    side: str | None = None   # "L"/"S" for OPEN
    volume: float | None = None
    price_ref: float | None = None   # sim entry/stop reference (for logs)
    sl: float | None = None          # desired SL (OPEN/MODIFY)
    ticket: int | None = None        # live position ticket (CLOSE/MODIFY)
    sim_fill: float | None = None    # SAME_BAR_EXIT_FALLBACK: sim's exit level
    motivo: str | None = None        # SAME_BAR_EXIT_FALLBACK: sim exit motivo
    reason: str = ""

    def sendable(self) -> bool:
        """True iff this action actually mutates the account (a market/SLTP
        order goes out). REJECT_*/SUPPRESSED_OPEN/NOOP/MISSING_SL_ALARM never
        touch the broker themselves (MISSING_SL_ALARM is paired with a MODIFY
        that does)."""
        return self.kind in ("OPEN", "CLOSE", "MODIFY", "SAME_BAR_EXIT_FALLBACK")


@dataclass
class ReconcileResult:
    config_id: str
    base_magic: int
    bar_t: int | None
    actions: list[Action] = field(default_factory=list)

    @property
    def sendable_actions(self) -> list[Action]:
        return [a for a in self.actions if a.sendable()]


def _norm_side(s: Any) -> str:
    """Normalize a live position 'type'/side to 'L'/'S'.
    Accepts 0/1 (MT5 POSITION_TYPE_BUY/SELL), 'BUY'/'SELL', 'LONG'/'SHORT',
    'L'/'S'."""
    if s in (0, "0"):
        return "L"
    if s in (1, "1"):
        return "S"
    t = str(s).upper()
    if t in ("L", "LONG", "BUY"):
        return "L"
    if t in ("S", "SHORT", "SELL"):
        return "S"
    return "?"


def _split_snapshot(snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]],
                                                       dict[str, dict[str, Any]]]:
    """Accept either the rich snapshot from `simular_variant(return_state=True)`
    ({"open":..., "last_bar_exits":..., "last_idx":...}) OR a bare open-state
    dict (back-compat for direct callers/tests). Returns (open_state,
    last_bar_exits)."""
    if snapshot and "open" in snapshot and "last_bar_exits" in snapshot:
        return snapshot["open"] or {}, snapshot["last_bar_exits"] or {}
    return snapshot or {}, {}


def reconcile(
    config_id: str,
    base_magic: int,
    desired_state: dict[str, Any],
    live_positions: list[dict[str, Any]],
    *,
    volume: float = 0.01,
    bar_t: int | None = None,
    sl_tol: float = 0.05,
    kill_switch: bool = False,
    total_open_fichas: int = 0,
    contract_size: float = 100.0,
) -> ReconcileResult:
    """Diff DESIRED (from `simular_variant(return_state=True)`) vs ACTUAL live
    positions for ONE config, returning the ordered action list.

    Parameters
    ----------
    desired_state : {"F1"|"F2"|"F3": {"side","entry","sl", ...}}
        The sim's open fichas at the last CLOSED bar. Absent tag = should be
        flat.
    live_positions : list of dicts with keys at least
        {"ticket","magic","type"|"side","volume","sl"}. Only positions whose
        magic is in the config's ficha band are considered; callers SHOULD
        pre-filter, but we defensively filter again here.
    volume : per-ficha order volume (config-level; capped at MAX_VOLUME).
    sl_tol : absolute price tolerance below which a SL difference is NOOP
        (avoids modify-thrash on sub-tick noise).
    kill_switch : suppress OPENs (still allow CLOSE/MODIFY + logging).
    total_open_fichas : count of live fichas already open ACROSS ALL configs,
        used for the 60-total cap. Incremented by the caller per OPEN it lets
        through.

    Ordering: CLOSE (orphans) first, then MODIFY, then OPEN -- so freed slots
    and risk reductions are applied before we add exposure.
    """
    res = ReconcileResult(config_id=config_id, base_magic=base_magic, bar_t=bar_t)
    open_state, last_bar_exits = _split_snapshot(desired_state)

    band = {base_magic + off for off in FICHA_OFFSET.values()}
    # index live positions by ficha tag (via magic offset); ignore anything
    # outside this config's band.
    live_by_tag: dict[str, dict[str, Any]] = {}
    off_to_tag = {off: tag for tag, off in FICHA_OFFSET.items()}
    for p in live_positions:
        m = p.get("magic")
        if m not in band:
            continue
        tag = off_to_tag[m - base_magic]
        # if two positions share a slot (shouldn't happen), keep first, flag
        if tag in live_by_tag:
            res.actions.append(Action(
                "CLOSE", config_id, m, tag, ticket=p.get("ticket"),
                reason=f"duplicate live position in slot {tag} -- closing extra"))
            continue
        live_by_tag[tag] = p

    running_total = total_open_fichas

    # ---- 1) CLOSE orphans: live position whose ficha is NOT desired ----
    # Two flavors:
    #   (a) SAME_BAR_EXIT_FALLBACK -- the sim exited this ficha DURING the just
    #       -closed bar (present in last_bar_exits) using that bar's own high/AC.
    #       Live's server-side SL sat at the prior bar's level so the broker did
    #       NOT stop it out mid-bar. Close at MARKET (next tick) and record the
    #       by-design price gap (sim exit level vs live market fill) + its $
    #       cost. NOT a divergence -- "same-bar optimism, by design".
    #   (b) plain orphan -- the ficha was already flat in the sim before this
    #       bar (a stale live position); ordinary CLOSE.
    for tag in FICHA_TAGS:
        if tag in live_by_tag and tag not in open_state:
            p = live_by_tag[tag]
            magic = base_magic + FICHA_OFFSET[tag]
            ex = last_bar_exits.get(tag)
            if ex is not None:
                # by-design same-bar exit: sim fill level known; live market
                # fill isn't yet (daemon fills it in on send). Cost is measured
                # against the sim level using the ficha's own entry side.
                side = _SIDE_NORM_L.get(str(ex.get("side")).upper(), "?")
                res.actions.append(Action(
                    "SAME_BAR_EXIT_FALLBACK", config_id, magic, tag,
                    side=side, ticket=p.get("ticket"), volume=p.get("volume"),
                    sim_fill=ex.get("price"), motivo=ex.get("motivo"),
                    reason=("sim exited this ficha WITHIN the just-closed bar "
                            f"({ex.get('motivo')} @ {ex.get('price')}); live SL "
                            "was at prior-bar level -> market-close next tick "
                            "(same-bar optimism, by design)")))
            else:
                res.actions.append(Action(
                    "CLOSE", config_id, magic, tag,
                    ticket=p.get("ticket"), volume=p.get("volume"),
                    reason="sim has this ficha flat; live position orphaned"))

    # ---- 2) MODIFY: desired ficha is open but live SL drifted ----
    for tag in FICHA_TAGS:
        if tag in open_state and tag in live_by_tag:
            d = open_state[tag]
            p = live_by_tag[tag]
            # defensive side check: a live position on the wrong side for this
            # slot is an inconsistency -> close it (reconcile re-opens next).
            if _norm_side(p.get("type", p.get("side"))) != d["side"]:
                res.actions.append(Action(
                    "CLOSE", config_id, base_magic + FICHA_OFFSET[tag], tag,
                    ticket=p.get("ticket"), volume=p.get("volume"),
                    reason=f"live side {p.get('type', p.get('side'))} != sim "
                           f"side {d['side']} -- closing to re-sync"))
                # treat slot as now-empty so the OPEN pass re-opens it
                del live_by_tag[tag]
                continue
            desired_sl = d.get("sl")
            live_sl = p.get("sl")
            # ALARM: a live ficha MUST carry a real server-side SL at all times
            # (intra-bar stop protection). A None/0 live SL is an alarm the
            # daemon must log loudly; the paired MODIFY below installs it.
            if live_sl is None or float(live_sl) == 0.0:
                res.actions.append(Action(
                    "MISSING_SL_ALARM", config_id, base_magic + FICHA_OFFSET[tag],
                    tag, side=d["side"], sl=desired_sl, ticket=p.get("ticket"),
                    reason="OPEN ficha has NO server-side SL -- intra-bar stop "
                           "protection absent; installing now"))
            if desired_sl is not None and (
                    live_sl is None or float(live_sl) == 0.0
                    or abs(float(live_sl) - float(desired_sl)) > sl_tol):
                res.actions.append(Action(
                    "MODIFY", config_id, base_magic + FICHA_OFFSET[tag], tag,
                    side=d["side"], sl=desired_sl, ticket=p.get("ticket"),
                    price_ref=d.get("entry"),
                    reason=f"trail SL {live_sl} -> {desired_sl}"))
            else:
                res.actions.append(Action(
                    "NOOP", config_id, base_magic + FICHA_OFFSET[tag], tag,
                    side=d["side"], sl=desired_sl, ticket=p.get("ticket"),
                    reason="in sync"))

    # ---- 3) OPEN: desired ficha with no live position ----
    for tag in FICHA_TAGS:
        if tag in open_state and tag not in live_by_tag:
            d = open_state[tag]
            magic = base_magic + FICHA_OFFSET[tag]
            # volume cap: reject, never clamp.
            if volume > MAX_VOLUME:
                res.actions.append(Action(
                    "REJECT_VOLUME", config_id, magic, tag, side=d["side"],
                    volume=volume, sl=d.get("sl"), price_ref=d.get("entry"),
                    reason=f"volume {volume} > MAX_VOLUME {MAX_VOLUME}"))
                continue
            # total-fichas cap (60 across all configs).
            if running_total >= MAX_FICHAS_TOTAL:
                res.actions.append(Action(
                    "REJECT_CAP", config_id, magic, tag, side=d["side"],
                    volume=volume, sl=d.get("sl"), price_ref=d.get("entry"),
                    reason=f"total open fichas {running_total} >= "
                           f"MAX_FICHAS_TOTAL {MAX_FICHAS_TOTAL}"))
                continue
            if kill_switch:
                res.actions.append(Action(
                    "SUPPRESSED_OPEN", config_id, magic, tag, side=d["side"],
                    volume=volume, sl=d.get("sl"), price_ref=d.get("entry"),
                    reason="kill-switch active (STOP file present)"))
                continue
            res.actions.append(Action(
                "OPEN", config_id, magic, tag, side=d["side"], volume=volume,
                sl=d.get("sl"), price_ref=d.get("entry"),
                reason="sim has this ficha open; no live position"))
            running_total += 1

    return res
