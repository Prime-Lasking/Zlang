import re
from errors import CompilerError, ErrorCode

# Precompiled regexes for better performance
IDENTIFIER_SANITIZE_RE = re.compile(r'[^a-zA-Z0-9_]')
IDENTIFIER_VALIDATE_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def format_parameters(params):
    """Format function parameters with their types, handling type declarations."""
    formatted = []
    i = 0
    while i < len(params):
        if i + 1 < len(params) and params[i] in ["int", "double", "float", "bool","string"]:
            param_type = params[i]
            param_name = IDENTIFIER_SANITIZE_RE.sub('_', params[i + 1])
            # Convert Z types to C types for parameters
            if param_type == "string":
                c_type = "const char*"
            else:
                c_type = param_type
            formatted.append(f"{c_type} {param_name}")
            i += 2
        else:
            # All parameters must be typed now
            raise CompilerError(f"Parameter {params[i]} must have explicit type", error_code=ErrorCode.TYPE_ERROR)
    return formatted

def sanitize_identifier(name):
    """Remove invalid characters from variable names."""
    return IDENTIFIER_SANITIZE_RE.sub('_', name)

def is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except Exception:
        return False

def sanitize_condition(cond):
    """Remove trailing colons from conditions like IF, WHILE."""
    return cond.rstrip(':')

def add_overflow_check(prefix: str, operation: str, a: str, b: str, res_var: str, line_num: int) -> list[str]:
    """Generate C code with overflow check for arithmetic operations.
    
    Args:
        prefix: Indentation prefix
        operation: The arithmetic operation ('+', '-', '*', '/', '%')
        a: Left operand
        b: Right operand
        res_var: Result variable name
        line_num: Line number for error reporting
        
    Returns:
        List of C code lines with overflow checking
    """
    lines = []
    if operation in ['+', '-', '*']:
        # For +, -, * we can do overflow checking
        lines.append(f"{prefix}{{")
        lines.append(f"{prefix}    long long _temp = (long long){a} {operation} (long long){b};")
        lines.append(f"{prefix}    if (_temp > INT_MAX || _temp < INT_MIN) {{")
        lines.append(f"{prefix}        error_exit({ErrorCode.NUMBER_OVERFLOW.value}, \"Integer overflow in {operation} operation at line {line_num}\");")
        lines.append(f"{prefix}    }}")
        lines.append(f"{prefix}    {res_var} = {a} {operation} {b};")
        lines.append(f"{prefix}}}")
    else:
        # For / and % we just do the operation directly
        lines.append(f"{prefix}{res_var} = {a} {operation} {b};")
    return lines

def translate_logical_operators(condition):
    """Translate Z logical operators to C logical operators."""
    # Replace Z operators with C operators
    condition = condition.replace(' AND ', ' && ')
    condition = condition.replace(' OR ', ' || ')
    condition = condition.replace(' NOT ', ' !')

    # Handle cases where operators might be at the beginning or end
    condition = condition.replace('AND ', '&& ')
    condition = condition.replace(' OR', ' ||')
    condition = condition.replace('OR ', '|| ')
    condition = condition.replace(' NOT', ' !')
    condition = condition.replace('NOT ', '! ')

    # Handle standalone operators (less common but possible)
    condition = condition.replace(' AND', ' &&')
    condition = condition.replace('AND', '&&')
    condition = condition.replace(' OR', ' ||')
    condition = condition.replace('OR', '||')
    condition = condition.replace(' NOT', ' !')
    condition = condition.replace('NOT', '!')

    return condition

def generate_c_code(instructions, variables, declarations, z_file="unknown.z"):
    """Generate compilable C code from parsed ZLang instructions."""
    c_lines = [
        "#define _CRT_SECURE_NO_WARNINGS",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <stdbool.h>",
        "#include <string.h>",
        "#include <math.h>",
        "",
        "// Built-in helpers",
        "void print_double(double d) { printf(\"%g\\n\", d); }",
        "void print_int(int i) { printf(\"%d\\n\", i); }",
        "void print_bool(bool b) { printf(\"%s\\n\", b ? \"true\" : \"false\"); }",
        "void print_str(const char* s) { printf(\"%s\\n\", s); }",
        "void error_exit(int code, const char* msg) {",
        "    fprintf(stderr, \"Error [E%d]: %s\\n\", code, msg);",
        "    exit(code);",
        "}",
        "double read_double(const char* prompt, double d) {",
        "    printf(\"%s\", prompt);",
        "    if (scanf(\"%lf\", &d) != 1) error_exit(1, \"Failed to read number\");",
        "    return d;",
        "}",
        "int read_int(const char* prompt, int i) {",
        "    printf(\"%s\", prompt);",
        "    if (scanf(\"%d\", &i) != 1) error_exit(1, \"Failed to read integer\");",
        "    return i;",
        "}",
        "const char* read_str(const char* prompt, const char* s) {",
        "    printf(\"%s\", prompt);",
        "    // Use a fixed-size buffer for simplicity",
        "    static char buffer[1024];",
        "    if (scanf(\"%1023s\", buffer) != 1) error_exit(1, \"Failed to read string\");",
        "    return buffer;",
        "}",
        ""
    ]
    
    # Cache for sanitized identifiers to avoid redundant processing
    sanitized_cache = {}

    # Helper to check if a variable is const
    def is_const(scope, name):
        if (scope, name) in declarations:
            return declarations[(scope, name)].get("const", False)
        if (None, name) in declarations:
            return declarations[(None, name)].get("const", False)
        return False

    # Helper to get C type from Z type
    def get_c_type(z_type):
        if z_type == "string":
            return "const char*"
        return z_type  # int, double, bool, float map directly to C

    # Helper to get variable type
    def get_var_type(scope, name):
        # Handle boolean literals
        if name in {"true", "false"}:
            return "bool"
        if (scope, name) in declarations:
            return declarations[(scope, name)].get("type", "double")
        if (None, name) in declarations:
            return declarations[(None, name)].get("type", "double")
        return "double"

    # Track variable types: var_name -> type
    variable_types = {}

    # Track local variables and function names
    function_params = {}
    function_names = set()
    local_vars = {}

    current_function = None
    func_depth = 0
    for op, operands, line_num in instructions:
        if op == "FNDEF":
            fname = operands[0]
            function_names.add(fname)
            current_function = fname
            func_depth = 0  # will increase on next INDENTs

            # Check if return type is specified
            if len(operands) > 1 and operands[-1] in ["int", "double", "float", "bool", "string"]:
                # Last operand is return type, exclude it from params
                params = operands[1:-1]
            else:
                params = operands[1:]

            function_params[fname] = params
            local_vars[fname] = set()
            
            # Track parameter types
            i = 0
            while i < len(params):
                if i + 1 < len(params) and params[i] in ["int", "double", "float", "bool", "string"]:
                    param_type = params[i]
                    param_name = params[i + 1]
                    variable_types[param_name] = param_type
                    i += 2
                else:
                    # All parameters must be typed
                    raise CompilerError(f"Parameter {params[i]} must have explicit type", error_code=ErrorCode.TYPE_ERROR)
                    i += 1
        elif current_function and op == "INDENT":
            func_depth += 1
        elif current_function and op == "DEDENT":
            func_depth = max(func_depth - 1, 0)
            if func_depth == 0:
                current_function = None
        elif current_function or op == "MOV":
            # Collect local identifiers based on operation semantics (including global MOV)
            dests = []
            if op == "MOV":
                if len(operands) >= 2 and operands[0] in ["int", "float", "double", "string", "bool"]:
                    # Typed MOV: type dest [value]
                    var_type = operands[0]
                    dest = operands[1]
                    # Track the variable type (for use in other operations)
                    if dest not in variable_types:
                        variable_types[dest] = var_type
                    dests.append(dest)
                elif len(operands) == 2:
                    # Assignment: dest expr - dest should already be declared
                    dest = operands[0]
                    dests.append(dest)
            elif op == "CONST":
                if len(operands) >= 2 and operands[0] in ["int", "float", "double", "string", "bool"]:
                    var_type = operands[0]
                    dest = operands[1]
                    # Track the variable type (for use in other operations)
                    if dest not in variable_types:
                        variable_types[dest] = var_type
                    dests.append(dest)
            elif op in ["ADD", "SUB", "MUL", "DIV", "MOD"] and len(operands) == 3:
                a, b, res = operands

                # Type inference for result based on operands
                res_type = "double"  # default

                # Check if result variable has explicit type declaration
                if res in variable_types:
                    res_type = variable_types[res]
                else:
                    # Try to infer from operands
                    a_type = variable_types.get(a, "double")
                    b_type = variable_types.get(b, "double")

                    # If both operands are int, result is int (except for division which is double)
                    if a_type == "int" and b_type == "int" and op != "DIV":
                        res_type = "int"
                    # If either operand is double, result is double
                    elif a_type == "double" or b_type == "double":
                        res_type = "double"
                    # If either operand is bool, convert to int for arithmetic
                    elif a_type == "bool" or b_type == "bool":
                        res_type = "int"

                # Track the inferred type
                if res not in variable_types:
                    variable_types[res] = res_type

                dests.append(res)
            for d in dests:
                if current_function and d in function_params[current_function]:
                    continue
                if d not in sanitized_cache:
                    sanitized_cache[d] = sanitize_identifier(d)
                d_clean = sanitized_cache[d]
                if not is_number(d_clean) and IDENTIFIER_VALIDATE_RE.match(d_clean):
                    if current_function:
                        local_vars[current_function].add(d_clean)
                    # For global variables, don't add to local_vars since they're handled separately

    # Global variables: filter to identifiers not declared as locals, params or function names
    if variables:
        declared_locals = set().union(*local_vars.values()) if local_vars else set()
        declared_params = set()
        for fname, params in function_params.items():
            i = 0
            while i < len(params):
                if params[i] in ["int", "float", "double", "bool", "string"] and i + 1 < len(params):
                    if params[i + 1] not in sanitized_cache:
                        sanitized_cache[params[i + 1]] = sanitize_identifier(params[i + 1])
                    declared_params.add(sanitized_cache[params[i + 1]])
                    i += 2
                else:
                    if params[i] not in sanitized_cache:
                        sanitized_cache[params[i]] = sanitize_identifier(params[i])
                    declared_params.add(sanitized_cache[params[i]])
                    i += 1

        global_var_lines = []
        for var in sorted(variables):
            if var in {"true", "false"}:
                continue
            if var not in sanitized_cache:
                sanitized_cache[var] = sanitize_identifier(var)
            var_clean = sanitized_cache[var]
            if (IDENTIFIER_VALIDATE_RE.match(var_clean)
                and var_clean not in function_names
                and var_clean not in declared_locals
                and var_clean not in declared_params):
                var_type = get_var_type(None, var)
                c_type = get_c_type(var_type)
                const_prefix = "const " if is_const(None, var) else ""

                if var_type == "string":
                    init_value = 'NULL'
                elif var_type == "int":
                    init_value = '0'
                elif var_type == "bool":
                    init_value = 'false'
                else:
                    init_value = '0.0'

                global_var_lines.append(f"{const_prefix}{c_type} {var_clean} = {init_value};")

        if global_var_lines:
            c_lines.append("// Global variables")
            c_lines.extend(global_var_lines)
            c_lines.append("")

    # Generate functions
    indent = "    "
    indent_level = 0
    func_stack = []  # stack of raw function names to know when closing

    for op, operands, line_num in instructions:
        prefix = indent * indent_level

        if op == "FNDEF":
            raw_name = operands[0]
            is_main = (raw_name == 'main')
            if not is_main and raw_name not in sanitized_cache:
                sanitized_cache[raw_name] = sanitize_identifier(raw_name)
            fname = ("main" if is_main else f"z_{sanitized_cache.get(raw_name, raw_name)}")
            params = operands[1:]

            # Check if return type is specified
            ret_type = "int" if is_main else "double"  # default
            if len(operands) > 1 and operands[-1] in ["int", "double", "float", "bool", "string"]:
                # Last operand is return type
                ret_type = operands[-1]
                params = operands[1:-1]  # exclude return type from params
            else:
                params = operands[1:]  # no return type specified

            # Convert return type to C type
            c_ret_type = get_c_type(ret_type)
            param_str = ", ".join(format_parameters(params)) if not is_main else "void"
            c_lines.append(f"{prefix}{c_ret_type} {fname}({param_str}) {{")  
            # declare local variables
            for var in sorted(local_vars.get(raw_name, set())):
                var_type = get_var_type(raw_name, var)
                c_type = get_c_type(var_type)
                const_prefix = "const " if is_const(raw_name, var) else ""

                # Initialize variables with appropriate default values based on type
                if var_type == "string":
                    init_value = 'NULL'
                elif var_type == "int":
                    init_value = '0'
                elif var_type == "bool":
                    init_value = 'false'
                else:  # double, float
                    init_value = '0.0'

                c_lines.append(f"{prefix}{indent}{const_prefix}{c_type} {var} = {init_value};")
            func_stack.append(raw_name)
            indent_level += 1
            continue

        if op == "DEDENT":
            indent_level = max(indent_level - 1, 0)
            # Only pop from func_stack if we're closing a function (indent_level == 0)
            if func_stack and indent_level == 0:
                closing_func = func_stack.pop()
                if closing_func == 'main':
                    c_lines.append(f"{prefix}{indent}return 0;")
            c_lines.append(f"{prefix}}}")
            continue

        if op in ["IF", "ELIF", "ELSE", "WHILE", "FOR"]:
            cond = " ".join(operands)
            cond = sanitize_condition(cond)
            cond = translate_logical_operators(cond)
            if op == "IF":
                c_lines.append(f"{prefix}if ({cond}) {{ ")
            elif op == "ELIF":
                c_lines.append(f"{prefix}else if ({cond}) {{ ")
            elif op == "ELSE":
                c_lines.append(f"{prefix}else {{ ")
            elif op == "WHILE":
                c_lines.append(f"{prefix}while ({cond}) {{ ")
            elif op == "FOR":
                if len(operands) >= 4:
                    var, start_or_sep, *rest = operands
                    # Handle both "var start .. end" and "var start..end" formats
                    if '..' in start_or_sep:
                        # Format: var start..end
                        parts = start_or_sep.split('..')
                        start = parts[0] if parts[0] else '0'
                        end = parts[1] if len(parts) > 1 and parts[1] else '0'
                    elif len(rest) >= 2 and rest[0] == '..':
                        # Format: var start .. end
                        start = start_or_sep
                        end = rest[1] if len(rest) > 1 else '0'
                    else:
                        # Fallback
                        start = start_or_sep
                        end = rest[-1] if rest else '0'
                else:
                    # Fallback for unexpected format
                    var = operands[0] if operands else 'i'
                    start = '0'
                    end = '0'
                if var not in sanitized_cache:
                    sanitized_cache[var] = sanitize_identifier(var)
                var_clean = sanitized_cache[var]
                c_lines.append(f"{prefix}for (int {var_clean} = {start}; {var_clean} <= {end}; {var_clean}++) {{")
            indent_level += 1
            continue

        if op == "MOV":
            if len(operands) >= 2 and operands[0] in ["int", "float", "double", "string", "bool"]:
                dest = operands[1]
                if dest not in sanitized_cache:
                    sanitized_cache[dest] = sanitize_identifier(dest)
                # Check if a value was provided
                if len(operands) > 2:
                    expr = " ".join(operands[2:])
                else:
                    # No value provided, use type-appropriate default
                    var_type = operands[0]
                    if var_type == "string":
                        expr = 'NULL'
                    elif var_type == "int":
                        expr = '0'
                    elif var_type == "bool":
                        expr = 'false'
                    else:  # double, float
                        expr = '0.0'
                # Generate only assignment (declaration is already at top of function)
                c_lines.append(f"{prefix}{sanitized_cache[dest]} = {expr}; ")
            elif len(operands) == 2:
                # Assignment: dest expr
                dest, expr = operands
                if dest not in sanitized_cache:
                    sanitized_cache[dest] = sanitize_identifier(dest)
                c_lines.append(f"{prefix}{sanitized_cache[dest]} = {expr}; ")
            continue

        if op == "CONST":
            if len(operands) >= 2 and operands[0] in ["int", "float", "double", "string", "bool"]:
                dest = operands[1]
                if dest not in sanitized_cache:
                    sanitized_cache[dest] = sanitize_identifier(dest)
                # Check if a value was provided
                if len(operands) > 2:
                    expr = " ".join(operands[2:])
                else:
                    # No value provided, use type-appropriate default
                    var_type = operands[0]
                    if var_type == "string":
                        expr = 'NULL'
                    elif var_type == "int":
                        expr = '0'
                    elif var_type == "bool":
                        expr = 'false'
                    else:  # double, float
                        expr = '0.0'
                # Generate only assignment (declaration is already at top of function)
                c_lines.append(f"{prefix}{sanitized_cache[dest]} = {expr}; ")
            continue

        if op == "ADD":
            a, b, res = operands
            if res not in sanitized_cache:
                sanitized_cache[res] = sanitize_identifier(res)
            c_lines.extend(add_overflow_check(prefix, '+', a, b, f"{sanitized_cache[res]}", line_num))
            continue
        if op == "SUB":
            a, b, res = operands
            if res not in sanitized_cache:
                sanitized_cache[res] = sanitize_identifier(res)
            c_lines.extend(add_overflow_check(prefix, '-', a, b, f"{sanitized_cache[res]}", line_num))
            continue
        if op == "MUL":
            a, b, res = operands
            if res not in sanitized_cache:
                sanitized_cache[res] = sanitize_identifier(res)
            c_lines.extend(add_overflow_check(prefix, '*', a, b, f"{sanitized_cache[res]}", line_num))
            continue
        if op == "DIV":
            a, b, res = operands
            if res not in sanitized_cache:
                sanitized_cache[res] = sanitize_identifier(res)
            c_lines.extend(add_overflow_check(prefix, '/', a, b, f"{sanitized_cache[res]}", line_num))
            continue
        if op == "MOD":
            a, b, res = operands
            if res not in sanitized_cache:
                sanitized_cache[res] = sanitize_identifier(res)
            c_lines.extend(add_overflow_check(prefix, '%', a, b, f"{sanitized_cache[res]}", line_num))
            continue
        if op == "PRINT":
            operand = operands[0]
            
            # Determine the type of the operand and call appropriate print function
            if operand in variable_types:
                var_type = variable_types[operand]
                if var_type == "int":
                    c_lines.append(f"{prefix}print_int({operand});")
                elif var_type == "bool":
                    c_lines.append(f"{prefix}print_bool({operand});")
                elif var_type == "string":
                    c_lines.append(f"{prefix}print_str({operand});")
                else:  # double or default
                    c_lines.append(f"{prefix}print_double({operand});")
            elif operand.startswith('"') and operand.endswith('"'):
                # String literal
                c_lines.append(f"{prefix}print_str({operand});")
            elif operand in ["true", "false"]:
                # Boolean literal
                c_lines.append(f"{prefix}print_bool({operand});")
            elif is_number(operand):
                # Numeric literal - check if it looks like an integer
                if '.' in operand or 'e' in operand.lower():
                    c_lines.append(f"{prefix}print_double({operand});")
                else:
                    c_lines.append(f"{prefix}print_int({operand});")
            else:
                # Default to double for variables/expressions without explicit type
                c_lines.append(f"{prefix}print_double({operand});")
            continue
        if op == "ERROR":
            msg = " ".join(operands)
            msg = msg.replace('"', '')
            c_lines.append(f"{prefix}error_exit(1, \"{msg}\");")
            continue
        if op == "RET":
            c_lines.append(f"{prefix}return {operands[0] if operands else '0'};")
            continue

        if op == "CALL":
            if operands[0] not in sanitized_cache:
                sanitized_cache[operands[0]] = sanitize_identifier(operands[0])
            func_name = f"z_{sanitized_cache[operands[0]]}"
            args = ", ".join(operands[1:-1])
            ret_var_name = operands[-1]

            # If return variable is "_", generate just the function call (discard return value)
            if ret_var_name == "_":
                c_lines.append(f"{prefix}{func_name}({args});")
            else:
                if ret_var_name not in sanitized_cache:
                    sanitized_cache[ret_var_name] = sanitize_identifier(ret_var_name)
                ret_var = sanitized_cache[ret_var_name]
                c_lines.append(f"{prefix}{ret_var} = {func_name}({args});")
            continue

        if op == "READ":
            if len(operands) == 3 and operands[0] in ["int", "double", "float", "string"]:
                # Enhanced READ: READ <type> <prompt> <variable>
                read_type = operands[0]
                prompt = operands[1]
                dest = operands[2]
                if dest not in sanitized_cache:
                    sanitized_cache[dest] = sanitize_identifier(dest)
                
                # Track the variable type for proper code generation
                if dest not in variable_types:
                    variable_types[dest] = read_type
                
                # Generate appropriate read function call based on type
                if read_type == "string":
                    c_lines.append(f"{prefix}{sanitized_cache[dest]} = read_str({prompt}, {sanitized_cache[dest]});")
                elif read_type == "int":
                    c_lines.append(f"{prefix}{sanitized_cache[dest]} = read_int({prompt}, {sanitized_cache[dest]});")
                else:  # double or float
                    c_lines.append(f"{prefix}{sanitized_cache[dest]} = read_double({prompt}, {sanitized_cache[dest]});")
            continue
        if op == "INC":
            var = operands[0]
            if var not in sanitized_cache:
                sanitized_cache[var] = sanitize_identifier(var)
            c_lines.append(f"{prefix}{sanitized_cache[var]}++;")
            continue
        if op == "DEC":
            var = operands[0]
            if var not in sanitized_cache:
                sanitized_cache[var] = sanitize_identifier(var)
            c_lines.append(f"{prefix}{sanitized_cache[var]}--;")
            continue
    while func_stack:
        closing_func = func_stack.pop()
        if closing_func == 'main':
            c_lines.append(f"return 0;")
        c_lines.append("}")

    return "\n".join(c_lines)
