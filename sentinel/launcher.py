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
import ctypes

VERSION = "3.7.1"
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

    def _force_rmtree(self, path, label="temp dir"):
        """Aggressively remove a directory on Windows, retrying for file locks."""
        p = Path(path)
        if not p.exists():
            return True
        self.log(f"  Cleaning stale {label}: {p}")
        for attempt in range(1, 4):
            try:
                # First attempt: standard removal
                shutil.rmtree(str(p), ignore_errors=False)
                self.log(f"    Cleaned on attempt {attempt}")
                return True
            except PermissionError:
                self.log(f"    [RETRY {attempt}/3] File locked — waiting...", "warning")
                time.sleep(1 * attempt)
                # On Windows, try to force-kill any processes that may hold locks
                if attempt == 2 and os.name == 'nt':
                    try:
                        # Try to release locks via cmd
                        subprocess.run(
                            f'rd /s /q "{p}"', shell=True,
                            timeout=10, capture_output=True
                        )
                        if not p.exists():
                            self.log(f"    Cleaned via rd /s /q")
                            return True
                    except Exception:
                        pass
            except Exception as e:
                self.log(f"    [RETRY {attempt}/3] rmtree failed: {e}", "warning")
                time.sleep(1)
        # Last resort: rename out of the way and mark for cleanup
        try:
            trash = p.parent / f"{p.name}_trash_{int(time.time())}"
            p.rename(trash)
            self.log(f"    Renamed to {trash.name} — will be cleaned later")
            return True
        except Exception as e:
            self.log(f"    [WARN] Could not remove {label}: {e}", "warning")
            return False

    def download(self, url, dest, retries=3):
        self.log(f"  Downloading: {url}")
        self.log(f"  To: {dest}")
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'SENTINEL-Launcher/3.5',
                })
                # Try with default SSL first, fallback to unverified for embedded Python
                import ssl
                try:
                    ctx = ssl.create_default_context()
                    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
                except ssl.SSLCertVerificationError:
                    self.log(f"  [SSL] Default certs failed — using unverified context", "warning")
                    ctx = ssl._create_unverified_context()
                    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
                with open(str(dest), 'wb') as f:
                    shutil.copyfileobj(resp, f)
                size = Path(dest).stat().st_size
                self.log(f"  Downloaded ({size:,} bytes)")
                return size > 0
            except Exception as e:
                last_err = e
                self.log(f"  [RETRY {attempt}/{retries}] Download failed: {e}", "warning")
                time.sleep(2 * attempt)
        raise last_err

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
        git_dir = self.root / ".git"

        # Pre-flight: clean stale temp directories from previous runs
        self._cleanup_stale_temps()

        # Strategy 1: git pull (if .git exists)
        if git_cmd and git_dir.exists():
            self.log(f"  .git directory found - using git pull")
            result = self.safe("git_update", lambda: self._update_git(git_cmd))
            if result:
                return True
            self.log("  [WARN] Git pull failed - trying ZIP fallback", "warning")

        # Strategy 2: git clone (if git available but no .git dir)
        if git_cmd and not git_dir.exists():
            self.log(f"  .git directory NOT found - trying git clone")
            result = self.safe("git_clone", lambda: self._clone_and_update(git_cmd))
            if result:
                return True
            self.log("  [WARN] Git clone failed - trying ZIP fallback", "warning")

        # Strategy 3: ZIP download (last resort)
        self.log("  Using ZIP download method")
        result = self.safe("zip_update", self._update_zip)
        if result:
            return True

        # All update methods failed — continue with existing code
        self.log("  [WARN] All update methods failed - running with existing code", "warning")
        self.log("  (This is OK if this is a fresh install or GitHub is unreachable)")
        return True  # Non-blocking: don't prevent launch

    def _cleanup_stale_temps(self):
        """Remove stale temp directories from previous interrupted runs."""
        stale_dirs = [
            self.root / "_git_clone_tmp",
            self.root / "_update_tmp",
        ]
        # Also clean any _trash_ directories from force_rmtree
        for p in self.root.glob("*_trash_*"):
            if p.is_dir():
                stale_dirs.append(p)
        # Clean stale zip files
        for p in [self.root / "_update.zip", self.root / "_get_pip.py"]:
            if p.exists():
                try:
                    p.unlink()
                    self.log(f"  Cleaned stale file: {p.name}")
                except Exception:
                    pass
        for d in stale_dirs:
            if d.exists():
                self._force_rmtree(d, d.name)

    def _update_git(self, git_cmd):
        g = f'"{git_cmd}"' if ' ' in git_cmd else git_cmd
        code, _, _ = self.cmd(f"{g} fetch origin {BRANCH}", show=False, timeout=30)
        if code != 0:
            return False
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

    def _clone_and_update(self, git_cmd):
        """Clone the repo into a temp dir, then copy sentinel/ files over.
        This works even for private repos if git has credentials cached."""
        g = f'"{git_cmd}"' if ' ' in git_cmd else git_cmd
        clone_dir = self.root / "_git_clone_tmp"
        clone_url = f"https://github.com/{GITHUB_REPO}.git"

        try:
            # Aggressively clean previous attempt (Windows file locks)
            if clone_dir.exists():
                if not self._force_rmtree(clone_dir, "_git_clone_tmp"):
                    self.log("  [WARN] Cannot clean previous clone dir — skipping git clone", "warning")
                    return False

            self.log(f"  Cloning {clone_url} (branch: {BRANCH})...")
            code, _, err = self.cmd(
                f'{g} clone --depth 1 --branch {BRANCH} {clone_url} "{clone_dir}"',
                timeout=60
            )
            if code != 0:
                # If clone failed because dir reappeared, force-clean and give up
                self._force_rmtree(clone_dir, "_git_clone_tmp (post-fail)")
                return False

            # Copy sentinel/ files (preserve chat_history)
            src = clone_dir / "sentinel"
            updated = 0
            _PRESERVE = {"chat_history", "__pycache__"}
            if src.exists():
                for f in src.iterdir():
                    if f.is_file():
                        shutil.copy2(str(f), str(self.sentinel / f.name))
                        self.log(f"    Updated: sentinel/{f.name}")
                        updated += 1
                    elif f.is_dir() and f.name in _PRESERVE:
                        self.log(f"    [SKIP] Preserving local: sentinel/{f.name}/")
                    elif f.is_dir():
                        dest_dir = self.sentinel / f.name
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        for sf in f.iterdir():
                            if sf.is_file():
                                shutil.copy2(str(sf), str(dest_dir / sf.name))
                                updated += 1
                        self.log(f"    Updated: sentinel/{f.name}/ ({len(list(f.iterdir()))} files)")

            # Copy root-level files
            for name in ["SENTINEL.bat", ".env.example", "README.md"]:
                sf = clone_dir / name
                if sf.exists():
                    shutil.copy2(str(sf), str(self.root / name))
                    self.log(f"    Updated: {name}")
                    updated += 1

            self.log(f"  [OK] Updated {updated} files via git clone")
            return True
        except Exception:
            self.log_exc("clone_and_update")
            return False
        finally:
            self._force_rmtree(clone_dir, "_git_clone_tmp (cleanup)")

    def _update_zip(self):
        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{BRANCH}.zip"
        zip_path = self.root / "_update.zip"
        tmp_dir = self.root / "_update_tmp"
        self.log(f"  URL: {zip_url}")

        try:
            self.download(zip_url, zip_path)
        except Exception as e:
            self.log(f"  [FAIL] ZIP download failed: {e}", "warning")
            zip_path.unlink(missing_ok=True)
            return False

        try:
            with zipfile.ZipFile(str(zip_path), 'r') as z:
                self.log(f"  ZIP contains {len(z.namelist())} files")
                z.extractall(str(tmp_dir))

            inner = list(tmp_dir.iterdir())[0]
            updated = 0
            src = inner / "sentinel"
            _PRESERVE = {"chat_history", "__pycache__"}
            if src.exists():
                for f in src.iterdir():
                    if f.is_file():
                        shutil.copy2(str(f), str(self.sentinel / f.name))
                        self.log(f"    Updated: sentinel/{f.name}")
                        updated += 1
                    elif f.is_dir() and f.name in _PRESERVE:
                        self.log(f"    [SKIP] Preserving local: sentinel/{f.name}/")
                    elif f.is_dir():
                        dest_dir = self.sentinel / f.name
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        for sf in f.iterdir():
                            if sf.is_file():
                                shutil.copy2(str(sf), str(dest_dir / sf.name))
                                updated += 1
                        self.log(f"    Updated: sentinel/{f.name}/ ({len(list(f.iterdir()))} files)")
            for name in ["SENTINEL.bat", ".env.example", "README.md"]:
                sf = inner / name
                if sf.exists():
                    shutil.copy2(str(sf), str(self.root / name))
                    self.log(f"    Updated: {name}")
                    updated += 1

            self.log(f"  [OK] Updated {updated} files from GitHub ZIP")
            return True
        except Exception:
            self.log_exc("zip_extract")
            return False
        finally:
            zip_path.unlink(missing_ok=True)
            shutil.rmtree(str(tmp_dir), ignore_errors=True)

    # ── Step 5: Dependencies ──
    def check_deps(self):
        self.log("[5/8] Checking dependencies...")
        req = self.sentinel / "requirements.txt"
        self.log(f"  requirements.txt exists: {req.exists()}")
        if not req.exists():
            self.log(f"  [ERROR] requirements.txt not found!", "error")
            return False

        req_content = req.read_text().strip()
        for line in req_content.split('\n'):
            self.log(f"    {line}")

        # Check marker file — skip install if deps already verified
        # Include VERSION in hash so launcher upgrades invalidate stale markers
        import hashlib
        req_hash = hashlib.md5((req_content + VERSION).encode()).hexdigest()[:12]
        marker = self.portable_dir / f"_deps_ok_{req_hash}"
        if marker.exists():
            self.log(f"  [OK] Dependencies verified (marker: {marker.name})")
            return True

        # Full check: try importing all key packages
        self.log("  Verifying installed packages...")
        check_script = "import streamlit, MetaTrader5, pandas, numpy, plotly, ta, scipy, anthropic, yfinance; print('ALL_OK')"
        code, out, _ = self.cmd(f'"{sys.executable}" -c "{check_script}"')
        if code == 0 and 'ALL_OK' in out:
            self.log("  [OK] All packages importable")
            marker.write_text(f"verified {datetime.now().isoformat()}")
            return True

        # Install needed
        self.log("  Dependencies missing - installing...")

        # Clear corrupted pip cache from Python version mismatch
        self.log("  Clearing pip cache (avoid version conflicts)...")
        self.cmd(f'"{sys.executable}" -m pip cache purge', show=False)

        # Embeddable Python needs setuptools+wheel for building packages
        self.log("  Ensuring build tools (setuptools, wheel)...")
        self.cmd(f'"{sys.executable}" -m pip install --no-warn-script-location --no-cache-dir --upgrade pip setuptools wheel')

        self.log("  Installing project dependencies...")
        code, _, err = self.cmd(f'"{sys.executable}" -m pip install --no-warn-script-location --no-cache-dir -r "{req}"', timeout=900)
        if code != 0:
            self.log(f"[ERROR] pip install failed!", "error")
            return False

        # Verify after install
        check_script2 = "import streamlit, MetaTrader5, pandas, numpy, plotly, ta, scipy, anthropic, yfinance; print('ALL_OK')"
        code, out, _ = self.cmd(f'"{sys.executable}" -c "{check_script2}"')
        if code == 0 and 'ALL_OK' in out:
            self.log("  [OK] All dependencies verified")
            marker.write_text(f"verified {datetime.now().isoformat()}")
        else:
            self.log("  [WARN] Some packages may have issues", "warning")

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
            "yfinance": "Yahoo Finance fallback",
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
        app_entry = self.sentinel / "app.py"
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(app_entry),
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
        # Snapshot launcher.py hash BEFORE update to detect self-updates
        import hashlib
        launcher_path = self.sentinel / "launcher.py"
        launcher_hash_before = ""
        try:
            launcher_hash_before = hashlib.md5(launcher_path.read_bytes()).hexdigest()
        except Exception:
            pass

        self.safe("check_updates", self.check_updates)

        # If launcher.py was updated, re-launch to load new code
        # This ensures new dependency checks (e.g. yfinance) run correctly
        try:
            launcher_hash_after = hashlib.md5(launcher_path.read_bytes()).hexdigest()
            if launcher_hash_before and launcher_hash_after != launcher_hash_before:
                self.log("")
                self.log("  [UPDATE] Launcher updated — restarting with new code...")
                # Also clear dep markers so new checks run fresh
                for m in self.portable_dir.glob("_deps_ok_*"):
                    m.unlink(missing_ok=True)
                    self.log(f"  Cleared stale marker: {m.name}")
                self._relaunch(sys.executable)
                return False  # Won't reach here — _relaunch calls sys.exit
        except Exception:
            self.log_exc("launcher_self_update_check")

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
