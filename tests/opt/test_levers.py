"""Tests for sentinel_engine.opt.levers (P4 wiring layer).

Exercises the lever-group map against the REAL gold InstrumentConfig
(no synthetic stand-in config needed -- levers.py is deliberately wired to
`sentinel_engine.config.InstrumentConfig`'s real field shape).
"""
from __future__ import annotations

import dataclasses

import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.opt.levers import LEVER_GROUPS, apply_overrides, priors_for
from sentinel_engine.opt.search import MAX_DIMS_PER_STAGE, MIN_DIMS_PER_STAGE


def test_lever_groups_construct_within_dim_cap():
    assert len(LEVER_GROUPS) >= 1
    for group in LEVER_GROUPS:
        n = len(group.params)
        assert MIN_DIMS_PER_STAGE <= n <= MAX_DIMS_PER_STAGE, (group.name, n)


def test_lever_groups_no_duplicate_names_within_or_across_groups():
    all_names = [p.name for g in LEVER_GROUPS for p in g.params]
    assert len(all_names) == len(set(all_names)), "duplicate param names across groups"
    group_names = [g.name for g in LEVER_GROUPS]
    assert len(group_names) == len(set(group_names)), "duplicate group names"


def test_lever_groups_stage_order_matches_fable_g_labels():
    # G4 -> G2/G3 -> G5 -> G1 -> G6 -> G7 (Fable Sec 2.5 stage order).
    names = [g.name for g in LEVER_GROUPS]
    assert names[0].startswith("G4")
    assert "G2" in names[1] and "G3" in names[1]
    assert names[2].startswith("G5")
    assert names[3].startswith("G1")
    assert names[4].startswith("G6")
    assert names[5].startswith("G7")


def test_apply_overrides_changes_targeted_field_and_returns_new_object():
    cfg = load_instrument("gold")
    original_threshold = cfg.composite.score_alert_threshold
    cfg2 = apply_overrides(cfg, {"composite.score_alert_threshold": 77.0})

    assert cfg2 is not cfg
    assert cfg2.composite is not cfg.composite
    assert cfg2.composite.score_alert_threshold == 77.0
    # original object untouched
    assert cfg.composite.score_alert_threshold == original_threshold


def test_apply_overrides_does_not_mutate_input():
    cfg = load_instrument("gold")
    before = dataclasses.asdict(cfg)
    apply_overrides(cfg, {"technical.indicators.ema_fast": 13, "macro.tanh_sensitivity": 8.0})
    after = dataclasses.asdict(cfg)
    assert before == after


def test_apply_overrides_rounds_int_params():
    cfg = load_instrument("gold")
    cfg2 = apply_overrides(cfg, {"technical.indicators.ema_fast": 12.6})
    assert cfg2.technical.indicators.ema_fast == 13
    assert isinstance(cfg2.technical.indicators.ema_fast, int)


def test_apply_overrides_renormalizes_composite_weights():
    cfg = load_instrument("gold")
    cfg2 = apply_overrides(cfg, {"composite.weights.technical": 0.7})
    assert cfg2.composite.weights["technical"] == pytest.approx(0.7)
    assert cfg2.composite.weights["correlation"] == pytest.approx(0.3)
    total = cfg2.composite.weights["technical"] + cfg2.composite.weights["correlation"]
    assert total == pytest.approx(1.0)


def test_apply_overrides_renormalizes_tf_weights_to_simplex():
    cfg = load_instrument("gold")
    cfg2 = apply_overrides(
        cfg,
        {
            "technical.tf_weights.M15": 1.0,
            "technical.tf_weights.M5": 1.0,
            "technical.tf_weights.M2": 1.0,
            "technical.tf_weights.M1": 1.0,
        },
    )
    total = sum(cfg2.technical.tf_weights.values())
    assert total == pytest.approx(1.0)
    for v in cfg2.technical.tf_weights.values():
        assert v == pytest.approx(0.25)


def test_apply_overrides_unknown_param_raises():
    cfg = load_instrument("gold")
    with pytest.raises(ValueError):
        apply_overrides(cfg, {"not.a.real.param": 1.0})


def test_priors_for_covers_every_group():
    cfg = load_instrument("gold")
    priors = priors_for(cfg)
    assert set(priors.keys()) == {g.name for g in LEVER_GROUPS}
    for group in LEVER_GROUPS:
        assert set(priors[group.name].keys()) == {p.name for p in group.params}


def test_priors_for_round_trips_through_apply_overrides():
    cfg = load_instrument("gold")
    priors = priors_for(cfg)
    for group in LEVER_GROUPS:
        cfg2 = apply_overrides(cfg, priors[group.name])
        # Round-tripping the CURRENT values back through apply_overrides
        # must reproduce the original config exactly (mod float precision).
        d1 = dataclasses.asdict(cfg)
        d2 = dataclasses.asdict(cfg2)
        _assert_dict_approx_equal(d1, d2)


def _assert_dict_approx_equal(a, b, path=""):
    if isinstance(a, dict):
        assert set(a.keys()) == set(b.keys()), path
        for k in a:
            _assert_dict_approx_equal(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, float):
        assert a == pytest.approx(b), path
    else:
        assert a == b, path
