"""Error handling for the Z compiler (ZLang)."""
from enum import Enum
from typing import Optional
class ErrorCode(Enum):
    """Error codes for different types of errors in the Z compiler."""
    # File and I/O related errors (1-10)
    FILE_NOT_FOUND = 1
    FILE_READ_ERROR = 2
    FILE_WRITE_ERROR = 3
    INVALID_FILE_FORMAT = 4
    IO_ERROR = 5
    
    # Syntax and parsing errors (11-20)
    SYNTAX_ERROR = 11
    UNEXPECTED_TOKEN = 12
    MISSING_TOKEN = 13
    INVALID_SYNTAX = 14
    UNKNOWN_OPCODE = 15
    INVALID_CONDITION = 16
    
    # Semantic analysis errors (21-30)
    UNDEFINED_SYMBOL = 21
    REDEFINED_SYMBOL = 22
    TYPE_MISMATCH = 23
    INVALID_OPERATION = 24
    INVALID_TYPE = 25
    INVALID_OPERAND = 26
    TYPE_ERROR = 27
    MISSING_RETURN = 28
    
    # Code generation errors (31-40)
    CODE_GEN_ERROR = 31
    COMPILER_ERROR = 32
    
    # Runtime errors (41-50)
    RUNTIME_ERROR = 41
    DIVISION_BY_ZERO = 42
    OUT_OF_BOUNDS = 43
    OVERFLOW = 45
    # System and environment errors (51-60)
    SYSTEM_ERROR = 51
    COMPILER_BUG = 52
    
    # External tool errors (61-70)
    EXTERNAL_TOOL_ERROR = 61
    COMPILATION_ERROR = 62
    COMPILATION_FAILED = 63
    NO_COMPILER = 64
    
    # Configuration errors (71-80)
    CONFIGURATION_ERROR = 71
    MISSING_DEPENDENCY = 72
    
    # Unexpected errors (90-99)
    UNEXPECTED_ERROR = 90
    NO_OUTPUT_FILE = 91
    
    # Custom error for user-defined errors
    CUSTOM_ERROR = 99

    def __str__(self):
        return f"E{self.value:02d}"

class CompilerError(Exception):
    """Custom exception for compiler errors with line tracking"""
    def __init__(self, message: str, line_num: Optional[int] = None,
                 error_code: ErrorCode = ErrorCode.SYNTAX_ERROR,
                 file_path: Optional[str] = None):
        self.message = message
        self.line_num = line_num
        self.error_code = error_code
        self.file_path = file_path
        super().__init__(self.format_error())

    def format_error(self) -> str:
        """Format error message like a real compiler."""
        if self.file_path and self.line_num:
            return f"{self.file_path}:{self.line_num}: error: [{self.error_code}] {self.message}"
        elif self.file_path:
            return f"{self.file_path}: error: [{self.error_code}] {self.message}"
        elif self.line_num:
            return f"line {self.line_num}: error: [{self.error_code}] {self.message}"
        else:
            return f"error: [{self.error_code}] {self.message}"
