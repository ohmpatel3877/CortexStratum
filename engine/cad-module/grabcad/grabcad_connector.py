#!/usr/bin/env python3
"""
grabcad_connector.py - Search, download, and import GrabCAD models
CortexStratum cad-module

Provides:
  - Search GrabCAD library by keyword
  - Download STEP/STL/IGS models
  - Convert to importable SCAD format
  - Maintain local cache of downloaded models
  - Generate SCAD use/include stubs for downloaded parts
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "grabcad-models"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Index file tracking what's been downloaded
INDEX_FILE = CACHE_DIR / "index.json"


def _load_index():
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {"models": [], "last_sync": None}


def _save_index(index):
    index["last_sync"] = datetime.now().isoformat()
    INDEX_FILE.write_text(json.dumps(index, indent=2))


def search_grabcad(query, max_results=10):
    """
    Search GrabCAD library for models matching query.
    Uses web fetch since no official public API exists.
    Returns list of (title, url, preview_img) tuples.
    """
    encoded = urllib.parse.quote(query)
    url = (
        f"https://grabcad.com/library?page=1&time=all_time&sort=recent&query={encoded}"
    )

    print(f"[grabcad] Searching: {query}")
    print(f"[grabcad] URL: {url}")
    print("[grabcad] Open this URL in browser to browse models")
    print("[grabcad] OR provide a direct GrabCAD model URL to download")
    print()

    # Return search URL for manual browsing
    return {
        "query": query,
        "search_url": url,
        "note": "Open the search URL in browser, find models, then pass the model page URL to download_model()",
    }


def download_model(url, output_dir=None):
    """
    Download a GrabCAD model from its page URL.

    Args:
        url: Full GrabCAD model page URL (e.g., https://grabcad.com/library/some-model)
        output_dir: Where to save the downloaded files

    Returns:
        dict with download results
    """
    if output_dir is None:
        output_dir = CACHE_DIR / "downloads"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_name = url.rstrip("/").split("/")[-1]
    print(f"[grabcad] Downloading model: {model_name}")
    print(f"[grabcad] Page URL: {url}")

    # Try to fetch the page and find download links
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Find STEP/STL/IGS download links
        formats = {
            ".step": r'href=[\'"]([^\'"]*\.step[^\'"]*)[\'"]',
            ".stp": r'href=[\'"]([^\'"]*\.stp[^\'"]*)[\'"]',
            ".stl": r'href=[\'"]([^\'"]*\.stl[^\'"]*)[\'"]',
            ".igs": r'href=[\'"]([^\'"]*\.igs[^\'"]*)[\'"]',
            ".iges": r'href=[\'"]([^\'"]*\.iges[^\'"]*)[\'"]',
        }

        downloads_found = []
        for ext, pattern in formats.items():
            for match in re.finditer(pattern, html, re.IGNORECASE):
                dl_url = match.group(1)
                if dl_url.startswith("//"):
                    dl_url = "https:" + dl_url
                elif dl_url.startswith("/"):
                    dl_url = "https://grabcad.com" + dl_url
                downloads_found.append((ext, dl_url))

        if downloads_found:
            results = []
            for ext, dl_url in downloads_found:
                local_path = output_dir / f"{model_name}{ext}"
                print(f"[grabcad] Downloading: {dl_url}")
                try:
                    dl_req = urllib.request.Request(
                        dl_url, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(dl_req, timeout=120) as dl_resp:
                        data = dl_resp.read()
                        local_path.write_bytes(data)
                    size_kb = len(data) / 1024
                    results.append(
                        {
                            "file": str(local_path),
                            "format": ext,
                            "size_kb": round(size_kb, 1),
                        }
                    )
                    print(f"[grabcad]   Saved: {local_path.name} ({size_kb:.0f} KB)")
                except Exception as e:
                    print(f"[grabcad]   Download failed: {e}")

            # Update index
            index = _load_index()
            index["models"].append(
                {
                    "name": model_name,
                    "url": url,
                    "downloaded_at": datetime.now().isoformat(),
                    "files": results,
                }
            )
            _save_index(index)

            return {
                "model": model_name,
                "files": results,
                "output_dir": str(output_dir),
            }
        else:
            print("[grabcad] No direct download links found on page.")
            print(
                "[grabcad] Model may require login or have download buttons behind JS."
            )
            return {
                "model": model_name,
                "error": "No downloadable links found",
                "url": url,
            }

    except Exception as e:
        print(f"[grabcad] Error fetching page: {e}")
        return {"model": model_name, "error": str(e), "url": url}


def convert_step_to_scad(step_path, output_path=None):
    """
    Convert a STEP file to SCAD-compatible format.
    Uses OpenSCAD's import() for STEP files (OpenSCAD 2025+).
    For older OpenSCAD, generates a stub with import() statement.
    """
    step_path = Path(step_path)
    if not step_path.exists():
        return {"error": f"File not found: {step_path}"}

    if output_path is None:
        output_path = step_path.with_suffix(".scad")
    output_path = Path(output_path)

    # OpenSCAD 2025+ supports STEP import natively
    scad_content = f"""//
// Imported from GrabCAD: {step_path.name}
// Source: {step_path}
// Auto-generated by grabcad_connector.py
//

// Uncomment to render this part standalone:
// import("{step_path.resolve()}");

module imported_{step_path.stem.replace("-", "_").replace(" ", "_")}() {{
    // Import the STEP/STL file
    import("{step_path.resolve()}");
}}

// Positioning data for assembly
// Origin: [0, 0, 0]
// Rotation: [0, 0, 0]
"""
    output_path.write_text(scad_content)
    print(f"[grabcad] SCAD wrapper created: {output_path}")
    return {"status": "ok", "scad_path": str(output_path)}


def list_cached_models():
    """List all previously downloaded GrabCAD models."""
    index = _load_index()
    models = index.get("models", [])
    if not models:
        print("[grabcad] No cached models found.")
        return []

    print(f"[grabcad] Cached models ({len(models)}):")
    for m in models:
        files_str = ", ".join([f["file"] for f in m.get("files", [])])
        print(f"  {m['name']}")
        print(f"    URL: {m['url']}")
        print(f"    Files: {files_str}")
        print(f"    Downloaded: {m['downloaded_at']}")
    return models


def recommend_models_for_project():
    """
    Recommend GrabCAD models useful for the Bottle Flipping System project.
    Returns search queries and specific model suggestions.
    """
    recommendations = [
        {
            "part": "Servo SM-S2309S Mount",
            "search": "SM-S2309S servo bracket",
            "url": "https://grabcad.com/library?query=servo+bracket+SM-S2309S",
            "alternative": "Standard servo mount (MG995/SG90 bracket, remeasurable)",
        },
        {
            "part": "Arduino Uno Enclosure/Mount",
            "search": "Arduino Uno mounting plate",
            "url": "https://grabcad.com/library?query=Arduino+Uno+mount",
            "alternative": "DIY acrylic mount from our base_frame.scad",
        },
        {
            "part": "Four-Bar Linkage Joints",
            "search": "linkage joint bearing pin",
            "url": "https://grabcad.com/library?query=linkage+joint+bearing",
            "alternative": "Our bearings.scad covers this",
        },
        {
            "part": "Bottle Gripper Jaws",
            "search": "parallel gripper jaw 500ml",
            "url": "https://grabcad.com/library?query=parallel+gripper+jaw",
            "alternative": "Custom design in clamping_arm.scad",
        },
        {
            "part": "Spur Gear Set (12T/36T)",
            "search": "spur gear module 1.5 12T 36T",
            "url": "https://grabcad.com/library?query=spur+gear+module+1.5",
            "alternative": "Our gears.scad generates custom gears",
        },
        {
            "part": "Worm Gear Drive",
            "search": "worm gear 30:1 module 1.5",
            "url": "https://grabcad.com/library?query=worm+gear+30:1",
            "alternative": "Our worm_gear.scad generates custom worm gear",
        },
    ]

    print("=" * 60)
    print("  Recommended GrabCAD Models for Bottle Flipper")
    print("=" * 60)
    print()
    for r in recommendations:
        print(f"  {r['part']}")
        print(f"    Search: {r['search']}")
        print(f"    URL: {r['url']}")
        print(f"    Fallback: {r['alternative']}")
        print()

    print("To download a model: python grabcad_connector.py download <url>")
    print("To list cached:     python grabcad_connector.py list")
    print("To import in SCAD:  use import() or the generated wrapper")

    return recommendations


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python grabcad_connector.py search <query>")
        print("  python grabcad_connector.py download <model-url>")
        print("  python grabcad_connector.py convert <step-file>")
        print("  python grabcad_connector.py list")
        print("  python grabcad_connector.py recommend")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "servo bracket"
        result = search_grabcad(query)
        print(json.dumps(result, indent=2))

    elif cmd == "download":
        if len(sys.argv) < 3:
            print("Usage: python grabcad_connector.py download <url>")
            sys.exit(1)
        result = download_model(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "convert":
        if len(sys.argv) < 3:
            print("Usage: python grabcad_connector.py convert <step-file>")
            sys.exit(1)
        result = convert_step_to_scad(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "list":
        list_cached_models()

    elif cmd == "recommend":
        recommend_models_for_project()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
