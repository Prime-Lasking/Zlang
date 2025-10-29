"""Setup and Update utilities for Z Compiler."""

import sys
import os
import shutil
import platform
import subprocess
import json
import tempfile
import stat
import ctypes
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

# Version information
VERSION = "0.9.5"

# Initialize colorama for Windows ANSI support
try:
    from colorama import init, Fore, Style
    init()  # Initialize colorama
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# Color codes for terminal output (with Windows compatibility)
class Colors:
    if HAS_COLORAMA:
        RED = Fore.RED
        GREEN = Fore.GREEN
        YELLOW = Fore.YELLOW
        BLUE = Fore.BLUE
        PURPLE = Fore.MAGENTA
        CYAN = Fore.CYAN
        WHITE = Fore.WHITE
        BOLD = Style.BRIGHT
        END = Style.RESET_ALL
    else:
        # Fallback for systems without colorama
        RED = ''
        GREEN = ''
        YELLOW = ''
        BLUE = ''
        PURPLE = ''
        CYAN = ''
        WHITE = ''
        BOLD = ''
        END = ''

def print_colored(text: str, color: str = Colors.WHITE):
    print(f"{color}{text}{Colors.END}")

def print_version():
    """Print version information and exit."""
    print(f"z {VERSION}")

def handle_cli_setup_and_version(argv):
    """Handle -v/--version and -setup/-begin flags early in CLI processing."""
    lower = [a.lower() for a in argv]
    if "-v" in lower or "--version" in lower:
        print_version()
        return True
    if "-setup" in lower or "-begin" in lower:
        code = run_setup()
        sys.exit(code)
    return False

# ============ INSTALLATION / PATH DETECTION ============

def is_windows():
    """Check if running on Windows."""
    return os.name == "nt"

def is_admin():
    """Check if running with admin privileges on Windows."""
    if not is_windows():
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def get_current_z_exe():
    """Get the path to the currently running z.exe."""
    # Prefer the actual running executable if frozen (e.g., PyInstaller)
    try:
        if getattr(sys, "frozen", False):
            p = Path(sys.executable).resolve()
            return str(p)
    except Exception:
        pass
    # Fallbacks when running as script
    argv0 = Path(sys.argv[0]).resolve()
    if argv0.suffix.lower() == ".exe":
        return str(argv0)
    cwd_candidate = Path.cwd() / "z.exe"
    if cwd_candidate.exists():
        return str(cwd_candidate.resolve())
    # Last resort: look up first z.exe on PATH
    found = shutil.which("z.exe")
    if found:
        return str(Path(found).resolve())
    raise RuntimeError("Could not locate current z.exe")

def ensure_install_dir():
    """Ensure the install directory exists and return its path."""
    # Try Program Files first
    try:
        base = os.environ.get("ProgramFiles", r"C:\Program Files")
        install_dir = Path(base) / "Z" / "bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        return str(install_dir.resolve())
    except PermissionError:
        # Fallback to user's local directory if Program Files access denied
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        install_dir = Path(base) / "Programs" / "Z" / "bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        return str(install_dir.resolve())

def copy_file_overwrite(src, dst):
    """Copy a file, overwriting the destination if it exists."""
    src = str(Path(src))
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Make destination writable if it exists
        if dst_path.exists():
            try:
                dst_path.chmod(stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except Exception:
                pass
        shutil.copy2(src, str(dst_path))
        return True, None
    except Exception as e:
        return False, str(e)

def find_all_z_in_path(exclude_dirs=None):
    """Find all z.exe files in PATH, excluding specified directories."""
    exclude_dirs = set([str(Path(p).resolve()).lower() for p in (exclude_dirs or [])])
    seen_dirs = set()
    results = []
    env_path = os.environ.get("PATH", "")
    for raw in env_path.split(";"):
        if not raw:
            continue
        p = Path(os.path.expandvars(raw.strip()))
        try:
            resolved_dir = str(p.resolve())
        except Exception:
            resolved_dir = str(p)
        key = resolved_dir.lower()
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        if key in exclude_dirs:
            continue
        candidate = Path(resolved_dir) / "z.exe"
        if candidate.exists():
            results.append(str(candidate))
    return results

def ask_yes_no(prompt, default_no=True):
    """Ask a yes/no question with input()."""
    suffix = " [y/N] " if default_no else " [Y/n] "
    ans = input(prompt + suffix).strip().lower()
    if not ans:
        return not default_no
    return ans in ("y", "yes")

# Windows registry PATH helpers
def _open_env_key_machine(access):
    """Open the machine-level environment registry key."""
    import winreg as reg
    return reg.OpenKey(reg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 0, access)

def _open_env_key_user(access):
    """Open the user-level environment registry key."""
    import winreg as reg
    return reg.OpenKey(reg.HKEY_CURRENT_USER, r"Environment", 0, access)

def _read_path_value(open_key_func):
    """Read PATH value from registry."""
    import winreg as reg
    try:
        k = open_key_func(reg.KEY_READ | getattr(reg, "KEY_WOW64_64KEY", 0))
        with k:
            value, vtype = reg.QueryValueEx(k, "Path")
            return value, vtype
    except FileNotFoundError:
        return "", None

def _write_path_value(open_key_func, new_value, value_type_hint=None):
    """Write PATH value to registry."""
    import winreg as reg
    k = open_key_func(reg.KEY_SET_VALUE | getattr(reg, "KEY_WOW64_64KEY", 0))
    with k:
        vtype = value_type_hint or reg.REG_EXPAND_SZ
        try:
            reg.SetValueEx(k, "Path", 0, vtype, new_value)
        except Exception:
            # Fallback to REG_SZ if expand failed
            reg.SetValueEx(k, "Path", 0, reg.REG_SZ, new_value)

def _normalize_dir(p):
    """Normalize a directory path for comparison."""
    try:
        return str(Path(os.path.expandvars(p)).resolve()).lower()
    except Exception:
        return str(Path(p)).lower()

def _dedupe_and_prepend_path(existing_path_str, new_dir):
    """Prepend new_dir to PATH, removing duplicates."""
    parts_raw = [s for s in existing_path_str.split(";") if s]
    new_dir_norm = _normalize_dir(new_dir)
    kept = []
    seen_norm = set()
    # First, ensure new_dir appears first
    kept.append(new_dir)
    seen_norm.add(new_dir_norm)
    for s in parts_raw:
        norm = _normalize_dir(s)
        if norm in seen_norm or norm == new_dir_norm:
            continue
        kept.append(s)
        seen_norm.add(norm)
    return ";".join(kept)

def broadcast_env_change():
    """Notify running processes that environment changed."""
    try:
        HWND_BROADCAST = 65535
        WM_SETTINGCHANGE = 26
        SMTO_ABORTIFHUNG = 2
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(res))
    except Exception:
        pass

def add_install_dir_to_path_prefer_system(install_dir):
    """Add install_dir to PATH, preferring system-wide, fallback to user."""
    if not is_windows():
        print("Setup currently supports Windows only.")
        return "none"
    # Try system-wide first
    try:
        old_val, old_type = _read_path_value(_open_env_key_machine)
        new_val = _dedupe_and_prepend_path(old_val or "", install_dir)
        if new_val != (old_val or ""):
            _write_path_value(_open_env_key_machine, new_val, old_type)
        broadcast_env_change()
        return "system"
    except PermissionError:
        # Fallback to user PATH
        try:
            old_val, old_type = _read_path_value(_open_env_key_user)
            new_val = _dedupe_and_prepend_path(old_val or "", install_dir)
            if new_val != (old_val or ""):
                _write_path_value(_open_env_key_user, new_val, old_type)
            broadcast_env_change()
            return "user"
        except Exception as e:
            print("Failed to update user PATH: " + str(e))
            return "none"
    except Exception as e:
        print("Failed to update system PATH: " + str(e))
        return "none"

def is_in_path() -> bool:
    """Check if z.exe is already available in PATH (legacy function for compatibility)."""
    try:
        script_dir = Path(__file__).parent.resolve() if not getattr(sys, 'frozen', False) else Path(sys.executable).parent.resolve()
        current_exe = Path(sys.executable).resolve()
        if platform.system().lower() == "windows":
            result = subprocess.run(['where', 'z.exe'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                paths = [Path(p.strip()).resolve() for p in result.stdout.strip().splitlines() if p.strip()]
                for p in paths:
                    if p != current_exe and p.parent != script_dir:
                        return True
        else:
            result = subprocess.run(['which', 'z'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                found_path = Path(result.stdout.strip()).resolve()
                return (found_path != current_exe and found_path.parent != script_dir)
    except Exception:
        pass
    return False

def run_setup() -> int:
    """Run the new setup process that installs current z.exe and handles PATH updates."""
    if not is_windows():
        print_colored("z -setup is Windows-first. Non-Windows setup is not implemented in this version.", Colors.RED)
        return 1
    
    print_colored("🚀 Z Compiler Setup Starting...", Colors.BOLD + Colors.CYAN)
    
    try:
        current_exe = get_current_z_exe()
        print_colored(f"Current z.exe: {current_exe}", Colors.WHITE)
        
        install_dir = ensure_install_dir()
        dest_exe = str(Path(install_dir) / "z.exe")
        print_colored(f"Installing to: {dest_exe}", Colors.WHITE)
        
        ok, err = copy_file_overwrite(current_exe, dest_exe)
        if not ok:
            print_colored(f"✗ Failed to install to {dest_exe}: {err}", Colors.RED)
            return 2
        
        print_colored(f"✓ Installed z.exe to {install_dir}", Colors.GREEN)
        
        # Scan PATH for other z.exe instances and prompt to overwrite
        others = find_all_z_in_path(exclude_dirs=[install_dir])
        if others:
            print_colored("Found other z.exe on PATH:", Colors.YELLOW)
            for p in others:
                print_colored(f" - {p}", Colors.WHITE)
            
            for p in others:
                if ask_yes_no(f"Replace {p} with the current z.exe?", default_no=False):
                    ok2, err2 = copy_file_overwrite(current_exe, p)
                    if ok2:
                        print_colored(f"✓ Replaced: {p}", Colors.GREEN)
                    else:
                        print_colored(f"✗ Could not replace {p}: {err2}", Colors.RED)
        else:
            print_colored("No other z.exe found on PATH.", Colors.WHITE)
        
        # Update PATH with install_dir at the front
        scope = add_install_dir_to_path_prefer_system(install_dir)
        if scope == "system":
            print_colored("✓ PATH updated system-wide. You may need to open a new terminal for changes to take effect.", Colors.GREEN)
        elif scope == "user":
            print_colored("✓ PATH updated for current user. If a system z.exe exists earlier on PATH, it may still shadow this one.", Colors.YELLOW)
        else:
            print_colored(f"⚠  Failed to update PATH automatically. You can add this directory manually: {install_dir}", Colors.YELLOW)
        
        print_colored("━" * 50, Colors.GREEN)
        print_colored("🎉 Setup Complete!", Colors.GREEN + Colors.BOLD)
        print_colored("━" * 50, Colors.GREEN)
        print_colored("You can now use 'z <file>' from anywhere to compile Z files!", Colors.WHITE)
        print_colored("Try: z --version", Colors.CYAN)
        
        return 0
        
    except Exception as e:
        print_colored(f"✗ Setup failed: {e}", Colors.RED)
        return 2

def show_setup_message():
    """Show message when Z is not set up."""
    print_colored("━" * 50, Colors.CYAN)
    print_colored("🚀 Z Compiler Setup Required", Colors.BOLD + Colors.YELLOW)
    print_colored("━" * 50, Colors.CYAN)
    print()
    print_colored("It looks like Z isn't set up yet!", Colors.WHITE)
    print_colored("To install Z and add it to your PATH, run:", Colors.WHITE)
    print()
    print_colored("  z -begin", Colors.GREEN + Colors.BOLD)
    print()
    print_colored("This will install Z so you can use it from anywhere!", Colors.WHITE)
    print_colored("━" * 50, Colors.CYAN)

# ============ UPDATE LOGIC ============

GITHUB_LATEST_API = "https://api.github.com/repos/Prime-Lasking/Zlang/releases/latest"


def _get_latest_z_exe_download_url() -> Optional[str]:
    """Return the browser_download_url for the z.exe asset from the latest GitHub release."""
    try:
        req = Request(GITHUB_LATEST_API, headers={"User-Agent": "ZCompiler-Updater"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        assets = data.get("assets", []) or []
        # Prefer an asset explicitly named z.exe
        for a in assets:
            name = (a.get("name") or "").lower()
            if name == "z.exe" or name.endswith("/z.exe"):
                return a.get("browser_download_url")
        # Fallback: any .exe asset
        for a in assets:
            name = (a.get("name") or "").lower()
            if name.endswith(".exe"):
                return a.get("browser_download_url")
        # Last resort: first asset url
        if assets:
            return assets[0].get("browser_download_url")
    except Exception as e:
        print_colored(f"✗ GitHub API error: {e}", Colors.RED)
        return None
    return None


def _download_file(url: str, dest: Path) -> bool:
    try:
        req = Request(url, headers={"User-Agent": "ZCompiler-Updater"})
        with urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return True
    except Exception as e:
        print_colored(f"✗ Download failed: {e}", Colors.RED)
        return False


def _find_installed_z_path() -> Optional[Path]:
    """Find the installed z.exe (or z) in PATH, preferring the standard install dir, excluding current exe/script dir."""
    script_dir = Path(__file__).parent.resolve() if not getattr(sys, 'frozen', False) else Path(sys.executable).parent.resolve()
    current_exe = Path(sys.executable).resolve()

    if platform.system().lower() == "windows":
        # Prefer our standard install location
        standard = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "Zlang" / "z.exe"
        if standard.exists():
            return standard
        try:
            result = subprocess.run(['where', 'z.exe'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.splitlines():
                    p = Path(line.strip()).resolve()
                    if p != current_exe and p.parent != script_dir and p.name.lower() == "z.exe" and p.exists():
                        return p
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(['which', 'z'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                p = Path(result.stdout.strip()).resolve()
                if p != current_exe and p.parent != script_dir and p.exists():
                    return p
        except Exception:
            pass
    return None


def update_z_compiler() -> bool:
    """Download the latest release z.exe and replace the existing one in PATH."""
    print_colored("🔄 Checking for latest Z release...", Colors.CYAN)
    url = _get_latest_z_exe_download_url()
    if not url:
        print_colored("✗ Could not determine latest release download URL", Colors.RED)
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / ("z.exe" if platform.system().lower() == "windows" else "z")
        print_colored("⬇️  Downloading latest Z...", Colors.CYAN)
        if not _download_file(url, tmp_path):
            return False

        target = _find_installed_z_path()
        if not target:
            print_colored("✗ Installed Z not found in PATH. Run 'z -begin' first.", Colors.RED)
            return False

        # Try to replace
        print_colored(f"📦 Updating at {target}", Colors.WHITE)
        backup = target.with_suffix(target.suffix + ".bak")
        try:
            # Backup existing
            if target.exists():
                try:
                    shutil.copy2(target, backup)
                except Exception:
                    pass
            # On Windows, if replacing the currently running exe, copy will fail
            try:
                shutil.copy2(tmp_path, target)
            except PermissionError as e:
                # Fallback: schedule replacement via a temporary batch script with retry
                if platform.system().lower() == "windows":
                    bat = Path(tmpdir) / "z_update.bat"
                    # Create a more robust batch script with retry logic
                    bat.write_text(
                        f"@echo off\n"
                        f"setlocal enabledelayedexpansion\n"
                        f"set \"max_attempts=5\"\n"
                        f"set \"attempt=0\"\n"
                        f":retry\n"
                        f"set /a \"attempt+=1\"\n"
                        f"echo Attempt !attempt! of %max_attempts%\n"
                        f"copy /Y \"{tmp_path}\" \"{target}\" > nul 2>&1 && (\n"
                        f"  echo Update successful\n"
                        f"  del \"{tmp_path}\" > nul 2>&1\n"
                        f"  del \"%~f0\"\n"
                        f"  exit /b 0\n"
                        f") || (\n"
                        f"  if !attempt! lss %max_attempts% (\n"
                        f"    timeout /t 2 /nobreak > nul\n"
                        f"    goto :retry\n"
                        f"  ) else (\n"
                        f"    echo Update failed after %max_attempts% attempts\n"
                        f"    del \"{tmp_path}\" > nul 2>&1\n"
                        f"    del \"%~f0\"\n"
                        f"    exit /b 1\n"
                        f"  )\n"
                        f")\n",
                        encoding="utf-8"
                    )
                    try:
                        result = subprocess.run(["cmd", "/c", str(bat)], capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            print_colored("✓ Replacement completed successfully.", Colors.GREEN)
                            return True
                        else:
                            print_colored(f"✗ Update failed after retries: {result.stderr}", Colors.RED)
                            return False
                    except subprocess.TimeoutExpired:
                        print_colored("✗ Update timed out", Colors.RED)
                        return False
                    except Exception as update_error:
                        print_colored(f"✗ Update failed: {update_error}", Colors.RED)
                        return False
                else:
                    print_colored(f"✗ Update failed: {e}", Colors.RED)
                    return False
        except Exception as e:
            print_colored(f"✗ Update failed: {e}", Colors.RED)
            return False

    print_colored("✓ Z updated successfully!", Colors.GREEN)
    return True
