# CAD Workshop Skill

Integrates the ai-memory-core cad-module for mechanical design validation, STL export, FEA analysis, and OpenSCAD project verification.

## When to use

Use when designing, validating, debugging, or exporting mechanical CAD files in OpenSCAD. Especially for multi-part assemblies with mechanical requirements.

## Steps

### Step 1: Validate SCAD files

Run the validator on all SCAD files:

```bash
python <cad-module>/cad_validator.py <path>
```

Checks: brace balance, unused vars, undefined modules, OpenSCAD pitfalls, $fn setting.

### Step 2: Structural FEA Analysis

Run the FEA analyzer to verify structural adequacy:

```bash
python <cad-module>/fea_analyzer.py --all
```

Checks: beam bending stress, column buckling, bolt shear, servo torque, safety factors.

### Step 3: Project Spec Verification

Verify all SCAD files collectively meet project requirements:

```bash
python <cad-module>/project_verifier.py <path>
```

Checks: mandatory subsystem coverage, dimensional sanity, mounting provisions.

### Step 4: Create Assembly SCAD

Generate an assembly.scad that positions all parts relative to each other using translate/rotate.

### Step 5: Export to STL

Batch export all SCAD files to STL for 3D printing:

```bash
python <cad-module>/cad_exporter.py <path> -q high
```

## Base directory

`C:\Users\ohmpa\github\ai-memory-core\cad-module\`
