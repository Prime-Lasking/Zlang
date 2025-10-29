# Z Compiler

🚀 The Compiler for the Z programming language.

**Single File Distribution** • **Integrated Installation** • **No Dependencies** • **Enhanced Robustness**

---

## ⚡ Quick Start

### For Users

1. **Get `z.exe`** (single file - no installation needed)
2. **Setup**: `z.exe -begin` or `z.exe -setup` (installs current z.exe and adds to PATH)
3. **Compile**: `z program.z` (creates program.exe)
4. **Update**: `z -update` (gets the latest release and replaces the installed `z.exe`)

```bash
# Download z.exe, then:
z.exe -begin          # One-time setup (installs current z.exe)
z.exe -setup          # Same as -begin
z -v                  # Check version
z hello.z             # Compile to hello.exe
z program.z -f c      # Generate C source
z -update             # Update to latest release
z --help              # Show all options
```

### For Developers

```bash
# Build the compiler
python -m PyInstaller --onefile --name=z --console --clean main.py

# Test
z.exe -begin
z test.z
```

---

## 📁 Distribution

**What users get:**
- ✅ **Single `z.exe` file** (7-8MB, completely self-contained)
- ✅ **No Python installation required**
- ✅ **No additional files needed**
- ✅ **Works offline**

**What `z -begin` and `z -setup` do:**
- **Windows**: Installs current z.exe to `%ProgramFiles%\Z\bin` (or `%LOCALAPPDATA%\Programs\Z\bin` if no admin rights)
- **System-wide PATH first**: Tries to update system PATH; falls back to user PATH if needed
- **Smart replacement**: Finds other z.exe files on PATH and prompts to replace them
- **PATH deduplication**: Ensures no duplicate entries while putting new install first
- **Linux/macOS**: Not implemented in v0.8 (Windows-first release)
- **⚠ Note**: PATH changes require opening a new terminal to take effect

**What `z -update` does:**
- Downloads the latest release from GitHub and replaces the existing `z.exe` found in PATH (backs up the old file as `.bak` when possible).

---

## 🔧 Usage

### Compilation Commands

```bash
# Default: Compile to executable
z program.z                    # → program.exe
z program.z -o myapp.exe       # → myapp.exe

# Generate C source
z program.z -f c               # → program.c
z program.z -f c -o output.c   # → output.c

# Specify compiler
z program.z -c gcc             # Use GCC instead of Clang
z program.z -c clang           # Use Clang (default)
```

### Setup & Update Commands

```bash
z -begin         # Install current Z compiler to PATH
z -setup         # Same as -begin
z -v             # Show version
z --version      # Show version
z -update | -u   # Update installed Z to latest release
z --help         # Show help
```

---

## ✨ Features

### 🎯 Core Features
- ✅ **Single executable distribution**
- ✅ **Integrated PATH installation**
- ✅ **Cross-platform** (Windows, Linux, macOS)
- ✅ **No external dependencies**
- ✅ **Automatic C compiler detection**
- ✅ **Built-in updater** (`z -update`)

### 🛡️ Enhanced Robustness & Security
- ✅ **Path traversal protection** for input/output files
- ✅ **Memory leak prevention** with proper cleanup on failures
- ✅ **Race condition fixes** in update mechanism with retry logic
- ✅ **Input validation** for all file operations
- ✅ **UTF-8 encoding enforcement** for source files

### 🎨 User Experience
- ✅ **Colored terminal output** (Windows-compatible)
- ✅ **Clear progress indicators**
- ✅ **Helpful error messages with file/line context**
- ✅ **Performance timing reports**
- ✅ **Comprehensive error codes** for better debugging

### 🔒 Error Handling & Validation
- ✅ **Variable redeclaration detection** prevents naming conflicts
- ✅ **Division by zero detection** in compile-time constants
- ✅ **Unknown opcode validation** prevents invalid instructions
- ✅ **Mixed indentation handling** (tabs vs spaces)
- ✅ **Type consistency** for global variables
- ✅ **Logical operator translation** (AND, OR, NOT → &&, ||, !)
- ✅ **Discard variable handling** in function calls

---

## 📘 Language Overview

Z provides a straightforward way to write procedural programs with explicit instructions like `MOV`, `ADD`, `SUB`, `PRINT`, combined with modern control flow structures.

### 🚀 Quick Example

**Input (`example.z`)**
```z
FN fibonacci(int n) -> int:
    IF n <= 1:
        RET n

    // Calculate fibonacci using iterative approach
    CONST int initial_a 0
    CONST int initial_b 1
    MOV int a initial_a
    MOV int b initial_b
    MOV int fib 0

    FOR i 2..n:
        // Calculate next fibonacci number: fib = a + b
        ADD a b fib
        // Shift: a becomes old b, b becomes new fib
        MOV a b
        MOV b fib

    RET b

FN main():
    MOV int count 10
    MOV int result 0

    // Calculate fibonacci
    CALL fibonacci(count) -> result
    PRINT result

    RET 0
```

**Output (`example.exe`)**
```
55
```

---

## 🧠 Language Features

### Variables & Data Types
- **Type declarations**: `int`, `float`, `double`, `bool`, `string`
- **Mutable variables**: `MOV int x 10` (mutable by default)
- **Immutable constants**: `CONST int MAX_SIZE 100` (cannot be reassigned)
- **Redeclaration protection**: Prevents accidental variable redeclaration

### Arithmetic Operations
- `ADD a b result` - Addition
- `SUB a b result` - Subtraction  
- `MUL a b result` - Multiplication
- `DIV a b result` - Division
- `MOD a b result` - Modulo
- `INC variable` - Increment variable by 1
- `DEC variable` - Decrement variable by 1

### Control Flow

**Functions:**
```z
FN function_name(param1, param2):
    // function body
    RET value

FN calculate(int x, double y) -> double:
    CONST double factor 2.5
    MUL x factor temp
    ADD temp y result
    RET result
```

**Function Calls:**
```z
CALL function_name(arg1, arg2) -> result_var
```

**Conditionals:**
```z
IF condition:
    // if body
ELIF other_condition:
    // elif body
ELSE:
    // else body
```

**Loops:**
```z
WHILE condition:
    // loop body

FOR variable start..end:
    // loop body
```

### I/O Operations
- `PRINT value` - Print a number
- `PRINTSTR "text"` - Print a string
- `READ variable` - Read input (backward compatibility)
- `READ <type> <prompt> <variable>` - Read with type and prompt (e.g., `READ int "Enter age: " age`)
- `ERROR "message"` - Print error and exit

### Enhanced Features
- **Logical operators**: `AND`, `OR`, `NOT` properly translated to C (`&&`, `||`, `!`)
- **Discard variables**: `CALL func() _` discards return value
- **Compile-time constants**: Division by zero and other errors caught at compile time

---

## ⚡ Compiler Optimizations

### Performance Features
- **Constant folding**: Compile-time evaluation of constant expressions
- **Precompiled regexes**: Module-level regex compilation for faster parsing
- **Identifier caching**: Memoized sanitization to avoid redundant processing
- **Smart code generation**: Efficient string building and cached transformations

### Example Optimization
```z
// Input
ADD 10 20 x
MUL 5 3 y
ADD x y result

// Optimized (constants folded)
MOV 30 x
MOV 15 y  
ADD x y result
```

### Robustness Improvements
- **File size validation** prevents memory exhaustion attacks
- **Path traversal protection** prevents accessing files outside intended directories
- **Memory cleanup** ensures temporary files are removed even on failures
- **Race condition fixes** in update mechanism with robust retry logic

---

## 🧩 Architecture

### Components

| File | Purpose |
|------|----------|
| `main.py` | Entry point and CLI (parsing, compilation, compiler discovery) |
| `setup_update.py` | Setup (PATH install), PATH detection, and updater (`z -update`) |
| `lexer.py` | Tokenizes `.z` source into structured instructions |
| `optimizer.py` | Optimizes instruction set with constant folding |
| `codegen.py` | Converts optimized code to C with type tracking |
| `errors.py` | Structured compiler error handling with codes |
| `semantics.py` | Semantic analysis and validation |

### Compilation Pipeline
```
.z source → lexer → optimizer → codegen → C code → [optional] C compiler → executable
```

### Enhanced Error Handling
- **File/line context** in all error messages
- **Error codes** for programmatic error handling
- **Path validation** for security
- **Memory-safe operations** throughout

---

## 🛠️ Compiler Requirements

### For Executable Output:
- **Windows**: MSVC (Visual Studio), MinGW-w64, or Clang
- **Linux/macOS**: GCC or Clang

The compiler automatically detects available C compilers.

### For C Generation:
- No additional requirements (works with just `z.exe`)

---

## 📊 Performance

The compiler provides detailed timing for each stage:

```
=== Compilation Summary ===
Parsing:       125.3 μs
Optimization:  45.2 μs
CodeGen:       238.7 μs
Write:         89.1 μs
Compilation:   1.2 s
------------------------------
Total time:    1.5 s
Output:        hello.exe
Size:          165.5 KB
```

## Improvements v0.9.5

The new version of Z, version 0.9.5 has added
- Added safeguards to booleans with capital True and capital False
- Fixed boolean decleration
- Added the Overflow error, error 45

Enjoy building with Z! 🚀
