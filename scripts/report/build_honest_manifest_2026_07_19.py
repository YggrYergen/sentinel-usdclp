"""scripts/report/build_honest_manifest_2026_07_19.py -- deterministic
generator for the honest mega-sweep manifest (Task B3a, honest program).

Builds `scripts/report/honest_manifest_2026_07_19.json`, the manifest the
honest-sweep harness (`scripts/report/gen_honest_sweep.py`) consumes for the
overnight re-judgement of the research corpus under honest fills
(`live_fill_mode=True`) + flat $0.50/round-trip friction.

EVERY kwargs dict is IMPORTED from the canonical tables -- nothing is
hand-copied:

  S1  honest twins of the live-4 (catalog IV.G.8, P7)
      <- sentinel_engine.strategies.live_configs_20.CONFIGS_LIVE
  S2  D90-13 distilled set re-run (IV.G.1)
      <- gen_livefill_bound.CONFIGS via config_kwargs()/config_tf()
  S3  D90-uncovered 7 (IV.G.2)
      <- live_configs_20.CONFIGS_LIVE (live ones) / CONFIGS_20 (rest);
         V10-* DEFER (runtime SuperTrend-M15 direction_mask, see _deferred)
  S4  batch-7 super-stacks (IV.G.3)
      <- gen_variant_batch7.STACK_SHAPES x AC_FACTOR_GRID x TFS (24)
  S5  V-07 AC-decel runner exit (IV.G.4)
      <- champion skeleton (gen_livefill_bound.skeleton_kwargs) +
         f3_ac_decel_exit=True + the engine's documented default
         f3_ac_decel_bars (cross-checked against gen_variant_batch3's
         V07_BARS_GRID and the batch-3 report's chosen bars=2)
  S6  Tier-A trail_atr_floor_k x ac_modulate grid on the live-4 (Task B3);
      the (ac_modulate=False, k=1.5) cell is the FIXED4 twin (asserted
      equal to live_configs_20.CONFIGS_SHADOW kwargs)
  S7  TP/BE grid on the 4 FIXED4 configs <- live_configs_20.CONFIGS_SHADOW
  S8  deferred items (spec-listed 4 + the 2 V10 direction-mask deferrals)
      -> written under "_deferred" (harness ignores "_"-prefixed keys)

Fixed rules (orchestrator spec, transcribed exactly):
  - Windows per TF: M1/M2 -> [IW, W1, W2]; M5/M15 -> [IW, W1, W2, W3]
    (lake fact: no M2-tier W3 bars). Keys/order from
    gen_livefill_bound.WINDOW_KEYS.
  - Every entry's kwargs include live_fill_mode=True.
  - variant_id = HON-<section>-<slug>-<tf>, deterministic, unique, <=64.
  - Every entry has prereg {hypothesis, metric: net_honest, threshold}.
  - FAIL LOUDLY on any unresolvable import/lookup -- no silent drops.

Validation performed on every entry (fail-loudly, before writing):
  - kwargs contain no key outside inspect.signature(simular_variant)
    (minus `bars`; `symbol` is stripped -- the harness supplies it);
  - a real Signature.bind() mirroring the harness call
    `simular_variant(bars, symbol=SYMBOL, **kwargs)` succeeds;
  - no duplicate variant_ids across the whole manifest.

CLI:
    python -m scripts.report.build_honest_manifest_2026_07_19 [--summary]
        [--out scripts/report/honest_manifest_2026_07_19.json]

Always (re)writes the JSON deterministically; --summary additionally prints
the full coverage matrix (entries per section, cells per window, deferred).
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import inspect
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies import live_configs_20 as _lc  # noqa: E402


def _load_module(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    if spec is None or spec.loader is None:
        raise ManifestBuildError(f"cannot load canonical module {rel!r}")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ManifestBuildError(RuntimeError):
    """Raised loudly whenever a canonical table/lookup cannot be resolved."""


# Canonical script-module tables (same importlib pattern the harness uses).
_LF = _load_module("gen_livefill_bound", "scripts/report/gen_livefill_bound.py")
_B7 = _load_module("gen_variant_batch7", "scripts/report/gen_variant_batch7.py")
_B3 = _load_module("gen_variant_batch3", "scripts/report/gen_variant_batch3.py")

OUT_DEFAULT = ROOT / "scripts" / "report" / "honest_manifest_2026_07_19.json"

_SIG = inspect.signature(simular_variant)
# Keyword names simular_variant accepts (everything but the positional bars).
_VALID_KW = {n for n in _SIG.parameters if n != "bars"}
SYMBOL = "XAUUSD"

# ---------------------------------------------------------------------------
# Windows per TF (orchestrator fixed rule; keys/order from the live-fill
# runner's canonical WINDOW_KEYS -- lake fact: no M2-tier W3 bars, so the
# M1/M2 tier drops W3).
# ---------------------------------------------------------------------------
WINDOW_KEYS: tuple[str, ...] = tuple(_LF.WINDOW_KEYS)
if WINDOW_KEYS != ("IW", "W1", "W2", "W3"):
    raise ManifestBuildError(
        f"gen_livefill_bound.WINDOW_KEYS drifted: {WINDOW_KEYS!r} -- the "
        "fixed windows-per-TF rule no longer applies, refusing to guess"
    )
_NO_W3_TFS = ("M1", "M2")


def windows_for(tf: str) -> list[str]:
    return [w for w in WINDOW_KEYS if not (tf in _NO_W3_TFS and w == "W3")]


# ---------------------------------------------------------------------------
# kwargs cleaning + validation (mirrors the harness call EXACTLY).
# ---------------------------------------------------------------------------
def _json_safe(v: Any) -> Any:
    if isinstance(v, tuple):
        return list(v)
    if isinstance(v, (set, frozenset)):
        return sorted(v)
    return v


def _clean_kwargs(kwargs: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Strip harness-supplied keys, JSON-normalize, force live_fill_mode=True,
    and validate against simular_variant's real signature. Fails loudly."""
    kw = dict(kwargs)
    sym = kw.pop("symbol", None)
    if sym is not None and sym != SYMBOL:
        raise ManifestBuildError(f"{source}: unexpected symbol {sym!r} != {SYMBOL!r}")
    if "direction_mask" in kw:
        raise ManifestBuildError(
            f"{source}: direction_mask is runtime bar-aligned data, not a "
            "static manifest kwarg -- this config must be deferred instead"
        )
    kw = {k: _json_safe(v) for k, v in kw.items()}
    kw["live_fill_mode"] = True

    unknown = sorted(set(kw) - _VALID_KW)
    if unknown:
        raise ManifestBuildError(
            f"{source}: kwargs not accepted by simular_variant: {unknown}"
        )
    try:
        # Mirrors gen_honest_sweep._price_cell: simular_variant(bars, symbol=..., **kw)
        _SIG.bind([], symbol=SYMBOL, **kw)
    except TypeError as exc:
        raise ManifestBuildError(f"{source}: signature bind failed: {exc}") from exc
    return kw


def _slug(cfg_id: str, tf: str) -> str:
    """Deterministic slug: uppercase id, minus a FIXED4 '-F' suffix, minus a
    trailing '-<TF>' (the tf is appended separately in the variant_id)."""
    s = cfg_id.upper()
    if s.endswith("-F"):
        s = s[: -len("-F")]
    suffix = "-" + tf.upper()
    if s.endswith(suffix):
        s = s[: -len(suffix)]
    return s


def _entry(
    section: str, slug: str, tf: str, kwargs: dict[str, Any], *,
    hypothesis: str, threshold: float | None, baseline_ref: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    variant_id = f"HON-{section}-{slug}-{tf}"
    if len(variant_id) > 64:
        raise ManifestBuildError(f"variant_id too long (> 64): {variant_id!r}")
    prereg: dict[str, Any] = {
        "hypothesis": hypothesis, "metric": "net_honest", "threshold": threshold,
    }
    if baseline_ref is not None:
        prereg["baseline_ref"] = baseline_ref
    entry: dict[str, Any] = {
        "variant_id": variant_id,
        "section": section,
        "tf": tf,
        "kwargs": _clean_kwargs(kwargs, source=variant_id),
        "windows": windows_for(tf),
        "prereg": prereg,
    }
    if tag is not None:
        entry["tag"] = tag
    return entry


# ---------------------------------------------------------------------------
# S1 -- honest twins of the live-4 (CONFIGS_LIVE verbatim + live_fill_mode).
# ---------------------------------------------------------------------------
def build_s1() -> list[dict[str, Any]]:
    entries = []
    for cfg in _lc.CONFIGS_LIVE:
        slug = _slug(cfg["id"], cfg["tf"])
        entries.append(_entry(
            "S1", slug, cfg["tf"], cfg["kwargs"],
            hypothesis=(
                f"Baseline reference (IV.G.8/P7): live-roster config {cfg['id']} "
                f"({cfg['tf']}) re-priced VERBATIM under honest fills "
                "(live_fill_mode=True) + flat $0.50/round-trip friction. "
                "Reference row -- no pass/fail threshold; anchors the S6 grid."
            ),
            threshold=None,
        ))
    if len(entries) != 4:
        raise ManifestBuildError(f"S1: expected 4 CONFIGS_LIVE twins, got {len(entries)}")
    return entries


# ---------------------------------------------------------------------------
# S2 -- D90-13 distilled set (gen_livefill_bound.CONFIGS via config_kwargs).
# ---------------------------------------------------------------------------
def build_s2() -> list[dict[str, Any]]:
    entries = []
    for cfg_id in _LF.CONFIGS:
        tf = _LF.config_tf(cfg_id)
        entries.append(_entry(
            "S2", _slug(cfg_id, tf), tf, _LF.config_kwargs(cfg_id),
            hypothesis=(
                f"IV.G.1: D90-13 distilled config {cfg_id} ({tf}; its own "
                "classic-fill run in the D90 live-fill bound report is the "
                "named baseline) survives honest fills + flat $0.50/round-trip "
                "friction: net_honest > 0 on each covered window."
            ),
            threshold=0.0,
        ))
    if len(entries) != 13:
        raise ManifestBuildError(f"S2: expected 13 configs, got {len(entries)}")
    return entries


# ---------------------------------------------------------------------------
# S3 -- D90-uncovered 7 (CONFIGS_LIVE for the live ones, CONFIGS_20 for the
# rest; direction-filter configs are deferred, never guessed).
# ---------------------------------------------------------------------------
S3_IDS = ("V10-M15", "V15-M15", "V09-CTRL-M15", "V11-M2", "V10-M5", "V13-M2",
          "V09-CTRL-M5")


def build_s3() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_id = {c["id"]: c for c in _lc.CONFIGS_20}
    live_ids = set(_lc.LIVE_ROSTER)
    entries: list[dict[str, Any]] = []
    deferred: list[dict[str, str]] = []
    missing = [i for i in S3_IDS if i not in by_id]
    if missing:
        raise ManifestBuildError(f"S3: ids not found in CONFIGS_20: {missing}")
    for cid in S3_IDS:
        cfg = by_id[cid]
        if cfg.get("direction_filter"):
            deferred.append({
                "item": f"S3 {cid}",
                "reason": (
                    "requires a runtime SuperTrend(14,3.0)-M15 previous-closed-"
                    "bar direction_mask (bar-aligned data computed per window by "
                    "gen_oow_validation.compute_direction_mask) -- not "
                    "expressible as a static manifest kwarg and the honest-sweep "
                    "harness computes no mask; running without it would judge a "
                    "different config (plain V06B), so deferred, not guessed."
                ),
            })
            continue
        source = "CONFIGS_LIVE" if cid in live_ids else "CONFIGS_20"
        entries.append(_entry(
            "S3", _slug(cid, cfg["tf"]), cfg["tf"], cfg["kwargs"],
            hypothesis=(
                f"IV.G.2: D90-uncovered config {cid} ({cfg['tf']}; kwargs from "
                f"live_configs_20.{source}, its classic-fill validation run is "
                "the named baseline) survives honest fills + flat "
                "$0.50/round-trip friction: net_honest > 0 on each covered "
                "window."
            ),
            threshold=0.0,
        ))
    if len(entries) + len(deferred) != len(S3_IDS):
        raise ManifestBuildError(
            f"S3: {len(entries)} entries + {len(deferred)} deferred != {len(S3_IDS)}"
        )
    return entries, deferred


# ---------------------------------------------------------------------------
# S4 -- batch-7 super-stacks: STACK_SHAPES x AC_FACTOR_GRID x TFS = 24.
# ---------------------------------------------------------------------------
def build_s4() -> list[dict[str, Any]]:
    tfs = list(_B7.TFS)
    if tfs != ["M1", "M2", "M5", "M15"]:
        raise ManifestBuildError(f"S4: gen_variant_batch7.TFS drifted: {tfs!r}")
    entries = []
    for shape, lever in _B7.STACK_SHAPES.items():
        for factor in _B7.AC_FACTOR_GRID:
            for tf in tfs:
                kw = {**_B7.skeleton_kwargs(tf), **lever, "ac_modulate_factor": factor}
                ftag = f"F{factor:.2f}".replace(".", "P")
                standing = _B7.STANDING_BEST[tf]["label"]
                entries.append(_entry(
                    "S4", f"{shape}-{ftag}", tf, kw,
                    hypothesis=(
                        f"IV.G.3: batch-7 super-stack {shape} "
                        f"(levers={sorted(lever)}) at ac_modulate_factor={factor} "
                        f"on the champion skeleton ({tf}; named classic baseline: "
                        f"standing best '{standing}') survives honest fills + "
                        "flat $0.50/round-trip friction: net_honest > 0 on each "
                        "covered window."
                    ),
                    threshold=0.0,
                ))
    if len(entries) != 24:
        raise ManifestBuildError(f"S4: expected 24 stack combos, got {len(entries)}")
    return entries


# ---------------------------------------------------------------------------
# S5 -- V-07 AC-decel runner exit: champion skeleton + f3_ac_decel_exit=True
# + the engine's documented default bars (cross-checked against batch3).
# ---------------------------------------------------------------------------
def build_s5() -> list[dict[str, Any]]:
    bars_param = _SIG.parameters.get("f3_ac_decel_bars")
    if bars_param is None or bars_param.default is inspect.Parameter.empty:
        raise ManifestBuildError("S5: f3_ac_decel_bars has no documented default")
    bars_default = bars_param.default
    grid = tuple(_B3.V07_BARS_GRID)
    if bars_default not in grid:
        raise ManifestBuildError(
            f"S5: engine default f3_ac_decel_bars={bars_default!r} not in "
            f"gen_variant_batch3.V07_BARS_GRID={grid!r} -- documented bars "
            "param is ambiguous, refusing to guess"
        )
    entries = []
    for tf in ("M1", "M2", "M5", "M15"):
        kw = {**_LF.skeleton_kwargs(tf), "f3_ac_decel_exit": True,
              "f3_ac_decel_bars": bars_default}
        entries.append(_entry(
            "S5", "V07-ACDECEL", tf, kw,
            hypothesis=(
                f"IV.G.4: V-07 runner AC-decel exit (f3_ac_decel_exit=True, "
                f"f3_ac_decel_bars={bars_default}, the batch-3-documented "
                f"default/chosen value) on the champion skeleton ({tf}; named "
                "classic baseline: batch-3 V-07 best leg, a wash vs V-01b) "
                "survives honest fills + flat $0.50/round-trip friction: "
                "net_honest > 0 on each covered window."
            ),
            threshold=0.0,
        ))
    if len(entries) != 4:
        raise ManifestBuildError(f"S5: expected 4 TFs, got {len(entries)}")
    return entries


# ---------------------------------------------------------------------------
# S6 -- Tier-A grid on the live-4: trail_atr_floor_k x ac_modulate (8 combos
# per base config); the (False, 1.5) cell is the FIXED4 twin and must equal
# the CONFIGS_SHADOW kwargs exactly.
# ---------------------------------------------------------------------------
S6_FLOOR_GRID = (0.0, 1.5, 2.0, 3.0)
S6_AC_GRID = (True, False)


def build_s6() -> list[dict[str, Any]]:
    shadow_by_base = {c["id"]: c for c in _lc.CONFIGS_SHADOW}
    entries = []
    for cfg in _lc.CONFIGS_LIVE:
        tf = cfg["tf"]
        slug = _slug(cfg["id"], tf)
        s1_ref = f"HON-S1-{slug}-{tf}"
        for k in S6_FLOOR_GRID:
            for ac in S6_AC_GRID:
                kw = {**cfg["kwargs"], "trail_atr_floor_k": k, "ac_modulate": ac}
                ktag = "K" + f"{k:.1f}".replace(".", "P")
                actag = f"AC{1 if ac else 0}"
                tag = None
                if ac is False and k == 1.5:
                    tag = "FIXED4-twin"
                    shadow = shadow_by_base.get(cfg["id"] + "-F")
                    if shadow is None:
                        raise ManifestBuildError(
                            f"S6: no CONFIGS_SHADOW twin for {cfg['id']!r}"
                        )
                    want = _clean_kwargs(shadow["kwargs"], source=f"S6 twin {cfg['id']}")
                    got = _clean_kwargs(kw, source=f"S6 cell {cfg['id']} k=1.5 ac=False")
                    if got != want:
                        raise ManifestBuildError(
                            f"S6: FIXED4-twin cell for {cfg['id']} != "
                            f"CONFIGS_SHADOW kwargs: {got} vs {want}"
                        )
                entries.append(_entry(
                    "S6", f"{slug}-{ktag}-{actag}", tf, kw,
                    hypothesis=(
                        f"Tier-A grid (plan Task B3): trail_atr_floor_k={k}, "
                        f"ac_modulate={ac} on live config {cfg['id']} ({tf}) "
                        f"beats the config's own S1 honest baseline {s1_ref}: "
                        "net_honest > 0 and above baseline_ref."
                    ),
                    threshold=0.0, baseline_ref=s1_ref, tag=tag,
                ))
    if len(entries) != 32:
        raise ManifestBuildError(f"S6: expected 32 grid cells, got {len(entries)}")
    return entries


# ---------------------------------------------------------------------------
# S7 -- TP/BE grid on the 4 FIXED4 configs (CONFIGS_SHADOW):
# f1_tp_r x be_at_r minus the (None, None) base = 5 combos per config.
# None = kwarg left unset (engine default 0.0 = disabled); be_offset_pips
# stays default.
# ---------------------------------------------------------------------------
S7_TP_GRID = (None, 1.0, 1.5)
S7_BE_GRID = (None, 1.0)


def _num_tag(prefix: str, v: float | None) -> str:
    return f"{prefix}NONE" if v is None else prefix + f"{v:.1f}".replace(".", "P")


def build_s7() -> list[dict[str, Any]]:
    entries = []
    for cfg in _lc.CONFIGS_SHADOW:
        tf = cfg["tf"]
        slug = _slug(cfg["id"], tf)
        twin_ref = f"HON-S6-{slug}-K1P5-AC0-{tf}"
        for tp in S7_TP_GRID:
            for be in S7_BE_GRID:
                if tp is None and be is None:
                    continue
                kw = dict(cfg["kwargs"])
                if tp is not None:
                    kw["f1_tp_r"] = tp
                if be is not None:
                    kw["be_at_r"] = be
                entries.append(_entry(
                    "S7", f"{slug}-{_num_tag('TP', tp)}-{_num_tag('BE', be)}",
                    tf, kw,
                    hypothesis=(
                        f"TP/BE grid (plan Task B3): f1_tp_r={tp}, be_at_r={be} "
                        f"(None = engine default/disabled; be_offset_pips stays "
                        f"default) on FIXED4 config {cfg['id']} ({tf}) beats its "
                        f"FIXED4 twin {twin_ref}: net_honest > 0 and above "
                        "baseline_ref."
                    ),
                    threshold=0.0, baseline_ref=twin_ref,
                ))
    if len(entries) != 20:
        raise ManifestBuildError(f"S7: expected 20 grid cells, got {len(entries)}")
    return entries


# ---------------------------------------------------------------------------
# S8 -- spec-listed deferrals (verified against the engine signature where a
# missing kwarg is the stated reason).
# ---------------------------------------------------------------------------
def build_s8_deferred() -> list[dict[str, str]]:
    for forbidden in ("max_hold_bars", "time_stop_bars", "max_hold"):
        if forbidden in _SIG.parameters:
            raise ManifestBuildError(
                f"S8: simular_variant now HAS {forbidden!r} -- the P51 "
                "deferral reason no longer holds, update the manifest spec"
            )
    return [
        {"item": "P51 time-stop",
         "reason": "no max-hold kwarg exists on simular_variant"},
        {"item": "P34 SuperTrend p14x3",
         "reason": "not expressible via simular_variant kwargs -- needs its "
                   "own engine port"},
        {"item": "P46 ficha-count",
         "reason": "handled as volume post-processing in metrics, not "
                   "manifest cells"},
        {"item": "close-confirmed exit",
         "reason": "no close-confirmed-exit kwarg exists on simular_variant"},
    ]


# ---------------------------------------------------------------------------
# Assembly + validation + summary.
# ---------------------------------------------------------------------------
def build_manifest() -> dict[str, Any]:
    s1 = build_s1()
    s2 = build_s2()
    s3, s3_deferred = build_s3()
    s4 = build_s4()
    s5 = build_s5()
    s6 = build_s6()
    s7 = build_s7()
    deferred = s3_deferred + build_s8_deferred()

    entries = s1 + s2 + s3 + s4 + s5 + s6 + s7

    # Duplicate variant_id check (whole manifest).
    seen: set[str] = set()
    dupes = []
    for e in entries:
        if e["variant_id"] in seen:
            dupes.append(e["variant_id"])
        seen.add(e["variant_id"])
    if dupes:
        raise ManifestBuildError(f"duplicate variant_ids: {sorted(set(dupes))}")

    # Every baseline_ref must resolve to a real manifest entry.
    bad_refs = sorted({
        e["prereg"]["baseline_ref"] for e in entries
        if e["prereg"].get("baseline_ref") and e["prereg"]["baseline_ref"] not in seen
    })
    if bad_refs:
        raise ManifestBuildError(f"baseline_refs not in manifest: {bad_refs}")

    return {
        "_meta": {
            "generator": "scripts/report/build_honest_manifest_2026_07_19.py",
            "task": "B3a honest mega-sweep manifest (IV.G + Tier-A/TP-BE grids)",
            "harness": "scripts/report/gen_honest_sweep.py",
            "cost_model": "flat0.5",
            "windows_rule": "M1/M2 -> IW,W1,W2; M5/M15 -> IW,W1,W2,W3",
            "sections": {
                "S1": len(s1), "S2": len(s2), "S3": len(s3), "S4": len(s4),
                "S5": len(s5), "S6": len(s6), "S7": len(s7),
            },
        },
        "_deferred": deferred,
        "entries": entries,
    }


def _summary(manifest: dict[str, Any]) -> str:
    entries = manifest["entries"]
    lines = ["Honest mega-sweep manifest -- coverage matrix", ""]
    header = f"{'section':>8} {'entries':>8} " + " ".join(f"{w:>5}" for w in WINDOW_KEYS) + f" {'cells':>6}"
    lines.append(header)
    total_cells = 0
    win_totals = {w: 0 for w in WINDOW_KEYS}
    for section in ("S1", "S2", "S3", "S4", "S5", "S6", "S7"):
        sec = [e for e in entries if e["section"] == section]
        per_win = {w: sum(1 for e in sec if w in e["windows"]) for w in WINDOW_KEYS}
        cells = sum(per_win.values())
        total_cells += cells
        for w in WINDOW_KEYS:
            win_totals[w] += per_win[w]
        lines.append(
            f"{section:>8} {len(sec):>8} "
            + " ".join(f"{per_win[w]:>5}" for w in WINDOW_KEYS)
            + f" {cells:>6}"
        )
    lines.append(
        f"{'TOTAL':>8} {len(entries):>8} "
        + " ".join(f"{win_totals[w]:>5}" for w in WINDOW_KEYS)
        + f" {total_cells:>6}"
    )
    lines.append("")
    lines.append(f"Deferred ({len(manifest['_deferred'])}):")
    for d in manifest["_deferred"]:
        lines.append(f"  - {d['item']}: {d['reason']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--summary", action="store_true",
                        help="print the full coverage matrix + deferred list")
    args = parser.parse_args()

    manifest = build_manifest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    n = len(manifest["entries"])
    cells = sum(len(e["windows"]) for e in manifest["entries"])
    print(f"Wrote {args.out} -- {n} entries, {cells} window-cells, "
          f"{len(manifest['_deferred'])} deferred.")
    if args.summary:
        print()
        print(_summary(manifest))


if __name__ == "__main__":
    main()
