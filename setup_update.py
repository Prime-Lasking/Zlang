"""Setup and Update utilities for Z Compiler."""

import sys
import os
import shutil
import platform
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_colored(text: str, color: str = Colors.WHITE):
    print(f"{color}{text}{Colors.END}")

# ============ INSTALLATION / PATH DETECTION ============

def is_in_path() -> bool:
    """Check if z.exe (or z) is already available in PATH, excluding the current exe/script dir."""
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

def get_shell_rc() -> Path:
    """Get the appropriate shell RC file."""
    home = Path.home()
    if "ZSH_VERSION" in os.environ or os.environ.get("SHELL", "").endswith("zsh"):
        return home / ".zshrc"
    elif "BASH_VERSION" in os.environ or os.environ.get("SHELL", "").endswith("bash"):
        return home / ".bashrc"
    else:
        return home / ".profile"

def install_windows() -> bool:
    """Install Z compiler on Windows to %LOCALAPPDATA%/Programs/Z_Compiler and add to PATH."""
    exe_name = "z.exe"
    current_exe = Path(sys.executable).resolve()
    if current_exe.name.lower() != exe_name:
        print_colored(f"✗ Error: This must be run from {exe_name}", Colors.RED)
        return False

    install_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "Z_Compiler"
    install_dir.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(current_exe, install_dir / exe_name)
        print_colored(f"✓ Installed {exe_name} to {install_dir}", Colors.GREEN)
    except Exception as e:
        print_colored(f"✗ Failed to copy executable: {e}", Colors.RED)
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                current_path, _ = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_path = ""
            if str(install_dir) not in current_path:
                new_path = f"{current_path};{install_dir}" if current_path else str(install_dir)
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                print_colored(f"✓ Added {install_dir} to PATH", Colors.GREEN)
                print_colored("⚠  Please restart your terminal for PATH changes to take effect", Colors.YELLOW)
            else:
                print_colored("✓ PATH already configured", Colors.GREEN)
    except Exception as e:
        print_colored(f"⚠  Could not modify PATH automatically: {e}", Colors.YELLOW)
        print_colored(f"Please manually add {install_dir} to your PATH", Colors.WHITE)

    return True

def install_unix() -> bool:
    """Install Z compiler on Unix-like systems to ~/.local/bin and add to PATH."""
    exe_name = "z"
    current_exe = Path(sys.executable).resolve()

    install_dir = Path.home() / ".local" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(current_exe, install_dir / exe_name)
        os.chmod(install_dir / exe_name, 0o755)
        print_colored(f"✓ Installed {exe_name} to {install_dir}", Colors.GREEN)
    except Exception as e:
        print_colored(f"✗ Failed to copy executable: {e}", Colors.RED)
        return False

    shell_rc = get_shell_rc()
    path_line = f'export PATH="$PATH:{install_dir}"'
    try:
        if shell_rc.exists():
            content = shell_rc.read_text()
            if str(install_dir) not in content:
                with shell_rc.open("a", encoding="utf-8") as f:
                    f.write(f"\n{path_line}\n")
                print_colored(f"✓ Added {install_dir} to PATH in {shell_rc}", Colors.GREEN)
                print_colored(f"⚠  Please run: source {shell_rc}", Colors.YELLOW)
            else:
                print_colored("✓ PATH already configured", Colors.GREEN)
        else:
            shell_rc.write_text(f"{path_line}\n", encoding="utf-8")
            print_colored(f"✓ Created {shell_rc} with PATH configuration", Colors.GREEN)
    except Exception as e:
        print_colored(f"⚠  Could not modify shell config: {e}", Colors.YELLOW)
        print_colored(f"Please manually add {install_dir} to your PATH", Colors.WHITE)

    return True

def run_setup() -> bool:
    """Run the setup process."""
    print_colored("🚀 Starting Z Compiler Setup...", Colors.BOLD + Colors.CYAN)
    print()

    if is_in_path():
        print_colored("✓ Z Compiler is already set up!", Colors.GREEN + Colors.BOLD)
        print_colored("You can use 'z <file>' to compile Z source files.", Colors.WHITE)
        return True

    print_colored("Installing Z Compiler...", Colors.YELLOW)
    system = platform.system().lower()
    success = install_windows() if system == "windows" else install_unix()

    if success:
        print()
        print_colored("━" * 50, Colors.GREEN)
        print_colored("🎉 Setup Complete!", Colors.GREEN + Colors.BOLD)
        print_colored("━" * 50, Colors.GREEN)
        print_colored("You can now use 'z <file>' from anywhere to compile Z files!", Colors.WHITE)
        print_colored("Try: z --help", Colors.CYAN)
    else:
        print_colored("Setup failed. Please try again or install manually.", Colors.RED)

    return success

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
    except Exception:
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
        standard = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "Z_Compiler" / "z.exe"
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
                # Fallback: schedule replacement via a temporary batch script
                if platform.system().lower() == "windows":
                    bat = Path(tmpdir) / "z_update.bat"
                    bat.write_text(
                        f"@echo off\n"
                        f"timeout /t 1 /nobreak > nul\n"
                        f"copy /Y \"{tmp_path}\" \"{target}\" > nul\n"
                        f"del \"{tmp_path}\" > nul 2>&1\n"
                        f"del \"%~f0\"\n",
                        encoding="utf-8"
                    )
                    try:
                        subprocess.Popen(["cmd", "/c", str(bat)], close_fds=True)
                        print_colored("⚠  Replacement scheduled. Close running Z and it will update.", Colors.YELLOW)
                        return True
                    except Exception:
                        print_colored(f"✗ Update failed: {e}", Colors.RED)
                        return False
                else:
                    print_colored(f"✗ Update failed: {e}", Colors.RED)
                    return False
        except Exception as e:
            print_colored(f"✗ Update failed: {e}", Colors.RED)
            return False

    print_colored("✓ Z updated successfully!", Colors.GREEN)
    return True
