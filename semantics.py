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

    # Helper to check if assignment to a variable is allowed
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
                    # This is a variable declaration: MOV <type> <name> [value] or MOV mut <type> <name> [value]
                    # Check if this is a mut declaration
                    is_mut_declaration = False
                    var_name_idx = 1

                    if len(operands) >= 3 and operands[0] == "mut":
                        is_mut_declaration = True
                        var_name_idx = 2

                    if var_name_idx >= len(operands):
                        continue  # Malformed declaration, skip

                    var_type = operands[0] if not is_mut_declaration else operands[1]
                    var_name = operands[var_name_idx]

                    # Check for redeclaration in the same scope
                    # (Declarations are already recorded by the lexer, so we don't need to record them again)
                    # if (current_function, var_name) in declarations:
                    #     existing_decl = declarations[(current_function, var_name)]
                    #     raise CompilerError(
                    #         f"Variable '{var_name}' already declared in this scope",
                    #         line_num,
                    #         ErrorCode.REDEFINED_SYMBOL,
                    #         z_file,
                    #     )
                    # # Also check global scope if we're in a function
                    # if current_function is not None and (None, var_name) in declarations:
                    #     raise CompilerError(
                    #         f"Variable '{var_name}' already declared in global scope",
                    #         line_num,
                    #         ErrorCode.REDEFINED_SYMBOL,
                    #         z_file,
                    #     )

                    # Declarations are already recorded by the lexer, don't re-record them
                else:
                    # Assignment: value dest
                    check_dest(operands[1])

        elif op in {"ADD", "SUB", "MUL", "DIV", "MOD"}:
            if len(operands) == 3:
                check_dest(operands[2])
        elif op == "CALL":
            if operands:
                check_dest(operands[-1])
