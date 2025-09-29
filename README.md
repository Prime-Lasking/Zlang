# Z 

## Table of Contents
- [Introduction](#introduction)
- [Syntax](#syntax)
- [Variables](#variables)
- [Instructions](#instructions)
  - [Data Movement](#data-movement)
  - [Arithmetic](#arithmetic)
  - [Control Flow](#control-flow)
  - [I/O Operations](#io-operations)
- [Labels](#labels)
- [Comments](#comments)
- [Example Programs](#example-programs)
- [Best Practices](#best-practices)

## Introduction

Z is a simple, assembly-like programming language designed for educational purposes and lightweight scripting. It features a minimalistic syntax and a small set of instructions that compile to efficient C code.

## Syntax

Z programs are text files with a `.z` extension. Each line contains either:
- An instruction with optional operands
- A label definition
- A comment

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

#### `ADD dest, src`
Adds source to destination and stores result in destination.

```
ADD x, 5       ; x = x + 5
ADD y, x       ; y = y + x
```

#### `SUB dest, src`
Subtracts source from destination and stores result in destination.

```
SUB x, 3       ; x = x - 3
```

#### `MUL dest, src`
Multiplies destination by source and stores result in destination.

```
MUL x, 2       ; x = x * 2
```

#### `DIV dest, src`
Divides destination by source and stores result in destination.

```
DIV x, 2       ; x = x / 2
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

## Comments

- Start with a semicolon `;`
- Extend to the end of the line
- Can appear on their own line or after an instruction

```
; This is a comment
MOV x, 10  ; Initialize x to 10
```

## Example Programs

### Countdown

```
; Count down from 10 to 1
MOV counter, 10

count_loop:
    PRINT counter
    SUB counter, 1
    CMP counter, 0
    JNZ count_loop

PRINTSTR "Blast off!"
HALT
```

### Simple Calculator

```
; Simple calculator: result = (a + b) * c - d
MOV a, 5
MOV b, 3
MOV c, 2
MOV d, 4

ADD a, b      ; a = a + b
MUL a, c      ; a = a * c
SUB a, d      ; a = a - d

PRINT a       ; Print the result
HALT
```

## Best Practices

1. **Variable Naming**: Use descriptive names for variables and labels
2. **Comments**: Document complex logic and the purpose of variables
3. **Whitespace**: Use consistent indentation (4 spaces recommended)
4. **Labels**: Use meaningful names for labels
5. **Error Handling**: Check for division by zero in your code
6. **Testing**: Test edge cases, especially with arithmetic operations

## Limitations

- No support for functions or procedures
- No arrays or complex data structures
- No string manipulation beyond printing literals
- All variables are global
