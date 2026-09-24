"""tests/service/test_web_includes.py — guard runtime <script> wiring.

Regression net for the class of bug where a new `web/lib/*.js` module (e.g.
`vlist.js`, `chartData.js`) is written and referenced by a section script
via its `window.SENTINEL.<ns>` global, but never added to `index.html`'s
`<script>` includes — so the global is `undefined` at runtime and the
section throws on boot. Substring/structural tests miss this because the
code *looks* right in isolation; only the served index.html reveals the
missing include. Found via headless-browser diagnosis (Wave A).
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"


def _index_html() -> str:
    return (WEB / "index.html").read_text(encoding="utf-8")


def _included_scripts() -> set[str]:
    # normalize `/lib/vlist.js?v=__ASSET_V__` -> `lib/vlist.js`
    srcs = re.findall(r'<script[^>]*src="([^"]+)"', _index_html())
    return {s.split("?", 1)[0].lstrip("/") for s in srcs}


def test_every_web_lib_module_is_script_included():
    """Every web/lib/*.js must be wired into index.html (classic scripts,
    global namespace — an omission = undefined global = runtime boot crash)."""
    included = _included_scripts()
    lib_files = {f"lib/{p.name}" for p in (WEB / "lib").glob("*.js")}
    missing = sorted(lib_files - included)
    assert not missing, f"web/lib modules not <script>-included in index.html: {missing}"


def test_vlist_and_chartdata_included():
    """Explicit anchors for the two modules whose omission blanked Trade View."""
    included = _included_scripts()
    assert "lib/vlist.js" in included
    assert "lib/chartData.js" in included
