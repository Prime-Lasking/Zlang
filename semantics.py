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
        
        # Process other instructions using the HANDLERS dictionary
        if op in HANDLERS:
            handler_name = HANDLERS[op]
            if hasattr(self, handler_name):
                # Special handling for operations that need the op name
                if op in ["ADD", "SUB", "MUL", "DIV", "MOD", "INC", "DEC", 
                         "PTR", "PTR_GET", "PTR_SET", "IF", "ELIF", "ELSE", 
                         "FOR", "WHILE", "PUSH", "POP"]:
                    getattr(self, handler_name)(op, operands, line_num)
                else:
                    getattr(self, handler_name)(operands, line_num)
        else:
            # Fallback to the old handler naming convention for backward compatibility
            handler_name = f"_handle_{op.lower()}"
            if hasattr(self, handler_name):
                # Check if the handler expects the op name as first argument
                handler = getattr(self, handler_name)
                if handler.__code__.co_argcount == 4:  # self + 3 args
                    handler(op, operands, line_num)
                else:
                    handler(operands, line_num)
        
        # Check for returns at the end of functions
        if op == "RET" and self.return_type and self.return_type != "void":
            self._check_return_type(operands, line_num)
    
    def _get_decl(self, name: str, scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get variable/function declaration from the current or global scope."""
        # If name is a list, use the first element (for handling return values)
        if isinstance(name, list):
            if not name:  # Empty list
                return None
            name = name[0]  # Use the first element
            
        scope = scope or self.current_function
        
        # First try with the current scope
        if scope:
            # Try with a string key first
            key = f"{scope}_{name}" if scope else name
            if key in self.declarations:
                return self.declarations[key]
                
            # Then try with a tuple key for backward compatibility
            tuple_key = (scope, name)
            if tuple_key in self.declarations:
                return self.declarations[tuple_key]
        
        # Then try with global scope
        if scope is not None:  # Only if we haven't already tried None scope
            # Try with a string key
            if name in self.declarations:
                return self.declarations[name]
                
            # Then try with a tuple key for backward compatibility
            global_key = (None, name)
            if global_key in self.declarations:
                return self.declarations[global_key]
        
        # If we get here, the variable wasn't found
        return None
    
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
            
        decl = self._get_decl(name)
        if not decl:
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
        """Handle function definition.
        
        The lexer provides operands in the format:
        ['func_name', 'param1_type', 'param1_name', 'param2_type', 'param2_name', ..., 'return_type']
        """
        print(f"DEBUG - _handle_fndef operands: {operands}")  # Debug print
        if not operands:
            return
            
        # The first operand is the function name
        func_name = operands[0]
        
        # Create a simple string key for the function
        func_key = f"func_{func_name}"
        
        # Check for duplicate function declaration
        for key in self.declarations:
            if isinstance(key, tuple) and len(key) == 2 and key[1] == func_key:
                self._error(
                    f"Duplicate function declaration: '{func_name}'",
                    line_num,
                    ErrorCode.DUPLICATE_DECLARATION
                )
                return
        
        # Parse parameters (pairs of type and name)
        params = []
        i = 1  # Start after function name
        
        # Look for parameters (pairs of type and name)
        while i + 1 < len(operands):
            param_type = operands[i]
            param_name = operands[i + 1]
            
            # Check if we've reached the return type
            if param_type == '->':
                i += 1  # Skip the '->'
                break
                
            if param_type not in types_set:
                self._error(
                    f"Invalid parameter type: '{param_type}'",
                    line_num,
                    ErrorCode.INVALID_TYPE
                )
                
            params.append((param_name, param_type))
            i += 2  # Move to next parameter pair
        
        # The remaining operand is the return type (default to 'void' if not specified)
        return_type = operands[-1] if i < len(operands) else 'void'
        
        # Validate return type
        if return_type not in types_set and return_type != 'void':
            self._error(
                f"Invalid return type: '{return_type}'",
                line_num,
                ErrorCode.INVALID_TYPE
            )
            return_type = 'void'  # Default to void on error
        
        # Initialize function context
        self.current_function = func_name
        self.func_depth = 0
        
        # Store function declaration with both simple and tuple keys for backward compatibility
        func_decl = {
            'kind': 'function',
            'name': func_name,
            'params': params,
            'return_type': return_type,
            'line': line_num
        }
        
        # Store with simple string key
        self.declarations[func_key] = func_decl
        
        # Also store with tuple key for backward compatibility
        tuple_key = (None, func_name)
        self.declarations[tuple_key] = func_decl
        
        # Add parameters to the declarations with function scope
        for param_name, param_type in params:
            param_key = f"{func_name}_{param_name}"
            param_decl = {
                'kind': 'parameter',
                'name': param_name,
                'type': param_type,
                'function': func_name,
                'line': line_num
            }
            self.declarations[param_key] = param_decl
            
            # Also store with tuple key for backward compatibility
            param_tuple_key = (func_name, param_name)
            self.declarations[param_tuple_key] = param_decl
        
        # Set current return type for return statement validation
        self.return_type = return_type
    
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
    
    def _handle_pointer_operations(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle pointer operations (PTR, PTR_GET, PTR_SET)."""
        if op == "PTR":
            # PTR <type> <ptr_name> <target_var>
            if len(operands) != 3:
                self._error("PTR operation requires 3 operands: type, pointer_name, target_variable",
                          line_num, ErrorCode.SYNTAX_ERROR)
                return
                
            type_name, ptr_name, target_var = operands
            
            # Check if type is valid
            if type_name not in types_set:
                self._error(f"Invalid type '{type_name}' for pointer", line_num, ErrorCode.INVALID_TYPE)
                return
                
            # Check if target variable exists
            self._check_variable_exists(target_var, line_num)
            
            # Add pointer to declarations with type "<type>*"
            scope = self.current_function
            self.declarations[(scope, ptr_name)] = {
                'mutable': True,
                'type': f"{type_name}*",
                'line': line_num
            }
    
    def _handle_arithmetic(self, op: str, operands: List[str], line_num: int) -> None:
        """Handle arithmetic operations (ADD, SUB, MUL, DIV, MOD)."""
        if len(operands) != 3:
            self._error(f"{op} requires exactly 3 operands", line_num, ErrorCode.SYNTAX_ERROR)
            
        dest = operands[2]
        
        # Handle pointer dereferencing in destination
        if dest.startswith('*'):
            ptr_name = dest[1:]
            self._check_variable_exists(ptr_name, line_num)
            # Check if it's actually a pointer
            decl = self._get_decl(ptr_name)
            if not decl or not decl['type'].endswith('*'):
                self._error(f"Cannot dereference non-pointer variable '{ptr_name}'", 
                          line_num, ErrorCode.TYPE_MISMATCH)
            # Get the base type (without the pointer)
            dest_type = decl['type'].rstrip('*')
        else:
            self._check_variable_exists(dest, line_num)
            self._check_const_assignment(dest, line_num)
            dest_type = self._get_type(dest)
        
        # Check if destination type is numeric
        if dest_type not in {"int", "float", "double"}:
            self._error(
                f"{op} destination must be a numeric type, got {dest_type}",
                line_num,
                ErrorCode.TYPE_MISMATCH
            )
            
        # Check operand types
        for i in range(2):
            # Handle pointer dereferencing in operands
            if operands[i].startswith('*'):
                ptr_name = operands[i][1:]
                self._check_variable_exists(ptr_name, line_num)
                # Check if it's actually a pointer
                decl = self._get_decl(ptr_name)
                if not decl or not decl['type'].endswith('*'):
                    self._error(f"Cannot dereference non-pointer variable '{ptr_name}'", 
                              line_num, ErrorCode.TYPE_MISMATCH)
                op_type = decl['type'].rstrip('*')
            else:
                op_type = self._infer_type(operands[i])
                
            if op_type and op_type not in {"int", "float", "double"}:
                self._error(
                    f"{op} operation requires numeric operands, got {op_type}",
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
        """Handle function calls.
        
        Format: CALL <func_name> [arg1 arg2 ...] [-> return_var]
        """
        print(f"DEBUG - _handle_call operands: {operands}")  # Debug print
        
        if not operands:
            self._error("Function name expected after CALL", line_num, ErrorCode.SYNTAX_ERROR)
            return
            
        # Extract function name and arguments
        func_name = operands[0]
        args = []
        return_var = None
        
        # Check for return value assignment (-> return_var)
        if '->' in operands:
            arrow_idx = operands.index('->')
            if arrow_idx < len(operands) - 1:
                return_var = operands[arrow_idx + 1]
            # Arguments are everything between function name and ->
            args = operands[1:arrow_idx]
        else:
            # Check if the last operand is the return variable without ->
            # This handles the case: CALL fibonacci(count) result
            if len(operands) > 2 and '->' not in operands:
                return_var = operands[-1]
                args = operands[1:-1]  # Everything between function name and return_var
            else:
                # All operands after function name are arguments
                args = operands[1:]
        
        print(f"DEBUG - After initial parsing - func_name: {func_name}, args: {args}, return_var: {return_var}")
            
        # Handle function calls with parentheses like 'fibonacci(count)'
        if len(args) == 1 and args[0].startswith('(') and args[0].endswith(')'):
            # Extract the argument from inside the parentheses
            arg_str = args[0][1:-1]  # Remove the parentheses
            args = [arg_str] if arg_str else []
            print(f"DEBUG - After handling parentheses - args: {args}")
        elif len(args) == 1 and args[0].endswith(')'):
            # Handle case like 'fibonacci(count' (missing closing parenthesis)
            self._error("Missing opening parenthesis in function call", line_num, ErrorCode.SYNTAX_ERROR)
        elif len(args) == 1 and args[0].startswith('('):
            # Handle case like 'fibonacci(count' (missing closing parenthesis)
            self._error("Missing closing parenthesis in function call", line_num, ErrorCode.SYNTAX_ERROR)
        
        # Check if function exists
        func_decl = self._get_decl(func_name, None)  # Functions are always in global scope
        if not func_decl or func_decl.get("kind") != "function":
            self._error(
                f"Function '{func_name}' not declared", 
                line_num, 
                ErrorCode.UNDEFINED_SYMBOL
            )
            return
            
        # Get function signature
        expected_params = func_decl.get("params", [])
        return_type = func_decl.get("return_type", "void")
        
        # Check argument count
        if len(args) != len(expected_params):
            self._error(
                f"Function '{func_name}' expects {len(expected_params)} arguments, got {len(args)}",
                line_num,
                ErrorCode.INVALID_OPERAND
            )
            return
            
        # Check argument types
        for i, (arg, (param_name, param_type)) in enumerate(zip(args, expected_params), 1):
            arg_type = self._infer_type(arg)
            
            # If type couldn't be inferred, check if it's a variable
            if not arg_type and not self._is_literal(arg):
                self._check_variable_exists(arg, line_num)
                arg_type = self._get_type(arg)
            
            if arg_type and arg_type != param_type:
                self._error(
                    f"Argument {i} to '{func_name}': expected {param_type}, got {arg_type}",
                    line_num,
                    ErrorCode.TYPE_MISMATCH
                )
        
        # Handle return value assignment if present
        if return_var is not None:
            if return_type == "void":
                self._error(
                    f"Cannot capture return value from void function '{func_name}'",
                    line_num,
                    ErrorCode.TYPE_MISMATCH
                )
                return
                
            self._check_variable_exists(return_var, line_num)
            self._check_const_assignment(return_var, line_num)
            
            # Check return type compatibility
            var_type = self._get_type(return_var)
            if var_type and var_type != return_type:
                self._error(
                    f"Cannot assign {return_type} return value to {var_type} variable '{return_var}'",
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
            
        # For PRINT, validate the variable exists
        for var in operands:
            # Check for pointer dereference (e.g., *ptr)
            if var.startswith('*'):
                ptr_name = var[1:]
                # Check if the pointer exists
                self._check_variable_exists(ptr_name, line_num)
                # Check if it's actually a pointer
                decl = self._get_decl(ptr_name)
                if decl and not decl['type'].endswith('*'):
                    self._error(f"Cannot dereference non-pointer variable '{ptr_name}'", 
                              line_num, ErrorCode.TYPE_MISMATCH)
            # Regular variable
            elif not self._is_literal(var):
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
    
    def _infer_type(self, value) -> Optional[str]:
        """Infer the type of a value (literal or variable).
        
        Args:
            value: Can be a string or a list of strings (for expressions)
        """
        # If value is a list, try to infer type from its elements
        if isinstance(value, list):
            if not value:  # Empty list
                return None
            # For non-empty lists, try to infer type from the first element
            return self._infer_type(value[0])
            
        # Handle string values
        if not isinstance(value, str):
            return None
            
        if value in {"true", "false"}:
            return "bool"
        elif value.isdigit():
            return "int"
        elif value.replace('.', '', 1).isdigit():
            return "float"  # Could be float or double, default to float
        elif value.startswith('"') and value.endswith('"'):
            return "string"
            
        # Check if it's a variable
        decl = self._get_decl(value)
        if decl:
            return decl.get('type')
            
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
    
    def _is_literal(self, value) -> bool:
        """Check if a value is a literal (number, string, etc.).
        
        Args:
            value: Can be a string or a list of strings
        """
        # If it's a list, check if all elements are literals
        if isinstance(value, list):
            return all(self._is_literal(v) for v in value)
            
        # Handle string values
        if not isinstance(value, str):
            return False
            
        if value in {"true", "false"}:
            return True
        try:
            float(value)  # Number literal
            return True
        except ValueError:
            return value.startswith('"') and value.endswith('"')  # String literal
            
    def _check_return_type(self, value, line_num: int) -> None:
        """Check if the return value type matches the function's return type.
        
        Args:
            value: Can be a string or a list of strings (for multiple return values)
            line_num: Line number for error reporting
        """
        if not self.return_type or self.return_type == "void":
            if value and value != ["0"]:  # Only allow empty return in void functions
                self._error("Void function should not return a value", line_num, ErrorCode.TYPE_MISMATCH)
            return
            
        # For non-void functions, a return value is required
        if not value or (isinstance(value, list) and not value):
            self._error("Function must return a value", line_num, ErrorCode.TYPE_MISMATCH)
            return
            
        # If value is a list, use the first element
        if isinstance(value, list):
            value = value[0] if value else ""
            
        # Get the type of the returned value
        value_type = self._infer_type(value)
        
        # If type couldn't be inferred, check if it's a variable
        if not value_type and not self._is_literal(value):
            # Check if it's a variable name (must be a string)
            if isinstance(value, str):
                self._check_variable_exists(value, line_num)
                value_type = self._get_type(value)
            else:
                self._error("Invalid return value", line_num, ErrorCode.SYNTAX_ERROR)
                return
            
        # Check type compatibility if we have type information
        if value_type and value_type != self.return_type:
            self._error(
                f"Expected return type {self.return_type}, got {value_type}",
                line_num,
                ErrorCode.TYPE_MISMATCH
            )

# Map opcodes to handler methods
HANDLERS = {
    # Variable operations
    "MOV": "_handle_mov",
    # Pointer operations
    "PTR": "_handle_pointer_operations",
    # Pointer operations
    "PTR": "_handle_pointer_operations",
    
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
        if handler_name in {"_handle_arithmetic", "_handle_inc_dec", "_handle_pointer_operations", 
                          "_handle_if_elif_else", "_handle_loop_start", "_handle_push_pop"}:
            # These handlers need the operation type as first argument
            def make_handler(op_name, h_name):
                def handler(self, operands, line_num):
                    return getattr(self, h_name)(op_name, operands, line_num)
                return handler
            setattr(SemanticAnalyzer, handler_name, 
                   make_handler(op, handler_name))
        else:
            # Standard handlers just take operands and line number
            def make_std_handler(h_name):
                def handler(self, operands, line_num):
                    return getattr(self, h_name)(operands, line_num)
                return handler
            setattr(SemanticAnalyzer, handler_name, 
                   make_std_handler(handler_name))

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
