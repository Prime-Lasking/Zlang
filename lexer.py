"""Lexical analysis for ZLang."""
import re
from typing import List, Tuple, Set, Dict, Optional
from errors import CompilerError, ErrorCode

# Precompiled regexes for better performance
IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
TOKEN_RE = re.compile(r'"[^"]*"|\S+')

OPS = {"MOV", "ADD", "SUB", "MUL", "DIV", "PRINT",
       "PRINTSTR", "HALT", "READ", "MOD", "INC", "DEC", "AND", "OR", "NOT",
       "CALL", "RET", "END", "ERROR", "FN", "FNDEF", "FOR", "WHILE", "IF", "ELSE", "ELIF", "BREAK"}

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

def parse_z_file(z_file: str) -> Tuple[list, set, set, Dict[Tuple[Optional[str], str], Dict[str, object]]]:
    """Parse ZLang source file and return (instructions, variables, labels, declarations).
    declarations: map of (scope, var_name) -> { 'mutable': bool, 'line': int }
    scope is function name or None for global scope.
    """
    try:
        with open(z_file, "r") as f:
            lines = f.readlines()
    except IOError as e:
        raise CompilerError(f"Cannot read file: {e}", error_code=ErrorCode.IO_ERROR, file_path=z_file)

    instructions, variables, labels = [], set(), set()
    indent_stack = [0]  # Track indentation levels

    # Track current function scope via FNDEF/INDENT/DEDENT events
    current_function: Optional[str] = None
    func_depth = 0

    # Declarations with mutability info
    declarations: Dict[Tuple[Optional[str], str], Dict[str, object]] = {}
    
    for line_num, raw in enumerate(lines, 1):
        # Calculate indentation
        line = raw.rstrip('\n')
        indent = len(line) - len(line.lstrip())
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
        
        # Remove comments and split into tokens
        line = line.split('//')[0].strip()
        if not line:
            continue
            
        tokens = TOKEN_RE.findall(line)
        if not tokens:
            continue
            
        op = tokens[0].upper()
        operands = tokens[1:]
        
        # Handle labels (tokens ending with ':') before other parsing
        if tokens[0].endswith(':'):
            label_name = tokens[0][:-1]
            instructions.append(("LABEL", [label_name], line_num))
            continue

        # Handle function definitions: FN name(params) [-> rettype]:
        if op == "FN":
            decl = line[2:].strip()  # after 'FN'
            decl = decl[:-1] if decl.endswith(':') else decl
            # Split off return type if present
            if '->' in decl:
                decl, _ = decl.split('->', 1)
                decl = decl.strip()
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
                            params.append(parts[-1])  # name only
                instructions.append(("FNDEF", [func_name] + params, line_num))
                current_function = func_name
                func_depth = 0
            else:
                func_name = decl.strip()
                instructions.append(("FNDEF", [func_name], line_num))
                current_function = func_name
                func_depth = 0
            continue

        # Handle function calls: CALL name(arg1, arg2) [-> ret] OR CALL name(arg1) ret
        if op == "CALL":
            joined = ' '.join(operands)
            ret_var = None
            call_expr = joined
            if '->' in joined:
                call_expr, ret_var = [s.strip() for s in joined.split('->', 1)]
            else:
                # If there's a trailing identifier after ) treat it as return var
                if ')' in joined:
                    before, after = joined.split(')', 1)
                    call_expr = before + ')'
                    after = after.strip()
                    if after:
                        ret_var = after
            # Parse function and args
            if '(' in call_expr and call_expr.endswith(')'):
                fname = call_expr.split('(')[0].strip()
                args_str = call_expr.split('(', 1)[1][:-1].strip()
                args = [a.strip() for a in args_str.split(',')] if args_str else []
            else:
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

        # Handle MOV with type declarations keeping full expression
        if op == "MOV":
            type_keywords = ["int", "float", "double", "string", "bool"]
            if operands and operands[0] == "mut" and len(operands) >= 3 and operands[1] in type_keywords:
                # MOV mut <type> <dest> [expr]
                type_decl = operands[1]
                remaining = operands[2:]
                if not remaining:
                    raise CompilerError("Missing destination for MOV", line_num, ErrorCode.SYNTAX_ERROR, z_file)
                dest = remaining[0]
                expr = " ".join(remaining[1:]).strip()
                if expr:
                    operands = [type_decl, dest] + [expr]
                else:
                    operands = [type_decl, dest]
                declarations[(current_function, dest)] = {"mutable": True, "line": line_num}
            elif operands and operands[0] in type_keywords:
                # MOV <type> <dest> [expr]  -> default immutable
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
                declarations[(current_function, dest)] = {"mutable": False, "line": line_num}
            elif len(operands) >= 2:
                # value dest
                value = " ".join(operands[:-1])
                dest = operands[-1]
                operands = [value, dest]

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
            if t_clean in {"int", "float", "double", "string", "bool", "from", "to", "..", "mut"}:
                continue
            if t_clean.startswith('"') and t_clean.endswith('"'):
                continue
            if '(' in t_clean or ')' in t_clean:
                continue
            if is_number(t_clean):
                continue
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

    return instructions, variables, labels, declarations
