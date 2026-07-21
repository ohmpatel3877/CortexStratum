#!/usr/bin/env python3
"""
sim-fea-module.py — Finite Element Analysis Engine

Honours Mechanical Engineering FEA calculations:
- 1D beam element stiffness matrix (Euler-Bernoulli)
- 1D truss element axial stiffness
- Cantilever beam modal analysis (first natural frequency)
- 1D steady-state heat conduction

All formulas use stdlib math only. No numpy dependency.
"""

import math


def read_sim_fea_beam(E, I, L):
    """
    K = (EI/L³) * [12, 6L, -12, 6L;
                    6L, 4L², -6L, 2L²;
                   -12, -6L, 12, -6L;
                    6L, 2L², -6L, 4L²]

    1D Euler-Bernoulli beam element with 2 nodes, 2 DOF per node (v, θ).

    Args:
        E: Young's modulus (Pa)
        I: Moment of inertia (m^4)
        L: Element length (m)

    Returns: 4x4 stiffness matrix as list of lists + LaTeX
    """
    if L <= 0:
        return {"error": "Element length (L) must be positive"}
    if E <= 0 or I <= 0:
        return {
            "error": "Young's modulus (E) and moment of inertia (I) must be positive"
        }

    EI = E * I
    L2 = L * L
    L3 = L * L * L
    c = EI / L3

    K = [
        [12 * c, 6 * L * c, -12 * c, 6 * L * c],
        [6 * L * c, 4 * L2 * c, -6 * L * c, 2 * L2 * c],
        [-12 * c, -6 * L * c, 12 * c, -6 * L * c],
        [6 * L * c, 2 * L2 * c, -6 * L * c, 4 * L2 * c],
    ]

    latex = (
        "K = \\frac{EI}{L^3} "
        "\\begin{bmatrix}"
        "12 & 6L & -12 & 6L \\\\"
        "6L & 4L^2 & -6L & 2L^2 \\\\"
        "-12 & -6L & 12 & -6L \\\\"
        "6L & 2L^2 & -6L & 4L^2"
        "\\end{bmatrix}"
    )

    return {
        "stiffness_matrix": K,
        "latex": latex,
        "dof": 4,
        "nodes": 2,
        "dof_per_node": 2,
        "inputs": {"E_Pa": E, "I_m4": I, "L_m": L},
        "formula": "K = (EI/L³) * [standard 4x4 beam matrix]",
        "units": "N/m",
    }


def read_sim_fea_truss(E, A, L, F=None):
    """
    Truss element: axial stiffness k = EA/L.
    Stress: σ = F/A.

    Args:
        E: Young's modulus (Pa)
        A: Cross-sectional area (m^2)
        L: Element length (m)
        F: Applied axial force (N), optional

    Returns: Axial stiffness and stress
    """
    if L <= 0:
        return {"error": "Element length (L) must be positive"}
    if A <= 0:
        return {"error": "Cross-sectional area (A) must be positive"}

    k = E * A / L

    result = {
        "axial_stiffness_Nm": k,
        "formula": "k = EA/L",
        "inputs": {"E_Pa": E, "A_m2": A, "L_m": L},
        "units": "N/m",
    }

    if F is not None:
        sigma = F / A
        result["stress_Pa"] = sigma
        result["stress_MPa"] = sigma / 1e6
        result["force_N"] = F
        result["stress_formula"] = "σ = F/A"
        result["stress_units"] = "Pa (Pascals)"

    return result


def read_sim_fea_modal(E, I, rho, A, L):
    """
    First natural frequency of a cantilever beam:
    f1 = (β₁² / 2πL²) * √(EI/ρA)
    where β₁ = 1.875 (first root of characteristic equation)

    Args:
        E: Young's modulus (Pa)
        I: Moment of inertia (m^4)
        rho: Material density (kg/m^3)
        A: Cross-sectional area (m^2)
        L: Beam length (m)

    Returns: First natural frequency (Hz)
    """
    if L <= 0:
        return {"error": "Beam length (L) must be positive"}
    if rho <= 0 or A <= 0:
        return {"error": "Density (ρ) and area (A) must be positive"}
    if E <= 0 or I <= 0:
        return {
            "error": "Young's modulus (E) and moment of inertia (I) must be positive"
        }

    beta1 = 1.875  # First root of cos(βL)·cosh(βL) = -1
    f1 = (beta1**2 / (2 * math.pi * L * L)) * math.sqrt(E * I / (rho * A))

    return {
        "frequency_Hz": f1,
        "frequency_rad_s": f1 * 2 * math.pi,
        "mode": 1,
        "beta_L": beta1,
        "inputs": {"E_Pa": E, "I_m4": I, "rho_kgm3": rho, "A_m2": A, "L_m": L},
        "formula": "f₁ = (β₁² / 2πL²) · √(EI/ρA),  β₁ = 1.875",
        "units": "Hz (Hertz)",
    }


def read_sim_fea_heat(k, A, T1, T2, L):
    """
    1D steady-state heat conduction (Fourier's law):
    q = -k·A·(T2 - T1) / L

    Heat flows from high temperature to low temperature.

    Args:
        k: Thermal conductivity (W/m·K)
        A: Cross-sectional area (m^2)
        T1: Temperature at face 1 (K or °C)
        T2: Temperature at face 2 (K or °C)
        L: Length of conducting path (m)

    Returns: Heat flux and heat transfer rate
    """
    if L <= 0:
        return {"error": "Conduction length (L) must be positive"}
    if A <= 0:
        return {"error": "Cross-sectional area (A) must be positive"}
    if k <= 0:
        return {"error": "Thermal conductivity (k) must be positive"}

    Q = -k * A * (T2 - T1) / L
    q = Q / A  # Heat flux

    return {
        "heat_transfer_rate_W": Q,
        "heat_flux_Wm2": q,
        "inputs": {"k_WmK": k, "A_m2": A, "T1": T1, "T2": T2, "L_m": L},
        "formula": "q = -k·A·(T₂ - T₁) / L",
        "units": "W (Watts)",
    }


def read_sim_fea_stress_recovery(E, strain):
    """Stress recovery from strain: σ = E·ε"""
    stress = E * strain
    return {
        "stress_Pa": stress,
        "stress_MPa": stress / 1e6,
        "formula": "σ = E·ε",
        "units": "Pa",
    }


def handle_tool_call(name, args):
    if name == "read_sim_fea_stress_recovery":
        return read_sim_fea_stress_recovery(args.get("E", 0), args.get("strain", 0))
    if name == "read_sim_fea_beam":
        return read_sim_fea_beam(args.get("E", 0), args.get("I", 0), args.get("L", 0))
    elif name == "read_sim_fea_truss":
        return read_sim_fea_truss(
            args.get("E", 0), args.get("A", 0), args.get("L", 0), args.get("F")
        )
    elif name == "read_sim_fea_modal":
        return read_sim_fea_modal(
            args.get("E", 0),
            args.get("I", 0),
            args.get("rho", 0),
            args.get("A", 0),
            args.get("L", 0),
        )
    elif name == "read_sim_fea_heat":
        return read_sim_fea_heat(
            args.get("k", 0),
            args.get("A", 0),
            args.get("T1", 0),
            args.get("T2", 0),
            args.get("L", 0),
        )
    return {"error": f"Unknown FEA tool: {name}"}
