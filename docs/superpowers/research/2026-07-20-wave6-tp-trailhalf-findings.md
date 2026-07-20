# Wave 6 findings — `tp_min` & trail-half honest re-score (v3 league)

> Date: 2026-07-20 | Branch `alvaro` | League: `2026-07-20-honest-league-v3.{json,md}` (225 cells)
> Manifest `honest_manifest_full_2026_07_20_v3.json` (`da8326c`); lever `tp_min_pips` (`0f3e7c0`).
> Pipeline: P35 WF + DSR + guards, `live_fill_mode`, flat-0.5 cost, fixed lot 0.10, windows {IW,W1,W2,W3}.
> Comparability (D17): ranked ONLY on honest re-scores + live demo fills; legacy optimistic sim reports excluded.

## Headline

1. **`tp_min` (minimum-legal TP) is DECISIVELY REFUTED — it is the single most harmful lever tested.**
   It turns the +$13.4k M15 champion into **−$25k…−$28k** (Sharpe +2.56 → **−5 to −12**), and drives the
   FIXED4 M2 lines from ~−$90–125k to **−$146k…−$190k**. Cause (as pre-flagged): capping every winner at
   a few cents while the SL side still takes full losses destroys the payoff distribution. Confirmed on the
   champion AND every FIXED4 base, at every grid value {5,10,20,40} pips.
2. **trail-half is NEUTRAL on the champion, harmful on the FIXED4-M15 line.** On the M15 champion the net is
   byte-identical to the base (the SAR/ATR-floor exits bind before the trail, so halving it changes nothing);
   on the plain FIXED4 M15 line it is worse (−$2.8k vs −$1.0k). Not a rescue, not a lift.
3. **The FIXED4 live roster is structurally unprofitable and unrescuable.** No lever (tp_min, trail-half,
   TS, CONF, SAR) makes the M2 lines positive.
4. **DSR still 0.0 / p = 1.0** (obs Sharpe 2.72 vs null-max 14.05 over 225 trials). No significant edge —
   consistent with Waves 1–5. Only **26 of 225** cells are pooled-net-positive; **all 26 are M15 V-15**.

## Champion base vs + new levers (pooled net, USD)

| Config | Pooled net | Sharpe | Note |
|---|---|---|---|
| `HON-S7-V15-TPNONE-BE1P0-M15` (champion base) | **+13,355.7** | +2.56 | positive all 4 windows |
| `HON-W6-B-CHMP-V15-M15-TRAILHALF` | +13,355.7 | +2.56 | identical → trail never binds |
| `HON-W6-A-CHMP-V15-M15-TPMIN40` | **−25,161.9** | −5.47 | tp_min destroys it |
| `HON-W6-A-CHMP-V15-M15-TPMIN5` | −28,326.3 | −12.29 | tighter TP = worse |
| `HON-S6-V15-K1P5-AC1-M15` (vol-target base) | +13,165.2 | +2.42 | positive all 4 windows |
| `HON-W6-B-CHMPVT-V15-M15-TRAILHALF` | +13,165.2 | +2.42 | identical to base |
| `HON-W6-A-CHMPVT-V15-M15-TPMIN*` | −25k…−28k | −5…−12 | destroyed |

## FIXED4 live roster — honest pooled net

| Live line | Manifest base | Pooled net | Sharpe |
|---|---|---|---|
| V15-M15 (surviving line) | `HON-S1-V15-M15` | **−959.7** | −0.06 |
| V11-M2 | `HON-S1-V11-M2` | −89,168.4 | −4.48 |
| V15-M2 | `HON-S1-V15-M2` | −101,328.0 | −5.76 |
| V13-M2 | `HON-S1-V13-M2` | −124,853.1 | −15.06 |

The demo bleed is fully explained: three M2 lines each lose ~$90–125k honestly; even the "surviving" plain
M15 FIXED4 config is marginally negative (−$960). The genuinely positive M15 configs are the SAR/vol-target
**tuned** variants (S6/S7 below), not the plain S1 FIXED4 configs.

## The net-positive set (26 of 225 — all M15 V-15) — go-live candidates

| Rank | Config | Pooled net | Sharpe |
|---|---|---|---|
| 1 | `HON-W2-S6-K2P0-M15-SAR` | +49,111.5 | +2.72 |
| 2 | `HON-W2-S7-TPNONE-M15-SAR` | +32,683.5 | +2.19 |
| 3 | `HON-W2-S6-K1P5-M15-SAR` | +32,493.0 | +2.24 |
| 4 | `HON-W2-S7-TP1P0-M15-SAR` | +30,642.5 | +1.68 |
| 5 | `HON-W2-S7-TPNONE-M15-SAR-F2` | +21,789.0 | +2.19 |
| … | champion / vol-target / TS40 / trail-half-champ | +11k…+13.4k | +2.4…+2.6 |

## Implications

- **Do NOT deploy `tp_min` in any form.** The hypothesis "a minimum-viable TP keeps positions net-positive"
  is empirically false; it is strictly value-destroying. (This is the honest answer to the directive.)
- **Do NOT restart the FIXED4 M2 lines.** They are structurally negative; no lever rescues them.
- **The only defensible live candidates** are the M15 V-15 **SAR-tuned** variants (top-5 above), pooled
  net-positive across {IW,W1,W2,W3} — but **still DSR 0 / sub-luck-bar**, so any live run is a
  **live-forward OOS test** (demo/paper), not a proven edge (D18 caveat).
- **trail-half** is optional (neutral on the champion); it does not help and is not needed.
- **Spread-gate (D15/D18):** the flat-0.5 league cannot model it; the marginal −$960 M15 line is the only
  plausible spread-rescue candidate, but it is dominated by the clearly-positive SAR variants anyway — so a
  spread-rescue analysis is low-value here. The spread-gate remains worthwhile as a live *cost-reduction/entry
  discipline* on whatever roster is chosen, not as a rescuer of losers.

## Caveats

- Pooled net is the sum of per-window honest nets; median-fold-J leaderboard is in the v3 `.md`.
- "Net-positive" ≠ real edge: DSR 0 / p 1 across all 225. The top-5 are in-sample winners, sub-luck-bar.
- Champion trail-half byte-identity is a *result* (trail non-binding on M15), pinned by P36 parity.
