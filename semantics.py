"""Semantic checks for ZLang, including const enforcement for variable declarations."""
from typing import Dict, Tuple, Optional, List
from errors import CompilerError, ErrorCode

types_set = {"int", "float", "double", "string", "bool"}


def validate_const_and_types(instructions: List[Tuple[str, list, int]],
                          declarations: Dict[Tuple[Optional[str], str], Dict[str, object]],
                          z_file: str) -> None:
    """
    Enforce const constraints and type checking for variables.
    Variables declared with CONST cannot be reassigned.
    Variables must be declared with explicit types.
    """
    # Helper to get declaration info for a variable
    def get_decl(scope: Optional[str], name: str) -> Optional[Dict[str, object]]:
        if (scope, name) in declarations:
            return declarations[(scope, name)]
        if (None, name) in declarations:
            return declarations[(None, name)]
        return None

    # Helper to check if a variable is const
    def is_const(scope: Optional[str], name: str) -> bool:
        decl = get_decl(scope, name)
        return decl is not None and bool(decl.get("const", False))

    # Helper to get type of a variable
    def get_type(scope: Optional[str], name: str) -> Optional[str]:
        decl = get_decl(scope, name)
        return decl.get("type") if decl else None

    # Helper to check if assignment to a variable is allowed (const and type)
    def check_dest(dest_name: str, src_type: Optional[str] = None):
        if not dest_name:
            return
        decl = get_decl(current_function, dest_name)
        if not decl:
            raise CompilerError(
                f"Variable '{dest_name}' not declared",
                line_num,
                ErrorCode.UNDEFINED_SYMBOL,
                z_file,
            )
        if is_const(current_function, dest_name):
            raise CompilerError(
                f"Cannot reassign to const variable '{dest_name}'",
                line_num,
                ErrorCode.INVALID_OPERATION,
                z_file,
            )
        if src_type and decl.get("type") != src_type:
            raise CompilerError(
                f"Type mismatch: cannot assign {src_type} to {decl.get('type')} variable '{dest_name}'",
                line_num,
                ErrorCode.TYPE_MISMATCH,
                z_file,
            )

    current_function: Optional[str] = None
    func_depth = 0

    for op, operands, line_num in instructions:
        if op == "FNDEF":
            current_function = operands[0] if operands else None
            func_depth = 0
            continue
        if op == "INDENT":
            if current_function is not None:
                func_depth += 1
            continue
        if op == "DEDENT":
            if current_function is not None:
                func_depth = max(func_depth - 1, 0)
                if func_depth == 0:
                    current_function = None
            continue

        if op == "MOV":
            if len(operands) >= 2:
                if operands[0] in types_set:
                    # This is a variable declaration: MOV <type> <name> [value]
                    # Declarations are already recorded by the lexer, don't re-record them
                    pass
                else:
                    # Assignment: dest expr
                    check_dest(operands[0])

        elif op in {"ADD", "SUB", "MUL", "DIV", "MOD"}:
            if len(operands) == 3:
                check_dest(operands[2])
        elif op == "CALL":
            if operands:
                check_dest(operands[-1])
