#!/usr/bin/env python3
"""
sim-mechanics-module.py — Applied Mechanics Simulation Engine

Honours Mechanical Engineering calculations:
- Beam stress analysis (bending, shear)
- Column buckling (Euler, Johnson)
- Fatigue life estimation (S-N, Goodman, Miner)
- Fastener/joint stress

All formulas use stdlib math only. No numpy dependency.
"""

import math

#
# Beam Stress Analysis
#


def beam_bending_stress(moment, distance_neutral, I):
    """
    σ = M*y / I

    Args:
        moment: Bending moment (N·m)
        distance_neutral: Distance from neutral axis (m)
        I: Moment of inertia (m^4)

    Returns: Bending stress (Pa)
    """
    if I == 0:
        return {"error": "Moment of inertia (I) cannot be zero"}
    stress = moment * distance_neutral / I
    return {
        "stress_pa": stress,
        "stress_mpa": stress / 1e6,
        "formula": "σ = M*y / I",
        "units": "Pa (Pascals)",
    }


def beam_shear_stress(shear_force, Q, I, width):
    """
    τ = V*Q / (I*b)

    Args:
        shear_force: Internal shear force (N)
        Q: First moment of area (m^3)
        I: Moment of inertia (m^4)
        width: Width at point of interest (m)

    Returns: Shear stress (Pa)
    """
    if I == 0 or width == 0:
        return {"error": "Moment of inertia (I) and width (b) must be non-zero"}
    stress = shear_force * Q / (I * width)
    return {
        "stress_pa": stress,
        "stress_mpa": stress / 1e6,
        "formula": "τ = V*Q / (I*b)",
        "units": "Pa (Pascals)",
    }


def beam_deflection_point_load(load, length, E, I, position=None):
    """
    Maximum deflection of simply supported beam with point load at center.
    δ_max = P*L^3 / (48*E*I)

    For off-center load: δ = P*b*x*(L^2 - x^2 - b^2) / (6*E*I*L)
    where a + b = L, x is position of interest

    Args:
        load: Point load (N)
        length: Beam length (m)
        E: Young's modulus (Pa)
        I: Moment of inertia (m^4)
        position: Dict with 'a' (distance from left support to load, m)
                  and 'x' (position of interest, m), or None for center load

    Returns: Deflection (m)
    """
    if E == 0 or I == 0:
        return {
            "error": "Young's modulus (E) and moment of inertia (I) must be non-zero"
        }

    if position is None:
        # Center load
        deflection = load * length**3 / (48 * E * I)
        formula = "δ_max = P*L³ / (48*E*I)"
    else:
        a = position.get("a", length / 2)
        x = position.get("x", length / 2)
        b = length - a
        if x <= a:
            deflection = load * b * x * (length**2 - x**2 - b**2) / (6 * E * I * length)
        else:
            deflection = (
                load
                * a
                * (length - x)
                * (2 * length * x - x**2 - a**2)
                / (6 * E * I * length)
            )
        formula = "δ = P*b*x*(L² - x² - b²) / (6*E*I*L)"

    return {
        "deflection_m": deflection,
        "deflection_mm": deflection * 1000,
        "formula": formula,
        "units": "m (meters)",
    }


def beam_moment_of_inertia_rect(width, height):
    """
    I = b*h^3 / 12
    For a rectangular cross-section about its centroidal axis.
    """
    I = width * height**3 / 12
    return {
        "I_m4": I,
        "formula": "I = b*h³ / 12",
        "section": "rectangular",
        "units": "m^4",
    }


def beam_moment_of_inertia_circle(diameter):
    """
    I = π*d^4 / 64
    For a circular cross-section about its centroidal axis.
    """
    I = math.pi * diameter**4 / 64
    return {
        "I_m4": I,
        "formula": "I = π*d⁴ / 64",
        "section": "circular",
        "units": "m^4",
    }


#
# Column Buckling
#


def column_euler_buckling(E, I, K, L):
    """
    P_cr = π²*E*I / (K*L)²

    Args:
        E: Young's modulus (Pa)
        I: Moment of inertia (m^4)
        K: Effective length factor (1.0 pinned-pinned, 0.5 fixed-fixed,
           0.7 fixed-pinned, 2.0 fixed-free)
        L: Actual column length (m)

    Returns: Critical buckling load (N)
    """
    if K * L == 0:
        return {"error": "Effective length (K*L) cannot be zero"}
    KL = K * L
    P_cr = math.pi**2 * E * I / (KL**2)
    slenderness = (
        L / math.sqrt(I / (math.pi * (I * 4 / math.pi) ** 0.5)) if I > 0 else 0
    )
    return {
        "critical_load_N": P_cr,
        "critical_load_kN": P_cr / 1000,
        "slenderness_ratio": round(slenderness, 2),
        "effective_length_m": KL,
        "formula": "P_cr = π²*E*I / (K*L)²",
        "buckling_regime": "Euler (long column)"
        if slenderness > 100
        else "Transitional",
        "units": "N (Newtons)",
    }


def column_johnson_buckling(E, sigma_y, A, K, L, r):
    """
    Johnson's parabolic formula for intermediate columns:
    P_cr/A = σ_y - (σ_y/(2π))² * (KL/r)²

    Valid when slenderness ratio (KL/r) < sqrt(2π²E/σ_y)

    Args:
        E: Young's modulus (Pa)
        sigma_y: Yield strength (Pa)
        A: Cross-sectional area (m^2)
        K: Effective length factor
        L: Actual length (m)
        r: Radius of gyration (m)

    Returns: Critical buckling load (N)
    """
    if r == 0:
        return {"error": "Radius of gyration (r) cannot be zero"}
    KL_r = K * L / r
    transition = math.sqrt(2 * math.pi**2 * E / sigma_y)

    if KL_r >= transition:
        # Use Euler instead
        I = A * r**2
        return column_euler_buckling(E, I, K, L)

    P_cr = A * (sigma_y - (sigma_y / (2 * math.pi)) ** 2 * (KL_r) ** 2)
    return {
        "critical_load_N": P_cr,
        "critical_load_kN": P_cr / 1000,
        "slenderness_ratio": round(KL_r, 2),
        "transition_slenderness": round(transition, 2),
        "regime": "Johnson (intermediate column)" if KL_r < transition else "Use Euler",
        "formula": "P_cr/A = σ_y - (σ_y/(2π))² * (KL/r)²",
        "units": "N (Newtons)",
    }


def column_critical_stress(P_cr, A):
    """σ_cr = P_cr / A"""
    if A == 0:
        return {"error": "Cross-sectional area (A) cannot be zero"}
    sigma = P_cr / A
    return {
        "critical_stress_pa": sigma,
        "critical_stress_mpa": sigma / 1e6,
        "formula": "σ_cr = P_cr / A",
        "units": "Pa (Pascals)",
    }


#
# Fatigue Analysis
#


def fatigue_sn_curve(Sf_prime, b, N):
    """
    Basquin's equation: S = Sf' * (2N)^b

    Args:
        Sf_prime: Fatigue strength coefficient (Pa)
        b: Fatigue strength exponent (typical -0.05 to -0.15)
        N: Number of cycles to failure

    Returns: Stress amplitude (Pa)
    """
    if N <= 0:
        return {"error": "Number of cycles (N) must be positive"}
    S = Sf_prime * (2 * N) ** b
    return {
        "stress_amplitude_pa": S,
        "stress_amplitude_mpa": S / 1e6,
        "cycles": N,
        "formula": "S = Sf' * (2N)^b",
        "units": "Pa (Pascals)",
    }


def fatigue_cycles_to_failure(Sf_prime, b, stress_amplitude):
    """
    Reverse Basquin: N = (S / Sf')^(1/b) / 2
    """
    if stress_amplitude <= 0:
        return {"error": "Stress amplitude must be positive"}
    if Sf_prime <= 0:
        return {"error": "Fatigue strength coefficient must be positive"}
    ratio = stress_amplitude / Sf_prime
    N = ratio ** (1 / b) / 2
    return {
        "cycles_to_failure": round(N),
        "log_cycles": round(math.log10(N), 2),
        "formula": "N = (S / Sf')^(1/b) / 2",
    }


def fatigue_goodman_correction(S_alt, S_mean, S_ut, S_e):
    """
    Goodman mean stress correction:
    (S_alt / S_e) + (S_mean / S_ut) = 1

    Returns equivalent fully-reversed stress amplitude.

    Args:
        S_alt: Alternating stress (Pa)
        S_mean: Mean stress (Pa)
        S_ut: Ultimate tensile strength (Pa)
        S_e: Endurance limit (Pa)
    """
    if S_ut == 0 or S_e == 0:
        return {"error": "S_ut and S_e must be non-zero"}
    ratio = S_alt / S_e + S_mean / S_ut
    safe = ratio <= 1.0
    return {
        "goodman_ratio": round(ratio, 4),
        "safe": safe,
        "margin": round(1 - ratio, 4) if safe else round(ratio - 1, 4),
        "status": "SAFE"
        if safe
        else f"FAILS (exceeds by {round((ratio - 1) * 100, 1)}%)",
        "equivalent_alternating_pa": S_alt / (1 - S_mean / S_ut)
        if S_mean < S_ut
        else float("inf"),
        "formula": "(S_alt / S_e) + (S_mean / S_ut) <= 1",
    }


def fatigue_miner_rule(blocks):
    """
    Miner's cumulative damage rule:
    D = Σ(n_i / N_i)

    Args:
        blocks: List of dicts with 'cycles' and 'cycles_to_failure'

    Returns: Cumulative damage D (D >= 1 means failure)
    """
    if not blocks:
        return {"error": "At least one load block required"}
    D = 0
    details = []
    for i, block in enumerate(blocks):
        n = block.get("cycles", 0)
        N = block.get("cycles_to_failure", 0)
        if N == 0:
            return {"error": f"Block {i}: cycles_to_failure cannot be zero"}
        damage = n / N
        D += damage
        details.append(
            {
                "block": i,
                "cycles": n,
                "cycles_to_failure": N,
                "damage_fraction": round(damage, 4),
            }
        )
    return {
        "cumulative_damage_D": round(D, 4),
        "status": "FAILED (D >= 1)"
        if D >= 1
        else f"SAFE (D < 1, remaining life factor: {round(1 / D - 1, 4) if D > 0 else 'inf'})",
        "blocks_analyzed": len(blocks),
        "block_details": details,
        "formula": "D = Σ(n_i / N_i)",
    }


#
# Fastener / Joint Stress
#


def fastener_shear(force, area, num_fasteners=1):
    """
    τ = F / (A * n)
    """
    if area == 0:
        return {"error": "Area cannot be zero"}
    if num_fasteners <= 0:
        return {"error": "Number of fasteners must be positive"}
    stress = force / (area * num_fasteners)
    return {
        "shear_stress_pa": stress,
        "shear_stress_mpa": stress / 1e6,
        "total_area": area * num_fasteners,
        "formula": "τ = F / (A * n)",
        "units": "Pa (Pascals)",
    }


def bolt_torque_preload(K, D, F):
    """
    T = K * D * F

    Args:
        K: Nut factor (typically 0.2 for plain, 0.3 for lubricated)
        D: Nominal bolt diameter (m)
        F: Desired preload (N)
    """
    T = K * D * F
    return {"torque_Nm": T, "formula": "T = K*D*F", "units": "N·m"}


#
# Glue / Bonded Joint
#


def bonded_joint_stress(force, width, overlap_length):
    """
    τ_avg = F / (w * L)

    Average shear stress in a bonded lap joint.
    (Covers wood glue / rabbet joint use case from Master Spec)
    """
    area = width * overlap_length
    if area == 0:
        return {"error": "Bond area (width * length) cannot be zero"}
    stress = force / area
    return {
        "shear_stress_pa": stress,
        "shear_stress_kpa": stress / 1000,
        "bond_area_m2": area,
        "formula": "τ_avg = F / (w * L)",
        "units": "Pa (Pascals)",
    }


#
# Handler Dispatch
#


def handle_tool_call(name, args):
    #  Merged: Fatigue (sn + cycles → solve_for)
    if name == "read_sim_mech_fatigue":
        solve_for = args.get("solve_for", "stress")
        if solve_for == "cycles":
            return fatigue_cycles_to_failure(
                args.get("Sf_prime", 0),
                args.get("b", -0.1),
                args.get("stress_amplitude", 0),
            )
        return fatigue_sn_curve(
            args.get("Sf_prime", 0), args.get("b", -0.1), args.get("N", 1000)
        )

    #  Merged: Buckling (Euler + Johnson → auto-select)
    if name == "read_sim_mech_buckle":
        # If Johnson params provided (sigma_y, A, r), auto-select
        if args.get("sigma_y") and args.get("A") and args.get("r"):
            return column_johnson_buckling(
                args.get("E", 0),
                args.get("sigma_y", 0),
                args.get("A", 0),
                args.get("K", 1.0),
                args.get("L", 0),
                args.get("r", 0),
            )
        return column_euler_buckling(
            args.get("E", 0), args.get("I", 0), args.get("K", 1.0), args.get("L", 0)
        )

    #  Merged: Moment of Inertia (rect + circle → shape param)
    if name == "read_sim_mech_moi":
        shape = args.get("shape", "rect")
        if shape == "circle":
            return beam_moment_of_inertia_circle(args.get("diameter", 0))
        return beam_moment_of_inertia_rect(args.get("width", 0), args.get("height", 0))

    #  Standard tools
    if name == "read_sim_mech_stress":
        return beam_bending_stress(
            args.get("moment", 0), args.get("distance_neutral", 0), args.get("I", 0)
        )
    elif name == "read_sim_mech_shear":
        return beam_shear_stress(
            args.get("shear_force", 0),
            args.get("Q", 0),
            args.get("I", 0),
            args.get("width", 0),
        )
    elif name == "read_sim_mech_deflection":
        return beam_deflection_point_load(
            args.get("load", 0),
            args.get("length", 0),
            args.get("E", 0),
            args.get("I", 0),
            args.get("position"),
        )
    # Backward compat: old fatigue/buckle/MOI names still work
    elif name == "read_sim_mech_buckle_johnson":
        return column_johnson_buckling(
            args.get("E", 0),
            args.get("sigma_y", 0),
            args.get("A", 0),
            args.get("K", 1.0),
            args.get("L", 0),
            args.get("r", 0),
        )
    elif name == "read_sim_mech_fatigue_sn":
        return fatigue_sn_curve(
            args.get("Sf_prime", 0), args.get("b", -0.1), args.get("N", 1000)
        )
    elif name == "read_sim_mech_fatigue_cycles":
        return fatigue_cycles_to_failure(
            args.get("Sf_prime", 0),
            args.get("b", -0.1),
            args.get("stress_amplitude", 0),
        )
    elif name == "read_sim_mech_moi_rect":
        return beam_moment_of_inertia_rect(args.get("width", 0), args.get("height", 0))
    elif name == "read_sim_mech_moi_circle":
        return beam_moment_of_inertia_circle(args.get("diameter", 0))
    elif name == "read_sim_mech_fatigue_goodman":
        return fatigue_goodman_correction(
            args.get("S_alt", 0),
            args.get("S_mean", 0),
            args.get("S_ut", 0),
            args.get("S_e", 0),
        )
    elif name == "read_sim_mech_fatigue_miner":
        return fatigue_miner_rule(args.get("blocks", []))
    elif name == "read_sim_mech_fastener_shear":
        return fastener_shear(
            args.get("force", 0), args.get("area", 0), args.get("num_fasteners", 1)
        )
    elif name == "read_sim_mech_bolt_torque":
        return bolt_torque_preload(
            args.get("K", 0.2), args.get("D", 0), args.get("F", 0)
        )
    elif name == "read_sim_mech_bonded_joint":
        return bonded_joint_stress(
            args.get("force", 0), args.get("width", 0), args.get("overlap_length", 0)
        )
    return {"error": f"Unknown mechanics tool: {name}"}
