# Dependencies

## Core (Always Required)

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Runtime |
| `json` | stdlib | Data serialization |
| `os`, `sys`, `re`, `time` | stdlib | System operations |
| `threading`, `queue` | stdlib | Concurrent MCP server |
| `pathlib` | stdlib | File paths |
| `hashlib`, `uuid` | stdlib | Identity and integrity |
| `importlib.util` | stdlib | Module factory |

## Optional Modules

### Sensory Module (web browsing, scraping, API)

| Package | Install | Required For |
|---------|---------|-------------|
| `playwright` | `pip install playwright && playwright install firefox` | `read_sensory_browse`, `read_sensory_screenshot`, `mutate_sensory_interact` |
| `beautifulsoup4` | `pip install beautifulsoup4` | `read_sensory_scrape`, `read_sensory_extract_html`, `read_sensory_search`, `read_sensory_fetch_rss` |
| `trafilatura` | `pip install trafilatura` | `read_sensory_extract_article`, markdown extraction |
| `pdfplumber` | `pip install pdfplumber` | `read_sensory_extract_pdf` |
| `Pillow` | `pip install Pillow` | `read_sensory_extract_image` (image metadata) |
| `pytesseract` | `pip install pytesseract` | `read_sensory_extract_image` (OCR) |

### Audio Module

| Package | Install | Required For |
|---------|---------|-------------|
| `numpy` | `pip install numpy` | `read_audio_frequency_analysis` (DFT) |

### Coder Module

All coder tools use stdlib-only logic. No external dependencies.

### Art Module

All art tools use stdlib-only logic. SVG generation is built-in.

### DevOps Module

All devops tools use stdlib-only logic. Configuration templates are generated inline.

### Game Dev Module

All game dev tools use stdlib-only logic. Project scaffolding generates file content.

### Literature Module

All literature tools use stdlib-only logic. Text analysis uses built-in algorithms.

## CI Dependencies

| Tool | Purpose |
|------|---------|
| GitHub Actions | CI/CD pipeline |
| Inno Setup 6+ | Installer build (Windows only) |
| `iscc.exe` | Inno Setup compiler |

## Zero Dependencies

The following modules have **zero external dependencies** — they work immediately after cloning:
- Memory engine (`memory_search.py`)
- Trace system (`trace.py`)
- Verifier middleware (`verifier_middleware.py`)
- Guardrails (`guardrails.py`)
- Coder module (`coder-module.py`)
- Art module (`art-module.py`)
- DevOps module (`devops-module.py`)
- Game Dev module (`game-dev-module.py`)
- Literature module (`literature-module.py`)
- All test scripts
