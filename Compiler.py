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
"PRINTSTR", "HALT","READ","MOD","INC","DEC","AND","OR","NOT",
"CALL", "RET", "END"}

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
    current_function = None
    function_params = {}
    in_function = False
    function_return_types = {}  # Track return types for functions

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
            
            current_function = func_name
            function_params[func_name] = params
            function_return_types[func_name] = 'double'  # Default return type
            in_function = True
            instructions.append(('FNDEF', [func_name] + params))
            continue

        # Handle labels (check AFTER function definitions)
        if line.endswith(':'):
            label = line[:-1].strip()
            if not label:
                print(f"Error: Empty label at line {line_num}", file=sys.stderr)
                continue
            instructions.append((f"{label}:", []))
            labels.add(label)
            continue
            
        # Check for END of function (can be indented)
        if line.strip() == 'END':
            if not in_function:
                raise ValueError(f"Unexpected END without function definition at line {line_num}")
            instructions.append(('END', []))
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
        
        # Process operands - commas are already removed by tokenizer, so tokens are already separated
        if len(tokens) > 1:
            operands = tokens[1:]
        
        # Handle CALL instruction with return value
        # Since commas are removed by tokenizer, operands are: ['add(x', 'y)', 'result']
        # We need to find where the function call ends (closing paren) and extract return var
        if op == 'CALL':
            if not operands:
                raise ValueError(f"CALL instruction requires function name at line {line_num}")
            
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
                        instructions.append(('CALL', [func_name] + args + [return_var]))
                    else:
                        instructions.append(('CALL', [func_name] + args))
                    continue
                else:
                    raise ValueError(f"Invalid function call syntax at line {line_num}")
            else:
                # No parentheses - simple call
                func_name = operands[0]
                instructions.append(('CALL', [func_name]))
                continue

        # Process RET instruction
        if op == 'RET':
            if not in_function:
                raise ValueError(f"RET instruction outside function at line {line_num}")
            if len(operands) > 1:
                raise ValueError(f"RET instruction requires 0 or 1 operands, got {len(operands)} at line {line_num}")
            instructions.append(('RET', operands))
            continue
                
        # Process normal instruction
        instructions.append((op, operands))
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

    return instructions, variables, labels


def generate_c_code(instructions, variables, labels):
    """Generate C code from parsed instructions."""
    output = StringIO()
    indent = '    '  # 4 spaces for indentation
    current_function = None
    function_stack = []
    
    output.write("#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include <math.h>\n\n// Use fmod for floating-point modulo\n#define MOD(a, b) fmod((a), (b))\n\n")

    # Global variables
    if variables:
        output.write("// Global variables\n")
        for var in variables:
            safe_var = safe_var_name(var)
            output.write(f"double {safe_var} = 0;\n")

    # First pass: collect function prototypes
    function_prototypes = []
    for instr, operands in instructions:
        if isinstance(instr, str) and instr == 'FNDEF':
            func_name = operands[0]
            params = operands[1:] if len(operands) > 1 else []
            param_list = ', '.join([f'double {p}' for p in params])
            function_prototypes.append(f'double {func_name}({param_list});')
    
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
    
    for instr, operands in instructions:
        if instr == 'FNDEF':
            current_func = []
            current_func.append((instr, operands))
        elif instr == 'END' and current_func is not None:
            current_func.append((instr, operands))
            functions.append(current_func)
            current_func = None
        elif current_func is not None:
            current_func.append((instr, operands))
        else:
            main_code.append((instr, operands))
    
    # Generate function definitions
    for func in functions:
        for instr, operands in func:
            if instr == 'FNDEF':
                func_name = operands[0]
                params = operands[1:] if len(operands) > 1 else []
                param_list = ', '.join([f'double {p}' for p in params])
                output.write(f"double {func_name}({param_list}) {{\n")
            elif instr == 'END':
                output.write("}\n\n")
            else:
                # Generate instruction code
                generate_instruction(output, instr, operands, indent)
    
    # Generate main function with main code
    if main_code:
        needs_cmp = any(instr in {'CMP', 'JZ', 'JNZ'} for instr, _ in main_code)
        output.write("int main() {\n")
        if needs_cmp:
            output.write(f"{indent}int cmp_flag=0;\n")
        
        for instr, operands in main_code:
            generate_instruction(output, instr, operands, indent)
        
        output.write(f"{indent}return 0;\n}}\n")
    
    # Get the generated code and close the StringIO object
    generated_code = output.getvalue()
    output.close()
    
    return generated_code

def generate_instruction(output, instr, operands, indent='    '):
    """Generate C code for a single instruction."""
    if instr == 'FNDEF' or instr == 'END':
        return  # Already handled
    
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
        output.write(f'{indent}goto {operands[0]};\n')
    elif instr == "JZ":
        output.write(f'{indent}if (cmp_flag == 0) goto {operands[0]};\n')
    elif instr == "JNZ":
        output.write(f'{indent}if (cmp_flag != 0) goto {operands[0]};\n')
    elif instr == "HALT":
        output.write(f"{indent}return 0;\n")
    elif instr == "RET":
        if operands:
            output.write(f"{indent}return {operands[0]};\n")
        else:
            output.write(f"{indent}return;\n")
    elif instr == "CALL":
        if not operands:
            raise ValueError("CALL instruction requires function name")
            
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
                raise ValueError("READ requires a prompt string and variable")
        else:
            raise ValueError("READ requires at least one operand (variable), or a prompt and variable")
    else:
        raise ValueError(f"Unknown OPCODE: {instr}")


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
