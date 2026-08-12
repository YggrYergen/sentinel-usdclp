"""tests/research/test_tasks_ticks_csv.py -- TDD for task-type `ticks_csv_mt5`.

Ingests the AVA GOLD tick CSV (manually exported from the MT5 terminal,
NOT via the MetaTrader5 python API) into monthly parquet files under a
lake SEPARATE from data/lake_ticks/XAUUSD/ (the Capitaria substrate that
feeds A6). No test touches MT5 or reads the real 8.65 GB CSV -- every CSV
here is a small synthetic fixture written under tmp_path.

Real CSV format (confirmed by reading the first lines of the actual file,
per brief SS PASO 0): TAB-separated, header
`<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>`, e.g.
`2022.01.02\t23:01:00.106\t1829.55\t1829.89\t\t\t6`. <LAST>/<VOLUME> empty
is normal for a spot/CFD feed, not a defect.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from scripts.research.runner import tasks_ticks_csv

HEADER = "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>"


def _row(date_str, time_str, bid, ask, last="", volume="", flags="6"):
    return f"{date_str}\t{time_str}\t{bid}\t{ask}\t{last}\t{volume}\t{flags}"


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join([HEADER] + rows) + "\n", encoding="utf-8")
    return path


def base_params(csv_path: Path, destino: Path) -> dict:
    return {"csv_path": str(csv_path), "destino": str(destino)}


# ---------------------------------------------------------------------------
# no test imports MetaTrader5, and the module itself must never reference it
# ---------------------------------------------------------------------------

def test_modulo_no_referencia_metatrader5():
    src = Path(tasks_ticks_csv.__file__).read_text(encoding="utf-8")
    assert "MetaTrader5" not in src
    assert "import mt5" not in src


# ---------------------------------------------------------------------------
# 1. parseo de fecha+hora con milisegundos, exacto y sin desplazamiento
# ---------------------------------------------------------------------------

def test_parseo_fecha_hora_sin_desplazamiento_horario():
    dt, t_msc = tasks_ticks_csv.parse_naive_timestamp("2022.01.02", "23:01:00.106")

    # el valor naive es exactamente el del fichero, campo por campo
    assert (dt.year, dt.month, dt.day) == (2022, 1, 2)
    assert (dt.hour, dt.minute, dt.second) == (23, 1, 0)
    assert dt.microsecond == 106_000

    # round-trip vía decodificacion zero-offset (misma convencion que el
    # lago existente: extract_ticks.py usa datetime.utcfromtimestamp() sobre
    # un t_msc que ya codifica el reloj de servidor) reproduce el original
    # sin importar la zona horaria del host que corre el test
    back = datetime.utcfromtimestamp(t_msc / 1000.0)
    assert (back.year, back.month, back.day) == (2022, 1, 2)
    assert (back.hour, back.minute, back.second) == (23, 1, 0)
    assert back.microsecond == 106_000

    # valor exacto e independiente de TZ: zero-offset epoch ms
    expected = calendar.timegm((2022, 1, 2, 23, 1, 0, 0, 0, 0)) * 1000 + 106
    assert t_msc == expected


# ---------------------------------------------------------------------------
# 2. LAST/VOLUME vacios se aceptan
# ---------------------------------------------------------------------------

def test_last_volume_vacios_se_aceptan(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89", last="", volume=""),
        _row("2022.01.02", "23:01:00.361", "1829.57", "1829.91", last="", volume=""),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert metrics["filas_leidas"] == 2
    assert metrics["filas_escritas"] == 2
    df = pd.read_parquet(destino / "202201.parquet")
    assert list(df.columns) == ["t_msc", "bid", "ask"]
    assert len(df) == 2


# ---------------------------------------------------------------------------
# 3. particionado por mes correcto cuando el CSV cruza un limite de mes
# ---------------------------------------------------------------------------

def test_particionado_por_mes_cruzando_limite(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.31", "23:59:59.500", "1800.00", "1800.10"),
        _row("2022.01.31", "23:59:59.999", "1800.01", "1800.11"),
        _row("2022.02.01", "00:00:00.000", "1800.02", "1800.12"),
        _row("2022.02.01", "00:00:00.500", "1800.03", "1800.13"),
        _row("2022.02.01", "00:00:01.000", "1800.04", "1800.14"),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    p_jan = destino / "202201.parquet"
    p_feb = destino / "202202.parquet"
    assert p_jan.exists()
    assert p_feb.exists()
    assert len(pd.read_parquet(p_jan)) == 2
    assert len(pd.read_parquet(p_feb)) == 3
    assert sorted(metrics["meses_generados"]) == ["202201", "202202"]
    assert metrics["filas_leidas"] == 5
    assert metrics["filas_escritas"] == 5


# ---------------------------------------------------------------------------
# 4. las 4 validaciones abortan, sin fichero de salida a medias
# ---------------------------------------------------------------------------

def test_ask_menor_que_bid_aborta_sin_salida_a_medias(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
        _row("2022.01.02", "23:01:00.361", "1829.90", "1829.80"),  # ask < bid
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError, match="3"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_bid_o_ask_no_positivo_aborta_sin_salida_a_medias(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
        _row("2022.01.02", "23:01:00.361", "0.00", "1829.91"),  # bid <= 0
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_timestamps_no_monotonos_abortan_sin_salida_a_medias(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.500", "1829.55", "1829.89"),
        _row("2022.01.02", "23:01:00.106", "1829.57", "1829.91"),  # va hacia atras
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError, match="monoton"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_numero_de_campos_distinto_aborta_sin_salida_a_medias(tmp_path):
    csv_path = tmp_path / "gold.csv"
    csv_path.write_text(
        HEADER + "\n"
        + _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89") + "\n"
        + "2022.01.02\t23:01:00.361\t1829.57\t1829.91\t6\n",  # solo 5 campos
        encoding="utf-8",
    )
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError, match="3"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_abort_limpia_tmp_de_meses_ya_flusheados_en_esta_corrida(tmp_path, monkeypatch):
    # batch pequeno para forzar un flush real a .tmp (escritor abierto) del
    # primer mes antes de llegar al segundo mes, invalido
    monkeypatch.setattr(tasks_ticks_csv, "BATCH_SIZE", 10)
    rows = [
        _row("2022.01.02", f"23:01:{i:02d}.000", "1829.55", "1829.89")
        for i in range(30)
    ]
    rows.append(_row("2022.02.01", "00:00:00.000", "1900.00", "1899.00"))  # ask < bid
    csv_path = write_csv(tmp_path / "gold.csv", rows)
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError):
        tasks_ticks_csv.ticks_csv_mt5(
            base_params(csv_path, destino), tmp_path / "out",
        )

    # el mes ya flusheado a .tmp (escritor abierto) tampoco deja rastro
    assert not destino.exists() or list(destino.glob("*")) == []


# ---------------------------------------------------------------------------
# 5. destino dentro de data/lake_ticks/ aborta
# ---------------------------------------------------------------------------

def test_destino_dentro_de_lake_ticks_aborta(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
    ])
    destino = tmp_path / "data" / "lake_ticks" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvDestinoError, match="lake_ticks"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists()


def test_destino_en_lake_ticks_ava_no_aborta(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
    ])
    destino = tmp_path / "data" / "lake_ticks_ava" / "GOLD"  # substring similar pero distinto

    tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert (destino / "202201.parquet").exists()


def test_assert_destino_seguro_directo():
    with pytest.raises(tasks_ticks_csv.TicksCsvDestinoError):
        tasks_ticks_csv.assert_destino_seguro(Path("data/lake_ticks/XAUUSD"))
    # no debe lanzar para un destino fuera del lago Capitaria
    tasks_ticks_csv.assert_destino_seguro(Path("data/lake_ticks_ava/GOLD"))


# ---------------------------------------------------------------------------
# 6. mes ya completo se salta; corrida interrumpida se reanuda sin duplicar
# ---------------------------------------------------------------------------

def test_mes_ya_completo_se_salta_en_segunda_corrida(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
        _row("2022.01.02", "23:01:00.361", "1829.57", "1829.91"),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out1")
    p = destino / "202201.parquet"
    mtime_before = p.stat().st_mtime_ns

    metrics2 = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out2")

    assert p.stat().st_mtime_ns == mtime_before
    assert metrics2["meses_generados"] == []
    assert metrics2["meses"]["202201"]["escrito"] is False
    assert list(destino.glob("*.bak-*")) == []


def test_corrida_interrumpida_se_reanuda_sin_duplicar(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
        _row("2022.01.02", "23:01:00.361", "1829.57", "1829.91"),
        _row("2022.01.02", "23:01:00.612", "1829.58", "1829.92"),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"
    destino.mkdir(parents=True)
    # simula una corrida anterior cortada a mitad: dejo un .tmp, nunca un final
    (destino / "202201.parquet.tmp").write_bytes(b"garbage-partial-data")

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not (destino / "202201.parquet.tmp").exists()
    df = pd.read_parquet(destino / "202201.parquet")
    assert len(df) == 3  # no duplicado: exactamente las filas del CSV
    assert metrics["meses_generados"] == ["202201"]


# ---------------------------------------------------------------------------
# 7. sobrescritura segura: crea .bak, el original no se pierde
# ---------------------------------------------------------------------------

def test_atomic_finalize_month_crea_bak_y_preserva_original(tmp_path):
    destino = tmp_path / "lake_ticks_ava" / "GOLD"
    destino.mkdir(parents=True)
    final_path = destino / "202201.parquet"
    old_df = pd.DataFrame({"t_msc": [1, 2], "bid": [1.0, 1.1], "ask": [1.5, 1.6]})
    old_df.to_parquet(final_path, index=False)
    old_bytes = final_path.read_bytes()

    tmp_path_pq = destino / "202201.parquet.tmp"
    new_df = pd.DataFrame({"t_msc": [10, 20, 30], "bid": [2.0, 2.1, 2.2], "ask": [2.5, 2.6, 2.7]})
    new_df.to_parquet(tmp_path_pq, index=False)

    out_dir = tmp_path / "out"
    bak_path = tasks_ticks_csv.atomic_finalize_month(tmp_path_pq, final_path, out_dir)

    assert bak_path is not None
    assert bak_path.read_bytes() == old_bytes
    assert not tmp_path_pq.exists()
    df_new = pd.read_parquet(final_path)
    assert len(df_new) == 3


def test_atomic_finalize_month_sin_original_no_crea_bak(tmp_path):
    destino = tmp_path / "lake_ticks_ava" / "GOLD"
    destino.mkdir(parents=True)
    final_path = destino / "202201.parquet"
    tmp_path_pq = destino / "202201.parquet.tmp"
    df = pd.DataFrame({"t_msc": [10], "bid": [2.0], "ask": [2.5]})
    df.to_parquet(tmp_path_pq, index=False)

    out_dir = tmp_path / "out"
    bak_path = tasks_ticks_csv.atomic_finalize_month(tmp_path_pq, final_path, out_dir)

    assert bak_path is None
    assert final_path.exists()
    assert list(destino.glob("*.bak-*")) == []


# ---------------------------------------------------------------------------
# metricas al LEDGER: checksum del csv, filas, meses, rango, bytes de salida
# ---------------------------------------------------------------------------

def test_metricas_completas(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89"),
        _row("2022.01.02", "23:01:00.361", "1829.57", "1829.91"),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    expected_checksum = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert metrics["csv_checksum_sha256"] == expected_checksum
    assert metrics["csv_path"] == str(csv_path)
    assert metrics["filas_leidas"] == 2
    assert metrics["filas_escritas"] == 2
    assert metrics["meses_generados"] == ["202201"]
    assert metrics["t_msc_min"] is not None
    assert metrics["t_msc_max"] is not None
    assert metrics["t_msc_min"] <= metrics["t_msc_max"]
    assert metrics["bytes_salida"] > 0
    assert str(destino / "202201.parquet") in metrics["ficheros_escritos"]


# ---------------------------------------------------------------------------
# arrastre del ultimo valor conocido (forward-fill) -- ronda de correccion:
# <FLAGS> es un campo de bits (2=solo cambio BID, 4=solo cambio ASK, 6=ambos)
# y el exportador de MT5 deja VACIO el lado que no cambio en ese tick. Esto
# reproduce lo que copy_ticks_range ya hace por su cuenta (ambos lados
# siempre poblados con el ultimo conocido), para que el lago AVA sea
# comparable con el de Capitaria, construido por esa via.
# ---------------------------------------------------------------------------

def test_ask_vacio_arrastra_el_ultimo_ask_conocido(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89", flags="6"),
        _row("2022.01.02", "23:01:00.361", "1829.57", "", flags="2"),  # solo cambio bid
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    df = pd.read_parquet(destino / "202201.parquet")
    assert len(df) == 2
    assert df["bid"].tolist() == [1829.55, 1829.57]
    assert df["ask"].tolist() == [1829.89, 1829.89]  # arrastrado exacto
    assert metrics["ticks_ask_arrastrado"] == 1
    assert metrics["ticks_bid_arrastrado"] == 0


def test_bid_vacio_arrastra_el_ultimo_bid_conocido(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89", flags="6"),
        _row("2022.01.02", "23:01:00.361", "", "1829.95", flags="4"),  # solo cambio ask
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    df = pd.read_parquet(destino / "202201.parquet")
    assert len(df) == 2
    assert df["bid"].tolist() == [1829.55, 1829.55]  # arrastrado exacto
    assert df["ask"].tolist() == [1829.89, 1829.95]
    assert metrics["ticks_bid_arrastrado"] == 1
    assert metrics["ticks_ask_arrastrado"] == 0


def test_ambos_vacios_arrastran_los_dos(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89", flags="6"),
        _row("2022.01.02", "23:01:00.361", "", "", flags="0"),  # ninguno cambio (raro, pero posible)
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    df = pd.read_parquet(destino / "202201.parquet")
    assert len(df) == 2
    assert df["bid"].tolist() == [1829.55, 1829.55]
    assert df["ask"].tolist() == [1829.89, 1829.89]
    assert metrics["ticks_bid_arrastrado"] == 1
    assert metrics["ticks_ask_arrastrado"] == 1


def test_vacio_en_primera_fila_sin_valor_previo_aborta_con_linea(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "", flags="2"),  # primera fila, ask vacio
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError, match="2"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_bid_vacio_en_primera_fila_sin_valor_previo_aborta(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "", "1829.89", flags="4"),  # primera fila, bid vacio
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError, match="2"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_arrastre_precede_a_la_validacion_ask_arrastrado_queda_bajo_bid_nuevo(tmp_path):
    # ask arrastrado (1830.10) queda por debajo del bid NUEVO (1830.20) --
    # el aborto por ask<bid debe ocurrir usando el valor YA arrastrado,
    # confirmando que el arrastre corre antes de las validaciones.
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1830.00", "1830.10", flags="6"),
        _row("2022.01.02", "23:01:00.361", "1830.20", "", flags="2"),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    with pytest.raises(tasks_ticks_csv.TicksCsvValidationError, match="ask < bid"):
        tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert not destino.exists() or list(destino.glob("*")) == []


def test_metricas_de_arrastre_y_distribucion_de_flags(tmp_path):
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89", flags="6"),
        _row("2022.01.02", "23:01:00.200", "1829.57", "", flags="2"),
        _row("2022.01.02", "23:01:00.300", "", "1829.95", flags="4"),
        _row("2022.01.02", "23:01:00.400", "1829.60", "1829.99", flags="6"),
        _row("2022.01.02", "23:01:00.500", "1829.62", "", flags="2"),
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    assert metrics["ticks_bid_arrastrado"] == 1
    assert metrics["ticks_ask_arrastrado"] == 2
    assert metrics["flags_distribucion"] == {"6": 2, "2": 2, "4": 1}
    assert metrics["filas_leidas"] == 5
    assert metrics["filas_escritas"] == 5


def test_flags_no_decide_el_arrastre_solo_el_campo_vacio(tmp_path):
    # FLAGS dice 6 (ambos cambiaron) pero el campo ask viene vacio de todas
    # formas -- debe arrastrarse igual, por el campo vacio, no por el bit.
    csv_path = write_csv(tmp_path / "gold.csv", [
        _row("2022.01.02", "23:01:00.106", "1829.55", "1829.89", flags="6"),
        _row("2022.01.02", "23:01:00.361", "1829.57", "", flags="6"),  # flags dice "ambos" pero ask vacio
    ])
    destino = tmp_path / "lake_ticks_ava" / "GOLD"

    metrics = tasks_ticks_csv.ticks_csv_mt5(base_params(csv_path, destino), tmp_path / "out")

    df = pd.read_parquet(destino / "202201.parquet")
    assert df["ask"].tolist() == [1829.89, 1829.89]
    assert metrics["ticks_ask_arrastrado"] == 1
    assert metrics["flags_distribucion"] == {"6": 2}


# ---------------------------------------------------------------------------
# registrado en el registry del runner via una linea de import en runner.py
# ---------------------------------------------------------------------------

def test_ticks_csv_mt5_registrado_en_tasks():
    from scripts.research.runner import tasks
    tasks_ticks_csv.ticks_csv_mt5  # noqa: B018 -- import side effect already ran register()
    assert "ticks_csv_mt5" in tasks.get_registry()


def test_ticks_csv_mt5_resoluble_via_runner_cli_sin_import_manual():
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    script = (
        "import scripts.research.runner.runner\n"
        "from scripts.research.runner import tasks\n"
        "assert 'ticks_csv_mt5' in tasks.get_registry(), 'ticks_csv_mt5 no registrado via runner import'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(repo_root),
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "OK" in result.stdout
