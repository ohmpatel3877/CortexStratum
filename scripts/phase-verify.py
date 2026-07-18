#!/usr/bin/env python3
"""Cross-phase verification test. Run after each phase to ensure nothing regressed."""
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
can_call_tool = server.can_call_tool
PERMISSIVE_MODE = server.PERMISSIVE_MODE
check("0", "NOT permissive", PERMISSIVE_MODE is False)
ok, reason = can_call_tool("write_memory_add", {"mode": "auto"})
check("0", "auto-block has fix string", "dry_run" in reason or "permissive" in reason)
ok2, reason2 = can_call_tool("read_memory_search", {"mode": "auto"})
check("0", "read tools work in auto", ok2 is True)

#  Phase 1: Compact Engine 
compact = _load("compact_module", "compact-module.py")
get_token_velocity = compact.get_token_velocity
synthesize = compact.synthesize
session_status = compact.session_status
v = get_token_velocity()
check("1", "token velocity shape", "velocity_5min" in v, str(v["velocity_5min"]))
s = synthesize("Decision: keep this.\n## Header here.\n```python\ncode block\n```\nMore text.")
check("1", "synthesize compresses", s["compressed_length"] > 0)
check("1", "artifact protection", s["protected_blocks"] == 1, f"{s['protected_blocks']} blocks")
check("1", "compression ratio > 0", s["compression_ratio"] > 0)
stat = session_status()
check("1", "status has velocity", "token_velocity" in stat)

#  Phase 4.4: Applied Mechanics 
mech = _load("mechanics_module", "sim-mechanics-module.py")
beam_bending_stress = mech.beam_bending_stress; beam_shear_stress = mech.beam_shear_stress
beam_deflection_point_load = mech.beam_deflection_point_load
column_euler_buckling = mech.column_euler_buckling; column_johnson_buckling = mech.column_johnson_buckling
fatigue_sn_curve = mech.fatigue_sn_curve; fatigue_cycles_to_failure = mech.fatigue_cycles_to_failure
fatigue_goodman_correction = mech.fatigue_goodman_correction; fatigue_miner_rule = mech.fatigue_miner_rule
fastener_shear = mech.fastener_shear; bolt_torque_preload = mech.bolt_torque_preload
bonded_joint_stress = mech.bonded_joint_stress
beam_moment_of_inertia_rect = mech.beam_moment_of_inertia_rect
beam_moment_of_inertia_circle = mech.beam_moment_of_inertia_circle

stress = beam_bending_stress(1000, 0.05, 1.2e-5)
check("4.4", "bending stress", abs(stress["stress_mpa"] - 4.167) < 0.01, f"{stress['stress_mpa']:.2f} MPa")

shear = beam_shear_stress(500, 0.001, 1.2e-5, 0.02)
check("4.4", "shear stress", "stress_pa" in shear, f"{shear['stress_mpa']:.2f} MPa")

deflect = beam_deflection_point_load(1000, 4.0, 200e9, 1.2e-5)
check("4.4", "deflection center", deflect["deflection_mm"] > 0, f"{deflect['deflection_mm']:.3f} mm")

buckle = column_euler_buckling(200e9, 1.2e-5, 1.0, 3.0)
check("4.4", "Euler buckling", buckle["critical_load_kN"] > 0, f"{buckle['critical_load_kN']:.2f} kN")

johnson = column_johnson_buckling(200e9, 250e6, 0.01, 1.0, 2.0, 0.05)
check("4.4", "Johnson buckling", "critical_load_N" in johnson, f"{johnson.get('critical_load_kN', 0):.2f} kN")

sn = fatigue_sn_curve(900e6, -0.12, 10000)
check("4.4", "S-N curve", sn["stress_amplitude_pa"] > 0, f"{sn['stress_amplitude_mpa']:.2f} MPa")

Nf = fatigue_cycles_to_failure(900e6, -0.12, 200e6)
check("4.4", "cycles to failure", Nf["cycles_to_failure"] > 0, f"{Nf['cycles_to_failure']} cycles")

goodman = fatigue_goodman_correction(100e6, 50e6, 400e6, 200e6)
check("4.4", "Goodman safe", goodman["safe"] is True, f"ratio={goodman['goodman_ratio']}")

miner = fatigue_miner_rule([{"cycles": 1000, "cycles_to_failure": 5000}, {"cycles": 2000, "cycles_to_failure": 10000}])
check("4.4", "Miner rule", miner["cumulative_damage_D"] > 0, f"D={miner['cumulative_damage_D']}")

fs = fastener_shear(5000, 0.0001, 4)
check("4.4", "fastener shear", abs(fs["shear_stress_mpa"] - 12.5) < 0.1, f"{fs['shear_stress_mpa']:.2f} MPa")

torque = bolt_torque_preload(0.2, 0.01, 20000)
check("4.4", "bolt torque", abs(torque["torque_Nm"] - 40) < 0.1, f"{torque['torque_Nm']:.1f} Nm")

bond = bonded_joint_stress(1000, 0.05, 0.1)
check("4.4", "bonded joint", bond["shear_stress_pa"] > 0, f"{bond['shear_stress_kpa']:.2f} kPa")

moi_r = beam_moment_of_inertia_rect(0.05, 0.1)
check("4.4", "MOI rect", moi_r["I_m4"] > 0, f"{moi_r['I_m4']:.2e} m4")

moi_c = beam_moment_of_inertia_circle(0.05)
check("4.4", "MOI circle", moi_c["I_m4"] > 0, f"{moi_c['I_m4']:.2e} m4")

#  Phase 2: Mutation Engine 
mutmod = _load("mutation_module", "mutation-module.py")
assess_scope = mutmod.assess_scope; audit_redundancy = mutmod.audit_redundancy
execute_mutation = mutmod.execute_mutation; get_status = mutmod.get_status

scope = assess_scope("debug memory consolidation with compaction")
check("2", "scope domains detected", len(scope["detected_domains"]) > 0, str(scope["detected_domains"]))
check("2", "scope has suggested tools", len(scope["suggested_tools"]) > 0)

audit = audit_redundancy(scope["scope_id"])
check("2", "audit total tools", audit["total_tools"] >= 60, f"{audit['total_tools']} (cache may be stale — run --list-tools to refresh)")
check("2", "audit has clusters", "cluster_count" in audit, str(audit["cluster_count"]))

mut = execute_mutation("verify-test", dry_run=True)
check("2", "mutation dry-run", mut["dry_run"] is True, f"status={mut['status']}")
check("2", "mutation has refactor plan", "refactoring_plan" in mut)

stat = get_status()
check("2", "mutation status", "mutation_count" in stat, str(stat["mutation_count"]))

#  Summary 
print(f"\n{'='*50}")
total = 30
passed = total - len(errors)
print(f"RESULTS: {passed}/{total} passed  ({len(errors)} failed)")
if errors:
    print(f"ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL PHASES VERIFIED — zero regressions")
    sys.exit(0)
