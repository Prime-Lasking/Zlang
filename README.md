# Z Compiler

A simple compiler that translates Z language source code into C or directly into an executable. The compiler is written in Python and uses GCC for final compilation.

## Table of Contents
- [Introduction](#introduction)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Language Reference](#language-reference)
  - [Syntax](#syntax)
  - [Variables](#variables)
  - [Instructions](#instructions)
    - [Data Movement](#data-movement)
    - [Arithmetic](#arithmetic)
    - [Control Flow](#control-flow)
    - [I/O Operations](#io-operations)
  - [Functions](#functions)
  - [Labels](#labels)
  - [Comments](#comments)
- [Example Programs](#example-programs)
- [Best Practices](#best-practices)
- [Performance](#performance)
- [License](#license)

## Introduction

Z is a simple, assembly-like programming language designed for educational purposes and lightweight scripting. It features a minimalistic syntax and a small set of instructions that compile to efficient C code.

## Features

- **Simple Syntax**: Easy-to-learn assembly-like language with flexible operand formatting
- **Fast Compilation**: Optimized for quick compilation times
- **Multiple Output Formats**: Generate C code or directly compile to executable
- **Cross-Platform**: Works on any platform with Python and GCC installed
- **Rich Instruction Set**: Supports arithmetic, control flow, I/O operations, and functions
- **Efficient Code Generation**: Produces optimized C code
- **Function Support**: Define and call functions with parameters and return values
- **Flexible Syntax**: Supports both comma and space-separated operands

## Requirements

- Python 3.8 or higher
- GCC (GNU Compiler Collection) for compiling to executables

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

## Syntax

Z programs are text files with a `.z` extension. Each line contains either:
- An instruction with optional operands
- A function definition
- A label definition
- A comment

### Operand Formatting

Z supports flexible operand formatting:
- **Comma-separated**: `MOV x, 10` or `ADD a, b, result`
- **Space-separated**: `MOV x 10` or `ADD a b result`
- **Mixed**: You can use commas for clarity in complex expressions

### Semicolons

- **Inside functions**: Semicolons are **required** at the end of each statement
- **Outside functions**: Semicolons are **optional**
- Inline comments can follow semicolons: `MOV x, 10; // Set x to 10`

## Variables

- Variable names must be valid C identifiers (letters, numbers, and underscores, not starting with a number)
- Variables are case-sensitive
- Variables are automatically declared upon first use and initialized to 0
- All variables are stored as double-precision floating-point numbers

## Instructions

### Data Movement

#### `MOV dest, src`
Copies a value or variable to a destination variable.

```
MOV x, 10      ; x = 10
MOV y, x       ; y = x
```

### Arithmetic

#### `ADD dest, src` or `ADD src1, src2, dest`
Adds values and stores the result. Can be used in two forms:
- Two operands: `dest += src` (adds src to dest)
- Three operands: `dest = src1 + src2` (adds src1 and src2, stores in dest)

```
ADD x, 5        ; x = x + 5
ADD a, b, y     ; y = a + b
```

#### `SUB dest, src1, src2?`
Subtracts values and stores the result. Can be used in two forms:
- Two operands: `dest -= src1`
- Three operands: `dest = src1 - src2`

```
SUB x, 3        ; x = x - 3
SUB y, x, 2     ; y = x - 2
```

#### `MUL dest, src1, src2?`
Multiplies values and stores the result. Can be used in two forms:
- Two operands: `dest *= src1`
- Three operands: `dest = src1 * src2`

```
MUL x, 2        ; x = x * 2
MUL y, x, 10    ; y = x * 10
```

#### `DIV dest, src1, src2?`
Divides values and stores the result. Can be used in two forms:
- Two operands: `dest /= src1`
- Three operands: `dest = src1 / src2`

```
DIV x, 2        ; x = x / 2
DIV y, x, 4     ; y = x / 4
```

#### `MOD dest, src1, src2?`
Calculates the modulo and stores the result. Can be used in two forms:
- Two operands: `dest = dest % src1`
- Three operands: `dest = src1 % src2`

```
MOD x, 3        ; x = x % 3
MOD y, x, 5     ; y = x % 5
```

### Control Flow

#### `CMP a, b, op`
Compares two values using the specified operator and sets the `cmp_flag` for conditional jumps (`JZ`, `JNZ`).

**Syntax:**

**Supported operators:**
- `==` (equal to)  
- `!=` (not equal to)  
- `<`  (less than)  
- `>`  (greater than)  
- `<=` (less than or equal to)  
- `>=` (greater than or equal to)  

**Examples:**
```asm
CMP x, y, ==       ; cmp_flag = (x == y)
CMP a, b, !=       ; cmp_flag = (a != b)
CMP i, 10, <       ; cmp_flag = (i < 10)
CMP score, 100, >= ; cmp_flag = (score >= 100)

```

#### `JMP label`
Jumps unconditionally to the specified label.

```
JMP loop_start
```

#### `JZ label`
Jumps to the label if the comparison result was zero (cmp_flag == 0).

```
JZ is_equal
```

#### `JNZ label`
Jumps to the label if the comparison result was not zero (cmp_flag != 0).

```
JNZ not_equal
```

### I/O Operations

#### `PRINT value`
Prints a numeric value to standard output.

```
PRINT x        ; Prints the value of x
PRINT 42       ; Prints the number 42
```

#### `PRINTSTR "text"`
Prints a string literal to standard output.

```
PRINTSTR "Hello, World!"
```

#### `HALT`
Terminates the program.

```
HALT
```

## Labels

- Labels mark locations in the code that can be jumped to
- Defined by a name followed by a colon `:`
- Must be unique within a program

```
start_loop:
    ; code here
    JMP start_loop
```

## Functions

Z now supports real functions that compile to C functions with proper parameters and return values.

### Function Definition

```
FN function_name(param1, param2, ...):
    // Function body (semicolons required)
    instruction1;
    instruction2;
    RET return_value;
END
```

**Example:**
```
FN add(a, b):
    ADD a, b, result;
    RET result;
END
```

This compiles to:
```c
double add(double a, double b) {
    result = a + b;
    return result;
}
```

### Function Calls

#### Without Return Value
```
CALL function_name(arg1, arg2, ...)
```

#### With Return Value
```
CALL function_name(arg1, arg2, ...), result_var
```

**Examples:**
```
CALL print_hello()                    // Call with no args
CALL add(x, y), sum                   // Call with return value
CALL calculate(a, b, c), result       // Multiple arguments
```

### Return Statement

```
RET value;      // Return a value
RET;            // Return without a value
```

**Note:** Return statements must end with a semicolon inside functions.

## Comments

- Start with `//` for inline comments
- Extend to the end of the line
- Can appear on their own line or after an instruction

```
// This is a comment
MOV x, 10            // Initialize x to 10
ADD a, b, result;    // Inside function (semicolon required)
```

## Example Programs

### Function Example: Add Two Numbers

```
// Function to add two numbers
FN add(a, b):
    ADD a, b, result;  // Add a and b, store in result
    RET result;         // Return the result
END

// Main program
MOV x, 10            // Set x to 10
MOV y, 20           // Set y to 20

// Call the add function and store result
CALL add(x, y), sum
PRINT sum           // Prints: 30
HALT
```

### Factorial Function

```
// Calculate factorial recursively
FN factorial(n):
    CMP n, 1, <=
    JZ base_case
    
    SUB n, 1, temp;
    CALL factorial(temp), result;
    MUL n, result, final;
    RET final;
    
base_case:
    MOV result, 1;
    RET result;
END

// Main program
MOV num, 5
CALL factorial(num), answer
PRINT answer        // Prints: 120
HALT
```

### Prime Number Checker

```
// Check if a number is prime
MOV number, 7919    // Number to check
MOV is_prime, 1     // Assume prime initially
MOV i, 2            // Start divisor from 2

// Special cases
CMP number, 2, <    // If number < 2
JZ not_prime
CMP number, 2, ==   // If number == 2
JZ is_prime_number

check_loop:
    // Check if i > sqrt(number)
    MOV temp, i
    MUL temp, temp
    CMP temp, number, >
    JZ is_prime_number
    
    // Check if number is divisible by i
    MOV temp, number
    MOD temp, i
    CMP temp, 0, ==
    JZ not_prime
    
    // Next divisor
    ADD i, 1
    JMP check_loop

not_prime:
    MOV is_prime, 0

is_prime_number:
    PRINT number
    PRINTSTR " is "
    CMP is_prime, 0, ==
    JZ print_prime
    PRINTSTR "not "
print_prime:
    PRINTSTR "a prime number\n"
    HALT
```

### Factorial Calculator

```
; Calculate factorial of a number
MOV n, 10          ; Number to calculate factorial of
MOV result, 1      ; Initialize result
MOV i, 1           ; Counter

fact_loop:
    MUL result, result, i  ; result = result * i
    ADD i, 1               ; i = i + 1
    CMP i, n, <=           ; Compare i <= n
    JNZ fact_loop          ; Loop if true

PRINT n
PRINTSTR "! = "
PRINT result
HALT
```

### Performance Benchmark

```
; Simple benchmark to test performance
MOV iterations, 1000000  ; Number of iterations
MOV x, 0
MOV y, 1
MOV i, 0

benchmark_loop:
    ; Perform some arithmetic operations
    ADD x, y
    MUL x, 2
    MOD x, 1000
    
    ; Update counter and loop
    ADD i, 1
    CMP i, iterations, <
    JNZ benchmark_loop

PRINTSTR "Benchmark completed. Final x = "
PRINT x
HALT
```

## Best Practices

1. **Variable Naming**: Use descriptive names for variables and labels (e.g., `counter` instead of `c`)
2. **Comments**: Document complex logic and the purpose of variables using `//`
3. **Whitespace**: Use consistent indentation (2-4 spaces recommended, especially inside functions)
4. **Labels**: Use meaningful names for labels (e.g., `process_data` instead of `l1`)
5. **Functions**: Break complex logic into reusable functions
6. **Semicolons**: Always use semicolons inside functions; they're optional outside
7. **Operand Formatting**: Use commas for clarity in multi-operand instructions
8. **Error Handling**: Check for division by zero and other edge cases
9. **Testing**: Test edge cases, especially with arithmetic operations and function calls
10. **Performance**: For critical loops, minimize instructions inside the loop
11. **Readability**: Place related instructions together with blank lines between logical sections

## Performance

The compiler provides detailed timing information:
- Parsing time
- Code generation time
- Compilation time (when generating executables)
- Total time

Times are automatically displayed in the most appropriate unit (s, ms, μs, or ns).

## Limitations

- No arrays or complex data structures
- No string manipulation beyond printing literals
- Function parameters and local variables share the global namespace
- Limited error reporting during compilation
- No nested function definitions
- No function overloading

## License

This project is open source and available under the [GNU General License](LICENSE).
