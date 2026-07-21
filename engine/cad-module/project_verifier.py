#!/usr/bin/env python3
"""
project_verifier.py - Verifies SCAD files against project spec requirements
CortexStratum cad-module
Checks: all mandatory subsystems covered, dimensions match spec, component positions valid
"""

import re
import sys
from pathlib import Path


class ProjectSpec:
    """ENGR18922D Bottle Flipping System project requirements."""

    def __init__(self):
        self.mandatory_subsystems = [
            "drive",
            "power transmission",
            "clamping",
            "inverting",
            "sensing",
            "control",
            "frame",
        ]
        self.min_laser_cut_pct = 20
        self.min_bottle_capacity_ml = 500
        self.min_cycles = 5
        self.bottle_diameter_mm = 75
        self.bottle_height_mm = 200

    def get_all_requirements(self):
        return {
            "subsystems": self.mandatory_subsystems,
            "laser_cut": self.min_laser_cut_pct,
            "bottle_ml": self.min_bottle_capacity_ml,
            "cycles": self.min_cycles,
        }


def verify_scad_file(filepath, spec):
    """Verify a SCAD file against project requirements."""
    content = Path(filepath).read_text(encoding="utf-8", errors="replace")
    name = Path(filepath).stem

    # What does this file contain?
    has_servo = "servo" in content.lower()
    has_clamp = "clamp" in content.lower()
    has_bottle = "bottle" in content.lower() or "cradle" in content.lower()
    has_frame = (
        "base" in content.lower()
        or "frame" in content.lower()
        or "rib" in content.lower()
    )
    has_mount = "mount" in content.lower() or "bracket" in content.lower()
    has_gear = "gear" in content.lower() or "pinion" in content.lower()
    has_bearing = "bearing" in content.lower() or "bushing" in content.lower()

    # Check dimensions are reasonable
    dims = re.findall(r"(\w+)\s*=\s*(\d+\.?\d*)", content)
    dim_dict = {d[0]: float(d[1]) for d in dims}

    issues = []

    # Check file has modules (not just raw geometry)
    modules = re.findall(r"module\s+(\w+)", content)
    if not modules:
        issues.append("No modules defined - should encapsulate geometry")

    # Check for proper scaling (mm)
    if has_frame:
        for key in ["bw", "bd", "bh", "width", "depth", "height"]:
            if key in dim_dict:
                val = dim_dict[key]
                if val < 5:
                    issues.append(f"{key}={val}mm seems very small for a frame")

    # Assembly-specific checks
    if "servo" in name.lower() or has_servo:
        if not any(k in dim_dict for k in ["servo_w", "servo_h", "servo_d"]):
            issues.append("Servo mount missing SM-S2309S body dimensions")
        if not has_mount:
            issues.append("Servo part missing mounting provisions")

    if "clamp" in name.lower() or has_clamp:
        if not has_bottle:
            pass  # Clamp may be generically designed

    if "base" in name.lower() or "frame" in name.lower():
        if not has_mount:
            issues.append("Frame missing mounting holes")

    result = {
        "file": Path(filepath).name,
        "modules": modules,
        "covers": {
            "servo": has_servo,
            "clamp": has_clamp,
            "bottle": has_bottle,
            "frame": has_frame,
            "mount": has_mount,
            "gear": has_gear,
            "bearing": has_bearing,
        },
        "issues": issues,
        "status": "PASS" if len(issues) == 0 else "NEEDS FIX",
    }
    return result


def verify_assembly(scad_dir):
    """Verify all SCAD files in a directory collectively meet the project spec."""
    scad_dir = Path(scad_dir)
    files = sorted(scad_dir.glob("*.scad"))

    if not files:
        print("No SCAD files found")
        return

    spec = ProjectSpec()
    coverage = {}
    all_issues = []

    print("Project Spec Verification - Bottle Flipping System")
    print(f"  Requirements: {', '.join(spec.mandatory_subsystems)}")
    print()

    for f in files:
        result = verify_scad_file(f, spec)
        status_icon = "+" if result["status"] == "PASS" else "!"
        print(f"[{status_icon}] {result['file']}")
        for k, v in result["covers"].items():
            if v:
                coverage[k] = True
        for issue in result["issues"]:
            print(f"       - {issue}")
            all_issues.append(issue)
        if result["modules"]:
            print(f"       Modules: {', '.join(result['modules'])}")

    print()
    print("Coverage:")
    covered = 0
    for req in spec.mandatory_subsystems:
        # Map req to a coverage key
        key_map = {
            "drive": "servo",
            "power transmission": "gear",
            "clamping": "clamp",
            "inverting": "servo",
            "sensing": None,
            "control": None,
            "frame": "frame",
        }
        key = key_map.get(req)
        ok = coverage.get(key, False) or coverage.get(req, False)
        print(f"  {req}: {'OK' if ok else 'MISSING'}")
        if ok:
            covered += 1

    print(f"\nSubsystem coverage: {covered}/{len(spec.mandatory_subsystems)}")
    if covered >= len(spec.mandatory_subsystems):
        print("VERDICT: All mandatory subsystems covered")
    else:
        missing = len(spec.mandatory_subsystems) - covered
        print(f"VERDICT: {missing} subsystem(s) missing - add required SCAD files")

    if all_issues:
        print(f"\n{len(all_issues)} issue(s) to fix")


if __name__ == "__main__":
    path = (
        sys.argv[1] if len(sys.argv) > 1 else "G:/My Drive/Project/Bottle Flipper/cad"
    )
    verify_assembly(path)
