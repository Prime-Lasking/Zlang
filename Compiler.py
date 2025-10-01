"""
Z Compiler - Compile Z source to C or executable

Usage:
    python Compiler.py [options] <input.z>

Options:
    -o, --output FILE    Output file name (default: input.c/input.exe)
    -f, --format FORMAT  Output format: c or exe (default: c)
    -h, --help           Show this help message
"""

import sys
import re
import os
import subprocess
import argparse
import time
from io import StringIO
from enum import Enum
from typing import Optional

# Error codes for Z compiler
class ErrorCode(Enum):
    """10 distinct error codes for different error types"""
    SYNTAX_ERROR = 1        # Invalid syntax or malformed instruction
    UNDEFINED_SYMBOL = 2    # Undefined variable, label, or function
    TYPE_ERROR = 3          # Type mismatch or invalid operation
    INVALID_OPERAND = 4     # Wrong number or type of operands
    FUNCTION_ERROR = 5      # Function definition or call errors
    LABEL_ERROR = 6         # Label redefinition or invalid label
    IO_ERROR = 7            # File I/O errors
    COMPILATION_ERROR = 8   # C compilation errors
    RUNTIME_ERROR = 9       # Runtime errors (user-defined)
    CUSTOM_ERROR = 10       # Custom user-defined errors

    def __str__(self):
        return f"E{self.value:02d}"


class CompilerError(Exception):
    """Custom exception for compiler errors with line tracking"""
    def __init__(self, message: str, line_num: Optional[int] = None, 
                 error_code: ErrorCode = ErrorCode.SYNTAX_ERROR, 
                 file_path: Optional[str] = None):
        self.message = message
        self.line_num = line_num
        self.error_code = error_code
        self.file_path = file_path
        super().__init__(self.format_error())
    
    def format_error(self) -> str:
        """Format error message with line number and error code (C compiler style)"""
        # Format: filename.z:line:column: error: [E##] message
        if self.file_path and self.line_num:
            return f"{self.file_path}:{self.line_num}: error: [{self.error_code}] {self.message}"
        elif self.file_path:
            return f"{self.file_path}: error: [{self.error_code}] {self.message}"
        elif self.line_num:
            return f"line {self.line_num}: error: [{self.error_code}] {self.message}"
        else:
            return f"error: [{self.error_code}] {self.message}"
    
    def is_critical(self) -> bool:
        """Determine if this error should stop compilation"""
        # All errors are critical except warnings (if we add them later)
        return True


# Instruction set
OPS = {"MOV", "ADD", "SUB", "MUL", "DIV", "CMP", "JMP", "JZ", "JNZ","PRINT", 
"PRINTSTR", "HALT","READ","MOD","INC","DEC","AND","OR","NOT",
"CALL", "RET", "END", "ERROR"}

# Reserved C keywords (forbidden as variable names)
C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default",
    "do", "double", "else", "enum", "extern", "float", "for", "goto",
    "if", "inline", "int", "long", "register", "restrict", "return",
    "short", "signed", "sizeof", "static", "struct", "switch",
    "typedef", "union", "unsigned", "void", "volatile", "while",
    "_Bool", "_Complex", "_Imaginary"
}


def is_identifier(token: str) -> bool:
    """Check if token is a valid C identifier and not a literal/keyword."""
    if not token or not token[0].isalpha() and token[0] != '_':
        return False
    for char in token[1:]:
        if not char.isalnum() and char != '_':
            return False
    return True

def safe_var_name(var: str) -> str:
    """Convert variable name to a safe C identifier by prefixing if it's a keyword."""
    if var in C_KEYWORDS:
        return f'z_{var}'
    return var


def parse_z_file(z_file):
    """Parse Z file and return instructions, variables, and labels."""
    try:
        with open(z_file, "r") as f:
            lines = f.readlines()
    except IOError as e:
        raise CompilerError(
            f"Cannot read file: {str(e)}",
            error_code=ErrorCode.IO_ERROR,
            file_path=z_file
        )

    instructions = []
    variables = set()
    labels = set()
    current_function = None
    function_params = {}
    in_function = False
    function_return_types = {}  # Track return types for functions
    has_main_function = False
    main_has_exit_code = False
    main_exit_code = None  # Track the exit code from main

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        
        # Remove inline comments (// after code) but preserve // in strings
        # Simple approach: split by '//' and take the first part if not in a string
        if '//' in line:
            # Check if '//' is inside a string
            in_str = False
            for i, char in enumerate(line):
                if char == '"' and (i == 0 or line[i-1] != '\\'):
                    in_str = not in_str
                elif char == '/' and i+1 < len(line) and line[i+1] == '/' and not in_str:
                    line = line[:i].rstrip()
                    break

        # Check for function definition FIRST (e.g., FN add(a b): or FN add(a, b):)
        fn_match = re.match(r'^FN\s+(\w+)\s*(\(([^)]*)\)|([^:]+))\s*:', line)
        if fn_match:
            func_name = fn_match.group(1)
            # Get parameters from either group 3 (with parentheses) or group 4 (without)
            params_str = fn_match.group(3) or fn_match.group(4) or ''
            # Handle both space and comma separated parameters
            params = []
            for p in re.split(r'[,\s]+', params_str):
                p = p.strip()
                if p:  # Only add non-empty parameters
                    params.append(p)
            
            # Check for duplicate function definitions
            if func_name in function_params:
                raise CompilerError(
                    f"Function '{func_name}' is already defined",
                    line_num=line_num,
                    error_code=ErrorCode.FUNCTION_ERROR,
                    file_path=z_file
                )
            
            # Check if this is the main function
            if func_name == 'main':
                has_main_function = True
                if params:  # main should have no parameters
                    raise CompilerError(
                        "main function must not have parameters",
                        line_num=line_num,
                        error_code=ErrorCode.FUNCTION_ERROR,
                        file_path=z_file
                    )
            
            current_function = func_name
            function_params[func_name] = params
            function_return_types[func_name] = 'double'  # Default return type
            in_function = True
            instructions.append(('FNDEF', [func_name] + params, line_num))
            continue

        # Handle labels (check AFTER function definitions)
        if line.endswith(':'):
            label = line[:-1].strip()
            if not label:
                raise CompilerError(
                    "Empty label is not allowed",
                    line_num=line_num,
                    error_code=ErrorCode.LABEL_ERROR,
                    file_path=z_file
                )
            if label in labels:
                raise CompilerError(
                    f"Label '{label}' is already defined",
                    line_num=line_num,
                    error_code=ErrorCode.LABEL_ERROR,
                    file_path=z_file
                )
            instructions.append((f"{label}:", [], line_num))
            labels.add(label)
            continue
            
        # Check for END of function (can be indented)
        if line.strip() == 'END':
            if not in_function:
                raise CompilerError(
                    "END statement without matching function definition",
                    line_num=line_num,
                    error_code=ErrorCode.FUNCTION_ERROR,
                    file_path=z_file
                )
            instructions.append(('END', [], line_num))
            in_function = False
            current_function = None
            continue
            
        # Process instruction
        # First, handle any string literals that might contain spaces
        in_string = False
        current_token = ""
        tokens = []
        
        i = 0
        while i < len(line):
            if line[i] == '"':
                in_string = not in_string
                current_token += '"'
                i += 1
                if not in_string:  # End of string literal
                    tokens.append(current_token)
                    current_token = ""
                continue
                
            if in_string:
                current_token += line[i]
            elif not line[i].isspace() and line[i] != ',':
                if line[i] == ';':  # Handle end of statement
                    if in_function and not in_string:
                        # In function, require semicolon at end
                        if current_token:
                            tokens.append(current_token)
                            current_token = ""  # Clear to avoid double-adding
                        break
                    else:
                        # Outside function, semicolon is optional
                        if current_token:
                            tokens.append(current_token)
                            current_token = ""
                        i += 1
                        # If there's more after semicolon, it's a comment
                        if i < len(line) and line[i] == ' ' and i+1 < len(line) and line[i+1] == ';':
                            i += 1  # Skip space after semicolon
                        break
                current_token += line[i]
            else:
                if current_token:  # End of a token
                    tokens.append(current_token)
                    current_token = ""
            i += 1
            
        # Add the last token if there is one
        if current_token:
            tokens.append(current_token)
            
        if not tokens:
            continue
            
        op = tokens[0].upper()
        operands = []
        
        # Check for custom ERROR instruction (user-defined errors)
        # Format: ERROR <error_code> "message" or ERROR "message"
        if op == 'ERROR':
            if len(tokens) < 2:
                raise CompilerError(
                    "ERROR instruction requires at least a message",
                    line_num=line_num,
                    error_code=ErrorCode.INVALID_OPERAND,
                    file_path=z_file
                )
            
            # Check if first operand is an error code (1-10)
            if tokens[1].isdigit() and 1 <= int(tokens[1]) <= 10:
                error_code_num = int(tokens[1])
                error_msg = ' '.join(tokens[2:]) if len(tokens) > 2 else "Custom error"
            else:
                error_code_num = 10  # Default to CUSTOM_ERROR
                error_msg = ' '.join(tokens[1:])
            
            # Remove quotes if present
            if error_msg.startswith('"') and error_msg.endswith('"'):
                error_msg = error_msg[1:-1]
            
            instructions.append(('ERROR', [str(error_code_num), error_msg], line_num))
            continue
        
        # Process operands - commas are already removed by tokenizer, so tokens are already separated
        if len(tokens) > 1:
            operands = tokens[1:]
        
        # Handle CALL instruction with return value
        # Since commas are removed by tokenizer, operands are: ['add(x', 'y)', 'result']
        # We need to find where the function call ends (closing paren) and extract return var
        if op == 'CALL':
            if not operands:
                raise CompilerError(
                    "CALL instruction requires function name",
                    line_num=line_num,
                    error_code=ErrorCode.INVALID_OPERAND,
                    file_path=z_file
                )
            
            # Reconstruct the full call by joining operands
            full_call = ' '.join(operands)
            
            # Check if there's a closing paren (function call with args)
            if ')' in full_call:
                # Find the closing paren
                paren_idx = full_call.index(')')
                func_part = full_call[:paren_idx+1]  # Everything up to and including ')'
                rest = full_call[paren_idx+1:].strip()  # Everything after ')'
                
                # Parse the function call
                args_match = re.match(r'(\w+)\s*\(([^)]*)\)', func_part)
                if args_match:
                    func_name = args_match.group(1)
                    args_str = args_match.group(2)
                    # Arguments are already space-separated (commas removed)
                    args = [a.strip() for a in args_str.split() if a.strip()]
                    
                    # Check if there's a return variable
                    if rest:
                        return_var = rest
                        instructions.append(('CALL', [func_name] + args + [return_var], line_num))
                    else:
                        instructions.append(('CALL', [func_name] + args, line_num))
                    continue
                else:
                    raise CompilerError(
                        "Invalid function call syntax",
                        line_num=line_num,
                        error_code=ErrorCode.SYNTAX_ERROR,
                        file_path=z_file
                    )
            else:
                # No parentheses - simple call
                func_name = operands[0]
                instructions.append(('CALL', [func_name], line_num))
                continue

        # Process RET instruction
        if op == 'RET':
            if not in_function:
                raise CompilerError(
                    "RET instruction outside function",
                    line_num=line_num,
                    error_code=ErrorCode.FUNCTION_ERROR,
                    file_path=z_file
                )
            if len(operands) > 1:
                raise CompilerError(
                    f"RET instruction requires 0 or 1 operands, got {len(operands)}",
                    line_num=line_num,
                    error_code=ErrorCode.INVALID_OPERAND,
                    file_path=z_file
                )
            
            # Check if this is a RET E# (exit code) in main function
            if current_function == 'main' and operands:
                ret_val = operands[0]
                # Check for E# format (E0-E10)
                if ret_val.startswith('E') and ret_val[1:].isdigit():
                    error_code_num = int(ret_val[1:])
                    if 0 <= error_code_num <= 10:
                        main_has_exit_code = True
                        main_exit_code = error_code_num  # Store the exit code
                        instructions.append(('RET_EXIT', [str(error_code_num)], line_num))
                        continue
                    else:
                        raise CompilerError(
                            f"Exit code must be E0-E10, got {ret_val}",
                            line_num=line_num,
                            error_code=ErrorCode.INVALID_OPERAND,
                            file_path=z_file
                        )
            
            instructions.append(('RET', operands, line_num))
            continue
        
        # Validate instruction exists
        if op not in OPS:
            raise CompilerError(
                f"Unknown instruction '{op}'",
                line_num=line_num,
                error_code=ErrorCode.SYNTAX_ERROR,
                file_path=z_file
            )
                
        # Process normal instruction
        instructions.append((op, operands, line_num))
        for operand in operands:
            # Skip function call syntax for variable collection
            if '(' in operand and ')' in operand:
                continue
            if is_identifier(operand) and operand not in labels and not operand.isdigit():
                variables.add(safe_var_name(operand))
                
        # If in function, add function parameters to variables
        if current_function and op not in ('FNDEF', 'CALL', 'RET', 'END'):
            for param in function_params.get(current_function, []):
                variables.add(safe_var_name(param))

    # Validate that main function exists
    if not has_main_function:
        raise CompilerError(
            "Program must have a 'main' function",
            error_code=ErrorCode.FUNCTION_ERROR,
            file_path=z_file
        )
    
    # Validate that main function returns an exit code
    if not main_has_exit_code:
        raise CompilerError(
            "main function must return an exit code using 'RET E#' (E0-E10)",
            error_code=ErrorCode.FUNCTION_ERROR,
            file_path=z_file
        )

    return instructions, variables, labels, main_exit_code


def generate_c_code(instructions, variables, labels, z_file=None):
    """Generate C code from parsed instructions."""
    output = StringIO()
    indent = '    '  # 4 spaces for indentation
    current_function = None
    function_stack = []
    
    output.write("#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include <math.h>\n#include <stdlib.h>\n\n// Use fmod for floating-point modulo\n#define MOD(a, b) fmod((a), (b))\n\n// Error handling function\nvoid z_error(int code, const char* msg, int line) {\n    fprintf(stderr, \"[E%02d] Runtime Error at line %d: %s\\n\", code, line, msg);\n    exit(code);\n}\n\n")

    # Global variables
    if variables:
        output.write("// Global variables\n")
        for var in variables:
            safe_var = safe_var_name(var)
            output.write(f"double {safe_var} = 0;\n")

    # First pass: collect function prototypes
    function_prototypes = []
    for item in instructions:
        instr = item[0]
        operands = item[1]
        if isinstance(instr, str) and instr == 'FNDEF':
            func_name = operands[0]
            params = operands[1:] if len(operands) > 1 else []
            param_list = ', '.join([f'double {p}' for p in params])
            # Rename Z main() to z_main() to avoid conflict with C main()
            c_func_name = 'z_main' if func_name == 'main' else func_name
            function_prototypes.append(f'double {c_func_name}({param_list});')
    
    # Output function prototypes
    if function_prototypes:
        output.write("// Function prototypes\n")
        for proto in function_prototypes:
            output.write(f"{proto}\n")
        output.write("\n")

    # Separate functions from main code
    functions = []
    main_code = []
    current_func = None
    
    for item in instructions:
        instr = item[0]
        operands = item[1]
        line_num = item[2] if len(item) > 2 else None
        
        if instr == 'FNDEF':
            current_func = []
            current_func.append((instr, operands, line_num))
        elif instr == 'END' and current_func is not None:
            current_func.append((instr, operands, line_num))
            functions.append(current_func)
            current_func = None
        elif current_func is not None:
            current_func.append((instr, operands, line_num))
        else:
            main_code.append((instr, operands, line_num))
    
    # Generate function definitions
    for func in functions:
        for item in func:
            instr = item[0]
            operands = item[1]
            line_num = item[2] if len(item) > 2 else None
            
            if instr == 'FNDEF':
                func_name = operands[0]
                params = operands[1:] if len(operands) > 1 else []
                param_list = ', '.join([f'double {p}' for p in params])
                # Rename Z main() to z_main() to avoid conflict with C main()
                c_func_name = 'z_main' if func_name == 'main' else func_name
                output.write(f"double {c_func_name}({param_list}) {{\n")
            elif instr == 'END':
                output.write("}\n\n")
            else:
                # Generate instruction code
                generate_instruction(output, instr, operands, indent, line_num, z_file)
    
    # Generate C main() that calls the Z main() function
    output.write("int main() {\n")
    output.write(f"{indent}return (int)z_main();\n")
    output.write("}\n")
    
    # Get the generated code and close the StringIO object
    generated_code = output.getvalue()
    output.close()
    
    return generated_code

def generate_instruction(output, instr, operands, indent='    ', line_num=None, z_file=None):
    """Generate C code for a single instruction."""
    if instr == 'FNDEF' or instr == 'END':
        return  # Already handled
    
    # Handle ERROR instruction (user-defined errors)
    if instr == 'ERROR':
        error_code = operands[0] if operands else '10'
        error_msg = operands[1] if len(operands) > 1 else 'Custom error'
        # Escape the error message for C string
        escaped_msg = error_msg.replace('\\', '\\\\').replace('"', '\\"')
        output.write(f'{indent}z_error({error_code}, "{escaped_msg}", {line_num or 0});\n')
        return
    
    if instr.endswith(":"):
        output.write(f"{instr}\n")
    elif instr == "MOV":
        output.write(f"{indent}{operands[0]} = {operands[1]};\n")
    elif instr == "ADD":
        if len(operands) == 2:
            output.write(f"{indent}{operands[0]} += {operands[1]};\n")
        elif len(operands) == 3:  # Three operands: ADD src1, src2, dest
            output.write(f"{indent}{operands[2]} = {operands[0]} + {operands[1]};\n")
        else:
            raise CompilerError(
                f"ADD instruction requires 2 or 3 operands, got {len(operands)}",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
    elif instr == "SUB":
        if len(operands) == 2:
            output.write(f"{indent}{operands[0]} -= {operands[1]};\n")
        elif len(operands) == 3:  # Three operands: SUB dest, src1, src2
            output.write(f"{indent}{operands[0]} = {operands[1]} - {operands[2]};\n")
        else:
            raise CompilerError(
                f"SUB instruction requires 2 or 3 operands, got {len(operands)}",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
    elif instr == "MUL":
        if len(operands) == 2:
            output.write(f"{indent}{operands[0]} *= {operands[1]};\n")
        elif len(operands) == 3:  # Three operands: MUL dest, src1, src2
            output.write(f"{indent}{operands[0]} = {operands[1]} * {operands[2]};\n")
        else:
            raise CompilerError(
                f"MUL instruction requires 2 or 3 operands, got {len(operands)}",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
    elif instr == "DIV":
        if len(operands) == 2:
            output.write(f"{indent}{operands[0]} /= {operands[1]};\n")
        elif len(operands) == 3:  # Three operands: DIV dest, src1, src2
            output.write(f"{indent}{operands[0]} = {operands[1]} / {operands[2]};\n")
        else:
            raise CompilerError(
                f"DIV instruction requires 2 or 3 operands, got {len(operands)}",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
    elif instr == "MOD":
        if len(operands) == 2:
            output.write(f"{indent}{operands[0]} = MOD({operands[0]}, {operands[1]});\n")
        elif len(operands) == 3:  # Three operands: MOD dest, src1, src2
            output.write(f"{indent}{operands[0]} = MOD({operands[1]}, {operands[2]});\n")
        else:
            raise CompilerError(
                f"MOD instruction requires 2 or 3 operands, got {len(operands)}",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
    elif instr == "INC":
        output.write(f"{indent}{operands[0]}++;\n")
    elif instr == "DEC":
        output.write(f"{indent}{operands[0]}--;\n")
    elif instr == "AND":
        output.write(f"{indent}if (({operands[0]}) && ({operands[1]})) {{ \
            {indent}    /* AND operation */ \
            {indent}}}\n")
    elif instr == "OR":
        output.write(f"{indent}if (({operands[0]}) || ({operands[1]})) {{ \
            {indent}    /* OR operation */ \
            {indent}}}\n")
    elif instr == "NOT":
        output.write(f"{indent}if (!({operands[0]})) {{ \
            {indent}    /* NOT operation */ \
            {indent}}}\n")
    elif instr == "PRINT":
        if not operands:
            raise CompilerError(
                "PRINT requires at least one operand",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
            
        # Check if it's a string literal (starts and ends with quotes)
        if len(operands) == 1 and operands[0].startswith('"') and operands[0].endswith('"'):
            # It's a string literal - remove the quotes and escape special characters
            str_content = operands[0][1:-1]  # Remove surrounding quotes
            # Escape backslashes and quotes
            escaped_str = str_content.replace('\\', '\\\\').replace('"', '\\"')
            output.write(f'{indent}printf(\"{escaped_str}\\n\");\n')
        else:
            # It's a variable or expression - print as number
            output.write(f'{indent}printf(\"%g\\n\", (double)({operands[0]}));\n')
            
    # For backward compatibility, PRINTSTR is the same as PRINT
    elif instr == "PRINTSTR":
        if not operands:
            raise CompilerError(
                "PRINTSTR requires at least one operand",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
            
        # Check if it's a string literal (starts and ends with quotes)
        if len(operands) == 1 and operands[0].startswith('"') and operands[0].endswith('"'):
            # It's a string literal - remove the quotes and escape special characters
            str_content = operands[0][1:-1]  # Remove surrounding quotes
            # Escape backslashes and quotes
            escaped_str = str_content.replace('\\', '\\\\').replace('"', '\\"')
            output.write(f'{indent}printf(\"{escaped_str}\\n\");\n')
        else:
            # It's a variable or expression - print as string
            output.write(f'{indent}printf(\"%s\\n\", (char*){operands[0]});\n')
    elif instr == "CMP":
        if len(operands) != 3:
            raise CompilerError(
                "CMP requires three operands: CMP x y op",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
        left, right, op = operands
        if op == "==":
            output.write(f"{indent}cmp_flag = ({left} == {right});\n")
        elif op == "!=":
            output.write(f"{indent}cmp_flag = ({left} != {right});\n")
        elif op == "<":
            output.write(f"{indent}cmp_flag = ({left} < {right});\n")
        elif op == ">":
            output.write(f"{indent}cmp_flag = ({left} > {right});\n")
        elif op == "<=":
            output.write(f"{indent}cmp_flag = ({left} <= {right});\n")
        elif op == ">=":
            output.write(f"{indent}cmp_flag = ({left} >= {right});\n")
        else:
            raise CompilerError(
                f"Unknown comparison operator: {op}",
                line_num=line_num,
                error_code=ErrorCode.SYNTAX_ERROR,
                file_path=z_file
            )
    elif instr == "JMP":
        output.write(f'{indent}goto {operands[0]};\n')
    elif instr == "JZ":
        output.write(f'{indent}if (cmp_flag == 0) goto {operands[0]};\n')
    elif instr == "JNZ":
        output.write(f'{indent}if (cmp_flag != 0) goto {operands[0]};\n')
    elif instr == "HALT":
        output.write(f"{indent}return 0;\n")
    elif instr == "RET_EXIT":
        # Return exit code from main function
        exit_code = operands[0] if operands else '0'
        output.write(f"{indent}return {exit_code};\n")
    elif instr == "RET":
        if operands:
            output.write(f"{indent}return {operands[0]};\n")
        else:
            output.write(f"{indent}return;\n")
    elif instr == "CALL":
        if not operands:
            raise CompilerError(
                "CALL instruction requires function name",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
            
        # Check if there's a return value (last operand is the return variable)
        if len(operands) > 1 and '=' not in operands[-1]:
            # Has return value: CALL func, x,y,result  ->  result = func(x,y);
            func_name = operands[0]
            args = operands[1:-1]  # Exclude the return variable
            return_var = operands[-1]
            args_str = ', '.join(args)
            output.write(f"{indent}{return_var} = {func_name}({args_str});\n")
        else:
            # Regular function call without return value
            func_name = operands[0]
            args = operands[1:] if len(operands) > 1 else []
            args_str = ', '.join(args)
            output.write(f"{indent}{func_name}({args_str});\n")
    elif instr == "READ":
        if len(operands) == 1:
            # Form: READ var
            var = operands[0]
            output.write(f'{indent}scanf("%lf", &{var});\n')
        elif len(operands) >= 2:
            # Form: READ "prompt" var
            prompt = " ".join(operands[:-1])
            var = operands[-1]
            if prompt.startswith('"') and prompt.endswith('"'):
                prompt = prompt[1:-1]
                escaped_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"')
                output.write(f'{indent}printf("{escaped_prompt}");\n')
                output.write(f'{indent}scanf("%lf", &{var});\n')
            else:
                raise CompilerError(
                    "READ requires a prompt string and variable",
                    line_num=line_num,
                    error_code=ErrorCode.INVALID_OPERAND,
                    file_path=z_file
                )
        else:
            raise CompilerError(
                "READ requires at least one operand (variable), or a prompt and variable",
                line_num=line_num,
                error_code=ErrorCode.INVALID_OPERAND,
                file_path=z_file
            )
    else:
        raise CompilerError(
            f"Unknown OPCODE: {instr}",
            line_num=line_num,
            error_code=ErrorCode.SYNTAX_ERROR,
            file_path=z_file
        )


def compile_to_exe(c_code, output_file):
    """Compile C code to an executable using gcc."""
    # Create a temporary C file
    c_file = output_file.rsplit('.', 1)[0] + '.c'
    try:
        with open(c_file, 'w') as f:
            f.write(c_code)

        # Basic compilation command with math library
        compile_cmd = [
            'gcc',
            '-o', output_file,
            c_file,  # Add the source file to compile
            '-lm'    # Link with math library for fmod
        ]

        # Run the compilation
        result = subprocess.run(compile_cmd, capture_output=True, text=True)

        # Clean up the temporary C file
        try:
            os.remove(c_file)
        except OSError:
            pass  # Ignore if file deletion fails

        # Check for compilation errors
        if result.returncode != 0:
            error_msg = f"GCC compilation failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f"\n{result.stderr}"
            raise CompilerError(
                error_msg,
                error_code=ErrorCode.COMPILATION_ERROR
            )
            
        return True

    except CompilerError:
        raise  # Re-raise CompilerError
    except Exception as e:
        raise CompilerError(
            f"Unexpected error during compilation: {str(e)}",
            error_code=ErrorCode.COMPILATION_ERROR
        )


if __name__ == "__main__":
    # Set UTF-8 encoding for stdout/stderr (cross-platform)
    try:
        import io
        # Only wrap if not already a TextIOWrapper with UTF-8
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except (AttributeError, OSError):
        # If wrapping fails (e.g., in some IDEs or redirected output), continue anyway
        pass
    
    start_time = time.time()
    parser = argparse.ArgumentParser(description='Compile Z to C or executable')
    parser.add_argument('input', help='Input .z file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-f', '--format', choices=['c', 'exe'], default='c', help='Output format')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        error = CompilerError(
            f"Input file not found",
            error_code=ErrorCode.IO_ERROR,
            file_path=args.input
        )
        print(error, file=sys.stderr)
        sys.exit(error.error_code.value)

    if not args.output:
        base = os.path.splitext(args.input)[0]
        ext = args.format
        args.output = f"{base}.{ext}"

    try:
        # Parse the input file first
        parse_start = time.perf_counter()
        instructions, variables, labels, exit_code = parse_z_file(args.input)
        parse_end = time.perf_counter()
        
        if args.format == 'c':
            # Time only the C code generation
            gen_start = time.perf_counter()
            code = generate_c_code(instructions, variables, labels, args.input)
            gen_end = time.perf_counter()
            
            # Write the output file
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(code)
                
            def format_time(seconds):
                if seconds >= 1.0:
                    return f"{seconds:.3f} s"
                elif seconds >= 0.001:  
                    return f"{seconds * 1000:.3f} ms"
                elif seconds >= 0.000001:  
                    return f"{seconds * 1_000_000:.1f} μs"
                else:                      
                    return f"{seconds * 1_000_000_000:.1f} ns"
                    
            parse_time = parse_end - parse_start
            gen_time = gen_end - gen_start
            total_time = gen_time + parse_time
            
            print(f"Generated C code: {args.output}")
            print(f"  Parsing:    {format_time(parse_time)}")
            print(f"  Generation: {format_time(gen_time)}")
            print(f"  Total time: {format_time(total_time)}")
            print(f"  Exit code:  E{exit_code} ({exit_code})")
            
        elif args.format == 'exe':
            # Time the C code generation and compilation
            gen_start = time.perf_counter()
            c_code = generate_c_code(instructions, variables, labels, args.input)
            gen_end = time.perf_counter()
            
            compile_start = time.perf_counter()
            compile_to_exe(c_code, args.output)
            compile_end = time.perf_counter()
            
            def format_time(seconds):
                if seconds >= 1.0:
                    return f"{seconds:.3f} s"
                elif seconds >= 0.001:  # 1ms
                    return f"{seconds * 1000:.3f} ms"
                elif seconds >= 0.000001:  # 1μs
                    return f"{seconds * 1_000_000:.1f} μs"
                else:
                    return f"{seconds * 1_000_000_000:.1f} ns"
                    
            parse_time = parse_end - parse_start
            gen_time = gen_end - gen_start
            compile_time = compile_end - compile_start
            total_time = compile_time + gen_time + parse_time
            
            print(f"Generated executable: {args.output}")
            print(f"  Parsing:    {format_time(parse_time)}")
            print(f"  Generation: {format_time(gen_time)}")
            print(f"  Compilation: {format_time(compile_time)}")
            print(f"  Total time: {format_time(total_time)}")
            print(f"  Exit code:  E{exit_code} ({exit_code})")
            
    except CompilerError as e:
        # Print formatted error and exit with error code (C compiler style)
        print(e, file=sys.stderr)
        sys.exit(e.error_code.value)
    except Exception as e:
        # Unexpected errors
        error = CompilerError(
            f"Unexpected error: {str(e)}",
            error_code=ErrorCode.SYNTAX_ERROR
        )
        print(error, file=sys.stderr)
        sys.exit(error.error_code.value)
