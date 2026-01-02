#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXO Language v3.1 - Production Ready Edition
✅ Fixed all critical bugs
✅ Proper error handling
✅ Lexical scoping
✅ Web server support
✅ Arabic/English support
"""

import os
import sys
import json
import math
import random
import time
import socket
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path

# ==================== SCOPE MANAGEMENT ====================
class Scope:
    """Manages variable scoping with proper parent chain"""
    def __init__(self, parent=None, name="global"):
        self.parent = parent
        self.name = name
        self.vars = {}
    
    def get(self, name):
        """Get variable value from current or parent scope"""
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise KeyError(f"Variable '{name}' not defined")
    
    def set(self, name, value, local=True):
        """Set variable in current or parent scope"""
        if local or name not in self.get_all_names():
            self.vars[name] = value
        else:
            scope = self
            while scope:
                if name in scope.vars:
                    scope.vars[name] = value
                    return
                scope = scope.parent
            self.vars[name] = value
    
    def exists(self, name):
        """Check if variable exists in current or parent scope"""
        if name in self.vars:
            return True
        if self.parent:
            return self.parent.exists(name)
        return False
    
    def get_all_names(self):
        """Get all variable names in scope chain"""
        names = set(self.vars.keys())
        if self.parent:
            names.update(self.parent.get_all_names())
        return names

# ==================== GLOBAL STATE ====================
global_scope = Scope(name="global")
current_scope = global_scope
functions = {}
modules = {}
output = []
web_routes = {}
call_stack = []
MAX_RECURSION_DEPTH = 1000

# ==================== ERROR HANDLING ====================
class ExoError(Exception):
    """Enhanced error with context information"""
    def __init__(self, msg, line=None, file=None, context=None):
        self.msg = msg
        self.line = line
        self.file = file
        self.context = context
        super().__init__(self.format_error())
    
    def format_error(self):
        """Format error message with context"""
        parts = ["❌ EXO Error"]
        if self.file:
            parts.append(f"\n📁 File: {self.file}")
        if self.line:
            parts.append(f"\n📍 Line: {self.line}")
        parts.append(f"\n💬 {self.msg}")
        
        if self.context:
            parts.append(f"\n\n📝 Context:")
            parts.append(f"   {self.context}")
        
        if call_stack:
            parts.append(f"\n\n📚 Call Stack:")
            for i, frame in enumerate(reversed(call_stack[-5:])):
                parts.append(f"   {i+1}. {frame}")
        
        return "".join(parts)

def error(msg, line=None, file=None, context=None):
    """Raise EXO error"""
    raise ExoError(msg, line, file, context)

# ==================== STRING UTILITIES ====================
def parse_string(s):
    """Parse escape sequences in strings"""
    return (s.replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\\r', '\r')
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace('\\\\', '\\'))

def is_number(s):
    """Check if string represents a number"""
    try:
        float(s)
        return True
    except:
        return False

# ==================== EXPRESSION PARSING ====================
def split_by_op(expr, op):
    """Split expression by operator respecting strings and brackets"""
    parts = []
    current = ""
    depth = 0
    in_string = False
    string_char = None
    i = 0
    
    while i < len(expr):
        char = expr[i]
        
        # Handle string delimiters
        if char in ('"', "'") and (i == 0 or expr[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
            current += char
            i += 1
            continue
        
        # Skip if inside string
        if in_string:
            current += char
            i += 1
            continue
        
        # Track bracket depth
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
        
        # Split at operator if at depth 0
        if depth == 0 and expr[i:i+len(op)] == op:
            if current.strip():
                parts.append(current.strip())
            current = ""
            i += len(op)
        else:
            current += char
            i += 1
    
    if current.strip():
        parts.append(current.strip())
    
    return parts if len(parts) > 1 else [expr]

# ==================== ARITHMETIC EVALUATION ====================
def eval_arith(expr, ln=None, file=None):
    """Evaluate arithmetic and logical expressions"""
    expr = expr.strip()
    
    # Remove outer parentheses if they wrap entire expression
    while expr.startswith('(') and expr.endswith(')'):
        depth = 0
        valid = True
        for i, c in enumerate(expr):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            if depth == 0 and i < len(expr) - 1:
                valid = False
                break
        if valid:
            expr = expr[1:-1].strip()
        else:
            break
    
    # Logical OR
    for sep in [' or ', ' او ', ' || ']:
        parts = split_by_op(expr, sep)
        if len(parts) > 1:
            return any(eval_arith(p, ln, file) for p in parts)
    
    # Logical AND
    for sep in [' and ', ' و ', ' && ']:
        parts = split_by_op(expr, sep)
        if len(parts) > 1:
            return all(eval_arith(p, ln, file) for p in parts)
    
    # Logical NOT
    if expr.startswith(('not ', 'ليس ', '!')):
        if expr.startswith('not '):
            rest = expr[4:]
        elif expr.startswith('ليس '):
            rest = expr[5:]
        else:
            rest = expr[1:]
        return not eval_arith(rest.strip(), ln, file)
    
    # Comparison operators
    ops = {
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
        '>=': lambda a, b: a >= b,
        '<=': lambda a, b: a <= b,
        '>': lambda a, b: a > b,
        '<': lambda a, b: a < b
    }
    
    for op in ['==', '!=', '>=', '<=', '>', '<']:
        parts = split_by_op(expr, op)
        if len(parts) == 2:
            left = eval_arith(parts[0], ln, file)
            right = eval_arith(parts[1], ln, file)
            return ops[op](left, right)
    
    # Addition and subtraction
    for op in ['+', '-']:
        parts = split_by_op(expr, op)
        if len(parts) > 1:
            result = eval_arith(parts[0], ln, file)
            for i in range(1, len(parts)):
                val = eval_arith(parts[i], ln, file)
                result = result + val if op == '+' else result - val
            return result
    
    # Multiplication, division, modulo
    for op in ['*', '/', '%']:
        parts = split_by_op(expr, op)
        if len(parts) > 1:
            result = eval_arith(parts[0], ln, file)
            for i in range(1, len(parts)):
                val = eval_arith(parts[i], ln, file)
                if op == '*':
                    result *= val
                elif op == '/':
                    if val == 0:
                        error("Division by zero", ln, file, expr)
                    result /= val
                else:
                    result %= val
            return result
    
    # Power operator
    if '^' in expr:
        parts = split_by_op(expr, '^')
        if len(parts) > 1:
            result = eval_arith(parts[-1], ln, file)
            for i in range(len(parts) - 2, -1, -1):
                result = eval_arith(parts[i], ln, file) ** result
            return result
    
    return eval_base(expr, ln, file)

# ==================== BASE VALUE EVALUATION ====================
def eval_base(expr, ln=None, file=None):
    """Evaluate base values (literals, variables, function calls)"""
    expr = expr.strip()
    if not expr:
        return None
    
    # Boolean literals
    if expr in ("True", "صح", "true"):
        return True
    if expr in ("False", "خطأ", "false"):
        return False
    if expr in ("null", "فارغ", "None"):
        return None
    
    # String literals
    if (expr.startswith('"') and expr.endswith('"')) or \
       (expr.startswith("'") and expr.endswith("'")):
        return parse_string(expr[1:-1])
    
    # Array literals
    if expr.startswith('[') and expr.endswith(']'):
        inner = expr[1:-1].strip()
        if not inner:
            return []
        
        items = []
        depth = 0
        current = ""
        in_string = False
        string_char = None
        
        for char in inner + ',':
            if char in ('"', "'") and (not current or current[-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            
            if not in_string:
                if char in '[{(':
                    depth += 1
                elif char in ']})':
                    depth -= 1
                
                if char == ',' and depth == 0:
                    if current.strip():
                        items.append(evaluate(current.strip(), ln, file))
                    current = ""
                    continue
            
            current += char
        
        return items
    
    # Object literals
    if expr.startswith('{') and expr.endswith('}'):
        inner = expr[1:-1].strip()
        if not inner:
            return {}
        
        obj = {}
        pairs = []
        depth = 0
        current = ""
        in_string = False
        string_char = None
        
        for char in inner + ',':
            if char in ('"', "'") and (not current or current[-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            
            if not in_string:
                if char in '[{(':
                    depth += 1
                elif char in ']})':
                    depth -= 1
                
                if char == ',' and depth == 0:
                    if current.strip():
                        pairs.append(current.strip())
                    current = ""
                    continue
            
            current += char
        
        for pair in pairs:
            if ':' not in pair:
                continue
            kp, vp = pair.split(':', 1)
            key = evaluate(kp.strip(), ln, file)
            value = evaluate(vp.strip(), ln, file)
            obj[key] = value
        
        return obj
    
    # Function calls
    if '(' in expr and expr.endswith(')'):
        pp = expr.find('(')
        fn = expr[:pp].strip()
        args_str = expr[pp+1:-1].strip()
        
        if fn and (fn in get_builtin_functions() or fn in functions or fn.isidentifier()):
            return call_function(fn, args_str, ln, file)
    
    # Array/object indexing
    if '[' in expr and ']' in expr:
        bp = expr.find('[')
        vn = expr[:bp].strip()
        idx_expr = expr[bp+1:expr.rfind(']')]
        
        try:
            var = current_scope.get(vn)
            idx = evaluate(idx_expr, ln, file)
            return var[idx]
        except KeyError:
            error(f"Variable '{vn}' not defined", ln, file, expr)
        except (IndexError, KeyError):
            error(f"Invalid index: {idx}", ln, file, expr)
    
    # Property access
    if '.' in expr and not is_number(expr):
        parts = expr.split('.')
        try:
            obj = current_scope.get(parts[0])
            for part in parts[1:]:
                if isinstance(obj, dict):
                    if part not in obj:
                        error(f"Key '{part}' not found", ln, file, expr)
                    obj = obj[part]
                else:
                    error(f"Cannot access '{part}' in {type(obj).__name__}", ln, file, expr)
            return obj
        except KeyError:
            error(f"Variable '{parts[0]}' not defined", ln, file, expr)
    
    # Variable lookup
    if current_scope.exists(expr):
        return current_scope.get(expr)
    
    # Number literals
    try:
        return float(expr) if '.' in expr else int(expr)
    except:
        pass
    
    error(f"Invalid expression: {expr}", ln, file, expr)

# ==================== BUILT-IN FUNCTIONS ====================
def get_builtin_functions():
    """Return list of built-in function names"""
    return [
        'print', 'اطبع', 'input', 'ادخال', 'len', 'طول', 'type', 'نوع',
        'str', 'نص', 'int', 'صحيح', 'float', 'عشري', 'sqrt', 'جذر',
        'pow', 'أس', 'random', 'عشوائي', 'range', 'نطاق', 'push', 'اضف',
        'pop', 'احذف', 'readFile', 'اقرأملف', 'writeFile', 'اكتبملف',
        'fileExists', 'ملفموجود', 'deleteFile', 'احذفملف', 'sleep', 'انتظر',
        'json', 'جيسون', 'parseJson', 'حللجيسون', 'html', 'import', 'استورد',
        'export', 'صدر', 'keys', 'مفاتيح', 'values', 'قيم', 'abs', 'مطلق',
        'round', 'تقريب', 'floor', 'أرضية', 'ceil', 'سقف', 'max', 'أكبر',
        'min', 'أصغر', 'sum', 'مجموع', 'join', 'ضم', 'split', 'تقسيم'
    ]

def parse_args(args_str, ln=None, file=None):
    """Parse function arguments"""
    if not args_str:
        return []
    
    args = []
    depth = 0
    current = ""
    in_string = False
    string_char = None
    
    for char in args_str + ',':
        if char in ('"', "'") and (not current or current[-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
        
        if not in_string:
            if char in '[{(':
                depth += 1
            elif char in ']})':
                depth -= 1
            
            if char == ',' and depth == 0:
                if current.strip():
                    args.append(evaluate(current.strip(), ln, file))
                current = ""
                continue
        
        current += char
    
    return args

def call_function(name, args_str, ln=None, file=None):
    """Call a built-in or user-defined function"""
    global current_scope
    
    args = parse_args(args_str, ln, file) if args_str else []
    
    # Print function
    if name in ('print', 'اطبع'):
        v = " ".join(str(a) for a in args)
        print(v)
        output.append(v)
        return None
    
    # Input function
    elif name in ('input', 'ادخال'):
        prompt = str(args[0]) if args else ""
        if prompt:
            print(prompt, end='')
        v = input()
        try:
            return float(v) if "." in v else int(v) if v.lstrip('-').isdigit() else v
        except:
            return v
    
    # Length function
    elif name in ('len', 'طول'):
        if not args:
            error("len requires one argument", ln, file)
        if not hasattr(args[0], '__len__'):
            error("Value has no length", ln, file)
        return len(args[0])
    
    # Type function
    elif name in ('type', 'نوع'):
        if not args:
            error("type requires one argument", ln, file)
        return type(args[0]).__name__
    
    # String conversion
    elif name in ('str', 'نص'):
        if not args:
            error("str requires one argument", ln, file)
        return str(args[0])
    
    # Integer conversion
    elif name in ('int', 'صحيح'):
        if not args:
            error("int requires one argument", ln, file)
        try:
            return int(float(args[0]))
        except:
            error("Cannot convert to integer", ln, file)
    
    # Float conversion
    elif name in ('float', 'عشري'):
        if not args:
            error("float requires one argument", ln, file)
        try:
            return float(args[0])
        except:
            error("Cannot convert to float", ln, file)
    
    # Math functions
    elif name in ('sqrt', 'جذر'):
        if not args or not isinstance(args[0], (int, float)):
            error("sqrt requires a number", ln, file)
        return math.sqrt(args[0])
    
    elif name in ('pow', 'أس'):
        if len(args) != 2:
            error("pow requires two arguments", ln, file)
        return pow(args[0], args[1])
    
    elif name in ('abs', 'مطلق'):
        if not args:
            error("abs requires one argument", ln, file)
        return abs(args[0])
    
    elif name in ('round', 'تقريب'):
        if not args:
            error("round requires one argument", ln, file)
        return round(args[0], args[1] if len(args) > 1 else 0)
    
    elif name in ('floor', 'أرضية'):
        if not args:
            error("floor requires one argument", ln, file)
        return math.floor(args[0])
    
    elif name in ('ceil', 'سقف'):
        if not args:
            error("ceil requires one argument", ln, file)
        return math.ceil(args[0])
    
    elif name in ('max', 'أكبر'):
        if not args:
            error("max requires at least one argument", ln, file)
        return max(args)
    
    elif name in ('min', 'أصغر'):
        if not args:
            error("min requires at least one argument", ln, file)
        return min(args)
    
    elif name in ('sum', 'مجموع'):
        if not args:
            error("sum requires one argument", ln, file)
        return sum(args[0])
    
    # Random function
    elif name in ('random', 'عشوائي'):
        if not args:
            return random.random()
        if len(args) != 2:
            error("random requires two arguments for range", ln, file)
        return random.randint(int(args[0]), int(args[1]))
    
    # Range function
    elif name in ('range', 'نطاق'):
        if len(args) == 1:
            return list(range(int(args[0])))
        elif len(args) == 2:
            return list(range(int(args[0]), int(args[1])))
        elif len(args) == 3:
            return list(range(int(args[0]), int(args[1]), int(args[2])))
        error("range requires 1-3 arguments", ln, file)
    
    # Array functions
    elif name in ('push', 'اضف'):
        if len(args) != 2:
            error("push requires (array, value)", ln, file)
        if not isinstance(args[0], list):
            error("First argument must be an array", ln, file)
        args[0].append(args[1])
        return None
    
    elif name in ('pop', 'احذف'):
        if not args or not isinstance(args[0], list):
            error("pop requires an array", ln, file)
        if not args[0]:
            error("Array is empty", ln, file)
        return args[0].pop()
    
    # Object functions
    elif name in ('keys', 'مفاتيح'):
        if not args:
            error("keys requires one argument", ln, file)
        if not isinstance(args[0], dict):
            error("keys requires an object", ln, file)
        return list(args[0].keys())
    
    elif name in ('values', 'قيم'):
        if not args:
            error("values requires one argument", ln, file)
        if not isinstance(args[0], dict):
            error("values requires an object", ln, file)
        return list(args[0].values())
    
    # String functions
    elif name in ('join', 'ضم'):
        if len(args) != 2:
            error("join requires (separator, array)", ln, file)
        return str(args[0]).join(str(x) for x in args[1])
    
    elif name in ('split', 'تقسيم'):
        if not args:
            error("split requires at least one argument", ln, file)
        sep = args[1] if len(args) > 1 else " "
        return str(args[0]).split(str(sep))
    
    # File I/O functions
    elif name in ('readFile', 'اقرأملف'):
        if not args:
            error("readFile requires a filename", ln, file)
        try:
            with open(args[0], 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            error(f"Failed to read file: {e}", ln, file)
    
    elif name in ('writeFile', 'اكتبملف'):
        if len(args) < 2:
            error("writeFile requires (filename, content)", ln, file)
        try:
            with open(args[0], 'w', encoding='utf-8') as f:
                f.write(str(args[1]))
            return True
        except Exception as e:
            error(f"Failed to write file: {e}", ln, file)
    
    elif name in ('fileExists', 'ملفموجود'):
        if not args:
            error("fileExists requires a filename", ln, file)
        return os.path.exists(args[0])
    
    elif name in ('deleteFile', 'احذفملف'):
        if not args:
            error("deleteFile requires a filename", ln, file)
        try:
            os.remove(args[0])
            return True
        except Exception as e:
            error(f"Failed to delete file: {e}", ln, file)
    
    # Utility functions
    elif name in ('sleep', 'انتظر'):
        if not args:
            error("sleep requires number of seconds", ln, file)
        time.sleep(args[0])
        return None
    
    elif name in ('json', 'جيسون'):
        if not args:
            error("json requires a value", ln, file)
        return json.dumps(args[0], ensure_ascii=False)
    
    elif name in ('parseJson', 'حللجيسون'):
        if not args:
            error("parseJson requires JSON text", ln, file)
        try:
            return json.loads(args[0])
        except:
            error("Failed to parse JSON", ln, file)
    
    elif name == 'html':
        if not args:
            error("html requires content", ln, file)
        return args[0]
    
    # Module functions
    elif name in ('import', 'استورد'):
        if not args:
            error("import requires a filename", ln, file)
        return import_module(args[0], ln, file)
    
    elif name in ('export', 'صدر'):
        if len(args) < 2:
            error("export requires (name, value)", ln, file)
        if file and file in modules:
            modules[file]['exports'][args[0]] = args[1]
        return None
    
    # User-defined functions
    elif name in functions:
        func_body, func_args, def_scope = functions[name]
        
        call_stack.append(f"{name}({', '.join(str(a)[:20] for a in args)})")
        
        if len(call_stack) > MAX_RECURSION_DEPTH:
            error(f"Recursion depth exceeded ({MAX_RECURSION_DEPTH})", ln, file)
        
        try:
            func_scope = Scope(parent=def_scope, name=f"func:{name}")
            
            for i, arg_name in enumerate(func_args):
                if i < len(args):
                    func_scope.set(arg_name, args[i])
                else:
                    func_scope.set(arg_name, None)
            
            old_scope = current_scope
            current_scope = func_scope
            
            try:
                result = run(func_body, file)
                return result
            finally:
                current_scope = old_scope
        
        finally:
            call_stack.pop()
    
    else:
        error(f"Function '{name}' not defined", ln, file)

# ==================== EXPRESSION EVALUATION ====================
def evaluate(expr, ln=None, file=None):
    """Main evaluation function"""
    if not expr or expr.strip().startswith('#'):
        return None
    
    expr = expr.split("#")[0].strip()
    
    if not expr:
        return None
    
    try:
        return eval_arith(expr, ln, file)
    except ExoError:
        raise
    except Exception as e:
        error(f"Evaluation error: {e}", ln, file, expr)

# ==================== MODULE SYSTEM ====================
def import_module(module_path, ln=None, file=None):
    """Import an EXO module"""
    global current_scope
    
    if not module_path.endswith('.exo'):
        module_path += '.exo'
    
    if file:
        base_dir = os.path.dirname(os.path.abspath(file))
        full_path = os.path.join(base_dir, module_path)
    else:
        full_path = module_path
    
    if full_path in modules:
        return modules[full_path]['exports']
    
    if not os.path.exists(full_path):
        error(f"File '{module_path}' not found", ln, file)
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        modules[full_path] = {'exports': {}}
        
        old_scope = current_scope
        module_scope = Scope(parent=global_scope, name=f"module:{module_path}")
        current_scope = module_scope
        
        try:
            run(code, full_path)
        finally:
            current_scope = old_scope
        
        return modules[full_path]['exports']
    
    except ExoError:
        raise
    except Exception as e:
        error(f"Failed to load module: {e}", ln, file)

# ==================== CODE EXECUTION ====================
def run(code_lines, file=None):
    """Execute EXO code"""
    global current_scope
    
    if isinstance(code_lines, str):
        code_lines = code_lines.split('\n')
    
    i = 0
    while i < len(code_lines):
        line = code_lines[i].strip()
        
        if not line or line.startswith('#'):
            i += 1
            continue
        
        try:
            # Variable declaration
            if line.startswith(('let ', 'متغير ', 'var ', 'const ')):
                prefix_len = len(line.split()[0]) + 1
                rest = line[prefix_len:].strip()
                
                # Array/object element assignment
                if '[' in rest and '=' in rest and rest.find('[') < rest.find('='):
                    vn = rest[:rest.find('[')].strip()
                    idx_expr = rest[rest.find('[')+1:rest.find(']')]
                    val_expr = rest.split('=', 1)[1].strip()
                    
                    try:
                        var = current_scope.get(vn)
                        idx = evaluate(idx_expr, i+1, file)
                        var[idx] = evaluate(val_expr, i+1, file)
                    except KeyError:
                        error(f"Variable '{vn}' not defined", i+1, file, line)
                
                else:
                    if '=' not in rest:
                        error("Invalid syntax: use = to assign value", i+1, file, line)
                    
                    name, value = rest.split('=', 1)
                    name = name.strip()
                    
                    if not name.isidentifier():
                        error(f"Invalid variable name: {name}", i+1, file, line)
                    
                    current_scope.set(name, evaluate(value.strip(), i+1, file))
            
            # Return statement
            elif line.startswith(('return ', 'ارجع ')):
                prefix_len = 7 if line.startswith('return ') else 6
                return evaluate(line[prefix_len:].strip(), i+1, file) if line[prefix_len:].strip() else None
            
            # Break statement
            elif line in ('break', 'اكسر'):
                return 'break'
            
            # Continue statement
            elif line in ('continue', 'استمر'):
                return 'continue'
            
            # Route definition
            elif line.startswith(('route ', 'مسار ')):
                route_path = line[6:].strip() if line.startswith('route ') else line[5:].strip()
                if not route_path.startswith('/'):
                    route_path = '/' + route_path
                
                body = []
                depth = 1
                i += 1
                while i < len(code_lines):
                    curr = code_lines[i].strip()
                    if curr.startswith(('route ', 'مسار ', 'func ', 'دالة ', 'function ', 'if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ')):
                        depth += 1
                    elif curr in ('end', 'نهاية'):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(code_lines[i])
                    i += 1
                web_routes[route_path] = body
                print(f"✅ Route: {route_path}")
            
            # Function definition
            elif line.startswith(('func ', 'دالة ', 'function ')):
                prefix_len = len(line.split()[0]) + 1
                rest = line[prefix_len:].strip()
                if '(' not in rest or ')' not in rest:
                    error("Invalid function syntax", i+1, file, line)
                
                fn = rest[:rest.find('(')].strip()
                args_str = rest[rest.find('(')+1:rest.find(')')]
                args_names = [a.strip() for a in args_str.split(',') if a.strip()]
                
                body = []
                depth = 1
                i += 1
                while i < len(code_lines):
                    curr = code_lines[i].strip()
                    if curr.startswith(('func ', 'دالة ', 'function ', 'if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ', 'route ', 'مسار ')):
                        depth += 1
                    elif curr in ('end', 'نهاية'):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(code_lines[i])
                    i += 1
                
                functions[fn] = (body, args_names, current_scope)
            
            # If-else statement
            elif line.startswith(('if ', 'اذا ')):
                prefix_len = 3 if line.startswith('if ') else 4
                executed = False
                
                while True:
                    cond = line[prefix_len:].strip()
                    body = []
                    depth = 1
                    i += 1
                    
                    while i < len(code_lines):
                        curr = code_lines[i].strip()
                        if curr.startswith(('if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ', 'func ', 'دالة ', 'function ', 'route ', 'مسار ')):
                            depth += 1
                        elif curr in ('end', 'نهاية', 'else', 'والا') or curr.startswith(('else if ', 'والا اذا ')):
                            if depth == 1:
                                break
                            if curr in ('end', 'نهاية'):
                                depth -= 1
                        body.append(code_lines[i])
                        i += 1
                    
                    if not executed and evaluate(cond, i+1, file):
                        result = run(body, file)
                        executed = True
                        if result in ('break', 'continue') or result is not None:
                            return result
                    
                    if i >= len(code_lines):
                        break
                    curr = code_lines[i].strip()
                    
                    if curr in ('end', 'نهاية'):
                        break
                    elif curr.startswith(('else if ', 'والا اذا ')):
                        prefix_len = 8 if curr.startswith('else if ') else 9
                        line = curr
                    elif curr in ('else', 'والا'):
                        if not executed:
                            i += 1
                            body = []
                            depth = 1
                            while i < len(code_lines):
                                curr = code_lines[i].strip()
                                if curr.startswith(('if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ', 'func ', 'دالة ', 'function ', 'route ', 'مسار ')):
                                    depth += 1
                                elif curr in ('end', 'نهاية'):
                                    depth -= 1
                                    if depth == 0:
                                        break
                                body.append(code_lines[i])
                                i += 1
                            result = run(body, file)
                            if result in ('break', 'continue') or result is not None:
                                return result
                        break
            
            # While loop
            elif line.startswith(('while ', 'بينما ')):
                prefix_len = 6 if line.startswith('while ') else 7
                cond = line[prefix_len:].strip()
                
                body = []
                depth = 1
                i += 1
                while i < len(code_lines):
                    curr = code_lines[i].strip()
                    if curr.startswith(('if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ', 'func ', 'دالة ', 'function ', 'route ', 'مسار ')):
                        depth += 1
                    elif curr in ('end', 'نهاية'):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(code_lines[i])
                    i += 1
                
                while evaluate(cond, i+1, file):
                    result = run(body, file)
                    if result == 'break':
                        break
                    elif result == 'continue':
                        continue
                    elif result is not None:
                        return result
            
            # For loop
            elif line.startswith(('for ', 'لكل ')):
                prefix_len = 4 if line.startswith('for ') else 5
                rest = line[prefix_len:].strip()
                
                if ' in ' not in rest and ' في ' not in rest:
                    error("Invalid for syntax", i+1, file, line)
                
                sep = ' in ' if ' in ' in rest else ' في '
                vn, iter_expr = rest.split(sep, 1)
                vn = vn.strip()
                iterable = evaluate(iter_expr.strip(), i+1, file)
                
                if not hasattr(iterable, '__iter__'):
                    error("Value is not iterable", i+1, file, line)
                
                body = []
                depth = 1
                i += 1
                while i < len(code_lines):
                    curr = code_lines[i].strip()
                    if curr.startswith(('if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ', 'func ', 'دالة ', 'function ', 'route ', 'مسار ')):
                        depth += 1
                    elif curr in ('end', 'نهاية'):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(code_lines[i])
                    i += 1
                
                for item in iterable:
                    current_scope.set(vn, item)
                    result = run(body, file)
                    if result == 'break':
                        break
                    elif result == 'continue':
                        continue
                    elif result is not None:
                        return result
            
            # Function call
            elif '(' in line and ')' in line and not line.startswith(('let ', 'var ', 'متغير ', 'const ')):
                evaluate(line, i+1, file)
            
            # Variable assignment
            elif '=' in line and not line.startswith(('let ', 'var ', 'متغير ', 'const ')):
                name, value = line.split('=', 1)
                name = name.strip()
                
                # Array/object element assignment
                if '[' in name:
                    vn = name[:name.find('[')].strip()
                    idx_expr = name[name.find('[')+1:name.find(']')]
                    try:
                        var = current_scope.get(vn)
                        idx = evaluate(idx_expr, i+1, file)
                        var[idx] = evaluate(value.strip(), i+1, file)
                    except KeyError:
                        error(f"Variable '{vn}' not defined", i+1, file, line)
                # Property assignment
                elif '.' in name:
                    parts = name.split('.')
                    try:
                        obj = current_scope.get(parts[0])
                        for part in parts[1:-1]:
                            obj = obj[part]
                        obj[parts[-1]] = evaluate(value.strip(), i+1, file)
                    except KeyError:
                        error(f"Variable '{parts[0]}' not defined", i+1, file, line)
                else:
                    if not current_scope.exists(name):
                        error(f"Variable '{name}' not defined - use 'let' to declare it first", i+1, file, line)
                    current_scope.set(name, evaluate(value.strip(), i+1, file), local=False)
            else:
                evaluate(line, i+1, file)
        
        except ExoError:
            raise
        except Exception as e:
            error(f"Unexpected error: {e}", i+1, file, line)
        
        i += 1
    
    return None

# ==================== WEB SERVER ====================
def get_local_ip():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

class ExoWebHandler(BaseHTTPRequestHandler):
    """HTTP request handler for EXO web server"""
    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {format % args}")
    
    def do_GET(self):
        global current_scope
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        
        print(f"\n📥 GET {path}")
        
        if path in web_routes:
            try:
                old_scope = current_scope
                request_scope = Scope(parent=global_scope, name=f"request:{path}")
                current_scope = request_scope
                current_scope.set('request', {
                    'path': path,
                    'query': parse_qs(parsed.query),
                    'method': 'GET'
                })
                
                try:
                    result = run(web_routes[path], f"route:{path}")
                finally:
                    current_scope = old_scope
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                if not result:
                    result = "<!DOCTYPE html><html><body><h1>✅ EXO</h1></body></html>"
                self.wfile.write(str(result).encode('utf-8'))
            
            except ExoError as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"<pre>{e}</pre>".encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            routes = ''.join(f'<li><a href="{r}">{r}</a></li>' for r in web_routes)
            self.wfile.write(f"<h1>404</h1><ul>{routes}</ul>".encode('utf-8'))

def start_web_server(port=8000):
    """Start the web server"""
    print(f"\n🚀 EXO Web Server v3.1\n")
    if not web_routes:
        print("❌ No routes defined!")
        return
    
    try:
        httpd = HTTPServer(('0.0.0.0', port), ExoWebHandler)
        ip = get_local_ip()
        print(f"✅ Server running at http://{ip}:{port}/\n")
        print("📌 Available routes:")
        for route in web_routes:
            print(f"   • http://{ip}:{port}{route}")
        print("\nPress Ctrl+C to stop")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✅ Server stopped")
    except Exception as e:
        print(f"\n❌ Server error: {e}")

# ==================== FILE EXECUTION ====================
def run_file(filepath):
    """Execute an EXO file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        print(f"🚀 Running: {filepath}\n")
        start = time.time()
        run(code, filepath)
        print(f"\n✅ Completed in {time.time()-start:.3f}s")
        
        if web_routes:
            if input("\nStart web server? (y/n): ").lower() == 'y':
                start_web_server()
    except ExoError as e:
        print(f"\n{e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n❌ File '{filepath}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)

# ==================== REPL ====================
def repl():
    """Interactive REPL with multi-line support"""
    print("=" * 50)
    print("🌟 EXO Interactive Mode v3.1")
    print("=" * 50)
    print("Type 'exit' to quit | 'help' for help\n")
    
    buffer = []
    
    while True:
        try:
            prompt = ">>> " if not buffer else "... "
            line = input(prompt).strip()
            
            # Exit commands
            if line in ('exit', 'خروج', 'quit'):
                if buffer:
                    print("⚠ Incomplete commands")
                    buffer = []
                    continue
                print("👋 Goodbye!")
                break
            
            # Clear command
            if line in ('clear', 'مسح'):
                global_scope.vars.clear()
                functions.clear()
                buffer = []
                print("✅ Cleared")
                continue
            
            # Show variables
            if line in ('vars', 'متغيرات'):
                if global_scope.vars:
                    print("\n📦 Variables:")
                    for k, v in global_scope.vars.items():
                        print(f"  {k} = {v}")
                else:
                    print("No variables")
                continue
            
            # Show functions
            if line in ('funcs', 'دوال'):
                if functions:
                    print("\n🔧 Functions:")
                    for fname in functions:
                        print(f"  • {fname}")
                else:
                    print("No functions")
                continue
            
            # Help command
            if line in ('help', 'مساعدة'):
                print("""
📖 Commands:
  let x = 10          - Declare variable
  print(x)            - Print
  func f(x) ... end   - Define function
  if ... end          - Conditional
  for x in ... end    - Loop
  while ... end       - While loop
  
🔧 REPL Commands:
  exit / خروج         - Exit
  help / مساعدة       - Help
  vars / متغيرات      - Show variables
  funcs / دوال        - Show functions
  clear / مسح         - Clear all
                """)
                continue
            
            # Add line to buffer
            if line:
                buffer.append(line)
                
                # Check if multi-line block
                if line.startswith(('func ', 'دالة ', 'if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ')):
                    if not line.endswith(('end', 'نهاية')):
                        continue
                
                # Check block depth
                if buffer:
                    depth = 0
                    for l in buffer:
                        l = l.strip()
                        if l.startswith(('func ', 'دالة ', 'if ', 'اذا ', 'while ', 'بينما ', 'for ', 'لكل ')):
                            depth += 1
                        if l in ('end', 'نهاية'):
                            depth -= 1
                    
                    if depth > 0:
                        continue
                
                # Execute buffer
                try:
                    result = run('\n'.join(buffer))
                    if result is not None and result not in ('break', 'continue'):
                        print(f"=> {result}")
                except ExoError:
                    pass
                except Exception as e:
                    print(f"❌ {e}")
                
                buffer = []
        
        except KeyboardInterrupt:
            print("\nPress Ctrl+C again or type 'exit'")
            buffer = []
        except EOFError:
            print("\n👋 Goodbye!")
            break

# ==================== MAIN ====================
def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════╗
║  🌟 EXO Language v3.1               ║
║  ✅ Production Ready                ║
║  ✅ Arabic/English Support          ║
║  ✅ Web Server Built-in             ║
╚══════════════════════════════════════╝
""")
    
    # If file argument provided, run it
    if len(sys.argv) > 1:
        run_file(sys.argv[1])
    else:
        # Default directory for EXO files
        base = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "lang")
        
        # Check if directory exists
        if not os.path.exists(base):
            print(f"⚠ Directory {base} not found")
            choice = input("Create directory? (y/n): ")
            if choice.lower() == 'y':
                try:
                    os.makedirs(base, exist_ok=True)
                    print(f"✅ Created: {base}")
                except:
                    print("❌ Failed to create directory")
            repl()
        else:
            # List .exo files
            files = [f for f in os.listdir(base) if f.endswith('.exo')]
            
            if files:
                print("📁 Files:")
                for i, f in enumerate(files, 1):
                    print(f"  {i}. {f}")
                print(f"  {len(files)+1}. REPL")
                
                choice = input("\nSelect: ").strip()
                
                try:
                    idx = int(choice) - 1
                    if idx == len(files):
                        repl()
                    elif 0 <= idx < len(files):
                        run_file(os.path.join(base, files[idx]))
                    else:
                        print("❌ Invalid selection")
                        repl()
                except ValueError:
                    if choice in files:
                        run_file(os.path.join(base, choice))
                    else:
                        print("❌ Invalid selection")
                        repl()
            else:
                print("⚠ No .exo files found")
                repl()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Stopped")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()