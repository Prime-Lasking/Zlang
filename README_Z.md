# Z Compiler

A simple compiler that translates Z language source code into C or directly into an executable. The compiler is written in Python and uses GCC for final compilation.

## Features

- **Simple Syntax**: Easy-to-learn assembly-like language
- **Fast Compilation**: Optimized for quick compilation times
- **Multiple Output Formats**: Generate C code or directly compile to executable
- **Cross-Platform**: Works on any platform with Python and GCC installed

## Requirements

- Python 3.8 or higher
- GCC (GNU Compiler Collection) for compiling to executables

### Python Dependencies

The compiler only uses Python's standard library, so no additional Python packages are required. The following standard library modules are used:
- `re` (regular expressions)
- `os` (file system operations)
- `subprocess` (for running gcc)
- `argparse` (command line argument parsing)
- `time` (for timing execution)
- `io` (in-memory string operations)

## Installation

1. Ensure you have Python 3.8+ installed
2. Install GCC (GNU Compiler Collection) for your platform:
   - **Windows**: Install [MinGW-w64](https://www.mingw-w64.org/)
   - **macOS**: Install Xcode Command Line Tools: `xcode-select --install`
   - **Linux**: `sudo apt-get install build-essential` (Debian/Ubuntu) or equivalent

## Usage

```bash
python Compiler.py [options] <input.z>
```

### Options

- `-o, --output FILE`  Output file name (default: input.c/input.exe)
- `-f, --format FORMAT`  Output format: `c` or `exe` (default: `c`)
- `-h, --help`  Show help message

### Examples

1. Compile to C code:
   ```bash
   python Compiler.py example.z
   ```
   This will generate `example.c`

2. Compile to executable:
   ```bash
   python Compiler.py -f exe example.z
   ```
   This will generate `example.exe` (Windows) or `example` (Unix-like)

3. Specify output filename:
   ```bash
   python Compiler.py -o myprogram.exe -f exe example.z
   ```

## Language Reference

### Supported Instructions

| Instruction | Description | Example |
|-------------|-------------|---------|
| `MOV` | Move value to variable | `MOV x 10` |
| `ADD` | Add values | `ADD x y` (x += y) |
| `SUB` | Subtract values | `SUB x y` (x -= y) |
| `MUL` | Multiply values | `MUL x y` (x *= y) |
| `DIV` | Divide values | `DIV x y` (x /= y) |
| `CMP` | Compare values | `CMP x y` (sets cmp_flag) |
| `JMP` | Unconditional jump | `JMP label` |
| `JZ` | Jump if zero | `JZ label` (jumps if cmp_flag == 0) |
| `JNZ` | Jump if not zero | `JNZ label` (jumps if cmp_flag != 0) |
| `PRINT` | Print numeric value | `PRINT x` |
| `PRINTSTR` | Print string literal | `PRINTSTR Hello, World!` |
| `HALT` | End program | `HALT` |

### Example Program

```
; Simple counter example
MOV counter 0
MOV limit 10

loop_start:
    PRINT counter
    ADD counter 1
    CMP counter limit
    JNZ loop_start

PRINTSTR "Done counting!"
HALT
```

## Performance

The compiler provides detailed timing information:
- Parsing time
- Code generation time
- Compilation time (when generating executables)
- Total time

Times are automatically displayed in the most appropriate unit (s, ms, μs, or ns).

## License

This project is open source and available under the [GNU General License](LICENSE).

