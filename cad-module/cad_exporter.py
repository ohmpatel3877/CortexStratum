#!/usr/bin/env python3
"""
cad_exporter.py - Batch SCAD to STL export via OpenSCAD CLI
ai-memory-core cad-module
"""
import subprocess
import sys
import time
from pathlib import Path


def find_openscad():
    """Locate OpenSCAD executable."""
    candidates = [
        'openscad',
        'C:/Program Files/OpenSCAD/openscad.exe',
        'C:/Program Files (x86)/OpenSCAD/openscad.exe',
        str(Path.home() / 'AppData/Local/OpenSCAD/openscad.exe'),
    ]
    for c in candidates:
        try:
            result = subprocess.run([c, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return c
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def export_stl(scad_path, output_dir=None, quality='medium'):
    """Export a single SCAD file to STL."""
    scad_path = Path(scad_path)
    if not scad_path.exists():
        return {'file': scad_path.name, 'success': False, 'error': 'File not found'}
    
    if output_dir:
        output_dir = Path(output_dir)
    else:
        output_dir = scad_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    stl_path = output_dir / f'{scad_path.stem}.stl'
    
    openscad = find_openscad()
    if not openscad:
        return {'file': scad_path.name, 'success': False, 'error': 'OpenSCAD not found'}
    
    # Quality settings
    fn_values = {'low': 12, 'medium': 24, 'high': 48, 'ultra': 96}
    fn = fn_values.get(quality, 24)
    
    cmd = [openscad, '-o', str(stl_path), '--export-format', 'binstl',
           '-D', f'$fn={fn}', str(scad_path)]
    
    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        elapsed = time.time() - start
        
        if result.returncode == 0:
            size_kb = stl_path.stat().st_size / 1024 if stl_path.exists() else 0
            return {
                'file': scad_path.name,
                'stl': str(stl_path),
                'success': True,
                'size_kb': round(size_kb, 1),
                'time_s': round(elapsed, 1),
            }
        else:
            return {
                'file': scad_path.name,
                'success': False,
                'error': result.stderr[:500] or f'Exit code {result.returncode}',
            }
    except subprocess.TimeoutExpired:
        return {'file': scad_path.name, 'success': False, 'error': 'Timed out (120s)'}
    except Exception as e:
        return {'file': scad_path.name, 'success': False, 'error': str(e)}


def batch_export(scad_dir, output_dir, quality='medium', parallel=False):
    """Export all SCAD files in a directory to STL."""
    scad_dir = Path(scad_dir)
    scad_files = sorted(scad_dir.glob('*.scad'))
    
    if not scad_files:
        print(f'No .scad files found in {scad_dir}')
        return []
    
    results = []
    for i, scad in enumerate(scad_files):
        print(f'[{i+1}/{len(scad_files)}] Exporting {scad.name}...', end=' ', flush=True)
        result = export_stl(scad, output_dir, quality)
        if result['success']:
            print(f'OK - {result["size_kb"]}KB in {result["time_s"]}s')
        else:
            print(f'FAILED - {result.get("error", "Unknown error")}')
        results.append(result)
    
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Export SCAD files to STL')
    parser.add_argument('input', nargs='?', default='G:/My Drive/Project/Bottle Flipper/cad',
                       help='SCAD file or directory')
    parser.add_argument('-o', '--output', default=None, help='Output directory')
    parser.add_argument('-q', '--quality', default='medium', choices=['low', 'medium', 'high', 'ultra'])
    parser.add_argument('--parallel', action='store_true', help='Export in parallel')
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if input_path.is_dir():
        results = batch_export(input_path, args.output or input_path, args.quality, args.parallel)
    else:
        result = export_stl(input_path, args.output or input_path.parent, args.quality)
        results = [result]
    
    success = sum(1 for r in results if r['success'])
    failed = sum(1 for r in results if not r['success'])
    print(f'\nDone: {success} exported, {failed} failed')
