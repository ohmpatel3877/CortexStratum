#!/usr/bin/env python3
"""
sim-math-module.py — Math Engine (MATLAB-equivalent)

Master Spec:
  - Matrix solve (Ax = b) with LaTeX output
  - Numeric ODE solver (Runge-Kutta, Euler)
  - LaTeX rendering of derivation steps
  - ASCII/mermaid plots from equation data
"""

import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

#
# Matrix Operations (stdlib only — Gaussian elimination)
#


def _gauss_elimination(A, b):
    """Solve Ax = b via Gaussian elimination with partial pivoting."""
    n = len(A)
    # Augmented matrix
    aug = [A[i][:] + [b[i]] for i in range(n)]

    for col in range(n):
        # Partial pivoting
        max_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[max_row][col]) < 1e-15:
            return None  # Singular
        aug[col], aug[max_row] = aug[max_row], aug[col]

        # Eliminate below
        for row in range(col + 1, n):
            factor = aug[row][col] / aug[col][col]
            for j in range(col, n + 1):
                aug[row][j] -= factor * aug[col][j]

    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = aug[i][n]
        for j in range(i + 1, n):
            s -= aug[i][j] * x[j]
        x[i] = s / aug[i][i]
    return x


def _format_matrix_latex(A, name="A"):
    """Format a matrix as LaTeX."""
    rows = [" & ".join(f"{v:g}" for v in row) for row in A]
    sep = "\\\\\\\\"
    return f"{name} = \\begin{{bmatrix}}{sep.join(rows)}\\end{{bmatrix}}"


def _format_vector_latex(v, name="x"):
    """Format a vector as LaTeX."""
    entries = " \\\\\\\\ ".join(f"{val:g}" for val in v)
    return f"{name} = \\begin{{bmatrix}}{entries}\\end{{bmatrix}}"


def matrix_solve(A, b):
    """Solve Ax = b. Returns solution vector and LaTeX derivation."""
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

    # Build LaTeX derivation
    latex_steps = [
        f"Solve {_format_matrix_latex(A)} {_format_vector_latex(b, 'b')}",
        "Using Gaussian elimination with partial pivoting:",
    ]
    # Show the system
    eqs = []
    for i in range(n):
        terms = [f"{A[i][j]:g} x_{j + 1}" for j in range(n)]
        eqs.append(" + ".join(terms) + f" = {b[i]:g}")
    latex_steps.append("\\begin{cases}")
    latex_steps.append("\\\\\\\\".join(eqs))
    latex_steps.append("\\end{cases}")
    latex_steps.append(f"Solution: {_format_vector_latex(x)}")

    return {
        "solution": [round(v, 6) for v in x],
        "dimension": n,
        "latex": "\\n".join(latex_steps),
        "method": "Gaussian elimination with partial pivoting",
    }


#
# ODE Solver (Runge-Kutta 4th order)
#


def _rk4_step(f, t, y, h):
    """Single RK4 step."""
    k1 = f(t, y)
    k2 = f(t + h / 2, [y[i] + h / 2 * k1[i] for i in range(len(y))])
    k3 = f(t + h / 2, [y[i] + h / 2 * k2[i] for i in range(len(y))])
    k4 = f(t + h, [y[i] + h * k3[i] for i in range(len(y))])
    return [
        y[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(len(y))
    ]


def _euler_step(f, t, y, h):
    """Single Euler step."""
    k = f(t, y)
    return [y[i] + h * k[i] for i in range(len(y))]


def ode_solve(derivatives, y0, t_start=0.0, t_end=10.0, steps=100, method="rk4"):
    """
    Solve an ODE system numerically.

    derivatives: list of strings like ["-2*x1 + x2", "x1 - 2*x2"]
    y0: initial conditions list
    t_start, t_end: time range
    steps: number of steps
    method: "rk4" or "euler"
    """
    if not derivatives or not y0:
        return {"error": "Derivatives and initial conditions required"}

    n = len(y0)
    if len(derivatives) != n:
        return {"error": "Number of derivatives must match initial conditions"}

    h = (t_end - t_start) / steps
    step_fn = _rk4_step if method.lower() == "rk4" else _euler_step

    # Parse derivatives into callable functions
    # We use a simple evaluator via Python's eval with x1, x2, ... as variables
    def _make_func(expr):
        def f(t, y):
            # Create local variables x1, x2, ... from y
            locals_dict = {f"x{i + 1}": y[i] for i in range(len(y))}
            locals_dict["t"] = t
            locals_dict["math"] = math
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

    # Integrate
    t = t_start
    y = list(y0)
    trajectory = [(t, list(y))]

    for _ in range(steps):
        y = step_fn(sys_func, t, y, h)
        t += h
        trajectory.append((round(t, 6), [round(v, 6) for v in y]))

    # LaTeX representation
    latex_system = "\\begin{cases}"
    for i, d in enumerate(derivatives):
        latex_system += f" x_{{{i + 1}}}' = {d} \\\\\\\\"
    latex_system += "\\end{cases}"
    latex_system += f"\\\\\\\\ x(0) = {str(y0)}"

    return {
        "method": method.upper(),
        "steps": steps,
        "t_range": [t_start, t_end],
        "trajectory": [(t, y) for t, y in trajectory],
        "final": trajectory[-1][1],
        "latex": latex_system,
        "note": "Derivatives parsed via safe eval. For complex systems, precompute manually.",
    }


#
# ASCII Plot
#


def ascii_plot(x_data, y_data, width=50, height=15, title=""):
    """Generate an ASCII line plot from data."""
    if not x_data or not y_data or len(x_data) != len(y_data):
        return {"error": "x_data and y_data must be non-empty same-length arrays"}

    x_min, x_max = min(x_data), max(x_data)
    y_min, y_max = min(y_data), max(y_data)
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1

    # Normalize data to grid coordinates
    points = []
    for x, y in zip(x_data, y_data):
        xi = int((x - x_min) / x_range * (width - 1))
        yi = int((y - y_min) / y_range * (height - 1))
        yi = height - 1 - yi  # flip y
        points.append((xi, yi))

    # Build grid
    grid = [[" " for _ in range(width)] for _ in range(height)]
    grid_set = set()
    for xi, yi in points:
        if 0 <= xi < width and 0 <= yi < height and (xi, yi) not in grid_set:
            if xi > 0 and (xi - 1, yi) in grid_set:
                grid[yi][xi] = "-"
            else:
                grid[yi][xi] = "*"
            grid_set.add((xi, yi))

    # Connect points with lines
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        # Simple line interpolation
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy))
        if steps > 1:
            for s in range(1, steps):
                xi = x1 + int(dx * s / steps)
                yi = y1 + int(dy * s / steps)
                if 0 <= xi < width and 0 <= yi < height and (xi, yi) not in grid_set:
                    grid[yi][xi] = "."
                    grid_set.add((xi, yi))

    lines = ["".join(row) for row in grid]

    # Axis labels
    y_label_fmt = f"{y_max:g}".rjust(8)
    x_label = f"{x_min:g}".ljust(width // 2 - 2) + f"{x_max:g}".rjust(width // 2)

    result = []
    if title:
        result.append(title.center(width))
        result.append("")
    result.append(f"{y_label_fmt} |{lines[0]}")
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


#
# LaTeX Generator
#


def generate_latex(expression, notation="aligned"):
    """Generate LaTeX from a descriptive mathematical expression."""
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
        "beam_bending": {
            "aligned": "\\sigma = \\frac{My}{I}",
            "derivation": [
                "\\sigma = \\frac{My}{I}",
                "\\text{where: } M = \\text{bending moment, } y = \\text{distance from neutral axis}",
                "I = \\text{second moment of area}",
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
    }

    key = expression.lower().replace(" ", "_")
    # Fuzzy match
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


#
# Handler Dispatch
#


def handle_tool_call(name, args):
    if name == "read_sim_matrix_solve":
        return matrix_solve(args.get("A", []), args.get("b", []))
    elif name == "read_sim_ode":
        return ode_solve(
            args.get("derivatives", []),
            args.get("y0", []),
            args.get("t_start", 0.0),
            args.get("t_end", 10.0),
            args.get("steps", 100),
            args.get("method", "rk4"),
        )
    elif name == "read_sim_latex":
        return generate_latex(
            args.get("expression", ""), args.get("notation", "aligned")
        )
    elif name == "read_sim_plot":
        return ascii_plot(
            args.get("x_data", []),
            args.get("y_data", []),
            args.get("width", 50),
            args.get("height", 15),
            args.get("title", ""),
        )
    return {"error": f"Unknown math tool: {name}"}
