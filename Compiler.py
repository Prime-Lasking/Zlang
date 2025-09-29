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
OPS = {"MOV", "ADD", "SUB", "MUL", "DIV", "CMP", "JMP", "JZ", "JNZ","PRINT", "PRINTSTR", "HALT"}

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
    if not token.isidentifier():
        return False
    if token in C_KEYWORDS:
        raise ValueError(f"Error: '{token}' is a reserved C keyword and cannot be used as a variable")
    return True


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
        tokens = line.split()
        if not tokens:
            continue

        op = tokens[0].upper()
        operands = tokens[1:]

        # Process normal instruction
        instructions.append((op, operands))
        for operand in operands:
            if is_identifier(operand) and operand not in labels:
                variables.add(operand)

    return instructions, variables, labels


def generate_c_code(instructions, variables, labels):
    """Generate C code from parsed instructions."""
    output = StringIO()
    output.write("#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include <math.h>\n\n")

    # Global variables
    if variables:
        output.write("// Global variables\n")
        for var in variables:
            output.write(f"double {var} = 0;\n")

    # Check if we need cmp_flag (if there are any CMP, JZ, or JNZ instructions)
    needs_cmp = any(instr in {'CMP', 'JZ', 'JNZ'} for instr, _ in instructions)
    output.write("int main(){\n")
    if needs_cmp:
        output.write("    int cmp_flag=0;\n")

    for instr, operands in instructions:
        if instr.endswith(":"):
            output.write(f"{instr}\n")
        elif instr == "MOV":
            output.write(f"    {operands[0]} = {operands[1]};\n")
        elif instr == "ADD":
            output.write(f"    {operands[0]} += {operands[1]};\n")
        elif instr == "SUB":
            output.write(f"    {operands[0]} -= {operands[1]};\n")
        elif instr == "MUL":
            output.write(f"    {operands[0]} *= {operands[1]};\n")
        elif instr == "DIV":
            output.write(f"    {operands[0]} /= {operands[1]};\n")
        elif instr == "PRINT":
            output.write(f'    printf("%g\\n", {operands[0]});\n')
        elif instr == "PRINTSTR":
            escaped_str = ' '.join(operands).replace('\\', '\\\\').replace('"', '\\"')
            output.write(f'    printf("{escaped_str}\\n");')
        elif instr == "CMP":
            if len(operands) != 3:
                raise ValueError("CMP requires three operands: CMP x y op")
            left, right, op = operands
            if op == "==":
                output.write(f"    cmp_flag = ({left} == {right});\n")
            elif op == "!=":
             output.write(f"    cmp_flag = ({left} != {right});\n")
            elif op == "<":
              output.write(f"    cmp_flag = ({left} < {right});\n")
            elif op == ">":
              output.write(f"    cmp_flag = ({left} > {right});\n")
            elif op == "<=":
             output.write(f"    cmp_flag = ({left} <= {right});\n")
            elif op == ">=":
                output.write(f"    cmp_flag = ({left} >= {right});\n")
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
        else:
            raise ValueError(f"Unknown OPCODE: {instr}")

    output.write("}\n")
    
    # Get the generated code and close the StringIO object
    generated_code = output.getvalue()
    output.close()
    
    return generated_code


def compile_to_exe(c_code, output_file):
    """Compile C code to an executable using gcc with optimizations."""
    # Create a temporary C file
    c_file = output_file.rsplit('.', 1)[0] + '.c'
    try:
        with open(c_file, 'w') as f:
            f.write(c_code)

        # Optimized compilation flags:
        # -O3: Maximum optimization
        # -s: Strip all symbols
        # -static: Static linking for better performance
        # -march=native: Optimize for the current CPU
        # -flto: Link-time optimization
        # -Wall -Wextra: Enable all warnings
        # -Werror: Treat warnings as errors
        compile_cmd = [
            'gcc',
            '-o', output_file,
            c_file,  # Add the source file to compile
            '-O3', '-s', '-static',
            '-march=native',
            '-flto',
            '-Wall', '-Wextra', '-Werror'
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
