#!/usr/bin/env python3
"""
cad_validator.py - SCAD file structure & syntax validator
ai-memory-core cad-module
Validates: brace balance, module definitions, parameter completeness,
           unused variables, common OpenSCAD pitfalls
"""
import re
import sys
from pathlib import Path


def validate_scad(filepath):
    """Validate a single .scad file and return issues."""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    lines = content.split('\n')
    issues = []
    
    name = Path(filepath).name
    
    # 1. Brace balance
    opens = content.count('{')
    closes = content.count('}')
    if opens != closes:
        issues.append(f'BRAE MISMATCH: {opens} open, {closes} close')
    
    # 2. Module definitions
    modules = re.findall(r'module\s+(\w+)', content)
    
    # 3. Unused variables (declared but never referenced in expressions)
    vars_declared = set()
    for m in re.finditer(r'^(\w+)\s*=\s*(.+?);', content, re.MULTILINE):
        name_v = m.group(1)
        if name_v not in ('pi', 'PI', '$fn', '$fa', '$fs'):
            vars_declared.add(name_v)
    
    vars_used = set()
    for m in re.finditer(r'\b([a-z_]\w*)\b', content):
        vars_used.add(m.group(1))
    
    unused = vars_declared - vars_used
    # Filter out common false positives
    unused = {v for v in unused if not v.startswith('_') and v not in modules}
    if unused:
        issues.append(f'UNUSED VARS: {", ".join(sorted(unused))}')
    
    # 4. Check for undefined modules being called
    called_modules = set()
    for m in re.finditer(r'\b([a-z_]\w*)\(', content):
        called_modules.add(m.group(1))
    defined = set(modules) | {'cube', 'sphere', 'cylinder', 'polyhedron', 'translate',
        'rotate', 'scale', 'mirror', 'union', 'difference', 'intersection',
        'hull', 'minkowski', 'linear_extrude', 'rotate_extrude',
        'projection', 'offset', 'text', 'surface', 'import', 'child',
        'echo', 'assert', 'color', 'assign', 'for', 'if', 'let', 'each',
        'ceil', 'floor', 'round', 'abs', 'sin', 'cos', 'tan', 'atan', 'atan2',
        'sqrt', 'pow', 'ln', 'log', 'exp', 'rands', 'min', 'max', 'len',
        'concat', 'lookup', 'search', 'sign', 'str', 'chr', 'ord',
        'cross', 'norm', 'PI', 'true', 'false', 'undef'}
    undefined = called_modules - defined
    if undefined:
        issues.append(f'UNDEFINED MODULES CALLED: {", ".join(sorted(undefined))}')
    
    # 5. Check for common OpenSCAD pitfalls
    for i, line in enumerate(lines, 1):
        # Missing semicolon after module call
        if re.match(r'\s*\w+\(.*\)\s*$', line) and not line.strip().endswith(';') and not line.strip().endswith('{'):
            if not line.strip().startswith('//') and not line.strip().startswith('/*'):
                pass  # This is too common to flag - could be a block start
    
        # Using = instead of == in condition
        if re.search(r'if\s*\([^)]*=[^)=]', line):
            issues.append(f'LINE {i}: Possibly using = instead of == in condition')
    
    # 6. Check for $fn on every file
    if '$fn' not in content:
        issues.append('WARN: No $fn set - may render with jagged edges')
    
    # 7. File size check
    if len(content) < 50:
        issues.append('WARN: Very short file (< 50 chars)')
    
    result = {
        'file': name,
        'lines': len(lines),
        'modules': modules,
        'issues': issues,
        'valid': len(issues) == 0
    }
    return result


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not paths:
        print('Usage: python cad_validator.py <file1.scad> [file2.scad ...]')
        print('       python cad_validator.py  (scans ./cad/ directory)')
        base = Path(__file__).parent.parent.parent
        gdrive = Path('G:/My Drive/Project/Bottle Flipper/cad')
        if gdrive.exists():
            paths = sorted(gdrive.glob('*.scad'))
        elif (base / 'cad').exists():
            paths = sorted((base / 'cad').glob('*.scad'))
    
    if not paths:
        print('No SCAD files found')
        return
    
    all_valid = True
    for p in paths:
        p = Path(p)
        if p.suffix != '.scad':
            continue
        result = validate_scad(p)
        status = 'OK' if result['valid'] else 'ISSUES'
        print(f'[{status}] {result["file"]} ({result["lines"]} lines)')
        if result['modules']:
            print(f'       Modules: {", ".join(result["modules"])}')
        for issue in result['issues']:
            print(f'       - {issue}')
            all_valid = False
    
    print()
    print(f'Total: {len(paths)} files, {"ALL VALID" if all_valid else "ISSUES FOUND"}')
    return 0 if all_valid else 1


if __name__ == '__main__':
    sys.exit(main())
