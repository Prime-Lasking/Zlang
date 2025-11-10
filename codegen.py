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
        if i + 1 < len(params) and params[i] in ["int", "double", "float", "bool", "string"]:
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
            raise CompilerError(f"Parameter {params[i]} must have explicit type",
                                error_code=ErrorCode.TYPE_ERROR)
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
        lines.append(f"{prefix}        error_exit({ErrorCode.OVERFLOW.value}, "
                     f"\"Integer overflow in {operation} operation at line {line_num}\");")
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
    condition = condition.replace(' OR', ' ||')
    condition = condition.replace('NOT ', '! ')
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
    # Track pointer variables to avoid double declaration
    pointer_vars = set()
    
    c_lines = [
        "#define _CRT_SECURE_NO_WARNINGS",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <string.h>",
        "#include <stdbool.h>",
        "#include <math.h>",
        "#include <limits.h>",
        "",
        "// Array structure",
        "typedef struct {",
        "    void* data;        // Pointer to array data",
        "    size_t size;       // Current number of elements",
        "    size_t capacity;   // Allocated capacity",
        "    size_t elem_size;  // Size of each element",
        "    char type[10];     // Type of elements",
        "} Array;",
        "",
        "// Array functions implementation",
        "Array* array_create_with_capacity(size_t elem_size, const char* type, size_t initial_capacity) {",
        "    Array* arr = (Array*)malloc(sizeof(Array));",
        "    if (!arr) { fprintf(stderr, \"Memory allocation failed\\n\"); exit(1); }",
        "    arr->size = 0;",
        "    arr->capacity = initial_capacity > 0 ? initial_capacity : 4;  // Ensure minimum capacity of 4",
        "    arr->elem_size = elem_size;",
        "    strncpy(arr->type, type, sizeof(arr->type) - 1);",
        "    arr->type[sizeof(arr->type) - 1] = '\\0';",
        "    arr->data = malloc(arr->capacity * elem_size);",
        "    if (!arr->data) { fprintf(stderr, \"Memory allocation failed\\n\"); exit(1); }",
        "    return arr;",
        "}",
        "",
        "Array* array_create(size_t elem_size, const char* type) {",
        "    // Default initial capacity of 4",
        "    return array_create_with_capacity(elem_size, type, 4);",
        "}",
        "",
        "void array_free(Array* arr) {",
        "    if (arr) {",
        "        if (strcmp(arr->type, \"string\") == 0) {",
        "            for (size_t i = 0; i < arr->size; i++) {",
        "                free(*((char**)arr->data + i));",
        "            }",
        "        }",
        "        free(arr->data);",
        "        free(arr);",
        "    }",
        "}",
        "",
        "void array_resize(Array* arr) {",
        "    if (arr->capacity > SIZE_MAX / 2) { ",
        "        fprintf(stderr, \"Error: Array too large\\n\"); ",
        "        exit(1); ",
        "    }",
        "    arr->capacity *= 2;",
        "    void* new_data = realloc(arr->data, arr->capacity * arr->elem_size);",
        "    if (!new_data) { ",
        "        fprintf(stderr, \"Memory reallocation failed\\n\"); ",
        "        exit(1); ",
        "    }",
        "    arr->data = new_data;",
        "}",
        "",
        "void array_push(Array* arr, const void* value) {",
        "    if (arr->size >= arr->capacity) {",
        "        array_resize(arr);",
        "    }",
        "    memcpy((char*)arr->data + arr->size * arr->elem_size, value, arr->elem_size);",
        "    arr->size++;",
        "}",
        "",
        "void array_pop(Array* arr, void* out) {",
        "    if (arr->size == 0) {",
        "        fprintf(stderr, \"Error: Cannot pop from empty array\\n\");",
        "        exit(1);",
        "    }",
        "    arr->size--;",
        "    memcpy(out, (char*)arr->data + arr->size * arr->elem_size, arr->elem_size);",
        "}",
        "",
        "size_t array_length(const Array* arr) {",
        "    if (!arr) { fprintf(stderr, \"Error: Null array\\n\"); exit(1); }",
        "    return arr->size;",
        "}",
        "",
        "void* array_get(Array* arr, size_t index) {",
        "    if (!arr) { fprintf(stderr, \"Error: Null array\\n\"); exit(1); }",
        "    if (index >= arr->size) {",
        "        fprintf(stderr, \"Error: Array index %zu out of bounds (size: %zu)\\n\", index, arr->size);",
        "        exit(1);",
        "    }",
        "    return (char*)arr->data + index * arr->elem_size;",
        "}",
        "",
        "// Print array function ",
        "void print_array(Array* arr) {",
        "    if (!arr) {",
        "        printf(\"NULL\\n\");",
        "        return;",
        "    }",
        "    printf(\"[\");",
        "    for (size_t i = 0; i < arr->size; i++) {",
        "        if (i > 0) printf(\", \");",
        "        if (strcmp(arr->type, \"int\") == 0) {",
        "            printf(\"%d\", *((int*)array_get(arr, i)));",
        "        } else if (strcmp(arr->type, \"float\") == 0) {",
        "            printf(\"%f\", *((float*)array_get(arr, i)));",
        "        } else if (strcmp(arr->type, \"double\") == 0) {",
        "            printf(\"%g\", *((double*)array_get(arr, i)));",
        "        } else if (strcmp(arr->type, \"bool\") == 0) {",
        "            printf(\"%s\", *((bool*)array_get(arr, i)) ? \"true\" : \"false\");",
        "        } else if (strcmp(arr->type, \"string\") == 0) {",
        "            printf(\"\\\"%s\\\"\", *((const char**)array_get(arr, i)));",
        "        }",
        "    }",
        "    printf(\"]\\n\");",
        "}",
        "",
        "// Print functions",
        "void print_int(int i) {",
        "    printf(\"%d\\n\", i);",
        "}",
        "",
        "void print_bool(int b) {",
        "    printf(\"%s\\n\", (b) ? \"true\" : \"false\");",
        "}",
        "",
        "void print_str(const char* s) {",
        "    printf(\"%s\\n\", s);",
        "}",
        "",
        "void print_ptr(const void* p) {",
        "    printf(\"%p\\n\", p);",
        "}",
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
        "const char* read_str(const char* prompt) {",
        "    (void)prompt;  // Explicitly mark as unused to avoid warnings",
        "    // Use a fixed-size buffer for simplicity",
        "    static char buffer[1024];",
        "    if (fgets(buffer, sizeof(buffer), stdin) == NULL) {",
        "        buffer[0] = '\\0';  // Return empty string on error",
        "    }",
        "    // Remove trailing newline if present",
        "    size_t len = strlen(buffer);",
        "    if (len > 0 && buffer[len-1] == '\\n') {",
        "        buffer[len-1] = '\\0';",
        "    }",
        "    return buffer;",
        "}",
        "",
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
        # Helper: map Z type → C type
    def get_c_type(z_type):
        if isinstance(z_type, str) and z_type.endswith('*'):
            return z_type  # already a pointer type (e.g., int*, double*)
        if z_type == "string":
            return "const char*"
        return z_type

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
    normal_types = ['string','int','bool','double','float']
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
                    # For CONST, we'll mark the variable as const in the declarations
                    if current_function:
                        declarations[(current_function, dest)] = {"const": True, "type": var_type, "line": line_num}
                    else:
                        declarations[(None, dest)] = {"const": True, "type": var_type, "line": line_num}
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
                if c_type in normal_types:
                    global_var_lines.append(f"{const_prefix}{c_type} {var_clean};")
                else:
                    continue

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
                if const_prefix:
                    continue


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

        if op in ["IF", "ELIF"]:
            cond = " ".join(operands)
            cond = sanitize_condition(cond)
            cond = translate_logical_operators(cond)
            if op == "IF":
                c_lines.append(f"{prefix}if ({cond}) {{ ")
            else:  # ELIF
                c_lines.append(f"{prefix}else if ({cond}) {{ ")
        elif op in ["ELSE", "ELSE:"]:
            if operands and operands != [":"]:  # Allow 'ELSE:' as valid syntax
                raise CompilerError("ELSE does not take any conditions", line_num, ErrorCode.SYNTAX_ERROR)
            c_lines.append(f"{prefix}else {{ ")
        elif op == "WHILE":
            cond = " ".join(operands)
            cond = sanitize_condition(cond)
            cond = translate_logical_operators(cond)
            c_lines.append(f"{prefix}while ({cond}) {{ ")
        elif op == "FOR":
            # Default values
            var = 'i'
            start = '0'
            end = '10'  # Default range end
            
            if operands:
                var = operands[0]
                if len(operands) >= 4:
                    # Handle FOR var start .. end format
                    try:
                        start = operands[1]
                        if operands[2] == '..':
                            end = operands[3] if len(operands) > 3 else '10'
                        else:
                            # Handle FOR var start..end format (no spaces around ..)
                            if '..' in operands[1]:
                                parts = operands[1].split('..')
                                start = parts[0] if parts[0] else '0'
                                end = parts[1] if len(parts) > 1 and parts[1] else '10'
                    except IndexError:
                        pass  # Use defaults if parsing fails
                if var not in sanitized_cache:
                    sanitized_cache[var] = sanitize_identifier(var)
                var_clean = sanitized_cache[var]
                c_lines.append(f"{prefix}for (int {var_clean} = {start}; {var_clean} <= {end}; {var_clean}++) {{")
            indent_level += 1
            continue

        if op == "MOV":
            if len(operands) >= 2 and operands[0] in ["int", "float", "double", "string", "bool"]:
                var_type = operands[0]
                dest = operands[1]
                if dest not in sanitized_cache:
                    sanitized_cache[dest] = sanitize_identifier(dest)
                dest_safe = sanitized_cache[dest]
                
                # Check if a value was provided
                if len(operands) > 2:
                    expr = " ".join(operands[2:])
                else:
                    # No value provided, use type-appropriate default
                    if var_type == "string":
                        expr = 'NULL'
                    elif var_type == "int":
                        expr = '0'
                    elif var_type == "bool":
                        expr = 'false'
                    elif var_type in ["double", "float"]:
                        expr = '0.0'
                
                # Check if this is a string literal
                is_string_literal = expr.startswith('"') and expr.endswith('"')
                
                # Check if this is a re-declaration
                is_redeclaration = any(
                    line.strip().startswith(f"{var_type} {dest_safe} =") or 
                    line.strip().startswith(f"const char* {dest_safe} =") 
                    for line in c_lines
                )
                
                # Generate appropriate code based on type and declaration status
                if is_string_literal:
                    if not is_redeclaration:
                        c_lines.append(f'{prefix}const char* {dest_safe} = {expr};')
                    else:
                        c_lines.append(f'{prefix}{dest_safe} = {expr};')
                else:
                    if not is_redeclaration:
                        c_lines.append(f'{prefix}{var_type} {dest_safe} = {expr};')
                    else:
                        c_lines.append(f'{prefix}{dest_safe} = {expr};')
                        
                # Track the variable type for future reference
                if dest_safe not in variable_types:
                    variable_types[dest_safe] = var_type
                    
            elif len(operands) == 2:
                # Assignment: dest = expr
                dest, expr = operands
                
                # Check for pointer dereferencing (e.g., *ptr = 100)
                is_pointer_deref = dest.startswith('*')
                
                if is_pointer_deref:
                    # Handle pointer dereference assignment: *ptr = value
                    ptr_name = dest[1:]  # Remove the *
                    if ptr_name not in sanitized_cache:
                        sanitized_cache[ptr_name] = sanitize_identifier(ptr_name)
                    ptr_safe = sanitized_cache[ptr_name]
                    c_lines.append(f'{prefix}*{ptr_safe} = {dest};')
                else:
                    # Check if this is an array access (e.g., numbers[i])
                    if '[' in expr and ']' in expr and '=' not in expr and '==' not in expr and '!=' not in expr:
                        # Handle array access
                        array_name = expr.split('[')[0]
                        array_idx = expr.split('[')[1].split(']')[0]
                        
                        # Get the array type (Aint, Afloat, etc.)
                        array_type = variable_types.get(array_name, 'Aint')  # Default to Aint if not found
                        
                        # Map ZLang array types to C types
                        type_map = {
                            'Aint': 'int',
                            'Afloat': 'float',
                            'Adouble': 'double',
                            'Abool': 'bool',
                            'Astring': 'const char*'
                        }
                        c_type = type_map.get(array_type, 'int')
                        
                        # Sanitize the destination variable name
                        if dest not in sanitized_cache:
                            sanitized_cache[dest] = sanitize_identifier(dest)
                        dest_safe = sanitized_cache[dest]
                        
                        # Generate the array access code
                        c_lines.append(f'{prefix}{c_type} {dest_safe} = *(({c_type}*)array_get({array_name}, {array_idx}));')
                        
                        # Track the variable type for future reference
                        if dest_safe not in variable_types:
                            variable_types[dest_safe] = c_type
                    else:
                        # Regular variable assignment
                        if dest not in sanitized_cache:
                            sanitized_cache[dest] = sanitize_identifier(dest)
                        dest_safe = sanitized_cache[dest]
                        
                        # Check if this is a re-declaration
                        is_redeclaration = any(
                            line.strip().startswith(f"{dest_safe} =") or 
                            line.strip().startswith(f"int {dest_safe} =") or
                            line.strip().startswith(f"double {dest_safe} =") or
                            line.strip().startswith(f"const char* {dest_safe} =")
                            for line in c_lines
                        )
                        
                        if not is_redeclaration and dest_safe not in variable_types:
                            # If we don't know the type, default to int
                            c_lines.append(f'{prefix}int {dest_safe} = {expr};')
                            variable_types[dest_safe] = 'int'
                        else:
                            c_lines.append(f'{prefix}{dest_safe} = {expr};')
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
                # Generate final const line with proper type handling for strings
                var_type = operands[0]
                if var_type == 'string':
                    # For strings, we don't need an extra 'const' since 'const char*' already includes it
                    c_lines.append(f"{prefix}const char* {sanitized_cache[dest]} = {expr};")
                else:
                    # For other types, use the original type with const
                    c_lines.append(f"{prefix}const {var_type} {sanitized_cache[dest]} = {expr};")
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
            # First, handle the case where there are no operands (just print a newline)
            if not operands:
                c_lines.append(f'{prefix}printf("\n");')
                continue
                
            # Process each operand and generate appropriate print function calls
            for operand in operands:
                # Check if this is a string literal
                if operand.startswith('"') and operand.endswith('"'):
                    # Use print_str for string literals
                    c_lines.append(f'{prefix}print_str({operand});')
                # Check if this is a variable
                elif operand in variable_types:
                    var_type = variable_types[operand]
                    if var_type == "int":
                        c_lines.append(f'{prefix}print_int({operand});')
                    elif var_type == "bool":
                        c_lines.append(f'{prefix}print_bool({operand});')
                    elif var_type == "string":
                        c_lines.append(f'{prefix}print_str({operand});')
                    elif var_type in ["float", "double"]:
                        c_lines.append(f'{prefix}print_double({operand});')
                    elif var_type.endswith('*'):  # Handle pointer types
                        c_lines.append(f'{prefix}print_ptr({operand});')
                    else:
                        # Default to print_str for unknown types
                        c_lines.append(f'{prefix}print_str({operand});')
                # Check if this is a number
                elif operand.replace('.', '', 1).isdigit() or (operand.startswith('-') and operand[1:].replace('.', '', 1).isdigit()):
                    # Numeric literal
                    if '.' in operand or 'e' in operand.lower():
                        c_lines.append(f'{prefix}print_double({operand});')
                    else:
                        c_lines.append(f'{prefix}print_int({operand});')
                # Check for boolean literals
                elif operand == "true" or operand == "false":
                    c_lines.append(f'{prefix}print_bool(1);' if operand == "true" else f'{prefix}print_bool(0);')
                else:
                    # Default to print_str for unknown literals
                    c_lines.append(f'{prefix}print_str("{operand}");')
            continue
        if op == "ERROR":
            msg = " ".join(operands)
            msg = msg.replace('"', '')
            c_lines.append(f"{prefix}error_exit(1, \"{msg}\");")
            continue
        if op == "RET":
            ret_val = operands[0] if operands else '0'
            c_lines.append(f"{prefix}return {ret_val};")
            continue

        if op == "PTR":
            # PTR <type> <ptr_name> <target_var>
            if len(operands) == 3:
                type_name, ptr_name, target_var = operands
                
                # Sanitize names for emitted C
                if ptr_name not in sanitized_cache:
                    sanitized_cache[ptr_name] = sanitize_identifier(ptr_name)
                if target_var not in sanitized_cache:
                    sanitized_cache[target_var] = sanitize_identifier(target_var)
                    
                ptr_safe = sanitized_cache[ptr_name]
                var_safe = sanitized_cache[target_var]
                
                # Add to pointer variables set
                pointer_vars.add(ptr_safe)
                
                # Check if this is a re-declaration
                is_redeclaration = any(line.strip().startswith(f"{type_name}* {ptr_safe} =") 
                                     for line in c_lines)
                
                # Emit pointer declaration and initialization
                if not is_redeclaration:
                    c_lines.append(f"{prefix}{type_name}* {ptr_safe} = &{var_safe};")

                # Ensure type-tracking matches sanitized name usage later
                variable_types[ptr_safe] = f"{type_name}*"

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
        if op == "ARR":
            if len(operands) >= 2:
                arr_type = operands[0]
                arr_name = operands[1]
                
                # Sanitize the array name
                if arr_name not in sanitized_cache:
                    sanitized_cache[arr_name] = sanitize_identifier(arr_name)
                safe_name = sanitized_cache[arr_name]

                # Map Z array types to C types
                type_map = {
                    "Aint": ("int", "int"),
                    "Afloat": ("float", "float"),
                    "Adouble": ("double", "double"),
                    "Abool": ("bool", "bool"),
                    "Astring": ("const char*", "string")
                }

                if arr_type not in type_map:
                    raise CompilerError(f"Unknown array type: {arr_type}", line_num,
                                     ErrorCode.INVALID_TYPE, z_file)

                c_type, arr_type_name = type_map[arr_type]

                # Handle array initialization with values if provided
                if len(operands) > 2:
                    # Check if the third operand is a number (capacity) or starts with '[' (values)
                    if operands[2].isdigit() and len(operands) > 3 and '[' in operands[3]:
                        # Format: ARR Aint arr 3 [1,2,3]
                        capacity = operands[2]
                        values_str = ' '.join(operands[3:])
                    else:
                        # Format: ARR Aint arr [1,2,3] or ARR Aint arr 1,2,3
                        values_str = ' '.join(operands[2:])
                        # Default capacity is the number of elements or 4, whichever is larger
                        if '[' in values_str and ']' in values_str:
                            # Extract values between [ and ]
                            values_part = values_str[values_str.find('[')+1:values_str.rfind(']')]
                            values = [v.strip() for v in values_part.split(',') if v.strip()]
                            capacity = str(max(len(values), 4))  # At least 4 elements
                        else:
                            capacity = '4'  # Default initial capacity
                    
                    # Check for [ ] syntax
                    if '[' in values_str and ']' in values_str:
                        # Extract content between brackets
                        start = values_str.find('[') + 1
                        end = values_str.rfind(']')
                        values_str = values_str[start:end].strip()
                        values = [v.strip() for v in values_str.split(',') if v.strip()]
                    else:
                        # Old style: comma-separated values without brackets
                        values = [v.strip() for v in values_str.split(',') if v.strip()]
                    
                    # Check if we have more values than capacity
                    if 'capacity' in locals() and len(values) > int(capacity):
                        raise CompilerError(
                            f"Array '{arr_name}' has {len(values)} elements but capacity is only {capacity}",
                            line_num,
                            ErrorCode.OVERFLOW,
                            z_file
                        )
                    
                    # Create the array with the calculated capacity
                    c_lines.append(f"{prefix}Array* {safe_name} = array_create_with_capacity(sizeof({c_type}), \"{arr_type_name}\", {capacity});")
                    
                    # Add values if any
                    for i, val in enumerate(values):
                        # Add bounds check for each element if capacity is specified
                        if 'capacity' in locals() and i >= int(capacity):
                            break
                        c_lines.append(f"{prefix}{{\n{prefix}    {c_type} _val = {val};\n{prefix}    array_push({safe_name}, &_val);\n{prefix}}}")
                    
                    # If we had to truncate due to capacity, show a warning
                    if 'capacity' in locals() and len(values) > int(capacity):
                        c_lines.append(f"{prefix}// Warning: Array '{arr_name}' truncated to {capacity} elements (capacity exceeded)")
                else:  # Empty array with no values
                    # Check if capacity is specified (ARR Aint arr 10)
                    if len(operands) == 3 and operands[2].isdigit():
                        capacity = operands[2]
                        c_lines.append(f"{prefix}Array* {safe_name} = array_create_with_capacity(sizeof({c_type}), \"{arr_type_name}\", {capacity});")
                    else:
                        c_lines.append(f"{prefix}Array* {safe_name} = array_create(sizeof({c_type}), \"{arr_type_name}\");")
                
                # Track array type for bounds checking
                variable_types[arr_name] = arr_type
            continue
            
        # Array operations
        if op == "PUSH":
            if len(operands) >= 2:
                arr_name = operands[0]
                value = " ".join(operands[1:])
                if arr_name not in variable_types:
                    raise CompilerError(f"Undefined array: {arr_name}", line_num, 
                                     ErrorCode.UNDEFINED_SYMBOL, z_file)
                
                # Get the array type from the variable_types dictionary
                arr_type = variable_types[arr_name]
                # Map array type to C type (remove 'A' prefix)
                type_map = {
                    "Aint": "int",
                    "Afloat": "float",
                    "Adouble": "double",
                    "Abool": "bool",
                    "Astring": "const char*"
                }
                c_type = type_map.get(arr_type, "double")  # Default to double if type not found
                
                # Special handling for string literals in string arrays
                if arr_type == "Astring" and value.startswith('"') and value.endswith('"'):
                    # For string literals, we need to strdup them
                    c_lines.append(f"{prefix}{{\n{prefix}    {c_type} _val = strdup({value});\n{prefix}    array_push({arr_name}, &_val);\n{prefix}}}")
                else:
                    c_lines.append(f"{prefix}{{\n{prefix}    {c_type} _val = {value};\n{prefix}    array_push({arr_name}, &_val);\n{prefix}}}")
            continue
            
        if op == "POP":
            if len(operands) >= 1:
                arr_name = operands[0]
                if arr_name not in variable_types:
                    raise CompilerError(f"Undefined array: {arr_name}", line_num,
                                     ErrorCode.UNDEFINED_SYMBOL, z_file)
                
                # Get the array type from the variable_types dictionary
                arr_type = variable_types[arr_name]
                # Map array type to C type (remove 'A' prefix)
                type_map = {
                    "Aint": "int",
                    "Afloat": "float",
                    "Adouble": "double",
                    "Abool": "bool",
                    "Astring": "char*"
                }
                c_type = type_map.get(arr_type, "double")  # Default to double if type not found
                
                if len(operands) == 2:
                    # POP into a variable
                    var_name = operands[1]
                    c_lines.append(f"{prefix}{{\n{prefix}    {c_type} _val;\n{prefix}    array_pop({arr_name}, &_val);")
                    
                    # Special handling for string arrays
                    if arr_type == "Astring":
                        c_lines.append(f"{prefix}    {var_name} = strdup(_val);")
                        c_lines.append(f"{prefix}    free(_val);")
                    else:
                        c_lines.append(f"{prefix}    {var_name} = _val;")
                    c_lines.append(f"{prefix}}}")
                else:
                    # Just remove the last element
                    c_lines.append(f"{prefix}{{\n{prefix}    {c_type} _val;\n{prefix}    array_pop({arr_name}, &_val);")
                    # Free the string if it's a string array
                    if arr_type == "Astring":
                        c_lines.append(f"{prefix}    free(_val);")
                    c_lines.append(f"{prefix}}}")
            continue
            
        if op == "LEN":
            if len(operands) == 2:
                arr_name = operands[0]
                var_name = operands[1]
                c_lines.append(f"{prefix}{var_name} = array_length({arr_name});")
            continue
            
        if op == "PRINTARR":
            if len(operands) == 1:
                arr_name = operands[0]
                c_lines.append(f"{prefix}print_array({arr_name});")
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
                    c_lines.append(f"{prefix}{sanitized_cache[dest]} = read_str({prompt});")
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
