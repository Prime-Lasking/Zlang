#!/usr/bin/env python3
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

# Instruction set
OPS = {"MOV", "ADD", "SUB", "MUL", "DIV", "CMP", "JMP", "JZ", "JNZ","PRINT", 
"PRINTSTR", "HALT","READ","MOD","INC","DEC","AND","OR","NOT"}

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
        raise IOError(f"Error reading file {z_file}: {str(e)}")

    instructions = []
    variables = set()
    labels = set()

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('//'):
            continue

        # Handle labels
        if line.endswith(':'):
            label = line[:-1].strip()
            if not label:
                print(f"Error: Empty label at line {line_num}", file=sys.stderr)
                continue
            instructions.append((f"{label}:", []))
            labels.add(label)
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
            elif not line[i].isspace():
                if line[i] == ';':  # Handle comments after instruction
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
        operands = tokens[1:]

        # Process normal instruction
        instructions.append((op, operands))
        for operand in operands:
            if is_identifier(operand) and operand not in labels:
                variables.add(safe_var_name(operand))

    return instructions, variables, labels


def generate_c_code(instructions, variables, labels):
    """Generate C code from parsed instructions."""
    output = StringIO()
    indent = '    '  # 4 spaces for indentation
    
    output.write("#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include <math.h>\n\n// Use fmod for floating-point modulo\n#define MOD(a, b) fmod((a), (b))\n\n")

    # Global variables
    if variables:
        output.write("// Global variables\n")
        for var in variables:
            safe_var = safe_var_name(var)
            output.write(f"double {safe_var} = 0;\n")

    # Check if we need cmp_flag (if there are any CMP, JZ, or JNZ instructions)
    needs_cmp = any(instr in {'CMP', 'JZ', 'JNZ'} for instr, _ in instructions)
    output.write("int main(){\n")
    if needs_cmp:
        output.write(f"{indent}int cmp_flag=0;\n")

    for instr, operands in instructions:
        if instr.endswith(":"):
            output.write(f"{instr}\n")
        elif instr == "MOV":
            output.write(f"{indent}{operands[0]} = {operands[1]};\n")
        elif instr == "ADD":
            if len(operands) == 2:
                output.write(f"{indent}{operands[0]} += {operands[1]};\n")
            elif len(operands) == 3:  # Three operands: ADD dest, src1, src2
                output.write(f"{indent}{operands[0]} = {operands[1]} + {operands[2]};\n")
            else:
                raise ValueError(f"ADD instruction requires 2 or 3 operands, got {len(operands)}")
        elif instr == "SUB":
            if len(operands) == 2:
                output.write(f"{indent}{operands[0]} -= {operands[1]};\n")
            elif len(operands) == 3:  # Three operands: SUB dest, src1, src2
                output.write(f"{indent}{operands[0]} = {operands[1]} - {operands[2]};\n")
            else:
                raise ValueError(f"SUB instruction requires 2 or 3 operands, got {len(operands)}")
        elif instr == "MUL":
            if len(operands) == 2:
                output.write(f"{indent}{operands[0]} *= {operands[1]};\n")
            elif len(operands) == 3:  # Three operands: MUL dest, src1, src2
                output.write(f"{indent}{operands[0]} = {operands[1]} * {operands[2]};\n")
            else:
                raise ValueError(f"MUL instruction requires 2 or 3 operands, got {len(operands)}")
        elif instr == "DIV":
            if len(operands) == 2:
                output.write(f"{indent}{operands[0]} /= {operands[1]};\n")
            elif len(operands) == 3:  # Three operands: DIV dest, src1, src2
                output.write(f"{indent}{operands[0]} = {operands[1]} / {operands[2]};\n")
            else:
                raise ValueError(f"DIV instruction requires 2 or 3 operands, got {len(operands)}")
        elif instr == "MOD":
            if len(operands) == 2:
                output.write(f"{indent}{operands[0]} = MOD({operands[0]}, {operands[1]});\n")
            elif len(operands) == 3:  # Three operands: MOD dest, src1, src2
                output.write(f"{indent}{operands[0]} = MOD({operands[1]}, {operands[2]});\n")
            else:
                raise ValueError(f"MOD instruction requires 2 or 3 operands, got {len(operands)}")
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
                raise ValueError("PRINT requires at least one operand")
                
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
                raise ValueError("PRINTSTR requires at least one operand")
                
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
                raise ValueError("CMP requires three operands: CMP x y op")
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
                raise ValueError(f"Unknown comparison operator: {op}")

        elif instr == "JMP":
            output.write(f'    goto {operands[0]};\n')
        elif instr == "JZ":
            output.write(f'    if (cmp_flag == 0) goto {operands[0]};\n')
        elif instr == "JNZ":
            output.write(f'    if (cmp_flag != 0) goto {operands[0]};\n')
        elif instr == "HALT":
            output.write("    return 0;\n")
        elif instr == "READ":
            if len(operands) == 1:
                # Form: READ var
                var = operands[0]
                output.write(f'    scanf("%lf", &{var});\n')
            elif len(operands) >= 2:
                # Form: READ "prompt" var
                prompt = " ".join(operands[:-1])
                var = operands[-1]

            if prompt.startswith('"') and prompt.endswith('"'):
                prompt = prompt[1:-1]

                escaped_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"')

                output.write(f'    printf("{escaped_prompt}");\n')
                output.write(f'    scanf("%lf", &{var});\n')
            else:
                raise ValueError("READ requires at least one operand (variable), or a prompt and variable")

        else:
            raise ValueError(f"Unknown OPCODE: {instr}")

    output.write("}\n")
    
    # Get the generated code and close the StringIO object
    generated_code = output.getvalue()
    output.close()
    
    return generated_code


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
            print(f"Compilation failed with exit code {result.returncode}:", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False
            
        return True

    except Exception as e:
        print(f"Error during compilation: {str(e)}", file=sys.stderr)
        return False


if __name__ == "__main__":
    start_time = time.time()
    parser = argparse.ArgumentParser(description='Compile Z to C or executable')
    parser.add_argument('input', help='Input .z file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-f', '--format', choices=['c', 'exe'], default='c', help='Output format')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    if not args.output:
        base = os.path.splitext(args.input)[0]
        ext = args.format
        args.output = f"{base}.{ext}"

    try:
        # Parse the input file first
        parse_start = time.perf_counter()
        instructions, variables, labels = parse_z_file(args.input)
        parse_end = time.perf_counter()
        
        if args.format == 'c':
            # Time only the C code generation
            gen_start = time.perf_counter()
            code = generate_c_code(instructions, variables, labels)
            gen_end = time.perf_counter()
            
            # Write the output file
            with open(args.output, 'w') as f:
                f.write(code)
                
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
            total_time = gen_time + parse_time
            
            print(f"Generated C code: {args.output}")
            print(f"  Parsing:    {format_time(parse_time)}")
            print(f"  Generation: {format_time(gen_time)}")
            print(f"  Total time: {format_time(total_time)}")
            
        elif args.format == 'exe':
            # Time the C code generation and compilation
            gen_start = time.perf_counter()
            c_code = generate_c_code(instructions, variables, labels)
            gen_end = time.perf_counter()
            
            compile_start = time.perf_counter()
            success = compile_to_exe(c_code, args.output)
            compile_end = time.perf_counter()
            
            if success:
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
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
