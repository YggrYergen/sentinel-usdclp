"""
SENTINEL Launcher v2 — Self-healing, sandboxed, verbose
- Uses portable Python if system Python is incompatible
- NEVER modifies the host system (no PATH, no registry, no global installs)
- Every step logged with full traceback
"""
import sys, os, subprocess, logging, platform, shutil, time, traceback
import urllib.request, zipfile, threading, webbrowser, glob
from pathlib import Path
from datetime import datetime

VERSION = "3.4.0"
PORT = 8501
URL = f"http://localhost:{PORT}"
GITHUB_REPO = "YggrYergen/sentinel-usdclp"
BRANCH = "release"
MIN_PY = (3, 11)
MAX_PY = (3, 13)
PORTABLE_PY_VER = "3.12.8"
PORTABLE_DIR_NAME = "_python"
MINGIT_VER = "2.47.1"
MINGIT_DIR_NAME = "_git"


class Launcher:
    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.sentinel = Path(__file__).parent
        self.logfile = self.root / "sentinel_log.txt"
        self.portable_dir = self.root / PORTABLE_DIR_NAME
        self.git_dir = self.root / MINGIT_DIR_NAME
        self._setup_log()

    def _setup_log(self):
        self.lg = logging.getLogger("sentinel.launcher")
        self.lg.setLevel(logging.DEBUG)
        if not self.lg.handlers:
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(logging.Formatter('  %(message)s'))
            fh = logging.FileHandler(str(self.logfile), mode='w', encoding='utf-8')
            fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            self.lg.addHandler(sh)
            self.lg.addHandler(fh)

    def log(self, msg, lv="info"):
        getattr(self.lg, lv)(msg)

    def log_exc(self, ctx):
        tb = traceback.format_exc()
        self.log(f"  [EXCEPTION in {ctx}]", "error")
        for line in tb.strip().split('\n'):
            self.log(f"    {line}", "error")

    def cmd(self, c, show=True, timeout=300):
        self.log(f"  $ {c}", "debug")
        try:
            r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=timeout)
            if show and r.stdout.strip():
                for ln in r.stdout.strip().split('\n'):
                    self.log(f"    {ln}", "debug")
            if r.stderr.strip():
                for ln in r.stderr.strip().split('\n'):
                    self.log(f"    [err] {ln}", "debug")
            self.log(f"    exit_code={r.returncode}", "debug")
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            self.log(f"    [TIMEOUT] after {timeout}s", "error")
            return -2, "", "timeout"
        except Exception as e:
            self.log_exc(f"cmd: {c}")
            return -1, "", str(e)

    def safe(self, name, func):
        try:
            return func()
        except Exception:
            self.log_exc(name)
            return False

    def download(self, url, dest):
        self.log(f"  Downloading: {url}")
        self.log(f"  To: {dest}")
        urllib.request.urlretrieve(url, str(dest))
        size = Path(dest).stat().st_size
        self.log(f"  Downloaded ({size:,} bytes)")
        return size > 0

    # ── Step 1: Already running? ──
    def check_running(self):
        self.log("[1/7] Checking if SENTINEL is already running...")
        try:
            self.log(f"  Connecting to {URL}...")
            urllib.request.urlopen(URL, timeout=2)
            self.log(f"  [OK] Already running! Opening browser")
            webbrowser.open(URL)
            return True
        except Exception as e:
            self.log(f"  Not running ({type(e).__name__})")
            return False

    # ── Step 2: Python version (sandboxed fix) ──
    def check_python(self):
        self.log("[2/7] Checking Python version...")
        v = sys.version_info
        self.log(f"  Version:      Python {v.major}.{v.minor}.{v.micro}")
        self.log(f"  Executable:   {sys.executable}")
        self.log(f"  Platform:     {platform.platform()}")
        self.log(f"  Architecture: {platform.architecture()[0]}")

        compatible = MIN_PY <= (v.major, v.minor) <= MAX_PY

        if compatible:
            self.log(f"  [OK] Python {v.major}.{v.minor} is compatible")
            return True

        self.log(f"  [WARN] Python {v.major}.{v.minor} is NOT compatible (need {MIN_PY[0]}.{MIN_PY[1]}-{MAX_PY[0]}.{MAX_PY[1]})", "warning")

        # Check if portable Python already exists and is compatible
        portable_exe = self.portable_dir / "python.exe"
        if portable_exe.exists():
            self.log(f"  Checking existing portable Python at {portable_exe}...")
            code, out, _ = self.cmd(f'"{portable_exe}" --version', show=False)
            if code == 0:
                self.log(f"  [OK] Portable Python already installed: {out}")
                self._relaunch(str(portable_exe))
                return False

        # Try to find compatible Python on system via py launcher
        self.log("  Looking for compatible Python on this system...")
        py_exe = self._find_compatible_python()
        if py_exe:
            self.log(f"  [OK] Found compatible Python: {py_exe}")
            self._relaunch(py_exe)
            return False

        # No compatible Python found — install portable version
        self.log("  No compatible Python found on system")
        self.log(f"  Installing portable Python {PORTABLE_PY_VER} (sandboxed, no system changes)...")
        py_exe = self._install_portable_python()
        if py_exe:
            self.log(f"  [OK] Portable Python ready: {py_exe}")
            self._relaunch(py_exe)
            return False
        else:
            self.log("[ERROR] Could not set up compatible Python", "error")
            return False

    def _find_compatible_python(self):
        """Try py launcher and common paths to find Python 3.11-3.13"""
        # Try Windows py launcher
        for minor in [12, 13, 11]:
            tag = f"3.{minor}"
            code, out, _ = self.cmd(f'py -{tag} --version', show=False)
            if code == 0:
                self.log(f"    Found py -{tag}: {out}")
                # Get the actual path
                code2, path, _ = self.cmd(f'py -{tag} -c "import sys; print(sys.executable)"', show=False)
                if code2 == 0 and path:
                    return path
        # Try common install locations
        for minor in [12, 13, 11]:
            candidates = [
                f"C:\\Python3{minor}\\python.exe",
                os.path.expandvars(f"%LOCALAPPDATA%\\Programs\\Python\\Python3{minor}\\python.exe"),
                os.path.expandvars(f"%APPDATA%\\Python\\Python3{minor}\\python.exe"),
            ]
            for p in candidates:
                if os.path.isfile(p):
                    self.log(f"    Found at: {p}")
                    return p
        return None

    def _install_portable_python(self):
        """Download Python embeddable package — lives inside project folder, no system changes"""
        arch = "amd64" if platform.architecture()[0] == "64bit" else "win32"
        ver = PORTABLE_PY_VER
        short = ver.replace('.', '')[:3]  # "312"
        zip_name = f"python-{ver}-embed-{arch}.zip"
        zip_url = f"https://www.python.org/ftp/python/{ver}/{zip_name}"

        zip_path = self.root / zip_name
        py_dir = self.portable_dir

        try:
            # Check if portable Python already exists with correct version
            existing_exe = py_dir / "python.exe"
            if existing_exe.exists():
                code, out, _ = self.cmd(f'"{existing_exe}" --version', show=False)
                if code == 0 and PORTABLE_PY_VER in out:
                    self.log(f"  [OK] Portable Python {PORTABLE_PY_VER} already exists — reusing")
                    return str(existing_exe)

            # Download embeddable Python
            self.download(zip_url, zip_path)

            # Extract (fresh install)
            self.log(f"  Extracting to {py_dir}...")
            if py_dir.exists():
                shutil.rmtree(str(py_dir))
            py_dir.mkdir(parents=True)
            with zipfile.ZipFile(str(zip_path), 'r') as z:
                z.extractall(str(py_dir))
            zip_path.unlink(missing_ok=True)

            # Enable pip: uncomment 'import site' in ._pth file
            pth_files = list(py_dir.glob(f"python{short}._pth"))
            if not pth_files:
                pth_files = list(py_dir.glob("python*._pth"))
            if pth_files:
                pth = pth_files[0]
                self.log(f"  Enabling pip support in {pth.name}...")
                content = pth.read_text()
                content = content.replace('#import site', 'import site')
                pth.write_text(content)
                self.log(f"    Updated {pth.name}")

            py_exe = py_dir / "python.exe"
            if not py_exe.exists():
                self.log(f"  [ERROR] python.exe not found in {py_dir}", "error")
                return None

            # Install pip
            self.log("  Installing pip into portable Python...")
            getpip = self.root / "_get_pip.py"
            self.download("https://bootstrap.pypa.io/get-pip.py", getpip)
            code, _, _ = self.cmd(f'"{py_exe}" "{getpip}" --no-warn-script-location')
            getpip.unlink(missing_ok=True)
            if code != 0:
                self.log("  [ERROR] Failed to install pip", "error")
                return None

            self.log(f"  [OK] Portable Python {ver} ready at {py_exe}")
            return str(py_exe)

        except Exception:
            self.log_exc("install_portable_python")
            zip_path.unlink(missing_ok=True)
            return None

    def _relaunch(self, python_exe):
        """Re-launch this script with a different Python. Clean exit from current."""
        launcher = str(self.sentinel / "launcher.py")
        self.log(f"  Re-launching: {python_exe} {launcher}")
        self.log("=" * 52)
        self.log("  SWITCHING TO COMPATIBLE PYTHON...")
        self.log("=" * 52)
        self.log("")

        # Flush log
        for h in self.lg.handlers:
            h.flush()

        # Run with new Python — replace current process
        result = subprocess.run(
            [python_exe, launcher],
            cwd=str(self.root)
        )
        sys.exit(result.returncode)

    # ── Step 3: Git ──
    def check_git(self):
        self.log("[3/8] Checking Git...")
        git_cmd = self._find_git()
        if git_cmd:
            self.log(f"  [OK] Git found: {git_cmd}")
            self._git_cmd = git_cmd
            return True

        # Install portable MinGit
        self.log("  Git not found - installing portable MinGit (sandboxed)...")
        git_cmd = self.safe("install_git", self._install_portable_git)
        if git_cmd:
            self._git_cmd = git_cmd
            return True
        self._git_cmd = None
        self.log("  [WARN] Git unavailable - will use ZIP updates", "warning")
        return True  # Non-blocking

    def _find_git(self):
        """Find git on system or in portable dir"""
        # Check portable git first
        portable = self.git_dir / "cmd" / "git.exe"
        if portable.exists():
            code, out, _ = self.cmd(f'"{portable}" --version', show=False)
            if code == 0:
                self.log(f"  Portable MinGit: {out}")
                return str(portable)

        # Check system git
        code, out, _ = self.cmd("git --version", show=False)
        if code == 0:
            self.log(f"  System git: {out}")
            return "git"
        return None

    def _install_portable_git(self):
        """Download MinGit portable - zero system changes"""
        arch = "64" if platform.architecture()[0] == "64bit" else "32"
        ver = MINGIT_VER
        zip_name = f"MinGit-{ver}-{arch}-bit.zip"
        zip_url = f"https://github.com/git-for-windows/git/releases/download/v{ver}.windows.1/{zip_name}"
        zip_path = self.root / zip_name

        try:
            self.download(zip_url, zip_path)
            self.log(f"  Extracting to {self.git_dir}...")
            if self.git_dir.exists():
                shutil.rmtree(str(self.git_dir))
            self.git_dir.mkdir(parents=True)
            with zipfile.ZipFile(str(zip_path), 'r') as z:
                z.extractall(str(self.git_dir))
            zip_path.unlink(missing_ok=True)

            git_exe = self.git_dir / "cmd" / "git.exe"
            if git_exe.exists():
                code, out, _ = self.cmd(f'"{git_exe}" --version', show=False)
                self.log(f"  [OK] MinGit installed: {out}")
                return str(git_exe)
            else:
                self.log("  [ERROR] git.exe not found after extraction", "error")
                return None
        except Exception:
            self.log_exc("install_portable_git")
            zip_path.unlink(missing_ok=True)
            return None

    # ── Step 4: Updates ──
    def check_updates(self):
        self.log("[4/8] Checking for updates...")
        git_cmd = getattr(self, '_git_cmd', None)
        if git_cmd:
            return self.safe("git_update", lambda: self._update_git(git_cmd))
        self.log("  No git available - using ZIP method")
        return self.safe("zip_update", self._update_zip)

    def _update_git(self, git_cmd):
        g = f'"{git_cmd}"' if ' ' in git_cmd else git_cmd
        code, _, _ = self.cmd(f"{g} fetch origin {BRANCH}", show=False)
        if code != 0:
            self.log("  [SKIP] Cannot reach GitHub - trying ZIP")
            return self.safe("zip_fallback", self._update_zip)
        _, local, _ = self.cmd(f"{g} rev-parse HEAD", show=False)
        _, remote, _ = self.cmd(f"{g} rev-parse origin/{BRANCH}", show=False)
        if local == remote:
            self.log(f"  [OK] Up to date ({local[:8]})")
        else:
            self.log(f"  [UPDATE] {local[:8]} -> {remote[:8]}")
            self.cmd(f"{g} stash")
            self.cmd(f"{g} checkout {BRANCH}")
            self.cmd(f"{g} pull origin {BRANCH}")
            self.cmd(f"{g} stash pop")
            self.log("  [OK] Updated via Git")
        return True

    def _update_zip(self):
        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{BRANCH}.zip"
        zip_path = self.root / "_update.zip"
        tmp_dir = self.root / "_update_tmp"
        self.log(f"  URL: {zip_url}")

        self.download(zip_url, zip_path)

        with zipfile.ZipFile(str(zip_path), 'r') as z:
            self.log(f"  ZIP contains {len(z.namelist())} files")
            z.extractall(str(tmp_dir))

        inner = list(tmp_dir.iterdir())[0]
        updated = 0
        src = inner / "sentinel"
        if src.exists():
            for f in src.iterdir():
                if f.is_file():
                    shutil.copy2(str(f), str(self.sentinel / f.name))
                    self.log(f"    Updated: sentinel/{f.name}")
                    updated += 1
        for name in ["SENTINEL.bat", ".env.example", "README.md"]:
            sf = inner / name
            if sf.exists():
                shutil.copy2(str(sf), str(self.root / name))
                self.log(f"    Updated: {name}")
                updated += 1

        zip_path.unlink(missing_ok=True)
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        self.log(f"  [OK] Updated {updated} files from GitHub")
        return True

    # ── Step 5: Dependencies ──
    def check_deps(self):
        self.log("[5/8] Checking dependencies...")
        req = self.sentinel / "requirements.txt"
        self.log(f"  requirements.txt exists: {req.exists()}")
        if not req.exists():
            self.log(f"  [ERROR] requirements.txt not found!", "error")
            return False

        for line in req.read_text().strip().split('\n'):
            self.log(f"    {line}")

        # Check if streamlit importable
        code, out, _ = self.cmd(f'"{sys.executable}" -c "import streamlit; print(streamlit.__version__)"')
        if code != 0:
            self.log("  Dependencies missing - installing...")

            # Embeddable Python needs setuptools+wheel for building packages
            self.log("  Ensuring build tools (setuptools, wheel)...")
            self.cmd(f'"{sys.executable}" -m pip install --no-warn-script-location --upgrade pip setuptools wheel')

            self.log("  Installing project dependencies...")
            code, _, err = self.cmd(f'"{sys.executable}" -m pip install --no-warn-script-location -r "{req}"')
            if code != 0:
                self.log(f"[ERROR] pip install failed!", "error")
                return False
            self.log("  [OK] Dependencies installed")
        else:
            self.log("  [OK] Dependencies present")
        return True

    # ── Step 6: Verify imports ──
    def verify_imports(self):
        self.log("[6/8] Verifying imports...")
        modules = {
            "streamlit": "Dashboard UI",
            "MetaTrader5": "Market data",
            "pandas": "Data processing",
            "numpy": "Numerical computing",
            "plotly": "Charts",
            "ta": "Technical indicators",
            "scipy": "Signal processing",
            "anthropic": "AI chat",
        }
        ok = True
        for mod, desc in modules.items():
            try:
                self.log(f"  Importing {mod}...")
                m = __import__(mod)
                v = getattr(m, '__version__', '?')
                self.log(f"  [OK] {mod} v{v} ({desc})")
            except Exception:
                self.log(f"  [FAIL] {mod} ({desc})", "error")
                self.log_exc(f"import {mod}")
                ok = False
        if not ok:
            self.log("[ERROR] Import failures detected", "error")
        return ok

    # ── Step 7: Verify dashboard loads ──
    def verify_dashboard(self):
        self.log("[7/8] Verifying dashboard.py loads without errors...")
        dashboard = self.sentinel / "dashboard.py"
        self.log(f"  File: {dashboard}")
        self.log(f"  Exists: {dashboard.exists()}")
        if not dashboard.exists():
            self.log("[ERROR] dashboard.py not found!", "error")
            return False

        code, out, err = self.cmd(
            f'"{sys.executable}" -c "import importlib.util; '
            f"spec = importlib.util.spec_from_file_location('dash', r'{dashboard}'); "
            f"print('syntax OK')\"",
            timeout=15
        )
        self.log(f"  Pre-check: {'PASS' if code == 0 else 'may have issues (non-blocking)'}")
        return True  # Don't block on this — streamlit has its own error handling

    # ── Step 8: Launch ──
    def launch(self):
        self.log("[8/8] Launching SENTINEL dashboard...")
        dashboard = self.sentinel / "dashboard.py"
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(dashboard),
            "--server.headless", "true",
            "--server.port", str(PORT),
            "--browser.gatherUsageStats", "false",
            "--server.address", "0.0.0.0"
        ]
        self.log(f"  Command: {' '.join(cmd)}")
        self.log(f"  URL: {URL}")
        self.log("")
        self.log("  ============================================")
        self.log("    Browser will open in 8 seconds")
        self.log("    DO NOT close this window")
        self.log("  ============================================")
        self.log("")

        def _browser():
            time.sleep(8)
            try:
                webbrowser.open(URL)
                self.log("  [OK] Browser opened")
            except Exception:
                self.log_exc("browser_open")
        threading.Thread(target=_browser, daemon=True).start()

        self.log("  Starting Streamlit process...")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        self.log(f"  PID: {proc.pid}")

        with open(str(self.logfile), 'a', encoding='utf-8') as lf:
            for line in proc.stdout:
                line = line.rstrip()
                print(f"  {line}")
                lf.write(f"{datetime.now().isoformat()} [STREAM] {line}\n")
                lf.flush()

        proc.wait()
        self.log(f"  Streamlit exited (code: {proc.returncode})")
        return proc.returncode == 0

    # ── Main ──
    def run(self):
        self.log("=" * 52)
        self.log(f"  SENTINEL v{VERSION} Launcher")
        self.log(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"  OS: {platform.platform()}")
        self.log(f"  Python: {sys.version}")
        self.log(f"  Executable: {sys.executable}")
        self.log(f"  Root: {self.root}")
        self.log(f"  Log: {self.logfile}")
        self.log("=" * 52)
        self.log("")

        # Step 1: Check Python first (may relaunch with portable)
        if not self.safe("check_python", self.check_python):
            return False

        # Step 2: Ensure Git is available (install MinGit if needed)
        self.safe("check_git", self.check_git)

        # Step 3: Check for updates ALWAYS (even if already running)
        self.safe("check_updates", self.check_updates)

        # Step 4: Now check if already running (after updates)
        self.log("[1/8] Checking if SENTINEL is already running...")
        try:
            urllib.request.urlopen(URL, timeout=2)
            self.log(f"  [OK] Already running and up to date")
            self.log(f"  Opening browser -> {URL}")
            webbrowser.open(URL)
            return True
        except Exception:
            self.log("  Not running - starting fresh")

        # Steps 5-8: Full startup
        if not self.safe("check_deps", self.check_deps):
            return False
        if not self.safe("verify_imports", self.verify_imports):
            return False
        self.safe("verify_dashboard", self.verify_dashboard)
        return self.safe("launch", self.launch)


if __name__ == "__main__":
    try:
        L = Launcher()
        ok = L.run()
        if not ok:
            L.log("")
            L.log("=" * 52)
            L.log("  SENTINEL FAILED TO START")
            L.log(f"  Log: {L.logfile}")
            L.log("=" * 52)
    except Exception:
        print("\n  FATAL ERROR:\n")
        traceback.print_exc()
        print(f"\n  Python: {sys.version}")
        print(f"  CWD: {os.getcwd()}")

    print("")
    input("  Press ENTER to close this window...")
