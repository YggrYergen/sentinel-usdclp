"""
SENTINEL Launcher — Self-healing, verbose, environment-aware
Logs everything to screen AND file simultaneously.
Auto-fixes: missing deps, updates via GitHub ZIP (no Git needed).
"""
import sys, os, subprocess, logging, platform, shutil, time, json
import urllib.request, zipfile, threading, webbrowser
from pathlib import Path
from datetime import datetime

VERSION = "3.4.0"
PORT = 8501
URL = f"http://localhost:{PORT}"
GITHUB_REPO = "YggrYergen/sentinel-usdclp"
BRANCH = "release"
MIN_PY = (3, 11)
MAX_PY = (3, 13)


class Launcher:
    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.sentinel = Path(__file__).parent
        self.logfile = self.root / "sentinel_log.txt"
        self._setup_log()

    def _setup_log(self):
        self.lg = logging.getLogger("sentinel.launcher")
        self.lg.setLevel(logging.DEBUG)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter('  %(message)s'))
        fh = logging.FileHandler(str(self.logfile), mode='w', encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.lg.addHandler(sh)
        self.lg.addHandler(fh)

    def log(self, msg, lv="info"):
        getattr(self.lg, lv)(msg)

    def cmd(self, c, show=True):
        self.log(f"  $ {c}", "debug")
        try:
            r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=300)
            if show and r.stdout.strip():
                for l in r.stdout.strip().split('\n'):
                    self.log(f"    {l}", "debug")
            if r.stderr.strip():
                for l in r.stderr.strip().split('\n'):
                    self.log(f"    [err] {l}", "debug")
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except Exception as e:
            self.log(f"    [EXCEPTION] {e}", "error")
            return -1, "", str(e)

    # ── Step 1 ──
    def check_running(self):
        self.log("[1/6] Checking if SENTINEL is already running...")
        try:
            urllib.request.urlopen(URL, timeout=2)
            self.log(f"[OK] Already running! Opening browser -> {URL}")
            webbrowser.open(URL)
            return True
        except:
            self.log("[OK] Not running yet — will start")
            return False

    # ── Step 2 ──
    def check_python(self):
        self.log("[2/6] Checking Python version...")
        v = sys.version_info
        self.log(f"  Version:  Python {v.major}.{v.minor}.{v.micro}")
        self.log(f"  Path:     {sys.executable}")
        self.log(f"  Platform: {platform.platform()}")
        self.log(f"  Arch:     {platform.architecture()[0]}")

        if (v.major, v.minor) < MIN_PY:
            self.log(f"[ERROR] Python {v.major}.{v.minor} too old (need >={MIN_PY[0]}.{MIN_PY[1]})", "error")
            self.log(f"  Download: https://www.python.org/downloads/release/python-3120/", "error")
            return False
        if (v.major, v.minor) > MAX_PY:
            self.log(f"[WARNING] Python {v.major}.{v.minor} may be TOO NEW for MetaTrader5!", "warning")
            self.log(f"  MetaTrader5 typically supports up to Python 3.13", "warning")
            self.log(f"  Recommended: Python 3.12", "warning")
            self.log(f"  Download: https://www.python.org/downloads/release/python-3120/", "warning")
        self.log(f"[OK] Python {v.major}.{v.minor}.{v.micro}")
        return True

    # ── Step 3 ──
    def check_updates(self):
        self.log("[3/6] Checking for updates...")
        code, out, _ = self.cmd("git --version", show=False)
        if code == 0:
            self.log(f"  {out}")
            return self._update_git()
        self.log("  Git not installed — using GitHub ZIP method")
        return self._update_zip()

    def _update_git(self):
        code, _, _ = self.cmd(f"git fetch origin {BRANCH}", show=False)
        if code != 0:
            self.log("  [SKIP] Cannot reach GitHub")
            return True
        _, local, _ = self.cmd("git rev-parse HEAD", show=False)
        _, remote, _ = self.cmd(f"git rev-parse origin/{BRANCH}", show=False)
        if local == remote:
            self.log(f"  [OK] Up to date ({local[:8]})")
        else:
            self.log(f"  [UPDATE] {local[:8]} -> {remote[:8]}")
            self.cmd("git stash")
            self.cmd(f"git checkout {BRANCH}")
            self.cmd(f"git pull origin {BRANCH}")
            self.cmd("git stash pop")
            self.log("  [OK] Updated via Git")
        return True

    def _update_zip(self):
        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{BRANCH}.zip"
        zip_path = self.root / "_update.zip"
        tmp_dir = self.root / "_update_tmp"
        try:
            self.log(f"  Downloading {zip_url}...")
            urllib.request.urlretrieve(zip_url, str(zip_path))
            size = zip_path.stat().st_size
            self.log(f"  Downloaded ({size:,} bytes)")

            with zipfile.ZipFile(str(zip_path), 'r') as z:
                z.extractall(str(tmp_dir))
            inner = list(tmp_dir.iterdir())[0]

            updated = 0
            src = inner / "sentinel"
            if src.exists():
                for f in src.iterdir():
                    if f.is_file():
                        shutil.copy2(str(f), str(self.sentinel / f.name))
                        updated += 1
            for name in ["SENTINEL.bat", ".env.example", "README.md"]:
                sf = inner / name
                if sf.exists():
                    shutil.copy2(str(sf), str(self.root / name))
                    updated += 1
            self.log(f"  [OK] Updated {updated} files from GitHub")
        except Exception as e:
            self.log(f"  [WARN] ZIP update failed: {e}", "warning")
            self.log(f"  Continuing with current version")
        finally:
            if zip_path.exists(): zip_path.unlink(missing_ok=True)
            if tmp_dir.exists(): shutil.rmtree(str(tmp_dir), ignore_errors=True)
        return True

    # ── Step 4 ──
    def check_deps(self):
        self.log("[4/6] Checking dependencies...")
        req = self.sentinel / "requirements.txt"
        if not req.exists():
            self.log(f"  [ERROR] {req} not found!", "error")
            return False

        code, _, _ = self.cmd(f'"{sys.executable}" -c "import streamlit"', show=False)
        if code != 0:
            self.log("  Installing dependencies (first time, may take minutes)...")
            code, out, err = self.cmd(f'"{sys.executable}" -m pip install -r "{req}"')
            if code != 0:
                self.log(f"[ERROR] pip install failed!", "error")
                return False
            self.log("  [OK] Dependencies installed")
        else:
            self.log("  [OK] Dependencies present")
        return True

    # ── Step 5 ──
    def verify_imports(self):
        self.log("[5/6] Verifying critical imports...")
        modules = {
            "streamlit": "Dashboard UI",
            "MetaTrader5": "Market data",
            "pandas": "Data processing",
            "plotly": "Charts",
            "ta": "Technical indicators",
            "scipy": "Signal processing",
            "anthropic": "AI chat",
        }
        ok = True
        for mod, desc in modules.items():
            try:
                m = __import__(mod)
                v = getattr(m, '__version__', '?')
                self.log(f"  [OK] {mod} v{v} — {desc}")
            except Exception as e:
                self.log(f"  [FAIL] {mod} — {desc}: {e}", "error")
                ok = False
        if not ok:
            self.log("[ERROR] Some imports failed. Python version may be incompatible.", "error")
            self.log(f"  Recommended: Python 3.12 from python.org", "error")
        return ok

    # ── Step 6 ──
    def launch(self):
        self.log("[6/6] Launching SENTINEL dashboard...")
        dashboard = self.sentinel / "dashboard.py"
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(dashboard),
            "--server.headless", "true",
            "--server.port", str(PORT),
            "--browser.gatherUsageStats", "false",
            "--server.address", "0.0.0.0"
        ]
        self.log(f"  Command: {' '.join(cmd)}")
        self.log(f"  Dashboard URL: {URL}")
        self.log("")
        self.log("  ============================================")
        self.log("    Browser will open in 8 seconds")
        self.log("    DO NOT close this window")
        self.log("  ============================================")
        self.log("")

        # Browser after delay
        def _browser():
            time.sleep(8)
            try:
                webbrowser.open(URL)
                self.log("  [OK] Browser opened")
            except:
                self.log(f"  [WARN] Open manually: {URL}", "warning")
        threading.Thread(target=_browser, daemon=True).start()

        # Stream output in real-time
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            with open(str(self.logfile), 'a', encoding='utf-8') as lf:
                for line in proc.stdout:
                    line = line.rstrip()
                    print(f"  {line}")
                    lf.write(f"{datetime.now().isoformat()} [STREAM] {line}\n")
                    lf.flush()
            proc.wait()
            self.log(f"  Streamlit exited with code: {proc.returncode}")
            return proc.returncode == 0
        except FileNotFoundError:
            self.log("[ERROR] streamlit not found!", "error")
            self.log(f"  Run: {sys.executable} -m pip install streamlit", "error")
            return False
        except Exception as e:
            self.log(f"[ERROR] Launch failed: {e}", "error")
            return False

    # ── Main ──
    def run(self):
        self.log("=" * 48)
        self.log(f"  SENTINEL v{VERSION} — Launcher")
        self.log(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"  OS: {platform.platform()}")
        self.log(f"  Log: {self.logfile}")
        self.log("=" * 48)
        self.log("")

        if self.check_running():
            return True
        if not self.check_python():
            return False
        self.check_updates()
        if not self.check_deps():
            return False
        if not self.verify_imports():
            return False
        return self.launch()


if __name__ == "__main__":
    L = Launcher()
    ok = L.run()
    if not ok:
        L.log("")
        L.log("=" * 48)
        L.log("  SENTINEL FAILED TO START")
        L.log(f"  Full log: {L.logfile}")
        L.log("=" * 48)
    print("")
    input("  Press ENTER to close this window...")
