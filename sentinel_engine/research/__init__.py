"""sentinel_engine.research — Registry v2 (SQLite/WAL) for SENTINEL research
data: strategies, variants, runs, trades, preregistrations, forward sessions.

See `docs/superpowers/plans/2026-07-09-sentinel-v2-tokata.md` §D.5 for the
normative DDL and Task M0.1 for the API contract.
"""
from .registry2 import ResearchRegistry

__all__ = ["ResearchRegistry"]
