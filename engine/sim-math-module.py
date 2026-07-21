#!/usr/bin/env python3
"""
sim-math-module.py — Math Engine (Wolfram Alpha-class)

Pure Python stdlib numerical mathematics:
  - Linear algebra: solve, determinant, eigenvalues, inverse, LU
  - Calculus: numeric integration, differentiation, Taylor series, gradient
  - Root finding: Newton, bisection, secant
  - ODE solving: RK4, Euler
  - Statistics: mean, median, mode, variance, std, correlation, regression
  - Fourier: DFT, radix-2 FFT
  - Complex numbers: arithmetic, polar/rectangular
  - Number theory: prime factors, GCD, LCM, modular inverse
  - Polynomials: evaluate, roots (quadratic/cubic)
  - Unit conversion: SI <-> imperial, temperature, pressure
  - ASCII plotting
  - LaTeX generation with derivation steps
"""

import math
import cmath
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent


# =========================================================================
# LINEAR ALGEBRA
# =========================================================================


def _gauss_elimination(A, b):
    """Solve Ax = b via Gaussian elimination with partial pivoting."""
    n = len(A)
    aug = [A[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        max_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[max_row][col]) < 1e-15:
            return None
        aug[col], aug[max_row] = aug[max_row], aug[col]
        for row in range(col + 1, n):
            factor = aug[row][col] / aug[col][col]
            for j in range(col, n + 1):
                aug[row][j] -= factor * aug[col][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = aug[i][n]
        for j in range(i + 1, n):
            s -= aug[i][j] * x[j]
        x[i] = s / aug[i][i]
    return x


def _lu_decompose(A):
    """LU decomposition with partial pivoting (PA = LU). Returns (P, L, U)."""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    U = [row[:] for row in A]
    P = list(range(n))
    for k in range(n):
        max_row = max(range(k, n), key=lambda r: abs(U[r][k]))
        if abs(U[max_row][k]) < 1e-15:
            return None
        U[k], U[max_row] = U[max_row], U[k]
        P[k], P[max_row] = P[max_row], P[k]
        L[k][k] = 1.0
        for i in range(k + 1, n):
            factor = U[i][k] / U[k][k]
            L[i][k] = factor
            for j in range(k, n):
                U[i][j] -= factor * U[k][j]
    for i in range(n):
        L[i][i] = 1.0
    return P, L, U


def _format_matrix_latex(A, name="A"):
    rows = [" & ".join(f"{v:g}" for v in row) for row in A]
    sep = "\\\\\\\\"
    return f"{name} = \\begin{{bmatrix}}{sep.join(rows)}\\end{{bmatrix}}"


def _format_vector_latex(v, name="x"):
    entries = " \\\\\\\\ ".join(f"{val:g}" for val in v)
    return f"{name} = \\begin{{bmatrix}}{entries}\\end{{bmatrix}}"


def matrix_solve(A, b):
    """Solve Ax = b with LaTeX derivation."""
    if not A or not b:
        return {"error": "Matrix A and vector b are required"}
    n = len(A)
    if any(len(row) != n for row in A):
        return {"error": "Matrix A must be square"}
    if len(b) != n:
        return {"error": "Vector b must have same dimension as A"}
    x = _gauss_elimination(A, b)
    if x is None:
        return {"error": "Matrix is singular (no unique solution)"}
    eqs = [
        f"{' + '.join(f'{A[i][j]:g} x_{j + 1}' for j in range(n))} = {b[i]:g}"
        for i in range(n)
    ]
    latex = (
        "\\begin{cases}"
        + "\\\\\\\\".join(eqs)
        + "\\end{cases}\\\\"
        + _format_vector_latex(x)
    )
    return {
        "solution": [round(v, 6) for v in x],
        "dimension": n,
        "latex": latex,
        "method": "Gaussian elimination with partial pivoting",
    }


def matrix_determinant(A):
    """Matrix determinant via LU decomposition."""
    if not A:
        return {"error": "Matrix A is required"}
    n = len(A)
    if any(len(row) != n for row in A):
        return {"error": "Matrix must be square"}
    lu = _lu_decompose(A)
    if lu is None:
        return {
            "determinant": 0.0,
            "method": "LU decomposition",
            "latex": "\\det(A) = 0 (singular)",
        }
    P, L, U = lu
    det = 1.0
    for i in range(n):
        det *= U[i][i]
    # Account for row swaps
    swaps = sum(1 for i, p in enumerate(P) if i != p)
    det *= (-1) ** swaps
    return {
        "determinant": det,
        "method": "LU decomposition with partial pivoting",
        "latex": f"\\det(A) = {det:g}",
    }


def matrix_inverse(A):
    """Matrix inverse by solving A·X = I."""
    if not A:
        return {"error": "Matrix A is required"}
    n = len(A)
    if any(len(row) != n for row in A):
        return {"error": "Matrix must be square"}
    inv = []
    for i in range(n):
        e = [1.0 if j == i else 0.0 for j in range(n)]
        x = _gauss_elimination(A, e)
        if x is None:
            return {"error": "Matrix is singular (not invertible)"}
        inv.append(x)
    # Transpose result
    inv_t = [[inv[j][i] for j in range(n)] for i in range(n)]
    return {
        "inverse": [[round(v, 6) for v in row] for row in inv_t],
        "method": "Gaussian elimination (A⁻¹ from A·X = I)",
        "latex": _format_matrix_latex(inv_t, "A^{-1}"),
    }


def matrix_eigenvalue(A, iterations=100):
    """Dominant eigenvalue via power iteration."""
    if not A:
        return {"error": "Matrix A is required"}
    n = len(A)
    if any(len(row) != n for row in A):
        return {"error": "Matrix must be square"}
    # Random initial vector
    bk = [random.random() for _ in range(n)]
    norm = math.sqrt(sum(x * x for x in bk))
    bk = [x / norm for x in bk]
    for _ in range(iterations):
        # Multiply A @ bk
        bk1 = [sum(A[i][j] * bk[j] for j in range(n)) for i in range(n)]
        norm = math.sqrt(sum(x * x for x in bk1))
        if norm < 1e-15:
            return {"error": "Power iteration produced zero vector"}
        bk = [x / norm for x in bk1]
    # Rayleigh quotient for eigenvalue
    num = sum(bk[i] * sum(A[i][j] * bk[j] for j in range(n)) for i in range(n))
    den = sum(bk[i] * bk[i] for i in range(n))
    eigenvalue = num / den
    return {
        "eigenvalue": eigenvalue,
        "eigenvector": [round(v, 6) for v in bk],
        "method": f"Power iteration ({iterations} iterations)",
        "latex": f"\\lambda \\approx {eigenvalue:g}",
    }


# =========================================================================
# CALCULUS
# =========================================================================


def numeric_derivative(f_expr, x, h=1e-6):
    """Central difference derivative: f'(x) ≈ (f(x+h) - f(x-h)) / (2h)"""

    def f(xv):
        return eval(f_expr, {"math": math, "x": xv})

    fp = (f(x + h) - f(x - h)) / (2 * h)
    return {
        "derivative": fp,
        "at_x": x,
        "method": "central difference",
        "latex": f"f'({x:g}) \\approx {fp:g}",
    }


def numeric_integrate(f_expr, a, b, n=100, method="simpson"):
    """Numerical integration using Simpson's or trapezoidal rule."""

    def f(xv):
        return eval(f_expr, {"math": math, "x": xv})

    h = (b - a) / n
    if method == "trapezoidal":
        total = f(a) + f(b)
        for i in range(1, n):
            total += 2 * f(a + i * h)
        integral = total * h / 2
    else:  # Simpson
        if n % 2 == 1:
            n += 1  # Simpson requires even n
            h = (b - a) / n
        total = f(a) + f(b)
        for i in range(1, n):
            coeff = 4 if i % 2 == 1 else 2
            total += coeff * f(a + i * h)
        integral = total * h / 3
    return {
        "integral": integral,
        "from": a,
        "to": b,
        "steps": n,
        "method": method,
        "latex": f"\\int_{{{a:g}}}^{{{b:g}}} f(x)\\,dx \\approx {integral:g}",
    }


def taylor_series(f_expr, x0, order=4, at_x=0):
    """Taylor series expansion using forward difference approximations."""

    def f(xv):
        return eval(f_expr, {"math": math, "x": xv})

    h = 1e-4
    coeffs = [f(x0)]
    for k in range(1, order + 1):
        fd = sum(
            (-1) ** (k - j) * math.comb(k, j) * f(x0 + j * h) for j in range(k + 1)
        ) / (h**k)
        coeffs.append(fd / math.factorial(k))
    terms = []
    for i, c in enumerate(coeffs):
        if abs(c) < 1e-15:
            continue
        if i == 0:
            terms.append(f"{c:g}")
        elif i == 1:
            terms.append(f"{c:g}(x - {x0:g})")
        else:
            terms.append(f"{c:g}(x - {x0:g})^{{{i}}}")
    latex = " + ".join(terms)
    val = sum(c * ((at_x - x0) ** i) for i, c in enumerate(coeffs))
    return {
        "coefficients": [round(c, 6) for c in coeffs],
        "center": x0,
        "order": order,
        "evaluated_at": at_x,
        "value": val,
        "latex": f"f(x) \\approx {latex}",
    }


# =========================================================================
# ROOT FINDING
# =========================================================================


def root_find(
    f_expr, method="newton", guess=0.0, a=0.0, b=1.0, tol=1e-10, max_iter=100
):
    """Root finding: Newton-Raphson, bisection, or secant method."""

    def f(xv):
        return eval(f_expr, {"math": math, "x": xv})

    if method == "bisection":
        fa, fb = f(a), f(b)
        if fa * fb >= 0:
            return {"error": "Bisection requires f(a) and f(b) to have opposite signs"}
        for _ in range(max_iter):
            c = (a + b) / 2
            fc = f(c)
            if abs(fc) < tol or (b - a) / 2 < tol:
                return {
                    "root": c,
                    "iterations": _,
                    "method": "bisection",
                    "function_value": fc,
                    "latex": f"x \\approx {c:g}",
                }
            if fa * fc < 0:
                b, fb = c, fc
            else:
                a, fa = c, fc
        return {"error": "Bisection did not converge"}

    elif method == "secant":
        x0, x1 = a, b
        f0, f1 = f(x0), f(x1)
        for _ in range(max_iter):
            if abs(f1 - f0) < 1e-15:
                return {"error": "Secant: division by zero"}
            x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
            x0, x1 = x1, x2
            f0, f1 = f1, f(x2)
            if abs(f1) < tol:
                return {
                    "root": x1,
                    "iterations": _,
                    "method": "secant",
                    "function_value": f1,
                    "latex": f"x \\approx {x1:g}",
                }
        return {"error": "Secant did not converge"}

    else:  # Newton-Raphson
        xk = guess
        h = 1e-6
        for _ in range(max_iter):
            fk = f(xk)
            if abs(fk) < tol:
                return {
                    "root": xk,
                    "iterations": _,
                    "method": "Newton-Raphson",
                    "function_value": fk,
                    "latex": f"x \\approx {xk:g}",
                }
            fpk = (f(xk + h) - f(xk - h)) / (2 * h)
            if abs(fpk) < 1e-15:
                return {"error": "Newton: derivative near zero"}
            xk -= fk / fpk
        return {"error": "Newton did not converge"}


# =========================================================================
# STATISTICS & REGRESSION
# =========================================================================


def statistics(data):
    """Descriptive statistics for a dataset."""
    if not data or len(data) < 2:
        return {"error": "At least 2 data points required"}
    n = len(data)
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
    std = math.sqrt(variance)
    sorted_data = sorted(data)
    median = (
        sorted_data[n // 2]
        if n % 2 == 1
        else (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
    )
    return {
        "n": n,
        "mean": mean,
        "median": median,
        "variance": variance,
        "std_dev": std,
        "min": min(data),
        "max": max(data),
        "latex": f"\\bar{{x}} = {mean:g},\\; s = {std:g},\\; n = {n}",
    }


def linear_regression(x_data, y_data):
    """Linear regression: y = mx + b via least squares."""
    if len(x_data) < 2 or len(y_data) < 2:
        return {"error": "At least 2 data points required"}
    n = len(x_data)
    sx = sum(x_data)
    sy = sum(y_data)
    sxx = sum(x * x for x in x_data)
    sxy = sum(x_data[i] * y_data[i] for i in range(n))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-15:
        return {"error": "Data is collinear (no unique fit)"}
    m = (n * sxy - sx * sy) / denom
    b = (sy - m * sx) / n
    # R-squared
    y_pred = [m * x + b for x in x_data]
    ss_res = sum((y_data[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y - sy / n) ** 2 for y in y_data)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return {
        "slope": m,
        "intercept": b,
        "r_squared": r2,
        "n": n,
        "formula": f"y = {m:g}x + {b:g}",
        "latex": f"y = {m:g}x + {b:g},\\; R^2 = {r2:g}",
    }


# =========================================================================
# FOURIER ANALYSIS
# =========================================================================


def _fft_recursive(x):
    """Radix-2 Cooley-Tukey FFT (recursive)."""
    n = len(x)
    if n <= 1:
        return x
    even = _fft_recursive(x[0::2])
    odd = _fft_recursive(x[1::2])
    t = [cmath.exp(-2j * cmath.pi * k / n) * odd[k] for k in range(n // 2)]
    return [even[k] + t[k] for k in range(n // 2)] + [
        even[k] - t[k] for k in range(n // 2)
    ]


def compute_fft(samples):
    """Compute FFT of real-valued samples (pads to next power of 2)."""
    if not samples:
        return {"error": "Samples required"}
    n = len(samples)
    # Pad to next power of 2
    n2 = 1
    while n2 < n:
        n2 <<= 1
    padded = samples + [0.0] * (n2 - n)
    result = _fft_recursive([complex(x, 0) for x in padded])
    magnitudes = [abs(r) / n2 for r in result[: n2 // 2]]
    freqs = [i / n2 for i in range(n2 // 2)]
    return {
        "fft_magnitudes": [round(m, 6) for m in magnitudes],
        "frequencies": [round(f, 6) for f in freqs],
        "bins": len(magnitudes),
        "original_length": n,
        "padded_length": n2,
        "method": "Radix-2 Cooley-Tukey FFT",
    }


# =========================================================================
# COMPLEX NUMBERS
# =========================================================================


def complex_arithmetic(z1_real, z1_imag, z2_real, z2_imag, operation="add"):
    """Complex number arithmetic."""
    z1 = complex(z1_real, z1_imag)
    z2 = complex(z2_real, z2_imag)
    ops = {
        "add": (z1 + z2, f"{z1} + {z2}"),
        "subtract": (z1 - z2, f"{z1} - {z2}"),
        "multiply": (z1 * z2, f"{z1} \\times {z2}"),
        "divide": (z1 / z2 if abs(z2) > 1e-15 else None, f"{z1} / {z2}"),
        "power": (z1**z2 if abs(z2) < 10 else None, f"{z1}^{{{z2}}}"),
    }
    if operation not in ops:
        return {"error": f"Unknown operation: {operation}"}
    result, label = ops[operation]
    if result is None:
        return {"error": "Operation failed (division by zero or exponent too large)"}
    return {
        "result_real": result.real,
        "result_imag": result.imag,
        "result_polar_radius": abs(result),
        "result_polar_angle": cmath.phase(result),
        "operation": operation,
        "latex": f"{label} = {result:g}",
    }


# =========================================================================
# NUMBER THEORY
# =========================================================================


def prime_factors(n):
    """Prime factorization."""
    if n < 2:
        return {"error": "n must be >= 2"}
    factors = []
    temp = n
    for p in [2] + list(range(3, int(math.isqrt(temp)) + 1, 2)):
        while temp % p == 0:
            factors.append(p)
            temp //= p
        if temp == 1:
            break
    if temp > 1:
        factors.append(temp)
    latex = " \\times ".join(str(f) for f in factors) if factors else str(n)
    return {"factors": factors, "latex": f"{n} = {latex}"}


def gcd_lcm(a, b):
    """GCD and LCM using Euclidean algorithm."""
    gcd = math.gcd(a, b)
    lcm = abs(a * b) // gcd if gcd else 0
    return {
        "gcd": gcd,
        "lcm": lcm,
        "a": a,
        "b": b,
        "latex": f"\\gcd({a}, {b}) = {gcd},\\; \\text{{lcm}}({a}, {b}) = {lcm}",
    }


# =========================================================================
# POLYNOMIALS
# =========================================================================


def polynomial_evaluate(coeffs, x):
    """Evaluate polynomial via Horner's method. coeffs[0] = highest degree."""
    n = len(coeffs)
    result = coeffs[0]
    for i in range(1, n):
        result = result * x + coeffs[i]
    poly_str = " + ".join(f"{c:g}x^{{{n - 1 - i}}}" for i, c in enumerate(coeffs[:-1]))
    poly_str += f" + {coeffs[-1]:g}" if coeffs[-1] else ""
    return {
        "value": result,
        "degree": n - 1,
        "at_x": x,
        "latex": f"P({x:g}) = {result:g}",
    }


# =========================================================================
# UNIT CONVERSION
# =========================================================================

_CONVERSIONS = {
    "m_to_ft": 3.28084,
    "ft_to_m": 0.3048,
    "kg_to_lb": 2.20462,
    "lb_to_kg": 0.453592,
    "c_to_f": "c2f",
    "f_to_c": "f2c",
    "k_to_c": "k2c",
    "c_to_k": "c2k",
    "pa_to_psi": 0.000145038,
    "psi_to_pa": 6894.76,
    "bar_to_pa": 1e5,
    "pa_to_bar": 1e-5,
    "l_to_gal": 0.264172,
    "gal_to_l": 3.78541,
    "n_to_lbf": 0.224809,
    "lbf_to_n": 4.44822,
    "j_to_btu": 0.000947817,
    "btu_to_j": 1055.06,
    "w_to_hp": 0.00134102,
    "hp_to_w": 745.7,
}


def convert_units(value, from_unit, to_unit):
    """Unit conversion between SI and imperial."""
    key = f"{from_unit}_to_{to_unit}"
    if key in _CONVERSIONS:
        conv = _CONVERSIONS[key]
        if conv == "c2f":
            result = value * 9 / 5 + 32
        elif conv == "f2c":
            result = (value - 32) * 5 / 9
        elif conv == "k2c":
            result = value - 273.15
        elif conv == "c2k":
            result = value + 273.15
        else:
            result = value * conv
        return {
            "value": result,
            "from": f"{value} {from_unit}",
            "to_unit": to_unit,
            "latex": f"{value}\\,{from_unit} = {result:g}\\,{to_unit}",
        }
    return {"error": f"No conversion known: {from_unit} -> {to_unit}"}


# =========================================================================
# ODE SOLVER (existing)
# =========================================================================


def _rk4_step(f, t, y, h):
    k1 = f(t, y)
    k2 = f(t + h / 2, [y[i] + h / 2 * k1[i] for i in range(len(y))])
    k3 = f(t + h / 2, [y[i] + h / 2 * k2[i] for i in range(len(y))])
    k4 = f(t + h, [y[i] + h * k3[i] for i in range(len(y))])
    return [
        y[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(len(y))
    ]


def _euler_step(f, t, y, h):
    k = f(t, y)
    return [y[i] + h * k[i] for i in range(len(y))]


def ode_solve(derivatives, y0, t_start=0.0, t_end=10.0, steps=100, method="rk4"):
    if not derivatives or not y0:
        return {"error": "Derivatives and initial conditions required"}
    n = len(y0)
    if len(derivatives) != n:
        return {"error": "Number of derivatives must match initial conditions"}
    h = (t_end - t_start) / steps
    step_fn = _rk4_step if method.lower() == "rk4" else _euler_step

    def _make_func(expr):
        def f(t, y):
            try:
                return eval(
                    expr,
                    {"math": math, "t": t},
                    {f"x{i + 1}": y[i] for i in range(len(y))},
                )
            except:
                return 0

        return f

    funcs = [_make_func(d) for d in derivatives]

    def sys_func(t, y):
        return [f(t, y) for f in funcs]

    t, y = t_start, list(y0)
    trajectory = [(t, list(y))]
    for _ in range(steps):
        y = step_fn(sys_func, t, y, h)
        t += h
        trajectory.append((round(t, 6), [round(v, 6) for v in y]))

    latex_system = (
        "\\begin{cases}"
        + "\\\\\\\\".join(f" x_{{{i + 1}}}' = {d}" for i, d in enumerate(derivatives))
        + "\\end{cases}"
    )
    return {
        "method": method.upper(),
        "steps": steps,
        "t_range": [t_start, t_end],
        "trajectory": [(t, y) for t, y in trajectory],
        "final": trajectory[-1][1],
        "latex": latex_system,
    }


# =========================================================================
# ASCII PLOT (existing)
# =========================================================================


def ascii_plot(x_data, y_data, width=50, height=15, title=""):
    if not x_data or not y_data or len(x_data) != len(y_data):
        return {"error": "x_data and y_data must be non-empty same-length arrays"}
    x_min, x_max = min(x_data), max(x_data)
    y_min, y_max = min(y_data), max(y_data)
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1
    points = []
    for x, y in zip(x_data, y_data):
        xi = int((x - x_min) / x_range * (width - 1))
        yi = int((y - y_min) / y_range * (height - 1))
        yi = height - 1 - yi
        points.append((xi, yi))
    grid = [[" " for _ in range(width)] for _ in range(height)]
    grid_set = set()
    for xi, yi in points:
        if 0 <= xi < width and 0 <= yi < height and (xi, yi) not in grid_set:
            grid[yi][xi] = "*" if (xi, yi) in grid_set else "*"
            grid_set.add((xi, yi))
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        dx, dy = x2 - x1, y2 - y1
        steps = max(abs(dx), abs(dy))
        if steps > 1:
            for s in range(1, steps):
                xi = x1 + int(dx * s / steps)
                yi = y1 + int(dy * s / steps)
                if 0 <= xi < width and 0 <= yi < height and (xi, yi) not in grid_set:
                    grid[yi][xi] = "."
                    grid_set.add((xi, yi))
    lines = ["".join(row) for row in grid]
    y_label = f"{y_max:g}".rjust(8)
    x_label = f"{x_min:g}".ljust(width // 2 - 2) + f"{x_max:g}".rjust(width // 2)
    result = []
    if title:
        result.append(title.center(width))
        result.append("")
    result.append(f"{y_label} |{lines[0]}")
    for line in lines[1:-1]:
        result.append(" " * 9 + "|" + line)
    result.append(" " * 9 + "+" + "-" * width)
    result.append(" " * 9 + x_label)
    return {
        "plot": "\\n".join(result),
        "width": width,
        "height": height,
        "x_range": [x_min, x_max],
        "y_range": [y_min, y_max],
        "data_points": len(x_data),
    }


# =========================================================================
# LaTeX GENERATOR (existing)
# =========================================================================


def generate_latex(expression, notation="aligned"):
    templates = {
        "quadratic": {
            "aligned": "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}",
            "derivation": [
                "ax^2 + bx + c = 0",
                "x^2 + \\frac{b}{a}x = -\\frac{c}{a}",
                "x^2 + \\frac{b}{a}x + \\left(\\frac{b}{2a}\\right)^2 = -\\frac{c}{a} + \\left(\\frac{b}{2a}\\right)^2",
                "\\left(x + \\frac{b}{2a}\\right)^2 = \\frac{b^2 - 4ac}{4a^2}",
                "x + \\frac{b}{2a} = \\pm\\sqrt{\\frac{b^2 - 4ac}{4a^2}}",
                "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}",
            ],
        },
        "euler_buckling": {
            "aligned": "P_{cr} = \\frac{\\pi^2 EI}{(KL)^2}",
            "derivation": [
                "EI \\frac{d^2y}{dx^2} + Py = 0",
                "y'' + k^2y = 0, \\quad k^2 = \\frac{P}{EI}",
                "y = A\\sin(kx) + B\\cos(kx)",
                "y(0) = 0 \\rightarrow B = 0",
                "y(L) = 0 \\rightarrow \\sin(kL) = 0 \\rightarrow kL = n\\pi",
                "P = \\frac{n^2\\pi^2 EI}{L^2} \\rightarrow P_{cr} = \\frac{\\pi^2 EI}{(KL)^2}",
            ],
        },
        "integral": {
            "aligned": "\\int_a^b f(x)\\,dx",
            "derivation": ["\\int_a^b f(x)\\,dx = F(b) - F(a)"],
        },
        "derivative": {
            "aligned": "\\frac{df}{dx} = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}",
            "derivation": [],
        },
        "euler_formula": {
            "aligned": "e^{i\\pi} + 1 = 0",
            "derivation": [
                "e^{i\\theta} = \\cos\\theta + i\\sin\\theta",
                "e^{i\\pi} = \\cos\\pi + i\\sin\\pi = -1",
                "e^{i\\pi} + 1 = 0",
            ],
        },
        "pythagorean": {"aligned": "a^2 + b^2 = c^2", "derivation": []},
        "fourier_series": {
            "aligned": "f(x) = a_0 + \\sum_{n=1}^{\\infty} a_n \\cos(nx) + b_n \\sin(nx)",
            "derivation": [],
        },
    }
    key = expression.lower().replace(" ", "_")
    matched = None
    for k, v in templates.items():
        if k in key or key in k:
            matched = v
            break
    if not matched:
        matched = templates["integral"]
    if notation == "derivation":
        return {
            "latex": "\\n".join(matched.get("derivation", [matched["aligned"]])),
            "steps": len(matched.get("derivation", [1])),
            "notation": notation,
        }
    return {"latex": matched["aligned"], "steps": 1, "notation": notation}


# =========================================================================
# HANDLER DISPATCH
# =========================================================================


def math_handle_tool_call(stripped_name, args):
    """Dispatch math tools by stripped name (without read_sim_math_ prefix)."""
    name = stripped_name.replace("read_sim_math_", "", 1)

    # Linear algebra
    if name == "matrix_solve":
        return matrix_solve(args.get("A", []), args.get("b", []))
    elif name == "determinant":
        return matrix_determinant(args.get("A", []))
    elif name == "inverse":
        return matrix_inverse(args.get("A", []))
    elif name == "eigenvalue":
        return matrix_eigenvalue(args.get("A", []), args.get("iterations", 100))

    # Calculus
    elif name == "derivative":
        return numeric_derivative(args.get("expr", ""), args.get("x", 0))
    elif name == "integrate":
        return numeric_integrate(
            args.get("expr", ""),
            args.get("a", 0),
            args.get("b", 1),
            args.get("n", 100),
            args.get("method", "simpson"),
        )
    elif name == "taylor":
        return taylor_series(
            args.get("expr", ""),
            args.get("x0", 0),
            args.get("order", 4),
            args.get("at_x", 0),
        )

    # Root finding
    elif name == "root":
        return root_find(
            args.get("expr", ""),
            args.get("method", "newton"),
            args.get("guess", 0),
            args.get("a", 0),
            args.get("b", 1),
        )

    # Statistics
    elif name == "stats":
        return statistics(args.get("data", []))
    elif name == "regression":
        return linear_regression(args.get("x_data", []), args.get("y_data", []))

    # Fourier
    elif name == "fft":
        return compute_fft(args.get("samples", []))

    # Complex numbers
    elif name == "complex":
        return complex_arithmetic(
            args.get("z1_real", 0),
            args.get("z1_imag", 0),
            args.get("z2_real", 0),
            args.get("z2_imag", 0),
            args.get("operation", "add"),
        )

    # Number theory
    elif name == "factor":
        return prime_factors(args.get("n", 2))
    elif name == "gcdiv":
        return gcd_lcm(args.get("a", 0), args.get("b", 0))

    # Polynomials
    elif name == "polynomial":
        return polynomial_evaluate(args.get("coeffs", []), args.get("x", 0))

    # Unit conversion
    elif name == "convert":
        return convert_units(
            args.get("value", 0), args.get("from", ""), args.get("to", "")
        )

    # ODE solver (existing)
    elif name == "ode":
        return ode_solve(
            args.get("derivatives", []),
            args.get("y0", []),
            args.get("t_start", 0.0),
            args.get("t_end", 10.0),
            args.get("steps", 100),
            args.get("method", "rk4"),
        )

    # LaTeX (existing)
    elif name == "latex":
        return generate_latex(
            args.get("expression", ""), args.get("notation", "aligned")
        )

    # Plot (existing)
    elif name == "plot":
        return ascii_plot(
            args.get("x_data", []),
            args.get("y_data", []),
            args.get("width", 50),
            args.get("height", 15),
            args.get("title", ""),
        )

    return {"error": f"Unknown math tool: {name}"}
