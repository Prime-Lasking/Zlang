"""Optimization stage for ZLang with advanced optimizations."""
from typing import List, Tuple, Dict, Set, Optional, Union
from errors import CompilerError, ErrorCode

def is_numeric_operand(x: str) -> bool:
    """Check if an operand is a numeric constant."""
    if not x:
        return False
    try:
        float(x)
        return True
    except ValueError:
        return x[0] == '-' and len(x) > 1 and is_numeric_operand(x[1:])

def fold_constant_expression(op: str, operands: List[str], line_num: int, z_file: str) -> Optional[Union[float, int]]:
    """Attempt to fold a constant expression."""
    try:
        if not all(is_numeric_operand(x) for x in operands[:-1]):
            return None
            
        nums = [float(x) for x in operands[:-1]]
        
        if op == "ADD":
            return nums[0] + nums[1]
        elif op == "SUB":
            return nums[0] - nums[1]
        elif op == "MUL":
            return nums[0] * nums[1]
        elif op == "DIV":
            if nums[1] == 0:
                raise CompilerError(
                    "Division by zero in constant expression",
                    error_code=ErrorCode.DIVISION_BY_ZERO,
                    file_path=z_file,
                    line_num=line_num
                )
            return nums[0] / nums[1]
        elif op == "MOD":
            if nums[1] == 0:
                raise CompilerError(
                    "Modulo by zero in constant expression",
                    error_code=ErrorCode.DIVISION_BY_ZERO,
                    file_path=z_file,
                    line_num=line_num
                )
            return nums[0] % nums[1]
    except (ValueError, IndexError, TypeError):
        pass
    return None

def constant_propagation(instructions: List[Tuple[str, list, int]], z_file: str) -> List[Tuple[str, list, int]]:
    """Perform constant propagation optimization."""
    constants = {}
    optimized = []
    
    for op, operands, line_num in instructions:
        # Replace operands with known constants
        new_operands = [constants.get(op, op) for op in operands]
        
        # Update constants with new assignments
        if op == "MOV" and len(new_operands) == 2 and is_numeric_operand(new_operands[0]):
            constants[new_operands[1]] = new_operands[0]
        
        # Check for operations that might invalidate constants
        if op in {"STORE", "CALL", "RET"} and operands and operands[0] in constants:
            del constants[operands[0]]
            
        optimized.append((op, new_operands, line_num))
    
    return optimized

def dead_code_elimination(instructions: List[Tuple[str, list, int]]) -> List[Tuple[str, list, int]]:
    """Remove dead code and unused assignments."""
    used_vars = set()
    # First pass: Find all used variables
    for op, operands, _ in reversed(instructions):
        if op == "MOV" and len(operands) == 2 and operands[1] not in used_vars:
            continue  # This is a dead store
        used_vars.update(op for op in operands if not is_numeric_operand(op))
    
    # Second pass: Keep only instructions that contribute to used variables
    optimized = []
    for op, operands, line_num in instructions:
        if op == "MOV" and len(operands) == 2 and operands[1] not in used_vars:
            continue  # Skip dead stores
        optimized.append((op, operands, line_num))
    
    return optimized

def strength_reduction(instructions: List[Tuple[str, list, int]]) -> List[Tuple[str, list, int]]:
    """Replace expensive operations with cheaper alternatives."""
    optimized = []
    
    for i, (op, operands, line_num) in enumerate(instructions):
        # Replace x * 2 with x + x
        if op == "MUL" and len(operands) == 3 and operands[0] == '2':
            optimized.append(("ADD", [operands[1], operands[1], operands[2]], line_num))
        # Replace x * 1 with x
        elif op == "MUL" and len(operands) == 3 and operands[0] == '1':
            optimized.append(("MOV", [operands[1], operands[2]], line_num))
        # Replace x + 0 with x
        elif op == "ADD" and len(operands) == 3 and operands[0] == '0':
            optimized.append(("MOV", [operands[1], operands[2]], line_num))
        else:
            optimized.append((op, operands, line_num))
    
    return optimized

def optimize_instructions(instructions: List[Tuple[str, list, int]], z_file: str = "") -> List[Tuple[str, list, int]]:
    """
    Perform multiple optimization passes on the instruction stream.
    
    Args:
        instructions: List of (operation, operands, line_number) tuples
        z_file: Source file path for error reporting
        
    Returns:
        Optimized list of instructions
    """
    if not instructions:
        return []
        
    # Apply optimization passes
    optimized = instructions
    
    # Multiple passes for better optimization
    for _ in range(3):  # Run multiple passes for better optimization
        optimized = constant_propagation(optimized, z_file)
        optimized = dead_code_elimination(optimized)
        optimized = strength_reduction(optimized)
        
        # Constant folding pass
        new_optimized = []
        for op, operands, line_num in optimized:
            # Constant folding for arithmetic operations
            if op in {"ADD", "SUB", "MUL", "DIV", "MOD"} and len(operands) >= 2:
                result = fold_constant_expression(op, operands, line_num, z_file)
                if result is not None and len(operands) == 3:
                    new_optimized.append(("MOV", [str(result), operands[2]], line_num))
                    continue
            new_optimized.append((op, operands, line_num))
        
        # Stop if no more optimizations can be made
        if len(new_optimized) == len(optimized) and all(
            a == b for a, b in zip(optimized, new_optimized)
        ):
            break
            
        optimized = new_optimized
    
    return optimized
