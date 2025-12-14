# Changelog

## [0.12.2] - 2024-07-22

### 🚀 New Features

#### 1. **LET Keyword Support**
- **Replaced MOV with LET**: The `MOV` keyword has been replaced with `LET` for variable declarations and assignments.
- **Enhanced readability**: The `LET` keyword improves code clarity and aligns with modern programming language conventions.

### 🐛 Bug Fixes

#### 1. **Keyword Replacement**
- **Updated lexer**: Modified the lexer to recognize `LET` instead of `MOV`.
- **Updated optimizer**: Adjusted the optimizer to handle `LET` for constant propagation, dead code elimination, and strength reduction.
- **Updated semantics analyzer**: Updated the semantics analyzer to validate `LET` operations.
- **Updated code generator**: Modified the code generator to emit C code for `LET` operations.

### 📚 Documentation Updates

#### 1. **Updated Example Code**
- **Comprehensive test suite**: The `example.z` file now uses `LET` instead of `MOV` for all variable declarations and assignments.

### 🔧 Technical Changes

#### 1. **Lexer.py**
- Replaced `MOV` with `LET` in the `OPS` set.
- Updated parsing logic to handle `LET` for variable declarations and assignments.

#### 2. **Optimizer.py**
- Updated constant propagation to recognize `LET` operations.
- Adjusted dead code elimination to handle `LET` assignments.
- Modified strength reduction to replace operations with `LET`.

#### 3. **Semantics.py**
- Renamed `_handle_mov` to `_handle_let`.
- Updated the `HANDLERS` dictionary to map `LET` to `_handle_let`.

#### 4. **Codegen.py**
- Updated code generation logic to handle `LET` operations.

#### 5. **Example.z**
- Replaced all instances of `MOV` with `LET`.

### 📋 Breaking Changes

1. **MOV Keyword Deprecation**: The `MOV` keyword is no longer supported. All existing code must be updated to use `LET` instead.

### 📖 Migration Guide

To migrate from `MOV` to `LET`, replace all instances of `MOV` with `LET` in your Zlang code. For example:

```z
// Before
MOV int x 10

// After
LET int x 10
```

## [0.12.1] - 2024-07-21

### 🚀 New Features

#### 1. **Pointer Dereferencing Support**
- **Added pointer dereferencing in PRINT statements**: You can now use `PRINT *ptr` to dereference and print pointer values
- **Added pointer dereferencing in MOV assignments**: You can now use `MOV dest *ptr` to dereference pointers in assignments
- **Enhanced semantics validation**: Added proper validation for pointer dereferencing operations

#### 2. **Enhanced Code Generation**
- **Improved pointer handling**: Better code generation for pointer operations
- **Enhanced array operations**: More robust array handling in generated C code
- **Improved error messages**: More descriptive error messages for pointer-related operations

### 🐛 Bug Fixes

#### 1. **Pointer Dereferencing**
- **Fixed pointer dereferencing in PRINT statements**: Previously, `PRINT *ptr` would cause a semantics error
- **Fixed pointer dereferencing in MOV assignments**: Previously, `MOV dest *ptr` was not supported
- **Fixed semantics analyzer**: Added proper handling for pointer dereferencing syntax

#### 2. **Fibonacci Calculation**
- **Fixed FOR loop syntax**: Corrected the FOR loop variable initialization issue
- **Fixed loop variable scoping**: Ensured FOR loop variables are properly declared and initialized
- **Fixed Fibonacci algorithm**: The Fibonacci sequence now calculates correctly (fib(10) = 55)

#### 3. **General Improvements**
- **Fixed type checking errors**: Resolved various type checking issues in the codebase
- **Improved code consistency**: Enhanced code formatting and organization
- **Better error handling**: More robust error handling throughout the compiler

### 📚 Documentation Updates

#### 1. **Updated Example Code**
- **Comprehensive test suite**: The `example.z` file now demonstrates all working features
- **Pointer examples**: Added working examples of pointer usage and dereferencing
- **Algorithm examples**: Added Fibonacci sequence calculation example

#### 2. **Code Quality Improvements**
- **Enhanced code comments**: Added more descriptive comments throughout the codebase
- **Improved variable naming**: More consistent and descriptive variable names
- **Better code organization**: Improved structure and organization of the code

### 🔧 Technical Changes

#### 1. **Codegen.py**
- Added support for pointer dereferencing in MOV assignments
- Enhanced pointer handling in PRINT statements
- Improved code generation for array operations

#### 2. **Semantics.py**
- Added pointer dereferencing validation in PRINT handler
- Enhanced error messages for pointer operations
- Improved type checking for pointer operations

#### 3. **Example.z**
- Updated to use working syntax for all features
- Added comprehensive test coverage
- Fixed Fibonacci calculation and pointer dereferencing

### 🎯 Known Limitations

1. **Constants**: The `CONST` keyword still causes recursion issues in the current compiler
2. **Float/Double Types**: Missing `print_double` function in codegen
3. **PRINTSTR**: Not implemented in codegen (using `PRINT` with string literals as workaround)
4. **Discard Variables**: The `_` variable for discarding function return values has issues in semantics validation

### 📊 Performance Improvements

- **Faster compilation**: Optimized code generation and semantics analysis
- **Reduced memory usage**: More efficient handling of variables and arrays
- **Better error reporting**: More descriptive and helpful error messages

### 🔒 Security Enhancements

- **Improved input validation**: Better validation of pointer operations
- **Enhanced error handling**: More robust handling of edge cases
- **Better memory management**: Improved cleanup of temporary variables

### 📋 Breaking Changes

None. This release maintains backward compatibility with existing Z language code.

### 📖 Migration Guide

No migration required.
