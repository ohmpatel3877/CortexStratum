#!/usr/bin/env python3
"""Art Module — SVG generation, color themes, design tools for OpenCode agents."""

import json
import math
import re

def _hex_to_hsl(hex_color: str) -> tuple:
    """Convert hex color (e.g. '#3b82f6') to HSL tuple.
    
    Returns (0, 0, 0) for invalid input instead of crashing.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6 or not all(c in "0123456789abcdefABCDEF" for c in hex_color):
        return (0, 0, 0)  # safe fallback for invalid input
    r, g, b = int(hex_color[0:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return (0, 0, round(l * 100))
    d = mx - mn
    s = d / (1 - abs(2 * l - 1))
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h = h / 6
    return (round(h * 360), round(s * 100), round(l * 100))


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    s /= 100
    l /= 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return "#{:02x}{:02x}{:02x}".format(
        round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)
    )


def _relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    vals = []
    for i in (0, 2, 4):
        c = int(hex_color[i:i+2], 16) / 255
        if c <= 0.03928:
            vals.append(c / 12.92)
        else:
            vals.append(((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]


def _contrast_ratio(c1: str, c2: str) -> float:
    l1, l2 = _relative_luminance(c1), _relative_luminance(c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _wcag_rating(ratio: float) -> str:
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "AA Large"
    return "Fail"


def generate_svg(description: str, **kwargs) -> str:
    try:
        params = json.loads(description) if description.strip().startswith("{") else {}
    except json.JSONDecodeError:
        params = {}
    desc_lower = description.lower()

    w = params.get("width", kwargs.get("width", 400))
    h = params.get("height", kwargs.get("height", 300))
    bg = params.get("background", "#ffffff")
    title = params.get("title", "Diagram")

    shapes = []
    if "flowchart" in desc_lower or "diagram" in desc_lower:
        y = 30
        steps = params.get("steps", ["Start", "Process", "Decision", "End"])
        for i, step in enumerate(steps):
            x = 50 + (i % 2) * 160
            row_y = y + (i // 2) * 80
            shapes.append(f'<rect x="{x}" y="{row_y}" width="130" height="40" rx="6" fill="#e2e8f0" stroke="#64748b" stroke-width="1.5"/>')
            shapes.append(f'<text x="{x + 65}" y="{row_y + 25}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#1e293b">{step}</text>')
            if i < len(steps) - 1:
                sx, sy = x + 65, row_y + 40
                nx = 50 + ((i + 1) % 2) * 160
                ny = y + ((i + 1) // 2) * 80 + 20
                shapes.append(f'<line x1="{sx}" y1="{sy}" x2="{nx}" y2="{ny}" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow)"/>')

    elif "chart" in desc_lower or "bar" in desc_lower:
        values = params.get("values", [30, 60, 45, 80, 55])
        labels = params.get("labels", [str(i) for i in range(len(values))])
        bar_w = max(20, (w - 60) // len(values))
        max_v = max(values) if values else 1
        for i, v in enumerate(values):
            bh = (v / max_v) * (h - 80)
            x = 30 + i * (bar_w + 10)
            y = h - 40 - bh
            colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]
            shapes.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="3" fill="{colors[i % len(colors)]}" opacity="0.85"/>')
            shapes.append(f'<text x="{x + bar_w / 2}" y="{h - 20}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#475569">{labels[i]}</text>')
            shapes.append(f'<text x="{x + bar_w / 2}" y="{y - 5}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#1e293b">{v}</text>')

    else:
        shapes.append(f'<text x="{w / 2}" y="40" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#1e293b">{title}</text>')
        shapes.append(f'<rect x="{(w - 200) / 2}" y="60" width="200" height="120" rx="8" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1"/>')
        shapes.append(f'<text x="{w / 2}" y="130" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#475569">Generated Illustration</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/>
    </marker>
  </defs>
  <rect width="{w}" height="{h}" fill="{bg}" rx="4"/>
  {chr(10).join("  " + s for s in shapes)}
</svg>'''
    return svg


def generate_theme(description: str) -> dict:
    desc_lower = description.lower()
    themes = {
        "dark cyberpunk": {
            "bg": "#0d1117", "text": "#e6edf3", "accent": "#ff00ff",
            "surface": "#161b22", "border": "#30363d", "success": "#00ff88",
            "warning": "#ffaa00", "error": "#ff3355",
        },
        "forest green": {
            "bg": "#f0f7f0", "text": "#1a3b2e", "accent": "#2d8a4e",
            "surface": "#e8f2e8", "border": "#a3c9a3", "success": "#1a8a3e",
            "warning": "#c97d1a", "error": "#8a2d2d",
        },
        "ocean blue": {
            "bg": "#f0f6ff", "text": "#1a2a4a", "accent": "#2563eb",
            "surface": "#e8f0fe", "border": "#b0c4de", "success": "#16a34a",
            "warning": "#d97706", "error": "#dc2626",
        },
        "sunset warm": {
            "bg": "#fff8f0", "text": "#4a1a1a", "accent": "#e85d3a",
            "surface": "#fff0e0", "border": "#e0c0a0", "success": "#3a8a3a",
            "warning": "#d4a017", "error": "#cc3333",
        },
        "monochrome": {
            "bg": "#ffffff", "text": "#111111", "accent": "#555555",
            "surface": "#f5f5f5", "border": "#cccccc", "success": "#2e7d32",
            "warning": "#f57f17", "error": "#c62828",
        },
        "dracula": {
            "bg": "#282a36", "text": "#f8f8f2", "accent": "#bd93f9",
            "surface": "#44475a", "border": "#6272a4", "success": "#50fa7b",
            "warning": "#f1fa8c", "error": "#ff5555",
        },
        "solarized light": {
            "bg": "#fdf6e3", "text": "#657b83", "accent": "#268bd2",
            "surface": "#eee8d5", "border": "#93a1a1", "success": "#859900",
            "warning": "#b58900", "error": "#dc322f",
        },
    }

    for key, palette in themes.items():
        if key in desc_lower:
            result = {**palette, "name": key, "description": f"{key.title()} theme"}
            break
    else:
        h = hash(description) % 360
        bg_h = h
        result = {
            "name": "custom",
            "description": description,
            "bg": _hsl_to_hex(bg_h, 5, 95),
            "text": _hsl_to_hex(bg_h, 10, 20),
            "accent": _hsl_to_hex(bg_h % 360, 70, 50),
            "surface": _hsl_to_hex(bg_h, 5, 90),
            "border": _hsl_to_hex(bg_h, 10, 75),
            "success": _hsl_to_hex(120, 60, 45),
            "warning": _hsl_to_hex(40, 80, 50),
            "error": _hsl_to_hex(0, 70, 50),
        }

    pairs = [("bg", "text"), ("bg", "accent"), ("surface", "text"), ("surface", "accent")]
    contrast_info = {}
    for fg, bgk in pairs:
        if fg in result and bgk in result:
            ratio = _contrast_ratio(result[fg], result[bgk])
            contrast_info[f"{fg}_on_{bgk}"] = {
                "ratio": round(ratio, 2),
                "wcag": _wcag_rating(ratio),
            }
    result["contrast"] = contrast_info
    return result


def extract_palette(base_color: str) -> dict:
    base_color = base_color.lstrip("#")
    if not re.match(r"^[0-9a-fA-F]{6}$", base_color):
        return {"error": f"Invalid hex color: #{base_color}"}
    h, s, l = _hex_to_hsl(f"#{base_color}")

    complementary = _hsl_to_hex((h + 180) % 360, s, l)

    analogous = [
        _hsl_to_hex((h - 30) % 360, s, l),
        _hsl_to_hex(h, s, l),
        _hsl_to_hex((h + 30) % 360, s, l),
    ]

    triadic = [
        _hsl_to_hex(h, s, l),
        _hsl_to_hex((h + 120) % 360, s, l),
        _hsl_to_hex((h + 240) % 360, s, l),
    ]

    split_complementary = [
        _hsl_to_hex(h, s, l),
        _hsl_to_hex((h + 150) % 360, s, l),
        _hsl_to_hex((h + 210) % 360, s, l),
    ]

    shades = [_hsl_to_hex(h, s, max(10, min(95, l + offset))) for offset in (-30, -15, 0, 15, 30)]

    monochromatic = []
    for lightness in [20, 40, 50, 60, 80]:
        monochromatic.append(_hsl_to_hex(h, max(10, s - 20), lightness))

    return {
        "base": f"#{base_color}",
        "hsl": {"h": h, "s": s, "l": l},
        "complementary": complementary,
        "analogous": analogous,
        "triadic": triadic,
        "split_complementary": split_complementary,
        "shades": shades,
        "monochromatic": monochromatic,
    }


def design_concept(requirements: str) -> dict:
    req_lower = requirements.lower()
    concepts = []

    if "dashboard" in req_lower:
        concepts.append({
            "type": "layout",
            "suggestion": "Sidebar navigation + top header + main content grid",
            "details": "Use a fixed 240px left sidebar for nav, 56px top bar with search, and a responsive 3-column card grid for the main area."
        })
    elif "landing" in req_lower or "homepage" in req_lower:
        concepts.append({
            "type": "layout",
            "suggestion": "Hero section + feature grid + footer",
            "details": "Full-width hero with headline (48px), subtitle (20px), CTA button. Below: 3-column feature cards with icons. Bottom: minimal footer."
        })
    elif "form" in req_lower:
        concepts.append({
            "type": "layout",
            "suggestion": "Single-column centered form with sections",
            "details": "Max-width 480px centered layout. Label on top, input below, helper text beneath input. Submit button full-width at bottom."
        })
    else:
        concepts.append({
            "type": "layout",
            "suggestion": "Standard content layout with header, main, footer",
            "details": "Responsive container (max-width 1200px) with centered content. Sections separated by 2rem spacing."
        })

    if "modern" in req_lower or "clean" in req_lower:
        typography = {
            "heading": "Inter or system-ui, 700 weight, 2.25rem / 1.75rem / 1.25rem",
            "body": "Inter or system-ui, 400 weight, 1rem / 0.875rem",
            "mono": "JetBrains Mono or Cascadia Code, 0.875rem",
        }
    elif "serious" in req_lower or "academic" in req_lower:
        typography = {
            "heading": "Merriweather or Georgia, 700 weight, 2rem / 1.5rem / 1.125rem",
            "body": "Merriweather or Georgia, 400 weight, 1.0625rem",
            "mono": "IBM Plex Mono or Courier New, 0.875rem",
        }
    else:
        typography = {
            "heading": "system-ui sans-serif, 700 weight, 2rem / 1.5rem / 1.25rem",
            "body": "system-ui sans-serif, 400 weight, 1rem / 0.875rem",
            "mono": "monospace, 0.875rem",
        }

    concepts.append({"type": "typography", "suggestion": typography})

    if "dark" in req_lower:
        spacing_rhythm = {
            "base_unit": "4px",
            "padding": {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "32px"},
            "margin": {"section": "48px", "component": "16px", "element": "8px"},
        }
    else:
        spacing_rhythm = {
            "base_unit": "8px",
            "padding": {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "32px"},
            "margin": {"section": "48px", "component": "16px", "element": "8px"},
        }

    concepts.append({"type": "spacing", "suggestion": spacing_rhythm})

    return {
        "requirements": requirements,
        "concepts": concepts,
    }


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    if action == "generate_svg":
        desc = sys.argv[2] if len(sys.argv) > 2 else "A simple diagram"
        print(generate_svg(desc))
    elif action == "generate_theme":
        desc = sys.argv[2] if len(sys.argv) > 2 else "dark cyberpunk"
        print(json.dumps(generate_theme(desc), indent=2))
    elif action == "extract_palette":
        color = sys.argv[2] if len(sys.argv) > 2 else "#3b82f6"
        print(json.dumps(extract_palette(color), indent=2))
    elif action == "design_concept":
        reqs = sys.argv[2] if len(sys.argv) > 2 else "A modern dashboard"
        print(json.dumps(design_concept(reqs), indent=2))
    else:
        print("Art Module — available actions: generate_svg, generate_theme, extract_palette, design_concept")
