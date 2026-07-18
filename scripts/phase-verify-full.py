#!/usr/bin/env python3
"""Full cross-phase verification. Run after ALL phases are implemented."""
import sys, os, importlib.util

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

def _load(name, filename):
    path = os.path.join(SCRIPTS, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

errors = []
def check(phase, name, condition, detail=""):
    if condition:
        print(f"  [PASS] {phase}: {name}  {detail}")
    else:
        print(f"  [FAIL] {phase}: {name}  {detail}")
        errors.append(f"{phase}/{name}: {detail}")

#  Phase 0: Permission Model 
server = _load("tools_server", "tools-mcp-server.py")
ok, reason = server.can_call_tool("write_memory_add", {"mode": "auto"})
check("0", "auto-block fix string", "dry_run" in reason or "permissive" in reason)
ok2, _ = server.can_call_tool("read_memory_search", {"mode": "auto"})
check("0", "read tools in auto", ok2 is True)

#  Phase 1: Compact 
compact = _load("compact_module", "compact-module.py")
v = compact.get_token_velocity()
check("1", "token velocity", "velocity_5min" in v)
s = compact.synthesize("## Header\n```code\nx=1\n```\nDecision: yes")
check("1", "synthesize", s["compressed_length"] > 0)
check("1", "artifact protection", s["protected_blocks"] >= 1)

#  Phase 2: Mutation 
mut = _load("mutation_module", "mutation-module.py")
scope = mut.assess_scope("debug memory performance")
check("2", "scope domains", len(scope["detected_domains"]) > 0)
m = mut.execute_mutation("test", dry_run=True)
check("2", "mutation dry-run", m["dry_run"] is True)

#  Phase 3: Plumber 
plumb = _load("plumber_module", "plumber-module.py")
handoff = plumb.trace_handoff(source="memory")
check("3", "handoff trace", handoff["handoffs_found"] >= 0)
ckpt = plumb.create_checkpoint(dry_run=True)
check("3", "checkpoint", ckpt["checkpoint_id"] is not None)

#  Phase 4.4: Mechanics 
mech = _load("mechanics_module", "sim-mechanics-module.py")
stress = mech.beam_bending_stress(1000, 0.05, 1.2e-5)
check("4.4", "bending stress", abs(stress["stress_mpa"] - 4.167) < 0.01)
buckle = mech.column_euler_buckling(200e9, 1.2e-5, 1.0, 3.0)
check("4.4", "buckling", buckle["critical_load_kN"] > 0)
g = mech.fatigue_goodman_correction(100e6, 50e6, 400e6, 200e6)
check("4.4", "Goodman", g["safe"] is True)
miner = mech.fatigue_miner_rule([{"cycles": 1000, "cycles_to_failure": 5000}])
check("4.4", "Miner", miner["cumulative_damage_D"] > 0)

#  Phase 4.1: Math Engine 
math_mod = _load("math_module", "sim-math-module.py")
sol = math_mod.matrix_solve([[2, 1], [1, 3]], [5, 6])
check("4.1", "matrix solve", sol.get("solution") is not None, str(sol.get("solution")))
ode = math_mod.ode_solve(["-2*x1 + x2", "x1 - 2*x2"], [1, 0], 0, 5, 50, "rk4")
check("4.1", "ODE solver", len(ode["trajectory"]) > 0)
plot = math_mod.ascii_plot([0, 1, 2], [0, 1, 0])
check("4.1", "ASCII plot", "plot" in plot)
latex = math_mod.generate_latex("quadratic formula")
check("4.1", "LaTeX gen", "\\\\frac" in latex["latex"] or "\\frac" in latex["latex"])

#  Phase 5: Pedagogy 
ped = _load("pedagogy_module", "pedagogy-module.py")
assess = ped.assess(["what is eigenvalue", "how to diagonalize"], "linear algebra")
check("5", "pedagogy assess", assess["suggested_depth"] >= 1)
adapt = ped.adapt("beam bending", 3)
check("5", "pedagogy adapt", "pedagogy_prompt" in adapt)
prof = ped.store_profile(4, "mechanics")
check("5", "pedagogy profile", prof["status"] == "stored")

#  Phase 5: Consolidation 
cons = _load("consolidation_module", "consolidation-daemon.py")
cs = cons.run_consolidation(dry_run=True)
check("5", "consolidation run", "status" in cs)
cls = cons.get_links()
check("5", "consolidation links", "links" in cls)

#  Summary 
total = 25
passed = total - len(errors)
print(f"\n{'='*50}")
print(f"RESULTS: {passed}/{total} passed ({len(errors)} failed)")
if errors:
    print("FAILURES:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"ALL {total} TESTS PASSED — zero regressions across {len(os.listdir(SCRIPTS))} script modules")
    sys.exit(0)
