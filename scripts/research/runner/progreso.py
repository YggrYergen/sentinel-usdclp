"""scripts.research.runner.progreso -- progress visibility (T0.9-B SS3).

Writes <resultados_dir>/_progreso.json and _progreso.txt atomically
(tmp+replace, same pattern as state.py) after every corrida finishes
(ok or fallido). A human running an unattended overnight grid can
`Get-Content _progreso.txt` and instantly see where the run is.

Timestamps: local host time, ISO 8601, no timezone suffix. The host clock
IS the broker server time (UTC-4) -- never utcnow(), never a zone
conversion (same convention as lineage.py / state.py).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

PROGRESO_JSON = "_progreso.json"
PROGRESO_TXT = "_progreso.txt"


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def write_progress(
    resultados_dir: Path,
    *,
    total: int,
    completadas: int,
    fallidas: int,
    run_key_actual: str | None,
    iniciado_en: str,
    historial: list[dict],
    failed_run_keys: list[str],
) -> None:
    """Write _progreso.json and _progreso.txt for this run.

    `historial` is the ordered list of {"run_key", "estado", "duration_s"}
    dicts for corridas finished so far in THIS run_manifest() invocation, in
    finish order; only the last 10 are shown in the .txt. `iniciado_en` is
    this run's start timestamp (ISO, local host time, no tz).
    """
    resultados_dir = Path(resultados_dir)
    pendientes = total - completadas - fallidas
    hechas = completadas + fallidas

    ahora = datetime.now()
    iniciado_dt = datetime.fromisoformat(iniciado_en)
    segundos_transcurridos = (ahora - iniciado_dt).total_seconds()

    segundos_por_corrida_media = (segundos_transcurridos / hechas) if hechas > 0 else None

    if segundos_por_corrida_media is not None:
        eta_segundos = segundos_por_corrida_media * pendientes
        eta_iso = (ahora + timedelta(seconds=eta_segundos)).isoformat(timespec="seconds")
    else:
        eta_segundos = None
        eta_iso = None

    payload = {
        "total": total,
        "completadas": completadas,
        "fallidas": fallidas,
        "pendientes": pendientes,
        "run_key_actual": run_key_actual,
        "iniciado_en": iniciado_en,
        "actualizado_en": ahora.isoformat(timespec="seconds"),
        "segundos_transcurridos": round(segundos_transcurridos, 3),
        "segundos_por_corrida_media": (
            round(segundos_por_corrida_media, 3) if segundos_por_corrida_media is not None else None
        ),
        "eta_segundos": round(eta_segundos, 3) if eta_segundos is not None else None,
        "eta_iso": eta_iso,
        "failed_run_keys": list(failed_run_keys),
    }
    _atomic_write_text(
        resultados_dir / PROGRESO_JSON,
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False),
    )

    pct = (hechas / total * 100.0) if total else 0.0
    if eta_segundos is not None:
        eta_txt = f"ETA {eta_segundos:.1f}s ({eta_iso})"
    else:
        eta_txt = "ETA n/a"
    header = (
        f"{hechas}/{total} corridas ({pct:.1f}%) -- "
        f"transcurrido {segundos_transcurridos:.1f}s -- {eta_txt}"
    )
    if run_key_actual is not None:
        header += f" -- en curso: {run_key_actual}"
    if failed_run_keys:
        header += f" -- fallidas: {', '.join(failed_run_keys)}"

    lines = [header, "", "ultimas corridas:"]
    ultimas = historial[-10:]
    if not ultimas:
        lines.append("  (ninguna todavia)")
    for entry in ultimas:
        lines.append(f"  [{entry['estado']}] {entry['run_key']} -- {entry['duration_s']:.3f}s")

    _atomic_write_text(resultados_dir / PROGRESO_TXT, "\n".join(lines) + "\n")


def read_progress_text(resultados_dir: Path) -> str | None:
    """Return the content of _progreso.txt, or None if it does not exist yet."""
    path = Path(resultados_dir) / PROGRESO_TXT
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
