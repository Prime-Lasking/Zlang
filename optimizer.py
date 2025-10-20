"""Optimization stage for ZLang."""
from typing import List, Tuple
from errors import CompilerError, ErrorCode

def optimize_instructions(instructions: List[Tuple[str, list, int]], z_file: str = ""):
    """Perform simple optimizations like constant folding."""
    optimized = []
    for op, operands, line_num in instructions:
        # Constant folding for arithmetic
        if op in {"ADD", "SUB", "MUL", "DIV", "MOD"} and len(operands) >= 2:
            # Fast check: only try numeric folding if operands look numeric
            # Check first character or if it starts with - (negative number)
            if all(x and (x[0].isdigit() or (x[0] == '-' and len(x) > 1 and x[1].isdigit()) or x[0] == '.')
                   for x in operands[:-1]):
                try:
                    nums = [float(x) for x in operands[:-1]]
                    result = None
                    if op == "ADD": result = nums[0] + nums[1]
                    elif op == "SUB": result = nums[0] - nums[1]
                    elif op == "MUL": result = nums[0] * nums[1]
                    elif op == "DIV":
                        if nums[1] == 0:
                            raise CompilerError(
                                f"Division by zero in constant expression",
                                error_code=ErrorCode.DIVISION_BY_ZERO,
                                file_path=z_file,
                                line_num=line_num
                            )
                        result = nums[0] / nums[1]
                    elif op == "MOD":
                        if nums[1] == 0:
                            raise CompilerError(
                                f"Modulo by zero in constant expression",
                                error_code=ErrorCode.DIVISION_BY_ZERO,
                                file_path=z_file,
                                line_num=line_num
                            )
                        result = nums[0] % nums[1]
                    if result is not None and len(operands) == 3:
                        optimized.append(("MOV", [str(result), operands[2]], line_num))
                        continue
                except (ValueError, IndexError):
                    pass
        optimized.append((op, operands, line_num))
    return optimized
