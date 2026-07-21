#!/usr/bin/env python3
"""
sim-cfd-module.py — Computational Fluid Dynamics Engine

Honours Mechanical Engineering CFD calculations:
- Pipe flow pressure drop (Darcy-Weisbach) with Reynolds number and friction factor
- Boundary layer thickness (flat plate, laminar & turbulent)
- Drag force on immersed bodies
- Bernoulli's equation solver

All formulas use stdlib math only. No numpy dependency.
"""

import math


def read_sim_cfd_pipe(rho, mu, v, D, L, roughness=None):
    """
    Pipe flow analysis using Darcy-Weisbach equation:
    ΔP = f · (L/D) · (ρ·v²/2)

    Reynolds number: Re = ρ·v·D/μ
    Friction factor:
      - Laminar (Re < 2300): f = 64/Re
      - Turbulent (Re >= 4000): f = 0.079·Re⁻⁰·²⁵ (Blasius)
      - Transitional (2300 <= Re < 4000): interpolated

    Args:
        rho: Fluid density (kg/m^3)
        mu: Dynamic viscosity (Pa·s or kg/m·s)
        v: Mean flow velocity (m/s)
        D: Pipe inner diameter (m)
        L: Pipe length (m)
        roughness: Pipe roughness (m), optional (not used in Blasius)

    Returns: Pressure drop, Re, friction factor, regime
    """
    if D <= 0:
        return {"error": "Pipe diameter (D) must be positive"}
    if L <= 0:
        return {"error": "Pipe length (L) must be positive"}
    if rho <= 0 or mu <= 0:
        return {"error": "Density (ρ) and viscosity (μ) must be positive"}
    if v < 0:
        return {"error": "Velocity (v) must be non-negative"}

    Re = rho * v * D / mu

    if Re < 2300:
        regime = "laminar"
        f = 64.0 / Re
    elif Re >= 4000:
        regime = "turbulent"
        f = 0.079 * Re**-0.25
    else:
        regime = "transitional"
        f_lam = 64.0 / 2300.0
        f_turb = 0.079 * 4000.0**-0.25
        t = (Re - 2300.0) / (4000.0 - 2300.0)
        f = f_lam + (f_turb - f_lam) * t

    dp = f * (L / D) * (rho * v * v / 2.0)

    return {
        "pressure_drop_Pa": dp,
        "pressure_drop_bar": dp / 1e5,
        "Reynolds_number": Re,
        "friction_factor": f,
        "flow_regime": regime,
        "inputs": {"rho_kgm3": rho, "mu_Pas": mu, "v_ms": v, "D_m": D, "L_m": L},
        "formula": "ΔP = f·(L/D)·(ρ·v²/2)",
        "units": "Pa (Pascals)",
    }


def read_sim_cfd_boundary(v, x, rho, mu):
    """
    Boundary layer thickness on a flat plate.

    Laminar (Re_x < 5e5):  δ = 5.0·x / √Re_x
    Turbulent (Re_x >= 5e5): δ = 0.37·x / Re_x⁰·²

    Args:
        v: Free-stream velocity (m/s)
        x: Distance from leading edge (m)
        rho: Fluid density (kg/m^3)
        mu: Dynamic viscosity (Pa·s)

    Returns: Boundary layer thickness at x
    """
    if x <= 0:
        return {"error": "Position x must be positive"}
    if rho <= 0 or mu <= 0:
        return {"error": "Density (ρ) and viscosity (μ) must be positive"}
    if v <= 0:
        return {"error": "Velocity (v) must be positive"}

    Re_x = rho * v * x / mu

    if Re_x < 5e5:
        regime = "laminar"
        delta = 5.0 * x / math.sqrt(Re_x)
        formula = "δ = 5.0·x / √Re_x"
    else:
        regime = "turbulent"
        delta = 0.37 * x / (Re_x**0.2)
        formula = "δ = 0.37·x / Re_x⁰·²"

    return {
        "boundary_layer_thickness_m": delta,
        "boundary_layer_thickness_mm": delta * 1000,
        "Reynolds_number_at_x": Re_x,
        "regime": regime,
        "position_x_m": x,
        "inputs": {"v_ms": v, "x_m": x, "rho_kgm3": rho, "mu_Pas": mu},
        "formula": formula,
        "units": "m (meters)",
    }


def read_sim_cfd_drag(rho, v, Cd, A):
    """
    Drag force on an immersed body:
    F_d = 0.5 · ρ · v² · Cd · A

    Args:
        rho: Fluid density (kg/m^3)
        v: Relative velocity (m/s)
        Cd: Drag coefficient (dimensionless)
        A: Reference area (m^2)

    Returns: Drag force in N
    """
    if rho <= 0:
        return {"error": "Density (ρ) must be positive"}
    if A <= 0:
        return {"error": "Reference area (A) must be positive"}
    if v < 0:
        return {"error": "Velocity (v) must be non-negative"}
    if Cd < 0:
        return {"error": "Drag coefficient (Cd) must be non-negative"}

    Fd = 0.5 * rho * v * v * Cd * A

    return {
        "drag_force_N": Fd,
        "inputs": {"rho_kgm3": rho, "v_ms": v, "Cd": Cd, "A_m2": A},
        "formula": "F_d = ½·ρ·v²·Cd·A",
        "units": "N (Newtons)",
    }


def read_sim_cfd_bernoulli(
    P1=None, v1=None, h1=None, P2=None, v2=None, h2=None, rho=1000.0, g=9.81
):
    """
    Bernoulli's equation for steady, incompressible, inviscid flow:
    P1 + ½·ρ·v1² + ρ·g·h1 = P2 + ½·ρ·v2² + ρ·g·h2

    Solves for any ONE unknown given the other 5 values.
    Pass the unknown as None; the other 5 must be provided.

    Args:
        P1: Pressure at point 1 (Pa)
        v1: Velocity at point 1 (m/s)
        h1: Elevation at point 1 (m)
        P2: Pressure at point 2 (Pa)
        v2: Velocity at point 2 (m/s)
        h2: Elevation at point 2 (m)
        rho: Fluid density (kg/m^3), default 1000 (water)
        g: Gravitational acceleration (m/s^2), default 9.81

    Returns: The unknown value with label
    """
    if rho <= 0:
        return {"error": "Density (ρ) must be positive"}
    if g <= 0:
        return {"error": "Gravitational acceleration (g) must be positive"}

    provided = {
        "P1": P1,
        "v1": v1,
        "h1": h1,
        "P2": P2,
        "v2": v2,
        "h2": h2,
    }
    none_keys = [k for k, v in provided.items() if v is None]

    if len(none_keys) != 1:
        return {
            "error": f"Exactly 1 unknown required (found {len(none_keys)} unknowns)"
        }

    unknown = none_keys[0]

    def left():
        return P1 + 0.5 * rho * v1 * v1 + rho * g * h1

    def right():
        return P2 + 0.5 * rho * v2 * v2 + rho * g * h2

    unknown_map = {
        "P1": lambda: right() - 0.5 * rho * v1 * v1 - rho * g * h1,
        "v1": lambda: math.sqrt(2.0 * (right() - P1 - rho * g * h1) / rho),
        "h1": lambda: (right() - P1 - 0.5 * rho * v1 * v1) / (rho * g),
        "P2": lambda: left() - 0.5 * rho * v2 * v2 - rho * g * h2,
        "v2": lambda: math.sqrt(2.0 * (left() - P2 - rho * g * h2) / rho),
        "h2": lambda: (left() - P2 - 0.5 * rho * v2 * v2) / (rho * g),
    }

    value = unknown_map[unknown]()
    unit_map = {"P1": "Pa", "v1": "m/s", "h1": "m", "P2": "Pa", "v2": "m/s", "h2": "m"}

    # Build the known inputs dict
    known = {k: v for k, v in provided.items() if k != unknown}

    return {
        "unknown": unknown,
        "value": value,
        "units": unit_map[unknown],
        "solved_for": unknown,
        "inputs": {**known, "rho_kgm3": rho, "g_ms2": g},
        "formula": "P₁ + ½ρv₁² + ρgh₁ = P₂ + ½ρv₂² + ρgh₂",
    }


def handle_tool_call(name, args):
    if name == "read_sim_cfd_pipe":
        return read_sim_cfd_pipe(
            args.get("rho", 0),
            args.get("mu", 0),
            args.get("v", 0),
            args.get("D", 0),
            args.get("L", 0),
            args.get("roughness"),
        )
    elif name == "read_sim_cfd_boundary":
        return read_sim_cfd_boundary(
            args.get("v", 0), args.get("x", 0), args.get("rho", 0), args.get("mu", 0)
        )
    elif name == "read_sim_cfd_drag":
        return read_sim_cfd_drag(
            args.get("rho", 0), args.get("v", 0), args.get("Cd", 0), args.get("A", 0)
        )
    elif name == "read_sim_cfd_bernoulli":
        return read_sim_cfd_bernoulli(
            P1=args.get("P1"),
            v1=args.get("v1"),
            h1=args.get("h1"),
            P2=args.get("P2"),
            v2=args.get("v2"),
            h2=args.get("h2"),
            rho=args.get("rho", 1000.0),
            g=args.get("g", 9.81),
        )
    return {"error": f"Unknown CFD tool: {name}"}
