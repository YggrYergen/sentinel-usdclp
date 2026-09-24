"""tests/research/test_tasks_ticks.py -- TDD for T0.4-impl (task-type `ticks_mt5`).

Spec: research/fases/F0-preparacion/02-specs/T0.4-brief-task-type-ticks.md.

No test touches MT5 or the network: the tick provider and the terminal
detector are injected doubles. Covers the 7 required cases from the brief:
1. no terminal running -> fail-loud, MT5 never called
2. forbidden (REAL) login -> aborts before reading ticks
3. non-sanctioned login -> aborts before reading ticks
4. happy path -> one parquet per month, correct columns and metrics
5. within-run idempotency -> pre-existing month file is not re-downloaded
6. integrity -> duplicates/non-monotonic/gaps counted; ask<bid aborts
7. ledger -> append onto a file with no trailing newline does not merge lines
"""
from __future__ import annotations

import calendar
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research.runner import integridad_ticks, ledger, tasks_ticks

REPO_ROOT = Path(__file__).resolve().parents[2]

REAL_LOGIN = 2883011573
SANCTIONED_DEMO = [2883015767, 2883016567]

TICK_DTYPE = np.dtype([
    ("time", "i8"),
    ("bid", "f8"),
    ("ask", "f8"),
    ("last", "f8"),
    ("volume", "u8"),
    ("time_msc", "i8"),
    ("flags", "u4"),
    ("volume_real", "f8"),
])


def make_ticks(rows):
    """rows: list of (t_msc, bid, ask) -> numpy structured array shaped like copy_ticks_range."""
    return np.array(
        [(t // 1000, bid, ask, 0.0, 0, t, 0, 0.0) for (t, bid, ask) in rows],
        dtype=TICK_DTYPE,
    )


class FakeProvider:
    """Injected double for the MT5 module surface ticks_mt5 uses."""

    COPY_TICKS_ALL = 1
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(
        self, *, login, months_data=None, initialize_ok=True,
        server="Capitaria-All", trade_mode=0, symbol_resolves=True,
    ):
        self.login = login
        self.months_data = months_data or {}
        self.initialize_ok = initialize_ok
        self.server = server
        self.trade_mode = trade_mode
        self.symbol_resolves = symbol_resolves
        self.initialize_calls = 0
        self.account_info_calls = 0
        self.copy_ticks_calls = []
        self.symbol_info_calls = []
        self.shutdown_calls = 0

    def initialize(self):
        self.initialize_calls += 1
        return self.initialize_ok

    def account_info(self):
        self.account_info_calls += 1
        return SimpleNamespace(login=self.login, server=self.server, trade_mode=self.trade_mode)

    def symbol_info(self, symbol):
        self.symbol_info_calls.append(symbol)
        return SimpleNamespace(name=symbol) if self.symbol_resolves else None

    def copy_ticks_range(self, symbol, start, end, flags):
        self.copy_ticks_calls.append((symbol, start, end, flags))
        return self.months_data.get((start.year, start.month))

    def last_error(self):
        return (0, "no error")

    def shutdown(self):
        self.shutdown_calls += 1


def base_params(destino, *, desde="2026-07-01", hasta="2026-07-31"):
    return {
        "symbol": "XAUUSD",
        "desde": desde,
        "hasta": hasta,
        "destino": str(destino),
        "logins_sancionados": list(SANCTIONED_DEMO),
        "login_prohibido": REAL_LOGIN,
        "expected_login": SANCTIONED_DEMO[0],
        "expected_server": "Capitaria-All",
    }


# ---------------------------------------------------------------------------
# 1. sin terminal corriendo => fail-loud, no se llama a MT5
# ---------------------------------------------------------------------------

def test_sin_terminal_corriendo_falla_y_no_llama_mt5(tmp_path):
    provider = FakeProvider(login=SANCTIONED_DEMO[0])
    params = base_params(tmp_path / "destino")

    with pytest.raises(tasks_ticks.TicksMT5Error, match="terminal64"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: False,
        )

    assert provider.initialize_calls == 0
    assert provider.copy_ticks_calls == []


# ---------------------------------------------------------------------------
# 2. login prohibido (cuenta REAL) => aborta antes de leer ticks
# ---------------------------------------------------------------------------

def test_login_prohibido_aborta_antes_de_leer_ticks(tmp_path):
    provider = FakeProvider(
        login=REAL_LOGIN,
        months_data={(2026, 7): make_ticks([(1, 1.0, 1.1)])},
    )
    params = base_params(tmp_path / "destino")

    with pytest.raises(tasks_ticks.TicksMT5Error, match=str(REAL_LOGIN)):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.copy_ticks_calls == []
    assert provider.shutdown_calls == 1
    assert not (tmp_path / "destino").exists() or list((tmp_path / "destino").glob("*.parquet")) == []


# ---------------------------------------------------------------------------
# 3. login no sancionado => aborta antes de leer ticks
# ---------------------------------------------------------------------------

def test_login_no_sancionado_aborta_antes_de_leer_ticks(tmp_path):
    other_login = 999999
    provider = FakeProvider(
        login=other_login,
        months_data={(2026, 7): make_ticks([(1, 1.0, 1.1)])},
    )
    params = base_params(tmp_path / "destino")

    with pytest.raises(tasks_ticks.TicksMT5Error, match=str(other_login)):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.copy_ticks_calls == []
    assert provider.shutdown_calls == 1


# ---------------------------------------------------------------------------
# 4. camino feliz: un parquet por mes con columnas correctas y metricas
# ---------------------------------------------------------------------------

def test_camino_feliz_escribe_parquet_por_mes_y_metricas(tmp_path):
    base_t = 1751328000000  # arbitrary ms epoch, July 2026-ish
    rows = [(base_t + i * 1000, 2000.0 + i * 0.01, 2000.5 + i * 0.01) for i in range(5)]
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        months_data={(2026, 7): make_ticks(rows)},
    )
    destino = tmp_path / "destino"
    params = base_params(destino, desde="2026-07-01", hasta="2026-07-31")

    metrics = tasks_ticks.ticks_mt5(
        params, tmp_path / "out",
        provider=provider, terminal_check=lambda: True,
    )

    p = destino / "202607.parquet"
    assert p.exists()
    df = pd.read_parquet(p)
    assert list(df.columns) == ["t_msc", "bid", "ask"]
    assert len(df) == 5

    assert metrics["ticks_total"] == 5
    assert metrics["meses"]["202607"]["ticks"] == 5
    assert metrics["meses"]["202607"]["t_msc_min"] == rows[0][0]
    assert metrics["meses"]["202607"]["t_msc_max"] == rows[-1][0]
    assert str(p) in metrics["ficheros_escritos"]
    assert provider.shutdown_calls == 1


# ---------------------------------------------------------------------------
# 5. idempotencia dentro de la corrida, por COMPLETITUD (correccion ronda 1):
#    completo = existe y max(t_msc) esta a < tolerancia_horas (def. 72) del
#    final del tramo solicitado para ese mes. Si no, se re-descarga el mes
#    completo con sobrescritura segura (tmp -> validar -> .bak -> rename).
# ---------------------------------------------------------------------------

def _month_end_ms(y: int, mo: int) -> int:
    """Independent (test-side) computation of the same zero-offset month-end
    epoch tasks_ticks uses -- calendar.timegm, never .timestamp() (no host
    tz consulted, mirrors the sanctioned utcfromtimestamp decode)."""
    end = datetime(y + (mo == 12), (mo % 12) + 1, 1)
    return calendar.timegm(end.timetuple()) * 1000


def test_dentro_de_tolerancia_no_redescarga(tmp_path):
    destino = tmp_path / "destino"
    destino.mkdir(parents=True)

    tramo_fin = _month_end_ms(2026, 7)
    existing = pd.DataFrame({
        "t_msc": [tramo_fin - 2_000, tramo_fin - 1_000],  # 1s before month-end: well within 72h
        "bid": [2000.0, 2000.1],
        "ask": [2000.5, 2000.6],
    })
    p = destino / "202607.parquet"
    existing.to_parquet(p, index=False)
    mtime_before = p.stat().st_mtime_ns

    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        months_data={(2026, 7): make_ticks([(999, 1.0, 1.1)])},
    )
    params = base_params(destino, desde="2026-07-01", hasta="2026-07-31")

    metrics = tasks_ticks.ticks_mt5(
        params, tmp_path / "out",
        provider=provider, terminal_check=lambda: True,
    )

    assert provider.copy_ticks_calls == []
    assert p.stat().st_mtime_ns == mtime_before
    assert metrics["meses"]["202607"]["ticks"] == 2
    assert metrics["meses"]["202607"]["escrito"] is False
    assert metrics["meses"]["202607"]["redescargado"] is False
    assert metrics["ficheros_escritos"] == []
    assert list(destino.glob("*.bak-*")) == []


def test_truncado_mas_alla_de_la_tolerancia_redescarga_y_crea_bak(tmp_path):
    destino = tmp_path / "destino"
    destino.mkdir(parents=True)

    tramo_fin = _month_end_ms(2026, 7)
    old_max = tramo_fin - 8 * 24 * 3_600_000  # ~8 days before month-end (~jul 24), beyond 72h tolerance
    old_min = old_max - 10_000
    existing = pd.DataFrame({
        "t_msc": [old_min, old_max],
        "bid": [2000.0, 2000.1],
        "ask": [2000.5, 2000.6],
    })
    p = destino / "202607.parquet"
    existing.to_parquet(p, index=False)
    old_bytes = p.read_bytes()

    new_rows = [
        (tramo_fin - 3_000, 2001.0, 2001.5),
        (tramo_fin - 2_000, 2001.1, 2001.6),
        (tramo_fin - 1_000, 2001.2, 2001.7),
    ]
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        months_data={(2026, 7): make_ticks(new_rows)},
    )
    params = base_params(destino, desde="2026-07-01", hasta="2026-07-31")

    metrics = tasks_ticks.ticks_mt5(
        params, tmp_path / "out",
        provider=provider, terminal_check=lambda: True,
    )

    assert provider.copy_ticks_calls  # re-downloaded
    assert list(destino.glob("*.tmp")) == []  # tmp cleaned up (renamed into place)

    baks = list(destino.glob("202607.parquet.bak-*"))
    assert len(baks) == 1
    assert baks[0].read_bytes() == old_bytes  # backup preserves the old content byte-for-byte

    df_new = pd.read_parquet(p)
    assert len(df_new) == 3
    assert list(df_new.columns) == ["t_msc", "bid", "ask"]

    entry = metrics["meses"]["202607"]
    assert entry["escrito"] is True
    assert entry["redescargado"] is True
    assert entry["ticks_antes"] == 2
    assert entry["ticks_despues"] == 3
    assert entry["rango_antes"] == [old_min, old_max]
    assert entry["rango_despues"] == [new_rows[0][0], new_rows[-1][0]]
    assert entry["bak"] == str(baks[0])
    assert str(p) in metrics["ficheros_escritos"]


def test_validacion_del_temporal_falla_original_intacto_sin_bak(tmp_path):
    destino = tmp_path / "destino"
    destino.mkdir(parents=True)

    tramo_fin = _month_end_ms(2026, 7)
    old_max = tramo_fin - 8 * 24 * 3_600_000  # beyond tolerance -> triggers re-download
    existing = pd.DataFrame({
        "t_msc": [old_max - 1_000, old_max],
        "bid": [2000.0, 2000.1],
        "ask": [2000.5, 2000.6],
    })
    p = destino / "202607.parquet"
    existing.to_parquet(p, index=False)
    old_bytes = p.read_bytes()
    mtime_before = p.stat().st_mtime_ns

    # provider returns a row with ask < bid -> integrity validation on the .tmp must fail
    bad_rows = [(tramo_fin - 1_000, 2001.5, 2001.4)]
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        months_data={(2026, 7): make_ticks(bad_rows)},
    )
    params = base_params(destino, desde="2026-07-01", hasta="2026-07-31")

    with pytest.raises(integridad_ticks.IntegrityError):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert p.read_bytes() == old_bytes
    assert p.stat().st_mtime_ns == mtime_before
    assert list(destino.glob("202607.parquet.bak-*")) == []
    assert list(destino.glob("202607.parquet.tmp")) != []  # left on disk for inspection


# ---------------------------------------------------------------------------
# GUARD DE IDENTIDAD (dos terminales MT5 a la vez, cuenta/broker equivocado):
# expected_login / expected_server / trade_mode==DEMO / symbol resuelve.
# Corre DESPUES de initialize() y ANTES de cualquier copy_ticks_range.
# ---------------------------------------------------------------------------

def test_login_no_coincide_con_expected_login_aborta_guard_identidad(tmp_path):
    # login SI esta en logins_sancionados (pasa el guard viejo) pero NO es
    # el expected_login especifico de esta corrida -> debe abortar igual.
    provider = FakeProvider(
        login=SANCTIONED_DEMO[1],
        months_data={(2026, 7): make_ticks([(1, 1.0, 1.1)])},
    )
    params = base_params(tmp_path / "destino")  # expected_login = SANCTIONED_DEMO[0]

    with pytest.raises(tasks_ticks.TicksMT5IdentityError, match=str(SANCTIONED_DEMO[0])):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.copy_ticks_calls == []
    assert provider.shutdown_calls == 1
    assert not (tmp_path / "destino").exists() or list((tmp_path / "destino").glob("*.parquet")) == []


def test_server_no_coincide_con_expected_server_aborta_guard_identidad(tmp_path):
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        server="AVA-Demo",  # terminal esta logueado en un broker distinto
        months_data={(2026, 7): make_ticks([(1, 1.0, 1.1)])},
    )
    params = base_params(tmp_path / "destino")  # expected_server = "Capitaria-All"

    with pytest.raises(tasks_ticks.TicksMT5IdentityError, match="AVA-Demo"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.copy_ticks_calls == []
    assert provider.shutdown_calls == 1
    assert not (tmp_path / "destino").exists() or list((tmp_path / "destino").glob("*.parquet")) == []


def test_trade_mode_no_demo_aborta_guard_identidad(tmp_path):
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        trade_mode=FakeProvider.ACCOUNT_TRADE_MODE_REAL,  # cuenta real o de concurso
        months_data={(2026, 7): make_ticks([(1, 1.0, 1.1)])},
    )
    params = base_params(tmp_path / "destino")

    with pytest.raises(tasks_ticks.TicksMT5IdentityError, match="trade_mode"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.copy_ticks_calls == []
    assert provider.shutdown_calls == 1
    assert not (tmp_path / "destino").exists() or list((tmp_path / "destino").glob("*.parquet")) == []


def test_symbol_no_resuelve_aborta_guard_identidad(tmp_path):
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        symbol_resolves=False,  # p.ej. terminal en un broker cuyo simbolo es "GOLD", no "XAUUSD"
        months_data={(2026, 7): make_ticks([(1, 1.0, 1.1)])},
    )
    params = base_params(tmp_path / "destino")

    with pytest.raises(tasks_ticks.TicksMT5IdentityError, match="XAUUSD"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.copy_ticks_calls == []
    assert provider.shutdown_calls == 1
    assert not (tmp_path / "destino").exists() or list((tmp_path / "destino").glob("*.parquet")) == []


def test_identidad_correcta_procede_y_registra_metricas(tmp_path):
    rows = [(1751328000000 + i * 1000, 2000.0, 2000.5) for i in range(3)]
    provider = FakeProvider(
        login=SANCTIONED_DEMO[0],
        server="Capitaria-All",
        trade_mode=FakeProvider.ACCOUNT_TRADE_MODE_DEMO,
        symbol_resolves=True,
        months_data={(2026, 7): make_ticks(rows)},
    )
    params = base_params(tmp_path / "destino")

    metrics = tasks_ticks.ticks_mt5(
        params, tmp_path / "out",
        provider=provider, terminal_check=lambda: True,
    )

    assert provider.copy_ticks_calls  # llego a descargar: el guard dejo pasar
    assert provider.symbol_info_calls == ["XAUUSD"]
    assert metrics["identidad"]["login"] == SANCTIONED_DEMO[0]
    assert metrics["identidad"]["server"] == "Capitaria-All"
    assert metrics["identidad"]["trade_mode"] == FakeProvider.ACCOUNT_TRADE_MODE_DEMO
    assert metrics["identidad"]["symbol_resuelto"] == "XAUUSD"


# ---------------------------------------------------------------------------
# Campos nuevos obligatorios en el manifiesto (expected_login, expected_server;
# symbol reutiliza el campo ya existente): su ausencia es error de validacion,
# nunca un valor por defecto.
# ---------------------------------------------------------------------------

def test_manifiesto_sin_expected_login_es_error_de_validacion(tmp_path):
    provider = FakeProvider(login=SANCTIONED_DEMO[0])
    params = base_params(tmp_path / "destino")
    del params["expected_login"]

    with pytest.raises(KeyError, match="expected_login"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.initialize_calls == 0
    assert provider.copy_ticks_calls == []


def test_manifiesto_sin_expected_server_es_error_de_validacion(tmp_path):
    provider = FakeProvider(login=SANCTIONED_DEMO[0])
    params = base_params(tmp_path / "destino")
    del params["expected_server"]

    with pytest.raises(KeyError, match="expected_server"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.initialize_calls == 0
    assert provider.copy_ticks_calls == []


def test_manifiesto_sin_symbol_es_error_de_validacion(tmp_path):
    # symbol reutiliza el campo ya existente (no se duplica) -- sigue siendo
    # obligatorio: su ausencia tambien es error de validacion.
    provider = FakeProvider(login=SANCTIONED_DEMO[0])
    params = base_params(tmp_path / "destino")
    del params["symbol"]

    with pytest.raises(KeyError, match="symbol"):
        tasks_ticks.ticks_mt5(
            params, tmp_path / "out",
            provider=provider, terminal_check=lambda: True,
        )

    assert provider.initialize_calls == 0
    assert provider.copy_ticks_calls == []


# ---------------------------------------------------------------------------
# 6. integridad: duplicados, no-monotonia y huecos contados bien; ask<bid aborta
# ---------------------------------------------------------------------------

def test_integridad_cuenta_duplicados_no_monotonicos_y_huecos(tmp_path):
    df = pd.DataFrame({
        "t_msc": [1_000, 1_000, 2_000, 1_500, 2_000 + 61 * 60_000],
        "bid": [1.0] * 5,
        "ask": [1.1] * 5,
    })
    p = tmp_path / "202607.parquet"
    df.to_parquet(p, index=False)
    out_dir = tmp_path / "out"

    report = integridad_ticks.validar_ticks(p, out_dir, gap_threshold_min=60)

    assert report["n_ticks"] == 5
    assert report["n_duplicados_exactos"] == 1
    assert report["n_no_monotonicos"] == 1
    assert len(report["huecos"]) == 1
    assert report["n_bid_ask_invalidos"] == 0
    assert report["anomalia"] is False
    assert (out_dir / f"integridad_{p.stem}.json").exists()


def test_integridad_ask_menor_que_bid_aborta(tmp_path):
    df = pd.DataFrame({
        "t_msc": [1_000, 2_000],
        "bid": [2000.5, 2000.6],
        "ask": [2000.4, 2000.7],  # first row: ask < bid
    })
    p = tmp_path / "202608.parquet"
    df.to_parquet(p, index=False)
    out_dir = tmp_path / "out"

    with pytest.raises(integridad_ticks.IntegrityError, match="anomal"):
        integridad_ticks.validar_ticks(p, out_dir)

    report_path = out_dir / f"integridad_{p.stem}.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["n_bid_ask_invalidos"] == 1
    assert report["anomalia"] is True


# ---------------------------------------------------------------------------
# 7. ledger: append sobre fichero sin salto de linea final no fusiona lineas
# ---------------------------------------------------------------------------

def _valid_row(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "timestamp": "2026-08-10T12:00:00",
        "etapa": "F0",
        "area": "INFRA",
        "experimento": "T0.4-topup-capitaria",
        "hipotesis_ref": "n/a",
        "substrate_id": "capitaria-ticks-2026",
        "engine_sha": "n/a",
        "git_sha": "deadbeef",
        "config_hash": "abc123",
        "generador": "runner:runner.py",
        "artefactos": ["x"],
        "estado": "ok",
    }


def test_ledger_append_sin_newline_final_no_fusiona_lineas(tmp_path):
    ledger_path = tmp_path / "LEDGER.jsonl"
    first_row = _valid_row("F0-DATA-0001")
    ledger_path.write_text(json.dumps(first_row, sort_keys=True), encoding="utf-8")

    second_row = _valid_row("F0-DATA-0002")
    ledger.append_row(ledger_path, second_row)

    content = ledger_path.read_text(encoding="utf-8")
    lines = [line for line in content.split("\n") if line.strip()]
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["run_id"] == "F0-DATA-0001"
    assert parsed[1]["run_id"] == "F0-DATA-0002"


# ---------------------------------------------------------------------------
# HALLAZGO 2 (ronda 1): ticks_mt5 debe resolverse por la ruta del CLI del
# runner sin que quien lo invoque tenga que importar tasks_ticks a mano.
# Corre en un interprete nuevo (subprocess) e importa SOLO
# scripts.research.runner.runner -- nunca toca MT5 ni tasks_ticks directo.
# ---------------------------------------------------------------------------

def test_ticks_mt5_resoluble_via_runner_cli_sin_import_manual():
    script = (
        "import scripts.research.runner.runner\n"
        "from scripts.research.runner import tasks\n"
        "assert 'ticks_mt5' in tasks.get_registry(), 'ticks_mt5 no registrado via runner import'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "OK" in result.stdout
