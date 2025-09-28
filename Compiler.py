#!/usr/bin/env python3
"""
The Z Compiler - Compile Z to C, Assembly, or executable

Usage:
    python Compiler.py [options] <input.z>

Options:
    -o, --output FILE    Output file name (default: output.c/output.s/output.exe)
    -f, --format FORMAT  Output format: c, asm, or exe (default: c)
    -h, --help           Show this help message
"""

import sys
import re
import os
import subprocess
import argparse

# Supported instructions
OPS = {"MOV", "ADD", "SUB", "MUL", "DIV", "CMP", "JMP", "JZ", "PRINT", "PRINTSTR", "HALT"}

def parse_z_file(z_file):
    """Parse Z file and return instructions, variables, and labels."""
    with open(z_file, "r") as f:
        lines = f.readlines()

    instructions = []
    variables = set()
    labels = set()
    
    for line in lines:
        line = re.sub(r"//.*", "", line).strip()  # remove comments
        if not line:
            continue
            
        if line.endswith(":"):
            label = line[:-1]
            instructions.append((f"{label}:", []))
            labels.add(label)
        else:
            tokens = line.split()
            if not tokens:
                continue
                
            op = tokens[0].upper()
            operands = tokens[1:]
            instructions.append((op, operands))
            
            # Collect variables
            if op in {"MOV", "ADD", "SUB", "MUL", "DIV"} and operands:
                variables.add(operands[0])
                if len(operands) > 1 and operands[1].isalpha() and operands[1] not in labels:
                    variables.add(operands[1])
            elif op == "CMP" and len(operands) >= 3:
                if operands[0].isalpha() and operands[0] not in labels:
                    variables.add(operands[0])
                if operands[2].isalpha() and operands[2] not in labels:
                    variables.add(operands[2])
    
    return instructions, variables, labels

def generate_c_code(instructions, variables, labels):
    """Generate C code from NAL instructions."""
    c_lines = ["#include <stdio.h>", "#include <stdbool.h>\n"]
    c_lines.extend([f"double {var} = 0;" for var in variables])
    c_lines.append("\nint main() {")
    cmp_flag = "cmp_flag"
    c_lines.append(f"    int {cmp_flag} = 0;")

    for instr, operands in instructions:
        if instr.endswith(":"):
            c_lines.append(f"{instr}")
        elif instr == "MOV":
            c_lines.append(f"    {operands[0]} = {operands[1]};")
        elif instr == "ADD":
            c_lines.append(f"    {operands[0]} += {operands[1]};")
        elif instr == "SUB":
            c_lines.append(f"    {operands[0]} -= {operands[1]};")
        elif instr == "MUL":
            c_lines.append(f"    {operands[0]} *= {operands[1]};")
        elif instr == "DIV":
            c_lines.append(f"    {operands[0]} /= {operands[1]};")
        elif instr == "CMP":
            left, op, right = operands
        elif instr == "JZ":
            c_lines.append(f"    if ({cmp_flag}) goto {operands[0]};")
        elif instr == "JMP":
            c_lines.append(f"    goto {operands[0]};")
        elif instr == "PRINT":
            c_lines.append(f'    printf("%g\n", {operands[0]});')
        elif instr == "PRINTSTR":
            c_lines.append(f'    printf("{' '.join(operands)}\\n");')
        elif instr == "HALT":
            c_lines.append("    return 0;")
        else:
            raise Exception(f"Unsupported instruction '{instr}'")

    c_lines.append("}")
    return "\n".join(c_lines)

def generate_assembly(instructions, variables, labels):
    """Generate x86_64 assembly code from NAL instructions."""
    asm = [
        "    .intel_syntax noprefix",
        "    .global _start\n",
        "    .section .data"
    ]
    
    # Data section - initialize all variables to 0
    for var in variables:
        asm.append(f"{var}: .quad 0")
    
    # Add string constants
    str_constants = []
    str_counter = 0
    
    # First pass to collect string constants
    for instr, operands in instructions:
        if instr == "PRINTSTR":
            str_constants.append((f"str_{str_counter}", ' '.join(operands)))
            str_counter += 1
    
    # Add string constants to data section
    for const_name, const_value in str_constants:
        asm.append(f'{const_name}: .asciz "{const_value}"')
    
    asm.extend([
        "",
        "    .section .text",
        "_start:",
        "    # Initialize stack pointer",
        "    mov rbp, rsp"
    ])
    
    # Text section with instructions
    str_idx = 0
    for instr, operands in instructions:
        # Add comment with original NAL instruction
        if not instr.endswith(':'):
            asm.append(f"\n    # {' '.join([instr] + operands)}")
        
        if instr.endswith(":"):
            asm.append(f"{instr}")
        elif instr == "MOV":
            dest, src = operands
            if src.isdigit() or (src[0] == '-' and src[1:].isdigit()):
                asm.append(f"    mov QWORD PTR [{dest}], {src}")
            else:
                asm.append(f"    mov rax, QWORD PTR [{src}]")
                asm.append(f"    mov QWORD PTR [{dest}], rax")
        elif instr in {"ADD", "SUB", "MUL", "DIV"}:
            dest, src = operands
            asm.append(f"    mov rax, QWORD PTR [{dest}]")  # Load first operand
            
            # Handle second operand (could be register or immediate)
            if src.isdigit() or (src[0] == '-' and src[1:].isdigit()):
                asm.append(f"    mov rbx, {src}")
            else:
                asm.append(f"    mov rbx, QWORD PTR [{src}]")  # Load second operand from memory
            
            # Perform the operation
            if instr == "ADD":
                asm.append("    add rax, rbx")
            elif instr == "SUB":
                asm.append("    sub rax, rbx")
            elif instr == "MUL":
                asm.append("    imul rax, rbx")
            elif instr == "DIV":
                asm.append("    cqo")
                asm.append("    idiv rbx")
                
            asm.append(f"    mov QWORD PTR [{dest}], rax")  # Store result
            
        elif instr == "CMP":
            left, op, right = operands
            asm.append(f"    mov rax, QWORD PTR [{left}]")  # Load left operand
            
            # Handle right operand (could be register or immediate)
            if right.isdigit() or (right[0] == '-' and right[1:].isdigit()):
                asm.append(f"    mov rbx, {right}")
            else:
                asm.append(f"    mov rbx, QWORD PTR [{right}]")  # Load right operand from memory
                
            asm.append(f"    cmp rax, rbx")  # Perform comparison
            
            # Map comparison operators to flags
            if op == "==":
                asm.append("    sete al")
            elif op == "!=":
                asm.append("    setne al")
            elif op == "<":
                asm.append("    setl al")
            elif op == "<=":
                asm.append("    setle al")
            elif op == ">":
                asm.append("    setg al")
            elif op == ">=":
                asm.append("    setge al")
                
            asm.append("    movzx rax, al")
            asm.append("    mov QWORD PTR [cmp_result], rax")
            
        elif instr == "JMP":
            asm.append(f"    jmp {operands[0]}")
            
        elif instr == "JZ":
            asm.append(f"    cmp QWORD PTR [cmp_result], 0")
            asm.append(f"    je {operands[0]}")
            
        elif instr == "PRINT":
            if operands[0].isdigit() or (operands[0][0] == '-' and operands[0][1:].isdigit()):
                asm.append(f"    mov rdi, {operands[0]}")
            else:
                asm.append(f"    mov rdi, QWORD PTR [{operands[0]}]")  # Load value to print
            asm.append("    call print_num")  # Call print function
            
        elif instr == "PRINTSTR":
            asm.append(f"    lea rdi, [str_{str_idx}]")  # Load string address
            asm.append(f"    mov rsi, {len(' '.join(operands))}")  # String length
            asm.append("    call print_str")  # Call print function
            str_idx += 1
            
        elif instr == "HALT":
            asm.append("    # Exit program")
            asm.append("    mov rax, 60")  # syscall number for exit
            asm.append("    xor rdi, rdi")  # exit code 0
            asm.append("    syscall")  # make system call
    
    # Add helper functions
    asm.extend([
        "",
        "# Helper function to print a number in rdi",
        "print_num:",
        "    push rbp",
        "    mov rbp, rsp",
        "    sub rsp, 32",
        "    lea rsi, [rbp-1]  # Buffer for the number string",
        "    mov BYTE PTR [rsi], 10  # Newline character",
        "    mov rax, rdi  # Number to print",
        "    mov rbx, 10   # Base 10",
        "    test rax, rax  # Check if negative",
        "    jns .loop",
        "    neg rax  # Make positive",
        "    push rax  # Save number",
        "    # Print minus sign",
        "    mov rax, 1  # sys_write",
        "    mov rdi, 1  # stdout",
        "    lea rsi, [minus]",
        "    mov rdx, 1  # length",
        "    syscall",
        "    pop rax  # Restore number",
        ".loop:",
        "    xor rdx, rdx",
        "    div rbx  # Divide by 10",
        "    add dl, '0'  # Convert to ASCII",
        "    dec rsi",
        "    mov [rsi], dl  # Store digit",
        "    test rax, rax  # Check if done",
        "    jnz .loop",
        "    # Print the number",
        "    mov rax, 1  # sys_write",
        "    mov rdi, 1  # stdout",
        "    mov rdx, rbp",
        "    sub rdx, rsi  # Calculate length",
        "    syscall",
        "    leave",
        "    ret",
        "",
        "# Helper function to print a string in rdi, length in rsi",
        "print_str:",
        "    mov rax, 1  # sys_write",
        "    mov rdx, rsi  # length",
        "    mov rsi, rdi  # string address",
        "    mov rdi, 1  # stdout",
        "    syscall",
        "    ret",
        "",
        "    .section .rodata",
        'minus: .asciz "-"',
        'cmp_result: .quad 0'  # Storage for comparison results'
    ])
    
    return "\n".join(asm)

def compile_to_exe(c_code, output_file):
    """Compile C code to an executable using gcc."""
    c_file = output_file.rsplit('.', 1)[0] + '.c'
    
    # Write C code to temporary file
    with open(c_file, 'w') as f:
        f.write(c_code)
    
    try:
        # Compile with gcc
        result = subprocess.run(
            ['gcc', c_file, '-o', output_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Compilation failed with error:\n{result.stderr}", file=sys.stderr)
            return False
            
        # Clean up temporary C file
        os.remove(c_file)
        return True
        
    except FileNotFoundError:
        print("Error: gcc not found. Please install gcc to compile to executable.", file=sys.stderr)
        return False

# -------------------------
# CLI Entry
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Compile Z to C, Assembly, or executable')
    parser.add_argument('input', help='Input .z file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-f', '--format', choices=['c', 'asm', 'exe'], default='c',
                      help='Output format (default: c)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)
    
    # Set default output filename if not provided
    if not args.output:
        base = os.path.splitext(args.input)[0]
        ext = 'c' if args.format == 'exe' else args.format
        args.output = f"{base}.{ext}"
    
    try:
        # Parse the Z file
        instructions, variables, labels = parse_z_file(args.input)
        
        # Generate output based on format
        if args.format == 'c':
            c_code = generate_c_code(instructions, variables, labels)
            with open(args.output, 'w') as f:
                f.write(c_code)
            print(f"Compiled '{args.input}' -> '{args.output}'")
            
        elif args.format == 'asm':
            asm_code = generate_assembly(instructions, variables, labels)
            with open(args.output, 'w') as f:
                f.write(asm_code)
            print(f"Generated assembly: '{args.output}'")
            print("To assemble and link:")
            print(f"  as --gstabs -o {os.path.splitext(args.output)[0]}.o {args.output}")
            print(f"  ld -o {os.path.splitext(args.output)[0]} {os.path.splitext(args.output)[0]}.o")
            
        elif args.format == 'exe':
            c_code = generate_c_code(instructions, variables, labels)
            if compile_to_exe(c_code, args.output):
                print(f"Compiled '{args.input}' -> '{args.output}'")
            else:
                sys.exit(1)
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
