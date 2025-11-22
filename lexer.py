"""Lexical analysis for ZLang."""
import re
import os
from typing import List, Tuple, Set, Dict, Optional
from errors import CompilerError, ErrorCode

# Precompiled regexes for better performance
IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
TOKEN_RE = re.compile(r'"[^"]*"|\S+')

OPS = {"MOV", "ADD", "SUB", "MUL", "DIV", "PRINT", "READ", "MOD", "INC", "DEC", "CALL", "RET", "ERROR",
       "FNDEF", "FN", "FOR", "WHILE", "IF", "ELSE", "ELIF", "PRINTSTR", "PRINTARR", "CONST",
       "ARR", "LEN", "PUSH", "POP", "PTR", "IMPORT"}

# Array types
ARRAY_TYPES = {"Aint", "Afloat", "Adouble", "Abool", "Astring"}

C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default",
    "do", "double", "else", "enum", "extern", "float", "for", "goto",
    "if", "inline", "int", "long", "register", "restrict", "return",
    "short", "signed", "sizeof", "static", "struct", "switch",
    "typedef", "union", "unsigned", "void", "volatile", "while"
}

def is_identifier(token: str) -> bool:
    return bool(IDENTIFIER_RE.match(token))

def is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except Exception:
        return False

def parse_z_file(z_file: str) -> Tuple[list, set, Dict[Tuple[Optional[str], str], Dict[str, object]]]:
    """Parse ZLang source file and return (instructions, variables, declarations).
    declarations: map of (scope, var_name) -> { 'mutable': bool, 'line': int }
    scope is function name or None for global scope.
    """
    try:
        with open(z_file, "r", encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        raise CompilerError(
            f"File encoding error - only UTF-8 files are supported",
            error_code=ErrorCode.INVALID_FILE_FORMAT,
            file_path=z_file
        )
    except IOError as e:
        raise CompilerError(f"Cannot read file: {e}", error_code=ErrorCode.IO_ERROR, file_path=z_file)

    instructions, variables = [], set()
    indent_stack = [0]  # Track indentation levels

    # Track current function scope via FNDEF/INDENT/DEDENT events
    current_function: Optional[str] = None
    func_depth = 0

    # Declarations with mutability info
    declarations: Dict[Tuple[Optional[str], str], Dict[str, object]] = {}
    
    for line_num, raw in enumerate(lines, 1):
        # Calculate indentation - normalize tabs to spaces for consistent calculation
        line = raw.rstrip('\n')
        # Replace tabs with spaces (4 spaces per tab, standard Python indentation)
        normalized_line = line.replace('\t', '    ')
        indent = len(normalized_line) - len(normalized_line.lstrip())
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('//'):
            continue
            
        # Handle indentation changes
        if indent > indent_stack[-1]:
            # New block started
            indent_stack.append(indent)
            instructions.append(("INDENT", [], line_num))
            if current_function is not None:
                func_depth += 1
        elif indent < indent_stack[-1]:
            # Block ended
            while indent < indent_stack[-1]:
                indent_stack.pop()
                instructions.append(("DEDENT", [], line_num))
                if current_function is not None:
                    func_depth = max(func_depth - 1, 0)
                    if func_depth == 0:
                        current_function = None
            if indent != indent_stack[-1]:
                raise CompilerError("Inconsistent indentation", line_num, 
                                 ErrorCode.SYNTAX_ERROR, z_file)
        
        # Remove comments and process the line
        line = line.split('//')[0].strip()
        if not line:
            continue
            
        # Special handling for array access in print statements
        line_stripped = line.strip()
        if line_stripped.startswith('PRINT '):
            # Extract the expression after PRINT
            expr = line[5:].strip()
            if '[' in expr and ']' in expr:
                # This is an array access, handle it as a single token
                tokens = ['PRINT', expr]
            else:
                tokens = TOKEN_RE.findall(line)
        # Special handling for array declarations
        elif line_stripped.startswith('ARR '):
            # Handle array declaration format: ARR type name size [values...]
            parts = line_stripped.split()
            if len(parts) >= 4 and '[' in line and ']' in line:
                start_idx = line.find('[')
                end_idx = line.rfind(']')
                array_values = line[start_idx:end_idx+1]

                before_values = line[:start_idx].strip()
                before_tokens = TOKEN_RE.findall(before_values)
                tokens = before_tokens + [array_values]
            else:
                tokens = TOKEN_RE.findall(line)
        else:
            # Handle ELSE: as a single token
            if 'ELSE:' in line and not ('IF' in line or 'ELIF' in line):
                # Replace 'ELSE:' with 'ELSE' to handle it as a single token
                line = line.replace('ELSE:', 'ELSE')
            tokens = TOKEN_RE.findall(line)
            
        if not tokens:
            continue
            
        op = tokens[0].upper()
        operands = tokens[1:]

        # Validate that the opcode is known
        if op not in OPS:
            raise CompilerError(
                f"Unknown opcode '{op}'",
                error_code=ErrorCode.SYNTAX_ERROR,
                file_path=z_file,
                line_num=line_num
            )

        # Handle function definitions: FN name(params) [-> rettype]:
        if op == "FN":
            decl = line[2:].strip()  # after 'FN'
            decl = decl[:-1] if decl.endswith(':') else decl
            # Split off return type if present
            ret_type = None
            if '->' in decl:
                decl, ret_type = decl.split('->', 1)
                decl = decl.strip()
                ret_type = ret_type.strip()
            # Name and params
            if '(' in decl and ')' in decl:
                func_name = decl.split('(')[0].strip()
                params_str = decl.split('(', 1)[1].rsplit(')', 1)[0].strip()
                params = []
                if params_str:
                    for p in params_str.split(','):
                        p = p.strip()
                        if not p:
                            continue
                        parts = p.split()
                        if len(parts) == 2 and parts[0] in {"int", "float", "double", "bool", "string"}:
                            params.extend(parts)  # [type, name]
                        else:
                            raise CompilerError(f"Function parameter '{p}' requires explicit type declaration (e.g., int param)", line_num, ErrorCode.SYNTAX_ERROR, z_file)
                # Include return type in FNDEF if present
                fndef_operands = [func_name] + params
                if ret_type:
                    fndef_operands.append(ret_type)
                instructions.append(("FNDEF", fndef_operands, line_num))
                current_function = func_name
                func_depth = 0
            else:
                func_name = decl.strip()
                instructions.append(("FNDEF", [func_name], line_num))
                current_function = func_name
                func_depth = 0
            continue

        # Handle function calls: CALL name(arg1, arg2) [-> ret] OR CALL name(arg1) ret OR CALL name -> ret
        if op == "CALL":
            joined = ' '.join(operands)
            ret_var = None
            call_expr = joined
            
            # Check for return value specification (-> ret)
            if '->' in joined:
                call_expr, ret_var = [s.strip() for s in joined.split('->', 1)]
            else:
                # Check for space-separated return variable at the end
                # This should be checked before parsing parentheses to handle cases like "add(x,y) a"
                parts = joined.split()
                if len(parts) > 1:
                    # Check if the last part could be a return variable (not a function argument)
                    last_part = parts[-1]
                    # If there are parentheses, check if the last part is outside them
                    if '(' in joined and ')' in joined:
                        # Count parentheses to find the actual end of the function call
                        paren_count = 0
                        for i, char in enumerate(joined):
                            if char == '(':
                                paren_count += 1
                            elif char == ')':
                                paren_count -= 1
                                if paren_count == 0:
                                    # Everything after the closing parenthesis could be the return variable
                                    after_paren = joined[i+1:].strip()
                                    if after_paren and not after_paren.startswith('->'):
                                        ret_var = after_paren
                                        call_expr = joined[:i+1].strip()
                                    break
                    else:
                        # No parentheses, so the last part is likely the return variable
                        ret_var = last_part
                        call_expr = ' '.join(parts[:-1])
            
            # Parse function name and arguments
            if '(' in call_expr and call_expr.endswith(')'):
                # Function call with arguments: name(arg1, arg2)
                fname = call_expr.split('(')[0].strip()
                args_str = call_expr.split('(', 1)[1][:-1].strip()
                args = [a.strip() for a in args_str.split(',')] if args_str else []
            else:
                # Function call without arguments: name
                fname = call_expr.strip()
                args = []
            
            if ret_var is None:
                ret_var = "_"
                
            instructions.append(("CALL", [fname] + args + [ret_var], line_num))
            continue

        # Special handling for FOR loops with .. syntax
        if op == "FOR" and len(operands) == 2:
            range_token = operands[1]
            if ".." in range_token and not range_token.endswith(':'):
                parts = range_token.split("..")
                if len(parts) == 2:
                    operands = [operands[0], parts[0], "..", parts[1]]
            elif ".." in range_token and range_token.endswith(':'):
                range_part = range_token[:-1]
                parts = range_part.split("..")
                if len(parts) == 2:
                    operands = [operands[0], parts[0], "..", parts[1]]

        # Handle CONST with type declarations
        if op == "CONST":
            type_keywords = ["int", "float", "double", "string", "bool"]
            if operands and operands[0] in type_keywords:
                type_decl = operands[0]
                remaining = operands[1:]
                if not remaining:
                    raise CompilerError("Missing destination for CONST", line_num, ErrorCode.SYNTAX_ERROR, z_file)
                dest = remaining[0]
                expr = " ".join(remaining[1:]).strip()
                if expr:
                    operands = [type_decl, dest] + [expr]
                else:
                    operands = [type_decl, dest]
                declarations[(current_function, dest)] = {"const": True, "type": type_decl, "line": line_num}
            else:
                raise CompilerError("CONST requires explicit type declaration (e.g., CONST int var value)", line_num, ErrorCode.SYNTAX_ERROR, z_file)

        # Handle MOV with type declarations (mutable by default)
        if op == "MOV":
            type_keywords = ["int", "float", "double", "string", "bool"]
            if operands and operands[0] in type_keywords:
                # MOV <type> <dest> [expr]  -> mutable by default
                type_decl = operands[0]
                remaining = operands[1:]
                if not remaining:
                    raise CompilerError("Missing destination for MOV", line_num, ErrorCode.SYNTAX_ERROR, z_file)
                dest = remaining[0]
                expr = " ".join(remaining[1:]).strip()
                if expr:
                    operands = [type_decl, dest] + [expr]
                else:
                    operands = [type_decl, dest]
                declarations[(current_function, dest)] = {"const": False, "type": type_decl, "line": line_num}
            elif len(operands) >= 2:
                # MOV <dest> <expr> - assignment to existing variable
                dest = operands[0]
                expr = " ".join(operands[1:]).strip()
                operands = [dest, expr]
                # Note: We don't add to declarations since it's a reassignment
            else:
                # Require explicit type declaration
                raise CompilerError("MOV requires explicit type declaration (e.g., MOV int var value)", line_num, ErrorCode.SYNTAX_ERROR, z_file)

        # Validate operands for invalid boolean literals before processing
        for i, t in enumerate(operands):
            stripped = t.strip()
            if stripped in {"True", "False"}:
                raise CompilerError(
                    f"Invalid boolean literal '{stripped}'. Use 'true' or 'false' (lowercase)",
                    error_code=ErrorCode.SYNTAX_ERROR,
                    file_path=z_file,
                    line_num=line_num,
                )

        # Build variables set: only identifiers
        for t in operands:
            if t is None:
                continue
            # strip punctuation around identifiers
            t_clean = t
            if '[' in t_clean and ']' in t_clean:
                t_clean = t_clean.split('[', 1)[0]
            if t_clean.endswith(':'):
                continue
            if t_clean in {"int", "float", "double", "string", "bool", "from", "to", "..", "mut", "const"}:
                continue
            if t_clean.startswith('"') and t_clean.endswith('"'):
                continue
            if '(' in t_clean or ')' in t_clean:
                continue
            if is_number(t_clean):
                continue
            # Filter out boolean literals
            if t_clean in {"true", "false"}:
                continue
            # Reject invalid boolean literals (redundant but kept for safety)
            if t_clean in {"True", "False"}:
                raise CompilerError(f"Invalid boolean literal '{t_clean}'. Use 'true' or 'false' (lowercase)", error_code=ErrorCode.SYNTAX_ERROR, file_path=z_file, line_num=line_num)
            if is_identifier(t_clean) and t_clean != "main":
                variables.add(t_clean)

        instructions.append((op, operands, line_num))
    
    # Close all remaining blocks at end of file
    while len(indent_stack) > 1:
        indent_stack.pop()
        instructions.append(("DEDENT", [], line_num))
        if current_function is not None:
            func_depth = max(func_depth - 1, 0)
            if func_depth == 0:
                current_function = None

    return instructions, variables, declarations
