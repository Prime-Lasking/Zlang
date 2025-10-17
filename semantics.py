"""Semantic checks for ZLang, including immutability enforcement for MOV declarations."""
from typing import Dict, Tuple, Optional, List
from errors import CompilerError, ErrorCode

types_set = {"int", "float", "double", "string", "bool"}


def validate_immutability(instructions: List[Tuple[str, list, int]],
                          declarations: Dict[Tuple[Optional[str], str], Dict[str, object]],
                          z_file: str) -> None:
    """
    Enforce that variables declared with `MOV <type> <name> ...` are immutable by default.
    Variables declared with `MOV mut <type> <name> ...` are mutable.

    Only assignments to declared variables are checked. Implicitly created variables via ops are not constrained.
    """
    # Helper to check mutability for a destination in current scope or global
    def is_immutable(scope: Optional[str], name: str) -> bool:
        if (scope, name) in declarations:
            return not bool(declarations[(scope, name)].get("mutable", False))
        if (None, name) in declarations:
            return not bool(declarations[(None, name)].get("mutable", False))
        return False

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

        # Determine if this instruction writes to a variable that may be immutable
        def check_dest(dest_name: str):
            if not dest_name:
                return
            if is_immutable(current_function, dest_name):
                raise CompilerError(
                    f"Cannot reassign to immutable variable '{dest_name}'",
                    line_num,
                    ErrorCode.INVALID_OPERATION,
                    z_file,
                )

        if op == "MOV":
            if len(operands) >= 2:
                if operands[0] in types_set:
                    # Typed MOV is a declaration; first assignment allowed
                    pass
                else:
                    # Assignment: value dest
                    check_dest(operands[1])
        elif op in {"ADD", "SUB", "MUL", "DIV", "MOD"}:
            if len(operands) == 3:
                check_dest(operands[2])
        elif op == "CALL":
            if operands:
                check_dest(operands[-1])
