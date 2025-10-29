"""ZLang Compiler — main entry point and CLI interface."""

import sys
import os
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from setup_update import Colors, print_colored, is_in_path, run_setup, show_setup_message, update_z_compiler, handle_cli_setup_and_version, print_version, VERSION

try:
    from lexer import parse_z_file
    from optimizer import optimize_instructions
    from codegen import generate_c_code
    from errors import CompilerError, ErrorCode
    from semantics import validate_const_and_types
except ImportError:
    # If running as standalone executable, modules might not be available
    parse_z_file = None
    optimize_instructions = None
    generate_c_code = None
    CompilerError = None
    ErrorCode = None
    validate_const_and_types = None
def format_time(seconds):
    if seconds < 0.001:  # Less than 1ms
        if seconds < 0.000001:  # Less than 1μs
            return f"{seconds * 1e9:.1f} ns"
        return f"{seconds * 1e6:.1f} μs"
    return f"{seconds * 1000:.1f} ms"

# ============ INSTALLATION FUNCTIONS ============






HELP_TEXT = f"""
🔧 Z Compiler v{VERSION}

SETUP/UPDATE:
    z -begin      Install Z compiler to PATH
    z -setup      Install Z compiler to PATH (alias for -begin)
    z -update     Update Z compiler to latest release (alias: -u)
    z -v          Show version
    z --version   Show version

USAGE:
    z <source.z> -f <format> [-o <output>] [-c <compiler>]
    z <source.z>             (defaults to .exe output)
    z -h                     Show this help

Options:
    -f <format>   Output format:
                    c   → generate C source code (.c)
                    exe → compile to executable (.exe) [default]
    -o <output>   Output file name (default: <source>.<format>)
    -c <compiler> C compiler to use (clang, gcc) [default: clang]
    -h, --help    Show this help
    -v, --version Show version

Examples:
    z program.z              # Compile to program.exe
    z program.z -f c         # Generate program.c
    z program.z -f exe -o my_program.exe
"""

def validate_input_path(input_path: str) -> str:
    """Validate and resolve input file path, preventing directory traversal."""
    try:
        # Resolve to absolute path
        abs_path = os.path.abspath(input_path)

        # Check if path exists and is a file
        if not os.path.isfile(abs_path):
            raise CompilerError(
                f"Input file not found: {input_path}",
                error_code=ErrorCode.FILE_NOT_FOUND,
                file_path=abs_path
            )

        # Basic security check - ensure path doesn't contain suspicious patterns
        # This is a simple check; in production, more sophisticated validation would be needed
        if '..' in abs_path or abs_path.startswith('/') and len(abs_path) > 1:
            # Additional validation could be added here for absolute paths
            pass

        return abs_path
    except Exception as e:
        if isinstance(e, CompilerError):
            raise
        raise CompilerError(f"Invalid input path: {e}", error_code=ErrorCode.INVALID_FILE_FORMAT, file_path=input_path)

def validate_output_path(output_path: str, input_path: str = "") -> str:
    """Validate and resolve output file path, preventing directory traversal."""
    try:
        # Resolve to absolute path
        abs_path = os.path.abspath(output_path)

        # Basic security check - ensure output is in a reasonable location
        # For now, we'll allow output anywhere, but this could be restricted
        # to specific directories in a production system

        return abs_path
    except Exception as e:
        raise CompilerError(f"Invalid output path: {e}", error_code=ErrorCode.INVALID_FILE_FORMAT, file_path=input_path)

def run_command(cmd, check=False):
    """
    Run a command and return (success: bool, output: str, error: str).
    
    Args:
        cmd: Command to run as list of strings
        check: If True, raise CalledProcessError on non-zero return code
    """
    try:
        import subprocess
        result = subprocess.run(
            cmd,
            check=check,  # Raise exception on non-zero exit if check=True
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,  # Safer to not use shell
            universal_newlines=True
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except Exception as e:
        return False, "", f"Command '{' '.join(cmd)}' failed: {str(e)}"

def find_compiler(preferred_compiler: Optional[str] = None) -> Tuple[Optional[str], Optional[list]]:
    """
    Find available C compiler, using preferred_compiler if specified,
    trying MSVC on Windows, then clang, then gcc.
    Returns (compiler_name, command_args) or (None, None) if no compiler found.
    """
    compilers_to_try = []
    
    # Add preferred compiler first if specified
    if preferred_compiler:
        compilers_to_try.append((preferred_compiler, [preferred_compiler], False))
    
    # On Windows, try to find MSVC first
    if sys.platform == 'win32':
        # Try to find MSVC compiler (cl.exe)
        vswhere_path = r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
        vswhere_path = os.path.expandvars(vswhere_path)
        
        if os.path.isfile(vswhere_path):
            try:
                import subprocess
                vswhere_cmd = [
                    vswhere_path,
                    '-latest',
                    '-products', '*',
                    '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                    '-property', 'installationPath'
                ]
                result = subprocess.run(vswhere_cmd, capture_output=True, text=True, check=True)
                vc_path = result.stdout.strip()
                
                if vc_path:
                    # Use raw string for Windows path to avoid escape sequence warnings
                    vcvars_path = os.path.join(vc_path, r'VC\Auxiliary\Build\vcvars64.bat')
                    if os.path.isfile(vcvars_path):
                        # Set up environment for MSVC using a temporary batch file
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.bat', delete=False, mode='w') as f:
                            f.write(f'@echo off\ncall "{vcvars_path}"\nset')
                            batch_file = f.name
                        
                        try:
                            result = subprocess.run(
                                ['cmd', '/c', batch_file],
                                capture_output=True,
                                text=True,
                                shell=True
                            )
                            
                            if result.returncode == 0:
                                # Update environment with MSVC variables
                                for line in result.stdout.splitlines():
                                    if '=' in line:
                                        name, value = line.split('=', 1)
                                        os.environ[name] = value
                        finally:
                            try:
                                os.unlink(batch_file)
                            except:
                                pass
                        compilers_to_try.append(("msvc", ["cl.exe"], True))
            except (subprocess.SubprocessError, OSError):
                pass
    
    # Add standard compilers to try
    compilers_to_try.extend([
        ("clang", ["clang"], False),
        ("gcc", ["gcc"], False),
        ("clang", ["clang.exe"], False),  # Windows variants
        ("gcc", ["gcc.exe"], False),
    ])
    
    # Try each compiler
    tested = set()
    for name, cmd, is_msvc in compilers_to_try:
        if name in tested:
            continue
            
        if is_msvc:
            # For MSVC, we just check if cl.exe exists since vswhere already found it
            success = os.path.isfile(cmd[0]) or any(
                os.path.isfile(os.path.join(path, cmd[0]))
                for path in os.environ.get('PATH', '').split(os.pathsep)
            )
            version = "Microsoft (R) C/C++"
        else:
            success, out, _ = run_command(cmd + ["--version"])
            version = out.split('\n')[0] if out and success else 'version unknown'
        
        if success:
            print(f"Found {name}: {version}")
            return name, cmd + (["-nologo"] if is_msvc else [])
            
        tested.add(name)
    
    # If we get here, no compilers were found
    error_msg = "No C compiler found. "
    if sys.platform == 'win32':
        error_msg += (
            "Please install one of the following:\n"
            "1. Microsoft Visual Studio with C++ workload\n"
            "2. MinGW-w64\n"
            "3. LLVM (clang) for Windows\n\n"
            "Then ensure the compiler is in your system PATH."
        )
    else:
        error_msg += "Please install clang or gcc and ensure it's in your PATH."

    raise CompilerError(error_msg, error_code=ErrorCode.MISSING_DEPENDENCY)

def compile_zlang(input_path: str, output_path: str, output_format: str, compiler: str = 'clang'):
    """Compile ZLang source into C or executable."""
    abs_c_file = None  # Track C file for cleanup
    try:
        # Validate and resolve input path
        validated_input_path = validate_input_path(input_path)
            
        # Ensure output directory exists
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir:  # Only create directory if path contains a directory
            os.makedirs(output_dir, exist_ok=True)
        
        import time
        
        # Parse and generate code with timing
        start_time = time.time()
        
        # 1. Parsing
        parse_start = time.time()
        instructions, variables, declarations = parse_z_file(validated_input_path)
        parse_time = time.time() - parse_start
        
        # 2. Optimization
        opt_start = time.time()
        optimized = optimize_instructions(instructions, validated_input_path)
        opt_time = time.time() - opt_start
        
        # 2.5 Semantic validation (const and type enforcement)
        validate_const_and_types(optimized, declarations, validated_input_path)
        
        # 3. Code Generation
        gen_start = time.time()
        c_code = generate_c_code(optimized, variables, declarations, z_file=validated_input_path)
        gen_time = time.time() - gen_start
               
        # Determine output file paths
        if output_format == 'exe':
            abs_c_file = os.path.abspath(os.path.splitext(output_path)[0] + '.c')
            # Only add .exe extension if not already present
            if sys.platform == 'win32' and not output_path.lower().endswith('.exe'):
                abs_output_path = os.path.abspath(output_path + '.exe')
            else:
                abs_output_path = os.path.abspath(output_path)
        else:
            abs_c_file = os.path.abspath(output_path)
            if not abs_c_file.lower().endswith('.c'):
                abs_c_file += '.c'
            abs_output_path = abs_c_file
        
        # Write C code to file
        write_start = time.time()
        try:
            with open(abs_c_file, 'w', encoding='utf-8') as f:
                f.write(c_code)
            write_time = time.time() - write_start
        except IOError as e:
            raise CompilerError(
                f"Failed to write output file '{abs_c_file}': {str(e)}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
                file_path=validated_input_path
            ) from e
        
        compile_time = 0
        link_time = 0
        
        # If target is executable, compile the C code
        if output_format == 'exe':
            compiler_name, compiler_cmd = find_compiler(compiler)
            
            if compiler_name == 'msvc':
                cmd = [
                    'cl.exe',
                    f'/Fe{abs_output_path}',
                    '/O2',
                    '/nologo',
                    abs_c_file,
                    '/link',
                    '/SUBSYSTEM:CONSOLE',
                    '/MACHINE:X64' if sys.maxsize > 2**32 else '/MACHINE:X86'
                ]
            else:
                # Use the actual compiler command found by find_compiler()
                cmd = compiler_cmd + [
                    abs_c_file,
                    '-o', abs_output_path,
                    '-O2',
                    '-Wall', '-Wextra',
                    '-D_CRT_SECURE_NO_WARNINGS'
                ]
                # For Windows, ensure we're targeting the right architecture and format
                if sys.platform == 'win32':
                    cmd.extend(['-target', 'x86_64-windows-msvc'])
            
            # Run the compiler
            compile_start = time.time()
            success, out, err = run_command(cmd, check=False)
            compile_time = time.time() - compile_start
            
            if not success:
                error_msg = f"Compilation failed with {compiler_name}"
                if err.strip():
                    error_msg += f"\n{err}"
                raise CompilerError(error_msg, error_code=ErrorCode.COMPILATION_ERROR, file_path=validated_input_path)
            
            if not os.path.exists(abs_output_path):
                raise CompilerError(
                    f"Compilation succeeded but output file was not created: {abs_output_path}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                    file_path=validated_input_path
                )
            
            # Clean up C file after successful compilation
            try:
                os.remove(abs_c_file)
                abs_c_file = None  # Mark as cleaned up
            except OSError:
                pass
            
            total_time = time.time() - start_time
            
            # Print performance summary
            print("\n=== Compilation Summary ===")
            print(f"Parsing:       {format_time(parse_time)}")
            print(f"Optimization:  {format_time(opt_time)}")
            print(f"CodeGen:       {format_time(gen_time)}")
            print(f"Write:         {format_time(write_time)}")
            print(f"Compilation:   {format_time(compile_time)}")
            print("-" * 30)
            print(f"Total time:    {format_time(total_time)}")
            print(f"Output:        {abs_output_path}")
            print(f"Size:          {os.path.getsize(abs_output_path) / 1024:.1f} KB")

    except CompilerError:
        # Clean up C file if compilation failed and we created one
        if abs_c_file and os.path.exists(abs_c_file):
            try:
                os.remove(abs_c_file)
            except OSError:
                pass
        raise  # Re-raise the CompilerError
    except Exception:
        # Clean up C file if any unexpected error occurred and we created one
        if abs_c_file and os.path.exists(abs_c_file):
            try:
                os.remove(abs_c_file)
            except OSError:
                pass
        raise  # Re-raise the exception

def parse_args(args):
    """Simple flag-based CLI parser."""
    # Handle setup commands first
    if len(args) == 1 and args[0] in ["-begin", "-setup"]:
        return "SETUP", None, None, None
    if len(args) == 1 and args[0] in ["-update", "-u"]:
        return "UPDATE", None, None, None
    
    if len(args) == 0:
        # Check if we're running from PATH or repo directory
        current_exe = Path(sys.executable).resolve()
        script_dir = Path(__file__).parent.resolve() if not getattr(sys, 'frozen', False) else Path(sys.executable).parent.resolve()
        running_from_repo = current_exe.parent == script_dir
        
        if not running_from_repo and not is_in_path():
            show_setup_message()
        else:
            print(HELP_TEXT)
        sys.exit(0)
    
    input_file = None
    output_path = None
    output_format = "exe"  # Default to exe
    compiler = 'clang'  # Default compiler
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == "-h" or arg == "--help":
            print(HELP_TEXT)
            sys.exit(0)
        elif arg == "-v" or arg == "--version":
            print_version()
            sys.exit(0)
        
        elif arg in ["-begin", "-setup"]:
            return "SETUP", None, None, None
        elif arg in ["-update", "-u"]:
            return "UPDATE", None, None, None
            
        elif arg == "-f" or arg == "--format":
            if i + 1 >= len(args):
                print_colored("Error: Missing format after -f", Colors.RED)
                print(HELP_TEXT)
                sys.exit(1)
            output_format = args[i + 1].lower()
            if output_format not in ["c", "exe"]:
                print_colored(f"Error: Invalid format '{output_format}'. Must be 'c' or 'exe'.", Colors.RED)
                sys.exit(1)
            i += 1
            
        elif arg == "-o" or arg == "--output":
            if i + 1 >= len(args):
                print_colored("Error: Missing output file after -o", Colors.RED)
                print(HELP_TEXT)
                sys.exit(1)
            output_path = args[i + 1]
            i += 1
            
        elif arg == "-c" or arg == "--compiler":
            if i + 1 >= len(args):
                print_colored("Error: Missing compiler after -c", Colors.RED)
                print(HELP_TEXT)
                sys.exit(1)
            compiler = args[i + 1].lower()
            if compiler not in ["clang", "gcc"]:
                print_colored(f"Error: Invalid compiler '{compiler}'. Must be 'clang' or 'gcc'.", Colors.RED)
                sys.exit(1)
            i += 1
            
        elif not arg.startswith("-"):
            if input_file is not None:
                print_colored("Error: Multiple input files specified", Colors.RED)
                print(HELP_TEXT)
                sys.exit(1)
            input_file = arg
            
        else:
            print_colored(f"Error: Unknown option '{arg}'", Colors.RED)
            print(HELP_TEXT)
            sys.exit(1)
            
        i += 1
    
    if input_file is None:
        print_colored("Error: No input file specified", Colors.RED)
        print(HELP_TEXT)
        sys.exit(1)
    
    if output_path is None:
        base = os.path.splitext(input_file)[0]
        output_path = f"{base}.{output_format}"
    
    return input_file, output_path, output_format, compiler

def check_compilation_requirements():
    """Check if all required modules are available for compilation"""
    if any(module is None for module in [parse_z_file, optimize_instructions, generate_c_code, CompilerError, ErrorCode, validate_const_and_types]):
        print_colored("✗ Error: Compiler modules not found", Colors.RED)
        print_colored("This Z executable doesn't include the compiler components.", Colors.WHITE)
        print_colored("Please ensure all .py files are available or use a complete build.", Colors.WHITE)
        return False
    return True

if __name__ == "__main__":
    # Handle version and setup flags early
    if handle_cli_setup_and_version(sys.argv[1:]):
        sys.exit(0)
    
    try:
        input_file, output_path, output_format, compiler = parse_args(sys.argv[1:])
        
        # Handle setup/update commands
        if input_file == "SETUP":
            sys.exit(run_setup())
        if input_file == "UPDATE":
            sys.exit(0 if update_z_compiler() else 1)
        
        # Check if we're running from an uninstalled location without setup
        current_exe = Path(sys.executable).resolve()
        script_dir = Path(__file__).parent.resolve() if not getattr(sys, 'frozen', False) else Path(sys.executable).parent.resolve()
        running_from_repo = current_exe.parent == script_dir
        
        if not running_from_repo and not is_in_path():
            print_colored("⚠  Z Compiler is not set up yet!", Colors.YELLOW + Colors.BOLD)
            print()
            print_colored("To set up Z Compiler, run:", Colors.WHITE)
            print_colored("  z -begin", Colors.GREEN + Colors.BOLD)
            print()
            sys.exit(1)
        
        # Check if compiler modules are available
        if not check_compilation_requirements():
            sys.exit(1)
        
        # Proceed with compilation
        compile_zlang(input_file, output_path, output_format, compiler)
        
    except KeyboardInterrupt:
        print_colored("\n⚠  Interrupted by user", Colors.YELLOW)
        sys.exit(130)
    except Exception as e:
        print_colored(f"✗ Unexpected error: {e}", Colors.RED)
        sys.exit(1)
