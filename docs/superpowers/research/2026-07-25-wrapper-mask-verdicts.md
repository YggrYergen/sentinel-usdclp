# Wrapper mask verdicts -- 2026-07-25

> Each mask VETOES a wrapper if it would have been catastrophic.
> **It never selects between variants** -- that would be re-tuning (spec R3).
> Substrate: 2347 positions, net 147,780,084 CLP @0.67 lot.

## B1
- **evaluable:** True
- **method:** real market reopens measured off the M15 bar stream (session_clock.market_reopens, gap >= 60 min with no bar); blocks positions opened < 50 min after a reopen
- **n_reopens:** 145
- **wait_minutes:** 50
- **verdict:** NO VETO -- the gap-wait gate was not catastrophic over the 7-month substrate
- **caveat:** sign is NOT stable across the wait parameter: a prototype sweep gave +13.3% at 30 min, +20.0% at 50 and 60 min, and -15.2% at 90 min. 50 min was fixed in advance from a live diagnosis, not chosen from this sweep -- this mask evaluates that fixed choice, it does not search for a better one.
- **kept_n:** 2138
- **dropped_n:** 209
- **kept_net_clp:** 177357685.36999962
- **total_net_clp:** 147780084.05000013
- **net_delta_clp:** 29577601.319999486
- **net_delta_pct:** 20.014605831454364

## B2
- **evaluable:** True
- **calendar_range:** ['2026-01-02T12:00:00', '2028-12-01T13:00:00']
- **method:** positions entered inside +/-30 min of a calendar event, over the covered range only
- **kept_n:** 2345
- **dropped_n:** 0
- **kept_net_clp:** 146170661.9800002
- **total_net_clp:** 146170661.9800002
- **net_delta_clp:** 0.0
- **net_delta_pct:** 0.0

## B3
- **evaluable:** True
- **cap:** 7
- **dropped_n:** 0
- **method:** chronological greedy replay against the observed-peak cap
- **expected:** ZERO drops -- the cap IS the observed peak, so it never bit

## B4
- **evaluable:** False
- **method:** the position CSVs carry no SL column; reconstructing it means re-simulating (out of scope)
- **verdict:** NOT MASKABLE -- B4 is a live BUG DETECTOR, not a filter
