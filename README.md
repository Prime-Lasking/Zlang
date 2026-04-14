# ZLang Compiler v0.13 (No longer worked on)

**ZLang** – Minimalist **programming language** and **compiler** written in **Python**.
Produces a **single-file executable** (`z.exe`) with **no dependencies** and **cross-platform support**. Ideal for learning, experimentation, and rapid prototyping.

## No longer worked on
Due to the low amount of contributors (just 1) and the amount of bugs and horrible code in this project, it is no longer maintained and worked on.
---

![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Stars](https://img.shields.io/github/stars/yourusername/zlang)
![Build](https://img.shields.io/github/actions/workflow/status/yourusername/zlang/python.yml)

---

## ⚡ ZLang Installation & Quick Start

### For Users

1. **Download**: `z.exe` (single file, no installation needed)
2. **Setup**: Run `z.exe` or double-click to install to PATH
3. **Compile**: `z program.z` → creates `program.exe`

```bash
# Quick commands
z.exe               # Run compiler
z -v                # Check version
z hello.z           # Compile to hello.exe
z program.z -f c     # Generate C source code
z --help            # Show all commands
```

### For Developers

```bash
# Build compiler from source
python -m PyInstaller --onefile --name=z --console --clean main.py

# Test
./z
z test.z
```

---

## 🔧 ZLang Compiler Usage

### Compilation Commands

```bash
# Default: compile to executable
z program.z                    # → program.exe
z program.z -o myapp.exe       # → custom executable

# Generate C source code
z program.z -f c               # → program.c
z program.z -f c -o output.c   # → output.c

# Specify compiler
z program.z -c gcc             # Use GCC
z program.z -c clang           # Use Clang (default)
```

---

## ✨ ZLang Features

### Core Features

* ✅ Single-file executable (`z.exe`)
* ✅ No external dependencies
* ✅ Cross-platform: Windows, Linux, macOS
* ✅ Module system with `IMPORT` statements
* ✅ Automatic C compiler detection

### Robustness & Security

* ✅ Path traversal protection
* ✅ Memory-safe operations and cleanup
* ✅ Race condition prevention in update mechanism
* ✅ Input validation and UTF-8 enforcement

### User Experience

* ✅ Colored terminal output
* ✅ Clear progress indicators
* ✅ Helpful error messages with file/line context
* ✅ Performance timing reports
* ✅ Comprehensive error codes

---

## 📘 ZLang Programming Language Overview

ZLang is a **procedural programming language** with modern control flow and explicit instructions like `LET`, `ADD`, `SUB`, `PRINT`.

### Quick Example – Fibonacci

```z
FN fibonacci(int n) -> int:
    IF n <= 1:
        RET n
    LET int a 0
    LET int b 1
    LET int fib 0
    FOR i 2..n:
        ADD a b fib
        LET a b
        LET b fib
    RET b

FN main():
    LET int count 10
    CALL fibonacci(count) -> result
    PRINT result
```

**Output:**

```
55
```

---

## 🧠 ZLang Language Features

### Variables & Data Types

* `int`, `float`, `double`, `bool`, `string`
* Mutable (`MOV`) and immutable (`CONST`)
* Pointer support: `PTR int ptr x`
* Arrays: fixed-size, dynamic, and empty

### Arithmetic Operations

* `ADD`, `SUB`, `MUL`, `DIV`, `MOD`
* `INC`, `DEC`

### Control Flow

* Functions: `FN name(params): ... RET value`
* Calls: `CALL func(args) -> result`
* Conditionals: `IF`, `ELIF`, `ELSE`
* Loops: `FOR`, `WHILE`

### I/O

* `IMPORT "file.z"`
* `PRINT`, `PRINTSTR`
* `READ` (with type and prompt)
* `ERROR "message"`

### Compiler Optimizations

* Constant folding
* Precompiled regexes
* Identifier caching
* Smart code generation

---

## 🧩 Architecture

| File              | Purpose                         |
| ----------------- | ------------------------------- |
| `main.py`         | CLI & entry point               |
| `setup_update.py` | PATH installation & updates     |
| `lexer.py`        | Tokenizes `.z` source code      |
| `optimizer.py`    | Constant folding & optimization |
| `codegen.py`      | Generates C code                |
| `errors.py`       | Error handling & codes          |
| `semantics.py`    | Semantic analysis & validation  |

**Compilation pipeline:**

```
.z source → lexer → optimizer → codegen → C code → [C compiler] → executable
```

---

## 🛠️ Requirements

* Windows: MSVC, MinGW-w64, or Clang
* Linux/macOS: GCC or Clang
* Python only needed for building compiler (`z.exe`)

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## ⭐ Boosting ZLang

If you like **ZLang**, please:

* ⭐ Star the repo
* 🍴 Fork & contribute
* 📢 Share with friends and communities

> Your support helps make ZLang better! 🚀
