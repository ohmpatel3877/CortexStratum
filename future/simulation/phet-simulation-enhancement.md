# PhET-Inspired Simulation Enhancement

**Status:** Spec only.  
**Goal:** Transform the 4 simulation engines (mechanics, FEA, CFD, math) from formula-crunching tools into interactive, visually-guided, educationally-sound simulations modeled after PhET Colorado (https://phet.colorado.edu).

## Vision

PhET Interactive Simulations (University of Colorado Boulder) are the gold standard for educational engineering/physics simulations. They succeed because:

- **Direct manipulation** — Drag beams, resize loads, twist dials, see results change in real-time
- **Visual primacy** — Force vectors, stress contours, flow lines drawn on the object itself
- **Progressive disclosure** — Start simple, reveal formulas/numbers on demand
- **Research-based** — Every sim is user-tested; controls match how people actually learn
- **No walls** — No signup, no paywall, no install — open instantly in a browser

CortexStratum's simulation engines currently output JSON numbers and ASCII formulas. This spec bridges that gap.

## Current State

| Engine | Tools | Output | PhET Gap |
|--------|-------|--------|----------|
| Mechanics | 14 (stress, buckling, fatigue, fasteners, MOI) | JSON + formula string | No beam visualization, no interactive load adjustment, no real-time stress contour |
| FEA | 4 (beam element, truss, modal, heat) | JSON matrix + eigenvals | No mesh visualization, no deformation animation, no mode shape display |
| CFD | 4 (pipe flow, boundary layer, drag, Bernoulli) | JSON pressure/velocity | No pipe geometry, no flow animation, no Reynolds regime visualization |
| Math | 4 (matrix solve, ODE, ASCII plot, LaTeX) | JSON + ASCII art | No interactive function plotting, no slider-driven parameter exploration |

## Key Enhancements

### 1. Visualization Layer (all engines)

Add an **ASCII + Mermaid + SVG output mode** to every simulation tool, gated by a `visual=true` parameter. Default: JSON only (backward compatible). With `visual=true`, return:

```
{
  "stress_mpa": 4.17,
  "visual": {
    "type": "mermaid",
    "diagram": "graph LR\n  Load-->Beam\n  Beam-->Support",
    "ascii": "  ↓ 1000N\n  ────────\n  ▲      ▲",
    "description": "Simply supported beam with point load at center"
  }
}
```

### 2. Interactive Parameter Exploration (parameter sweep)

Each simulation tool gains a `sweep` parameter — an array of parameter names + ranges to sweep over. Returns a table of results instead of a single output:

```
read_sim_mech_stress(moment=[100, 500, 1000], distance_neutral=0.05, I=1.2e-5, sweep=["moment"])
→ {
  "sweep": [
    {"moment": 100, "stress_mpa": 0.42},
    {"moment": 500, "stress_mpa": 2.08},
    {"moment": 1000, "stress_mpa": 4.17}
  ],
  "trend": "linear (σ ∝ M)",
  "visual": {"type": "ascii_plot", "data": "stress vs moment"}
}
```

### 3. Educational Context (explain + compare)

Each tool returns an `education` block when `explain=true`:

```
{
  "stress_mpa": 4.17,
  "education": {
    "formula": "σ = M*y / I",
    "derivation": "Bending stress is maximum at the outermost fiber...",
    "units": "MPa (megapascals) = 10⁶ N/m²",
    "real_world": "A 4 MPa stress is comparable to the weight of a small car on a 1cm² area",
    "common_mistakes": [
      "Using diameter instead of radius for circular cross-sections",
      "Confusing area moment of inertia (I) with polar moment (J)"
    ],
    "analogy": "Think of the beam as a stack of paper sheets — the top sheets stretch, bottom sheets compress",
    "phet_link": "https://phet.colorado.edu/sims/html/bending-light/latest/bending-light_en.html"
  }
}
```

### 4. Material Library (shared across all simulation engines)

Add a `read_sim_material_library` tool with pre-loaded material properties:

```
read_sim_material_library(material="steel_astm_a36")
→ {
  "E": 200e9,        // Young's modulus (Pa)
  "G": 79.3e9,       // Shear modulus (Pa)
  "nu": 0.26,        // Poisson's ratio
  "sigma_yield": 250e6,  // Yield strength (Pa)
  "sigma_ult": 400e6,    // Ultimate tensile strength (Pa)
  "rho": 7850,            // Density (kg/m³)
  "alpha": 1.2e-5,       // Thermal expansion (1/K)
  "typical_uses": ["Structural beams", "Automotive frames", "Pressure vessels"],
  "educational_note": "A36 is the most common structural steel in the US — it's what skyscrapers are made of"
}
```

Initial library: aluminum_6061, copper, brass, titanium_6al4v, concrete_30mpa, wood_douglas_fir, ABS, PLA, nylon.

### 5. Real-Time "What If" Mode

Add a `read_sim_mech_whatif` tool that accepts a base configuration + one changed parameter, returns the delta:

```
read_sim_mech_whatif(
  base={"beam_type": "simply_supported", "load": 1000, "span": 3, "section": "W200x52"},
  change={"span": 4.5}
)
→ {
  "delta": {"max_stress": "+50%", "deflection": "+125%", "buckling_load": "-44%"},
  "explanation": "Doubling the span increases deflection by ~8x (L³ relationship)",
  "visual": "overlay diagram showing original vs lengthened beam deformation"
}
```

## Implementation Order

### Phase 1 — Foundation (stdlib only, no new deps)
1. **Visual output mode** — Add `visual=true` to all 26 simulation tools, return ASCII diagrams + Mermaid graphs
2. **Educational context** — Add `explain=true` block with formula, derivation, analogy, common mistakes
3. **Material library** — `read_sim_material_library` tool with ~20 common materials
4. **Sweep mode** — Parameter sweep across any numeric input

### Phase 2 — Interactivity (requires code restructure)
5. **What-If tool** — `read_sim_mech_whatif` / `read_sim_cfd_whatif` / `read_sim_fea_whatif`
6. **Cross-section visualizer** — ASCII/Mermaid rendering of I-beam, channel, angle, tube sections
7. **Load case composer** — Combine multiple loads (point, distributed, moment) on a single beam
8. **Buckling mode shapes** — Visualize Euler buckling modes 1-4

### Phase 3 — Advanced (requires numpy + optionally matplotlib)
9. **SVG/HTML output** — Generate proper scalable beam diagrams with force vectors
10. **Stress contour overlay** — Heat-map style ASCII shading of stress distribution
11. **Frequency response curves** — For modal analysis (FEA)
12. **Flow regime animation** — Laminar → turbulent transition visualization (CFD)

## Architecture

### New Files

```
engine/simulation/
  sim-visualizer.py        ← Shared visualization helpers (ASCII, Mermaid, SVG)
  sim-material-library.py  ← Material property database
  sim-whatif.py            ← What-If delta calculator
  sim-education.py         ← Educational context templates
```

### Modified Files

```
engine/simulation/sim-mechanics-module.py  ← Add visual/explain/sweep params
engine/simulation/sim-fea-module.py        ← Add visual/explain/sweep params
engine/simulation/sim-cfd-module.py        ← Add visual/explain/sweep params
engine/simulation/sim-math-module.py       ← Add visual/explain/sweep params
scripts/tools-mcp-server.py                ← Register new tools
```

### Tool Registration

New tools to register in the MCP server:

| Tool | Phase | Permission |
|------|-------|------------|
| `read_sim_material_library` | 1 | read |
| `read_sim_mech_whatif` | 2 | read |
| `read_sim_cfd_whatif` | 2 | read |
| `read_sim_fea_whatif` | 2 | read |
| `read_sim_visualize_beam` | 3 | read |
| `read_sim_visualize_flow` | 3 | read |

### Naming Convention Fix

Current mismatch between server registration and module dispatch (resolved via audit):
- Server has merged tools: `beam_analysis`, `joint`
- Module has individual: `stress`, `shear`, `deflection`, `fastener_shear`, `bolt_torque`, `bonded_joint`

**Fix:** Phase 1 must reconcile these. Register all individual tools in the server. Keep `beam_analysis` and `joint` as convenience wrappers that call the individual tools in sequence.

## Dependencies

- **Phase 1**: stdlib only (no new deps)
- **Phase 2**: stdlib only
- **Phase 3**: `numpy` for numerical work, `matplotlib` for SVG rendering (optional, graceful fallback)

## References

- PhET Homepage: https://phet.colorado.edu
- PhET Research: https://phet.colorado.edu/en/research
- PhET Design Process: https://phet.colorado.edu/en/design
- Current simulation README limits: See README.md "Simulation limits" section
- Naming audit: resolved — findings documented in spec above
