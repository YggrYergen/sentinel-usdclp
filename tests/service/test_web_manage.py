"""M2.7 — management UI (create variant, run backtest, graduate strategy).
Pure static-serve + source assertions (TestClient, no browser automation) —
mirrors tests/service/test_frontend.py / test_web_runs.py's pattern."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_runs_and_positions_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in ("/sections/runs.js", "/sections/positions.js", "/style.css"):
            resp = client.get(path)
            assert resp.status_code == 200, path


def test_no_cdn_in_manage_assets():
    for rel in ("sections/runs.js", "sections/positions.js"):
        text = (WEB_DIR / rel).read_text(encoding="utf-8")
        assert "cdn.jsdelivr" not in text.lower()
        assert "cdnjs." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()


def test_runs_js_references_variant_creation():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "/api/variants" in runs_js
    assert "POST" in runs_js
    assert "variant_exists" in runs_js  # inline 409 "ya existe" handling


def test_runs_js_references_backtest_flow():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "/api/backtest" in runs_js
    assert "/api/jobs/" in runs_js
    # polling loop must exist for GET /api/jobs/{job_id}
    assert "setInterval" in runs_js


def test_runs_js_has_add_variant_and_backtest_ui_hooks():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "＋ Variante" in runs_js or "manage-add-variant-btn" in runs_js
    assert "runs-backtest-btn" in runs_js


def test_positions_js_references_strategy_estado_management():
    positions_js = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "/api/strategies/" in positions_js
    assert "estado" in positions_js
    for estado in ("activa", "pausada", "graduada"):
        assert estado in positions_js


def test_positions_js_marks_graduated_with_star():
    positions_js = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "★" in positions_js or "&#9733;" in positions_js  # ★


def test_style_css_has_manage_and_modal_classes():
    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    assert ".manage-" in css
    assert ".modal-" in css
