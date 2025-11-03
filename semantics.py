"""Semantic checks for ZLang, including const enforcement, type checking, and semantic validation."""
from typing import Dict, Tuple, Optional, List, Set, Any
from errors import CompilerError, ErrorCode

# Supported primitive types
types_set = {"int", "float", "double", "string", "bool"}
# Array types
array_types = {"Aint", "Afloat", "Adouble", "Abool", "Astring"}
# All valid types
all_types = types_set.union(array_types)

# Mapping of array types to their element types
array_type_map = {
    "Aint": "int",
    "Afloat": "float",
    "Adouble": "double",
    "Abool": "bool",
    "Astring": "string"
}

class SemanticAnalyzer:
    """Performs semantic analysis on ZLang code."""
    
    def __init__(self, 
                instructions: List[Tuple[str, list, int]],
                declarations: Dict[Tuple[Optional[str], str], Dict[str, Any]],
                z_file: str) -> None:
        self.instructions = instructions
        self.declarations = declarations
        self.z_file = z_file
        self.current_function: Optional[str] = None
        self.func_depth: int = 0
        self.loop_depth: int = 0
        self.return_type: Optional[str] = None
        self.in_loop: bool = False
        
    def analyze(self) -> None:
        """Run the semantic analysis on all instructions."""
        for op, operands, line_num in self.instructions:
            self._process_instruction(op, operands, line_num)
    
    def _process_instruction(self, op: str, operands: List[str], line_num: int) -> None:
        """Process a single instruction with semantic checks."""
        # Handle control flow first
        if op == "FNDEF":
            self._handle_fndef(operands, line_num)
            return
        elif op == "INDENT":
            self.func_depth += 1 if self.current_function is not None else 0
            return
        elif op == "DEDENT":
            self.func_depth = max(0, self.func_depth - 1)
            if self.func_depth == 0:
                self.current_function = None
                self.return_type = None
            return
        elif op in {"FOR", "WHILE"}:
            self._handle_loop_start(op, operands, line_num)
            return
        elif op == "END_LOOP":
            self._handle_loop_end()
            return
        
        # Process other instructions
        handler_name = f"_handle_{op.lower()}"
        if hasattr(self, handler_name):
            getattr(self, handler_name)(operands, line_num)
        
        # Check for returns at the end of functions
        if op == "RET" and self.return_type and self.return_type != "void":
            self._check_return_type(operands, line_num)
    
    def _get_decl(self, name: str, scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get variable/function declaration from the current or global scope."""
        scope = scope or self.current_function
        return self.declarations.get((scope, name)) or self.declarations.get((None, name))
    
    def _is_const(self, name: str, scope: Optional[str] = None) -> bool:
        """Check if a variable is declared as const."""
        decl = self._get_decl(name, scope)
        return bool(decl and decl.get("const", False))
    
    def _get_type(self, name: str, scope: Optional[str] = None) -> Optional[str]:
        """Get the type of a variable or function return type."""
        # Handle array access like arr[1]
        if '[' in name and ']' in name:
            array_name = name.split('[')[0]
            decl = self._get_decl(array_name, scope)
            if not decl:
                return None
            array_type = decl.get("type")
            if array_type in array_type_map:
                return array_type_map[array_type]
            return None
            
        decl = self._get_decl(name, scope)
        return decl.get("type") if decl else None
    
    def _check_variable_exists(self, name: str, line_num: int) -> None:
        """Check if a variable exists in the current or global scope."""
        # Handle array access like arr[1]
        if '[' in name and ']' in name:
            array_name = name.split('[')[0]
            if not self._get_decl(array_name):
                self._error(f"Array '{array_name}' not declared", line_num, ErrorCode.UNDEFINED_SYMBOL)
            return
            
        if not self._get_decl(name):
            self._error(f"Variable '{name}' not declared", line_num, ErrorCode.UNDEFINED_SYMBOL)
    
    def _check_const_assignment(self, name: str, line_num: int) -> None:
        """Check if we can assign to a variable (not const)."""
        if self._is_const(name):
            self._error(f"Cannot assign to const variable '{name}'", line_num, ErrorCode.INVALID_OPERATION)
    
    def _check_type_compatibility(self, var_name: str, value_type: str, line_num: int) -> None:
        """Check if value_type is compatible with the variable's declared type."""
        var_type = self._get_type(var_name)
        if not var_type:
            return
            
        # Handle array types
        if var_type in array_types:
            if value_type not in array_types and value_type != 'null':
                self._error(
                    f"Cannot assign {value_type} to array type {var_type}", 
                    line_num, 
                    ErrorCode.TYPE_MISMATCH
                )
            return
            
        # Handle basic type compatibility
        if var_type != value_type and value_type != 'null':
            self._error(
                f"Type mismatch: cannot assign {value_type} to {var_type} variable '{var_name}'",
                line_num,
                ErrorCode.TYPE_MISMATCH
            )
    
    def _error(self, message: str, line_num: int, error_code: ErrorCode) -> None:
        """Raise a semantic error."""
        raise CompilerError(message, line_num, error_code, self.z_file)
    
    def _handle_fndef(self, operands: List[str], line_num: int) -> None:
        """Handle function definition."""
        if not operands:
            return
            
        # Extract function name, parameters, and return type
        func_name = operands[0]
        self.current_function = func_name
        self.func_depth = 0
        
        # Find return type if specified
        if '->' in ' '.join(operands):
            ret_type_idx = operands.index('->') + 1
            if ret_type_idx < len(operands):
                self.return_type = operands[ret_type_idx]
            else:
                self.return_type = None
    
    def _handle_loop_start(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle the start of a loop (FOR/WHILE)."""
        self.in_loop = True
        if op == "FOR":
            # FOR var start..end
            if len(operands) >= 3 and operands[1] == "..":
                var_name = operands[0]
                self._check_variable_exists(var_name, line_num)
                self._check_const_assignment(var_name, line_num)
    
    def _handle_loop_end(self) -> None:
        """Handle the end of a loop."""
        self.in_loop = False
    
    def _handle_mov(self, operands: List[str], line_num: int) -> None:
        """Handle MOV instruction (variable declaration/assignment)."""
        if len(operands) < 2:
            return
            
        dest = operands[0]
        
        # Variable declaration: MOV type var [value]
        if operands[0] in types_set:
            if len(operands) < 2:
                self._error("Missing variable name in declaration", line_num, ErrorCode.SYNTAX_ERROR)
            var_name = operands[1]
            # Type checking for the initializer if present
            if len(operands) > 2:
                value = operands[2]
                self._check_value_type(value, operands[0], line_num)
        # Assignment: MOV dest value
        else:
            self._check_variable_exists(dest, line_num)
            self._check_const_assignment(dest, line_num)
            
            # Type checking for the assigned value
            value_type = self._infer_type(operands[1])
            if value_type:
                self._check_type_compatibility(dest, value_type, line_num)
    
    def _handle_arithmetic(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle arithmetic operations (ADD, SUB, MUL, DIV, MOD)."""
        if len(operands) != 3:
            self._error(f"{op} requires exactly 3 operands", line_num, ErrorCode.SYNTAX_ERROR)
            
        dest = operands[2]
        self._check_variable_exists(dest, line_num)
        self._check_const_assignment(dest, line_num)
        
        # Check operand types
        for i in range(2):
            op_type = self._infer_type(operands[i])
            if op_type and op_type not in {"int", "float", "double"}:
                self._error(
                    f"{op} operation requires numeric operands, got {op_type}",
                    line_num,
                    ErrorCode.TYPE_MISMATCH
                )
        
        # Check destination type
        dest_type = self._get_type(dest)
        if dest_type and dest_type not in {"int", "float", "double"}:
            self._error(
                f"{op} destination must be a numeric type, got {dest_type}",
                line_num,
                ErrorCode.TYPE_MISMATCH
            )
    
    def _handle_inc_dec(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle increment/decrement operations (INC, DEC)."""
        if not operands:
            self._error(f"{op} requires a variable name", line_num, ErrorCode.SYNTAX_ERROR)
            
        var_name = operands[0]
        self._check_variable_exists(var_name, line_num)
        self._check_const_assignment(var_name, line_num)
        
        var_type = self._get_type(var_name)
        if var_type not in {"int", "float", "double"}:
            self._error(
                f"{op} operation requires a numeric variable, got {var_type}",
                line_num,
                ErrorCode.TYPE_MISMATCH
            )
    
    def _handle_call(self, operands: List[str], line_num: int) -> None:
        """Handle function calls."""
        if not operands:
            return
            
        func_name = operands[0]
        
        # Check if function exists
        func_decl = self._get_decl(func_name, None)  # Functions are always in global scope
        if not func_decl or func_decl.get("kind") != "function":
            self._error(f"Function '{func_name}' not declared", line_num, ErrorCode.UNDEFINED_SYMBOL)
            return
            
        # Check return value assignment if present
        if len(operands) > 1 and '->' in operands:
            arrow_idx = operands.index('->')
            if arrow_idx < len(operands) - 1:
                ret_var = operands[arrow_idx + 1]
                self._check_variable_exists(ret_var, line_num)
                self._check_const_assignment(ret_var, line_num)
                
                # Check return type compatibility
                ret_type = func_decl.get("return_type")
                if ret_type and ret_type != "void":
                    var_type = self._get_type(ret_var)
                    if var_type and var_type != ret_type:
                        self._error(
                            f"Cannot assign {ret_type} return value to {var_type} variable '{ret_var}'",
                            line_num,
                            ErrorCode.TYPE_MISMATCH
                        )
    
    def _handle_ret(self, operands: List[str], line_num: int) -> None:
        """Handle return statements."""
        if not self.return_type or self.return_type == "void":
            if operands and operands[0] != "0":
                self._error("Void function should not return a value", line_num, ErrorCode.TYPE_MISMATCH)
        elif self.return_type:
            if not operands:
                self._error("Function must return a value", line_num, ErrorCode.TYPE_MISMATCH)
            else:
                value_type = self._infer_type(operands[0])
                if value_type and value_type != self.return_type:
                    self._error(
                        f"Expected return type {self.return_type}, got {value_type}",
                        line_num,
                        ErrorCode.TYPE_MISMATCH
                    )
    
    def _handle_arr(self, operands: List[str], line_num: int) -> None:
        """Handle array declarations and operations."""
        if len(operands) < 2:
            self._error("Invalid array operation", line_num, ErrorCode.SYNTAX_ERROR)
            return
            
        # ARR <type> <name> <size> [initializer] or ARR <type> <name> [initializer]
        if operands[0] not in array_types:
            self._error(f"Invalid array type: {operands[0]}", line_num, ErrorCode.INVALID_TYPE)
            return
            
        array_type = operands[0]
        array_name = operands[1]
        
        # Check if array is already declared
        if self._get_decl(array_name):
            self._error(f"Variable '{array_name}' already declared", line_num, ErrorCode.DUPLICATE_DECLARATION)
            return
            
        # Add the array to declarations
        self.declarations[(self.current_function, array_name)] = {
            'type': array_type,
            'mutable': True,
            'line': line_num
        }
        
        # Handle array initializer if present
        if len(operands) >= 3:
            initializer = operands[2]
            if initializer.startswith('[') and initializer.endswith(']'):
                # Simple check for array literals
                pass
    
    def _handle_push_pop(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle PUSH and POP operations on arrays."""
        if len(operands) < 1:
            self._error(f"{op} requires an array name", line_num, ErrorCode.SYNTAX_ERROR)
            return
            
        array_name = operands[0]
        self._check_variable_exists(array_name, line_num)
        
        array_type = self._get_type(array_name)
        if array_type not in array_types:
            self._error(f"{op} operation requires an array, got {array_type}", 
                       line_num, ErrorCode.TYPE_MISMATCH)
            return
            
        if op == "PUSH" and len(operands) >= 2:
            # Check if value type matches array element type
            value_type = self._infer_type(operands[1])
            elem_type = array_type_map.get(array_type)
            if value_type and value_type != elem_type:
                self._error(
                    f"Cannot push {value_type} to array of type {array_type}",
                    line_num,
                    ErrorCode.TYPE_MISMATCH
                )
        elif op == "POP" and len(operands) >= 2:
            # Check if destination type matches array element type
            dest = operands[1]
            self._check_variable_exists(dest, line_num)
            self._check_const_assignment(dest, line_num)
            
            dest_type = self._get_type(dest)
            elem_type = array_type_map.get(array_type)
            if dest_type and dest_type != elem_type:
                self._error(
                    f"Cannot pop {elem_type} to {dest_type} variable",
                    line_num,
                    ErrorCode.TYPE_MISMATCH
                )
    
    def _handle_len(self, operands: List[str], line_num: int) -> None:
        """Handle LEN operation (get array length)."""
        if len(operands) != 2:
            self._error("LEN requires an array and a destination variable", 
                       line_num, ErrorCode.SYNTAX_ERROR)
            return
            
        array_name = operands[0]
        dest_var = operands[1]
        
        self._check_variable_exists(array_name, line_num)
        self._check_variable_exists(dest_var, line_num)
        self._check_const_assignment(dest_var, line_num)
        
        array_type = self._get_type(array_name)
        if array_type not in array_types:
            self._error(f"LEN operation requires an array, got {array_type}", 
                       line_num, ErrorCode.TYPE_MISMATCH)
    
    def _handle_print(self, operands: List[str], line_num: int) -> None:
        """Handle PRINT and PRINTSTR operations."""
        if not operands:
            self._error("PRINT requires at least one argument", line_num, ErrorCode.SYNTAX_ERROR)
            return
            
        # For PRINT, we just validate the variable exists
        for var in operands:
            if not self._is_literal(var):
                self._check_variable_exists(var, line_num)
    
    def _handle_if_elif_else(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle IF, ELIF, and ELSE statements."""
        if op in {"IF", "ELIF"} and not operands:
            self._error(f"{op} requires a condition", line_num, ErrorCode.SYNTAX_ERROR)
            return
            
        # For IF/ELIF, check that the condition is a boolean expression
        if op in {"IF", "ELIF"}:
            # Simple check - in a real compiler, we'd parse the expression
            # Here we just check if it's a boolean variable or a comparison
            cond = ' '.join(operands)
            if not any(op in cond for op in {'==', '!=', '<', '>', '<=', '>=', '&&', '||', '!'}):
                # Might be a boolean variable
                self._check_variable_exists(operands[0], line_num)
                var_type = self._get_type(operands[0])
                if var_type and var_type != "bool":
                    self._error(
                        f"Condition must be a boolean expression, got {var_type}",
                        line_num,
                        ErrorCode.TYPE_MISMATCH
                    )
    
    # Helper methods for type inference and checking
    
    def _infer_type(self, value: str) -> Optional[str]:
        """Infer the type of a value (literal or variable)."""
        if value in {"true", "false"}:
            return "bool"
        elif value.isdigit():
            return "int"
        elif value.replace('.', '', 1).isdigit():
            return "float"  # Could be float or double, default to float
        elif value.startswith('"') and value.endswith('"'):
            return "string"
        elif value in self.declarations:
            return self._get_type(value)
        return None
    
    def _check_value_type(self, value: str, expected_type: str, line_num: int) -> None:
        """Check if a value matches the expected type."""
        value_type = self._infer_type(value)
        if value_type and value_type != expected_type:
            self._error(
                f"Expected {expected_type}, got {value_type}",
                line_num,
                ErrorCode.TYPE_MISMATCH
            )
    
    def _is_literal(self, value: str) -> bool:
        """Check if a value is a literal (not a variable)."""
        return (value in {"true", "false"} or
                value.isdigit() or
                value.replace('.', '', 1).isdigit() or
                (value.startswith('"') and value.endswith('"')))

# Map opcodes to handler methods
HANDLERS = {
    # Variable operations
    "MOV": "_handle_mov",
    
    # Arithmetic operations
    "ADD": "_handle_arithmetic",
    "SUB": "_handle_arithmetic",
    "MUL": "_handle_arithmetic",
    "DIV": "_handle_arithmetic",
    "MOD": "_handle_arithmetic",
    "INC": "_handle_inc_dec",
    "DEC": "_handle_inc_dec",
    
    # Control flow
    "IF": "_handle_if_elif_else",
    "ELIF": "_handle_if_elif_else",
    "ELSE": "_handle_if_elif_else",
    "FOR": "_handle_loop_start",
    "WHILE": "_handle_loop_start",
    "END_LOOP": "_handle_loop_end",
    
    # Function calls
    "CALL": "_handle_call",
    "RET": "_handle_ret",
    
    # I/O
    "PRINT": "_handle_print",
    "PRINTSTR": "_handle_print",
    "READ": "_handle_read",
    
    # Arrays
    "ARR": "_handle_arr",
    "PUSH": "_handle_push_pop",
    "POP": "_handle_push_pop",
    "LEN": "_handle_len",
    
    # Error handling
    "ERROR": "_handle_error"
}

# Add handler methods for each opcode
for op, handler_name in HANDLERS.items():
    if not hasattr(SemanticAnalyzer, handler_name):
        setattr(SemanticAnalyzer, f"_handle_{op.lower()}", 
                lambda self, o, ln, op=op, h=handler_name: 
                    getattr(self, h)(op, o, ln) if h.startswith('_handle_') 
                    else getattr(self, h)(o, ln))

def validate_const_and_types(instructions: List[Tuple[str, list, int]],
                          declarations: Dict[Tuple[Optional[str], str], Dict[str, Any]],
                          z_file: str) -> None:
    """
    Main entry point for semantic analysis.
    
    Args:
        instructions: List of (opcode, operands, line_number) tuples
        declarations: Dictionary of variable/function declarations
        z_file: Path to the source file (for error reporting)
    """
    analyzer = SemanticAnalyzer(instructions, declarations, z_file)
    analyzer.analyze()
