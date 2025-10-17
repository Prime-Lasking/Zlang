# Z Compiler

🚀 A minimalist, blazingly fast, cross-platform compiler for the Z programming language.

**Single File Distribution** • **Integrated Installation** • **No Dependencies**

---

## ⚡ Quick Start

### For Users

1. **Get `z.exe`** (single file - no installation needed)
2. **Setup**: `z.exe -begin` (adds to PATH automatically)
3. **Compile**: `z program.z -f exe` (creates program.exe)
4. **Update**: `z -update` (gets the latest release and replaces the installed `z.exe`)

```bash
# Download z.exe, then:
z.exe -begin          # One-time setup
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

**What `z -begin` does:**
- **Windows**: Installs to `%LOCALAPPDATA%\Programs\Z_Compiler` + adds to PATH via registry
- **Linux/macOS**: Installs to `~/.local/bin` + configures shell profiles
- **All platforms**: Automatic duplicate detection and PATH management

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
z -begin         # Install Z compiler to PATH
z -setup         # Alias for -begin
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

### 🛡️ Safeguards
- ✅ **Duplicate installation prevention**
- ✅ **PATH conflict detection**
- ✅ **Setup requirement warnings**
- ✅ **Graceful error handling**
- ✅ **Repository vs installed detection**

### 🎨 User Experience
- ✅ **Colored terminal output**
- ✅ **Clear progress indicators**
- ✅ **Helpful error messages**
- ✅ **Performance timing reports**

---

## 📘 Language Overview

Z provides a straightforward way to write procedural programs with explicit instructions like `MOV`, `ADD`, `SUB`, `PRINT`, combined with modern control flow structures.

### 🚀 Quick Example

**Input (`example.z`)**
```z
FN main():
    // Immutable by default
    MOV int x 10
    // Mutable variable  
    MOV mut int y 20
    ADD x y result
    PRINT result
    
    FOR i 1..5:
        MUL i 2 doubled
        PRINT doubled
```

**Output (`example.exe`)**
```
30
2
4
6
8
10
```

---

## 🧠 Language Features

### Variables & Data Types
- **Type declarations**: `int`, `float`, `double`, `bool`, `string`
- **Immutable by default**: `MOV int x 10` (immutable)
- **Mutable variables**: `MOV mut int y 20` (mutable)
- **Dynamic typing**: Variables default to `double` if no type specified

### Arithmetic Operations
- `ADD a b result` - Addition
- `SUB a b result` - Subtraction  
- `MUL a b result` - Multiplication
- `DIV a b result` - Division
- `MOD a b result` - Modulo
- `INC variable` - Increment
- `DEC variable` - Decrement

### Control Flow

**Functions:**
```z
FN function_name(param1, param2):
    // function body
    RET value

FN calculate(int x, double y) -> double:
    MUL x y result
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
- `READ variable` - Read input from user
- `ERROR "message"` - Print error and exit

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

---

## 🧩 Architecture

### Components

| File | Purpose |
|------|----------|
| `main.py` | Entry point and CLI (parsing, compilation, compiler discovery) |
| `setup_update.py` | Setup (PATH install), PATH detection, and updater (`z -update`) |
| `lexer.py` | Tokenizes `.z` source into structured instructions |
| `optimizer.py` | Optimizes instruction set |
| `codegen.py` | Converts optimized code to C |
| `errors.py` | Structured compiler error handling |
| `semantics.py` | Semantic analysis and validation |

### Compilation Pipeline
```
.z source → lexer → optimizer → codegen → C code → [optional] C compiler → executable
```

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

Enjoy building with Z! 🚀
