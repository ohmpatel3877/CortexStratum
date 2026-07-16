---
name: framework-builder
description: Design and build application frameworks with Rust core, cross-language FFI, and structured app flows. Covers Rust workspaces, Tauri integration, MCP servers, WASM compilation, state machines, event-driven architectures, and CI/CD pipelines. Use when scaffolding a new project, designing application architecture, integrating Rust with other languages, or building MCP/tooling frameworks.
---

# Framework Builder — Rust-Centric Application Architecture

Design and build application frameworks with a Rust core, cross-language FFI boundaries, structured application flows, and MCP/tooling integration. This skill sits above individual language skills — it's about the architecture and integration patterns that connect Rust, Python, TypeScript, and WebAssembly into cohesive systems.

## When to Use This Skill

- Scaffolding a new Rust workspace with multiple crates
- Designing the architecture for a Tauri 2 desktop application
- Building an MCP server in Rust or Python
- Integrating Rust with Python/Node via FFI
- Compiling Rust to WASM for web targets
- Designing state machines and event-driven flows
- Setting up cross-language CI/CD pipelines
- Choosing between async patterns, actors, or channels

## Architecture Decision Framework

```
┌────────────────────────────────────────────────────────────────┐
│                    Framework Decision Tree                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Desktop App? ──→ Tauri 2 (Rust core + web frontend)           │
│       or Electron (JS-only, heavier)                            │
│                                                                │
│  CLI Tool? ──→ Rust native (clap, termion)                      │
│       or Python (rich, typer)                                   │
│                                                                │
│  Web Service? ──→ Rust (axum, actix) for performance            │
│       or Python (FastAPI) for rapid development                 │
│                                                                │
│  MCP Server? ──→ Rust (mcp-sdk) for production                  │
│       or Python (mcp library) for prototyping                   │
│                                                                │
│  Cross-Platform Lib? ──→ Rust core + bindings per language      │
│       WASM for web, PyO3 for Python, napi-rs for Node          │
│                                                                │
│  Game/GPU? ──→ Rust (wgpu, bevy, macroquad)                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Rust Workspace Architecture

### Standard Workspace Layout

```
project/
├── Cargo.toml              # [workspace] with members
├── crates/
│   ├── core/               # Core library (no external deps beyond std)
│   │   ├── Cargo.toml
│   │   └── src/
│   ├── cli/                # CLI binary
│   │   ├── Cargo.toml
│   │   └── src/
│   ├── server/             # HTTP/WebSocket server
│   │   ├── Cargo.toml
│   │   └── src/
│   ├── mcp/                # MCP protocol implementation
│   │   ├── Cargo.toml
│   │   └── src/
│   └── ffi/                # FFI bindings (cdylib)
│       ├── Cargo.toml
│       └── src/
├── tests/                  # Integration tests
├── benches/                # Benchmarks
├── scripts/                # Build/deploy scripts
└── .github/workflows/
```

### Cargo.toml Template

```toml
[workspace]
resolver = "2"
members = [
    "crates/core",
    "crates/cli",
    "crates/server",
    "crates/mcp",
    "crates/ffi",
]
edition = "2024"

[workspace.package]
version = "0.1.0"
edition = "2024"
license = "MIT"

[workspace.dependencies]
serde = { version = "1", features = ["derive"] }
tokio = { version = "1", features = ["full"] }
thiserror = "2"
tracing = "0.1"
tracing-subscriber = "0.3"
```

## Application Flow Patterns

### 1. State Machine (Best for: UI flows, protocols, multi-step processes)

```rust
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
enum AppState {
    Idle,
    Loading,
    Ready,
    Error(String),
    ShuttingDown,
}

struct StateMachine {
    state: AppState,
    transitions: HashMap<(AppState, AppState), fn() -> Result<(), String>>,
}

impl StateMachine {
    fn new() -> Self {
        let mut sm = Self {
            state: AppState::Idle,
            transitions: HashMap::new(),
        };
        sm.add_transition(AppState::Idle, AppState::Loading, || Ok(()));
        sm.add_transition(AppState::Loading, AppState::Ready, || {
            println!("Initialization complete");
            Ok(())
        });
        sm
    }

    fn add_transition(&mut self, from: AppState, to: AppState, handler: fn() -> Result<(), String>) {
        self.transitions.insert((from, to), handler);
    }

    fn transition(&mut self, to: AppState) -> Result<(), String> {
        let key = (self.state.clone(), to.clone());
        if let Some(handler) = self.transitions.get(&key) {
            handler()?;
            self.state = to;
            Ok(())
        } else {
            Err(format!("Invalid transition: {:?} → {:?}", self.state, to))
        }
    }
}
```

### 2. Actor Model (Best for: concurrent services, MCP servers)

```rust
use tokio::sync::{mpsc, oneshot};

enum ActorMessage {
    GetData { respond_to: oneshot::Sender<Vec<u8>> },
    Process { data: Vec<u8>, respond_to: oneshot::Sender<Result<(), String>> },
    Shutdown,
}

struct Actor {
    receiver: mpsc::Receiver<ActorMessage>,
    state: Vec<u8>,
}

impl Actor {
    fn new(receiver: mpsc::Receiver<ActorMessage>) -> Self {
        Self { receiver, state: Vec::new() }
    }

    async fn run(&mut self) {
        while let Some(msg) = self.receiver.recv().await {
            match msg {
                ActorMessage::GetData { respond_to } => {
                    let _ = respond_to.send(self.state.clone());
                }
                ActorMessage::Process { data, respond_to } => {
                    self.state.extend(data);
                    let _ = respond_to.send(Ok(()));
                }
                ActorMessage::Shutdown => break,
            }
        }
    }
}

#[derive(Clone)]
struct ActorHandle {
    sender: mpsc::Sender<ActorMessage>,
}

impl ActorHandle {
    fn new() -> Self {
        let (tx, rx) = mpsc::channel(32);
        let mut actor = Actor::new(rx);
        tokio::spawn(async move { actor.run().await });
        Self { sender: tx }
    }

    async fn get_data(&self) -> Vec<u8> {
        let (tx, rx) = oneshot::channel();
        self.sender.send(ActorMessage::GetData { respond_to: tx }).await.unwrap();
        rx.await.unwrap()
    }
}
```

### 3. Event-Driven Pipeline (Best for: data processing, build systems)

```rust
use tokio::sync::broadcast;

#[derive(Debug, Clone)]
enum PipelineEvent {
    SourceDiscovered(String),
    BuildStarted { crate_name: String, target: String },
    BuildComplete { crate_name: String, success: bool, duration_ms: u64 },
    TestRun { crate_name: String, passed: u32, failed: u32 },
    DeploymentStarted { target: String },
    DeploymentComplete { target: String, success: bool },
}

struct Pipeline {
    tx: broadcast::Sender<PipelineEvent>,
    stages: Vec<Box<dyn PipelineStage>>,
}

trait PipelineStage {
    fn name(&self) -> &str;
    fn execute(&self, event: &PipelineEvent) -> Vec<PipelineEvent>;
}

struct BuildStage;
impl PipelineStage for BuildStage {
    fn name(&self) -> &str { "build" }
    fn execute(&self, event: &PipelineEvent) -> Vec<PipelineEvent> {
        match event {
            PipelineEvent::SourceDiscovered(crate_name) => {
                vec![PipelineEvent::BuildStarted {
                    crate_name: crate_name.clone(),
                    target: "x86_64-pc-windows-msvc".into(),
                }]
            }
            _ => vec![],
        }
    }
}
```

## Cross-Language FFI Patterns

### Rust → Python (PyO3)

```rust
// crates/ffi/src/lib.rs
use pyo3::prelude::*;
use pyo3::types::PyDict;

#[pyfunction]
fn analyze_data(data: Vec<f64>) -> PyResult<PyObject> {
    let mean = data.iter().sum::<f64>() / data.len() as f64;
    let variance = data.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / data.len() as f64;

    Python::with_gil(|py| {
        let result = PyDict::new(py);
        result.set_item("mean", mean)?;
        result.set_item("variance", variance)?;
        result.set_item("count", data.len())?;
        Ok(result.into())
    })
}

#[pymodule]
fn core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(analyze_data, m)?)?;
    Ok(())
}
```

```toml
# crates/ffi/Cargo.toml
[package]
name = "core-ffi"
edition = "2024"

[lib]
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.23", features = ["extension-module"] }
```

```bash
# Build: maturin build --release
# Install: pip install target/wheels/core_ffi-*.whl
maturin develop  # dev mode, builds + installs in one step
```

### Rust → Node.js (napi-rs)

```rust
// crates/ffi/src/lib.rs (with napi feature)
#[napi]
fn fibonacci(n: u32) -> u32 {
    match n {
        0 => 0,
        1 => 1,
        _ => fibonacci(n - 1) + fibonacci(n - 2),
    }
}

#[napi(object)]
struct AnalysisResult {
    pub mean: f64,
    pub variance: f64,
    pub count: u32,
}
```

```bash
# Build: npx napi build --release
# Use: const { fibonacci } = require('./core.node')
```

### Rust → WebAssembly (wasm-pack)

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub struct Database {
    inner: Vec<String>,
}

#[wasm_bindgen]
impl Database {
    pub fn new() -> Self { Self { inner: Vec::new() } }
    pub fn insert(&mut self, data: String) { self.inner.push(data); }
    pub fn search(&self, query: String) -> Vec<String> {
        self.inner.iter().filter(|s| s.contains(&query)).cloned().collect()
    }
}
```

```bash
wasm-pack build --target web
# Serves as npm package or directly in browser
```

## MCP Server Framework

### Rust MCP Server

```rust
// crates/mcp/src/lib.rs
use mcp_core::{Tool, ToolContent, ToolResult};
use serde_json::json;
use std::collections::HashMap;

pub struct AppMCPServer {
    tools: HashMap<String, Box<dyn Fn(String) -> ToolResult + Send + Sync>>,
}

impl AppMCPServer {
    pub fn new() -> Self {
        let mut server = Self { tools: HashMap::new() };
        server.register_tool("analyze", |input| {
            Ok(vec![ToolContent::Text { text: format!("Analyzed: {}", input) }])
        });
        server
    }

    fn register_tool<F: 'static + Fn(String) -> ToolResult + Send + Sync>(
        &mut self, name: &str, handler: F,
    ) {
        self.tools.insert(name.to_string(), Box::new(handler));
    }

    pub fn handle_call(&self, tool: &str, input: &str) -> ToolResult {
        match self.tools.get(tool) {
            Some(handler) => handler(input.to_string()),
            None => Err(format!("Unknown tool: {}", tool)),
        }
    }
}
```

### Python MCP Server (Faster prototyping)

```python
# scripts/mcp-server.py
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio

async def serve() -> None:
    server = Server("app-framework")

    @server.list_tools()
    async def list_tools() -> list:
        return [
            Tool(name="analyze", description="Analyze input data",
                 inputSchema={"type": "object", "properties": {"data": {"type": "string"}}}),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list:
        if name == "analyze":
            return [TextContent(type="text", text=f"Analyzed: {arguments['data']}")]

    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, InitializationOptions(server_name="app-framework"))

if __name__ == "__main__":
    import asyncio; asyncio.run(serve())
```

## Tauri 2 Desktop App Framework

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Tauri 2 Desktop App                   │
├───────────────────────┬──────────────────────────────┤
│   Rust Backend        │   Web Frontend               │
│                       │                              │
│   ┌───────────────┐   │   ┌──────────────────────┐   │
│   │ State Machine  │   │   │  React/Vue/Svelte    │   │
│   │ (app flow)     │◄──┼──►│  (Frontend UI)       │   │
│   └───────────────┘   │   └──────────────────────┘   │
│   ┌───────────────┐   │                              │
│   │ MCP Server     │   │                              │
│   │ (embedded)     │   │                              │
│   └───────────────┘   │                              │
│   ┌───────────────┐   │                              │
│   │ FFI Bridge     │   │                              │
│   │ (Python/Node)  │   │                              │
│   └───────────────┘   │                              │
└───────────────────────┴──────────────────────────────┘
```

### Tauri Commands

```rust
// src-tauri/src/lib.rs
use tauri::{AppHandle, Manager, State};
use std::sync::Mutex;

struct AppState {
    counter: Mutex<u32>,
    mcp_server: Mutex<AppMCPServer>,
}

#[tauri::command]
async fn greet(name: String) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn run_mcp_tool(state: State<'_, AppState>, tool: String, input: String) -> Result<String, String> {
    let server = state.mcp_server.lock().map_err(|e| e.to_string())?;
    server.handle_call(&tool, &input).map(|r| format!("{:?}", r))
}

#[tauri::command]
async fn get_system_info() -> serde_json::Value {
    json!({
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "cpu_count": num_cpus::get(),
    })
}

pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            counter: Mutex::new(0),
            mcp_server: Mutex::new(AppMCPServer::new()),
        })
        .invoke_handler(tauri::generate_handler![greet, run_mcp_tool, get_system_info])
        .run(tauri::generate_context!())
        .expect("error running app");
}
```

## Build & CI/CD Integration

### GitHub Actions — Cross-Platform Build

```yaml
name: Build Framework

on: [push, pull_request]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        target: [x86_64, aarch64]

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - name: Setup Rust
        uses: actions-rust-lang/setup-rust-toolchain@v1
        with:
          targets: ${{ matrix.target }}-unknown-linux-gnu

      - name: Build workspace
        run: cargo build --release --workspace

      - name: Run tests
        run: cargo test --workspace

      - name: Build Python bindings (PyO3)
        run: |
          pip install maturin
          maturin build --release --manifest-path crates/ffi/Cargo.toml

      - name: Build WASM bindings
        run: |
          cargo install wasm-pack
          wasm-pack build crates/ffi --target web --out-dir ../../pkg

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: framework-${{ matrix.os }}-${{ matrix.target }}
          path: |
            target/release/*
            target/wheels/*.whl
            pkg/
```

## Scripts Reference

### `scripts/build-all.sh` — Full workspace build + FFI + WASM

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== Building Rust workspace ==="
cargo build --release --workspace

echo "=== Running tests ==="
cargo test --workspace

echo "=== Building Python bindings ==="
cd crates/ffi
maturin build --release --out ../../dist/python
cd ../..

echo "=== Building WASM ==="
wasm-pack build crates/ffi --target web --out-dir ../../dist/wasm --release

echo "=== Creating FFI headers ==="
cbindgen --config crates/ffi/cbindgen.toml --output dist/include/core.h crates/ffi/

echo "=== Done ==="
ls -la dist/
```

## Integration Patterns Summary

| Pattern | Rust Side | Other Side | Best For |
|---------|-----------|------------|----------|
| **PyO3** | `cdylib` crate | Python `import core_rs` | Data processing, ML inference |
| **napi-rs** | `cdylib` crate | Node.js `require()` | CLI tools, build systems |
| **WASM** | `wasm-pack` | Browser/JS `import` | Web apps, Edge compute |
| **MCP** | `mcp_core` | OpenCode/Claude | AI tool integration |
| **Tauri** | `tauri` crate | React/Vue/Svelte | Desktop apps |
| **IPC** | `tokio` + pipes | Any language | Local service communication |
| **HTTP** | `axum`/`actix` | Any HTTP client | Microservices, REST APIs |

## Common Issues

| Issue | Fix |
|-------|-----|
| PyO3 compile slow | Use `maturin develop` for dev (incremental), `--release` for prod |
| napi-rs ABI mismatch | Match Node.js ABI version — rebuild after Node upgrade |
| WASM too large | Enable LTO, optimize size: `[profile.release] lto = true, codegen-units = 1, opt-level = "z"` |
| Tauri IPC timeout | Keep commands short (< 30s), use events for long operations |
| Cargo workspace bloat | Use `cargo metadata` to audit deps, `cargo modules` for structure |
| Cross-compile fails | Install matching target: `rustup target add aarch64-unknown-linux-gnu` |

## See Also

- `inno-setup-pipeline` skill — packaging the final binary
- `vm-test-engine` skill — testing the built framework on clean OSes
- `debug-samba` skill — debugging network integration
