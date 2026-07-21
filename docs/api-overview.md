# CortexStratum API Documentation

*Generated: 2026-07-16 03:13:16 UTC*

---

## Project Overview

| Metric | Count |
|--------|-------|
| Python scripts | 31 |
| PowerShell scripts | 17 |
| Total functions | 286 |
| Total classes | 13 |
| MCP tools | 122 |
| MCP tool modules | 26 |
| Data files | 30 |

---

## Script Index

| Script | Language | Purpose | Key Functions |
|--------|----------|---------|---------------|
| `art-module.py` | py | Art Module — SVG generation, color themes, design tools for OpenCode agents. | `_hex_to_hsl, _hsl_to_hex, _relative_luminance, _contrast_ratio, _wcag_rating +4 more` |
| `audio-module.py` | py | Audio Module — AI auditory analysis assistant. Analyzes WAV files, music theory, | `_note_to_freq, _freq_to_note_name, _freq_to_midi, _match_chord_from_semitones, _match_scales +14 more` |
| `benchmark-harness.py` | py | Benchmark Harness: deepseek-v4-flash vs Frontier Models  Runs curated sample que | `safe_json_load, safe_json_save, score_mmlu, score_gpqa, score_humaneval +14 more` |
| `blind-benchmark.py` | py | Blind benchmark test for deepseek-v4-flash. Questions are generated fresh so the | `main` |
| `cheat-test.py` | py | Cheat test: compare my answers to the now-revealed answer key. | `` |
| `check-commitments.ps1` | ps1 | *No docstring* | `Seed-DefaultRegistry, Read-Registry` |
| `check-status.ps1` | ps1 | *No docstring* | `` |
| `coder-module.py` | py | Coder Module — AI senior developer assistant. Provides code analysis, framework  | `_score_to_grade, _estimate_complexity, _line_number, _detect_long_functions, _get_nesting_depth +11 more` |
| `consultation-room.ps1` | ps1 | .SYNOPSIS Multi-perspective decision analysis for the Consultation Room. .DESCRI | `Get-Timestamp, Get-FileTimestamp` |
| `dag-coordinator.py` | py | DAG Coordinator — topological execution engine for multi-agent pipelines.  Reads | `get_state_manager, now_iso, ensure_dirs, load_json, write_json +10 more` |
| `dashboard-ne-memory.py` | py | NE-Memory query helper for dashboard.ps1 - fetches recent memories via local store. | `` |
| `dashboard.ps1` | ps1 | .SYNOPSIS CortexStratum Dashboard — usage, memories, goals, commitments, errors | `` |
| `decision-trace.ps1` | ps1 | *No docstring* | `Ensure-Registry, Load-Registry, Get-Timestamp, Invoke-Add, Invoke-Update +3 more` |
| `devops-module.py` | py | DevOps/Container Module — AI DevOps expert for Podman, Docker, permissions, Samb | `dockerfile_analyze, network_troubleshoot, devops_handle_tool_call` |
| `error-trace.ps1` | ps1 | *No docstring* | `Ensure-Registry, Load-Registry, Invoke-LogError, Invoke-LogAttempt, Invoke-Resolve +2 more` |
| `firefox-provider-signup.py` | py | Free AI Provider Signup Navigator Opens each free AI provider's signup/API-key p | `` |
| `game-dev-module.py` | py | Game Development Module — AI game development expert. Specializes in Unity, Unre | `_analyze_fun_factor, _generate_engagement_loops, _find_similar_games, gamedev_design_analyze, _unity_scaffold_fps +6 more` |
| `generate-blind-test.py` | py | BLIND TEST RUNNER — questions in, answers hidden, score computed at end.  I (the | `` |
| `generate-config.ps1` | ps1 | *No docstring* | `` |
| `goal-registry.ps1` | ps1 | *No docstring* | `Get-SessionId` |
| `identity-manager.py` | py | Identity Manager — Consolidate, store, and inject persona identity from NE-Memory.  R | `ensure_dirs, now_iso, _load_json, _save_json, _list_profiles +3 more` |
| `inject-identity.ps1` | ps1 | .SYNOPSIS Injects the current identity profile as a session prompt fragment. .DE | `` |
| `integration-status.py` | py | Integration Status Report Generator — Checks all 5 workstream outputs, validates | `now_iso, check_file, check_dir, check_import, check_adr_completeness +3 more` |
| `literature-module.py` | py | Literature Module — Text analysis, concept extraction, study guides for social s | `_count_syllables, _flesch_kincaid, _extract_key_phrases, _extract_claims_evidence, analyze_text +3 more` |
| `load-skills.ps1` | ps1 | .SYNOPSIS Matches a user message against skill-router.json triggers and outputs  | `` |
| `logic-verify.ps1` | ps1 | *No docstring* | `Show-Usage, Test-ReasoningStructure, Get-LogicPrompt, Invoke-DCPPipeline` |
| `memory_search.py` | py | *No docstring* | `_get_searcher, search, synthesize, add_memory, consolidate +1 more` |
| `ne-consolidation-daemon.ps1` | ps1 | .SYNOPSIS NE-Memory auto-consolidation daemon — runs every N minutes to deduplic | `` |
| `orchestrate-all.ps1` | ps1 | .SYNOPSIS Unified Orchestration Entry Point — Full pipeline orchestrator for ai- | `` |
| `output-condenser.ps1` | ps1 | .SYNOPSIS Condenses verbose tool outputs to extract only signal (errors, key dat | `Write-CondenserLog, Get-CosineSimilarity, Invoke-CondenseBash, Invoke-CondenseRead, Invoke-CondenseGrep +1 more` |
| `preset-manager.ps1` | ps1 | *No docstring* | `` |
| `run-blind-test.py` | py | Blind test runner — presents questions, collects answers, scores at end. Answer  | `longest_palindromic, fizzbuzz` |
| `run-eval-harness.py` | py | Agent Tool Systems Evaluation Harness Tests all 6 performance-enhancing tools bu | `test, run_powershell, test_skill_router, test_commitment_checker, test_goal_registry +6 more` |
| `sandbox-integration.ps1` | ps1 | .SYNOPSIS Sandbox Integration Wrapper — calls sandbox-manager.py with structured | `` |
| `sandbox-manager.py` | py | Sandbox Manager — Lightweight code execution sandbox for running untrusted or is | `_compute_code_hash, _now_iso, _load_log, _append_log, format_result +3 more` |
| `score-blind-benchmark.py` | py | Score the blind benchmark by comparing my answers to the answer key. | `is_anagram` |
| `security-scan.py` | py | Security Scanner — CortexStratum toolchain security audit module.  Scans a code | `find_target_files, scan_secrets_in_file, scan_code_antipatterns_in_file, parse_version, scan_dependency_vulnerabilities +10 more` |
| `sensory-module.py` | py | Sensory Module — AI agent sensory input layer. Connects AI tools to: web browsin | `_get_requests, _get_bs4, _get_pdfplumber, _get_trafilatura, _get_playwright +14 more` |
| `side-by-side-comparison.py` | py | Side-by-Side Comparison: Agent WITH tools vs WITHOUT tools  Tests the same task  | `safe_json_load, seed_json, section, report, test_skill_router +7 more` |
| `state_file_manager.py` | py | DAG State File Manager — atomic file-based state passing between DAG nodes.  Pro | `now_iso, _ensure_dir` |
| `task-analyzer.py` | py | Task Analyzer — Evaluates task complexity and recommends execution mode. Part of | `analyze_task` |
| `task-orchestrator.py` | py | Task Orchestrator v2 — ACTIVE orchestrator that works WHILE subagents run. Usage | `ensure_dirs, now_iso, _run_dag, print_box, call_temperature_mcp +4 more` |
| `team-mode.ps1` | ps1 | *No docstring* | `Get-Timestamp, Get-FileTimestamp` |
| `test-integration-layer.py` | py | Integration Layer Test Suite — Verifies all 5 workstream outputs wire together c | `test, skip, import_from_path, test_dag_coordinator_import, test_identity_manager_import +10 more` |
| `test-mcp-server.py` | py | Test harness for tools-mcp-server.py Validates the MCP stdio protocol and all 6  | `send_mcp_message, main` |
| `test-sensory-module.py` | py | Integration tests for sensory-module.py Run: python test-sensory-module.py | `run, test_scrape_text, test_scrape_json, test_scrape_links, test_extract_html_clean +8 more` |
| `tools-mcp-server.py` | py | MCP Server: CortexStratum Toolchain Exposes xTrace, DTrace, Skill Router, Outpu | `_get_verifier, _get_memory_search, read_exact, _get_art_module, _get_lit_module +15 more` |
| `verifier_middleware.py` | py | verifier-middleware.py — Parallel verifier for CortexStratum MCP pipeline.  Cro | `_demo` |

---
## MCP Tools

Total: **122** tools across **26** modules.

### Art

_4 tools_

#### `art_generate_svg`

**Description:** Generate SVG diagrams, flowcharts, and illustrations from a text description
**Required:** description

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `string` |  |
| `width` | `integer` |  |
| `height` | `integer` |  |


#### `art_generate_theme`

**Description:** Generate a color theme with roles and WCAG contrast validation from a description
**Required:** description

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `string` |  |


#### `art_extract_palette`

**Description:** Extract complementary, analogous, and triadic palettes from a base hex color
**Required:** color

| Parameter | Type | Description |
|-----------|------|-------------|
| `color` | `string` |  |


#### `art_design_concept`

**Description:** Generate a design concept with layout, typography, and spacing guidelines from requirements
**Required:** requirements

| Parameter | Type | Description |
|-----------|------|-------------|
| `requirements` | `string` |  |


### Audio

_7 tools_

#### `audio_analyze_file`

**Description:** Analyze WAV audio file: duration, channels, sample rate, amplitude stats
**Required:** None

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `string` |  |
| `data_base64` | `string` |  |
| `format` | `string` |  |


#### `audio_waveform`

**Description:** Generate ASCII waveform visualization from audio file
**Required:** file_path

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `string` |  |
| `width` | `integer` |  |
| `height` | `integer` |  |


#### `audio_frequency_analysis`

**Description:** DFT-based frequency analysis: band energy, dominant frequency, spectral centroid
**Required:** file_path

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `string` |  |
| `num_bands` | `integer` |  |


#### `audio_music_theory`

**Description:** Music theory analysis: chord detection, scale matching, intervals from notes or frequencies
**Required:** None

| Parameter | Type | Description |
|-----------|------|-------------|
| `notes` | `array` |  |
| `frequencies` | `array` |  |


#### `audio_speech_analysis`

**Description:** Speech transcript analysis: WPM, filler words, pace rating, readability
**Required:** transcript, duration_seconds

| Parameter | Type | Description |
|-----------|------|-------------|
| `transcript` | `string` |  |
| `duration_seconds` | `number` |  |


#### `audio_convert_guide`

**Description:** Audio format conversion guide with ffmpeg commands and quality comparison
**Required:** source_format, target_format

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_format` | `string` |  |
| `target_format` | `string` |  |
| `quality` | `string` |  |


#### `audio_generate_tone`

**Description:** Generate sine/square/saw/triangle wave tone as base64 WAV
**Required:** None

| Parameter | Type | Description |
|-----------|------|-------------|
| `frequency` | `number` |  |
| `duration_seconds` | `number` |  |
| `sample_rate` | `integer` |  |
| `amplitude` | `number` |  |
| `waveform` | `string` |  |


### Coder

_7 tools_

#### `coder_analyze_code`

**Description:** Analyze code for quality, complexity, smells, and security issues across 12 languages
**Required:** code, language

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | `string` |  |
| `language` | `string` |  |


#### `coder_generate_framework`

**Description:** Generate complete project scaffold (web-api, cli-tool, library, desktop, microservice, data-pipeline, fullstack) for 12 languages
**Required:** project_type, language

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_type` | `string` |  |
| `language` | `string` |  |
| `features` | `array` |  |
| `name` | `string` |  |


#### `coder_debug`

**Description:** Analyze error messages and stack traces, suggest fixes (50+ error patterns across languages)
**Required:** error, language

| Parameter | Type | Description |
|-----------|------|-------------|
| `error` | `string` |  |
| `code_context` | `string` |  |
| `language` | `string` |  |


#### `coder_review`

**Description:** Code review with severity ratings (security, performance, readability, architecture, testing)
**Required:** code, language

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | `string` |  |
| `language` | `string` |  |
| `focus` | `string` |  |


#### `coder_explain`

**Description:** Educational code explanation at beginner/intermediate/advanced level
**Required:** code, language

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | `string` |  |
| `language` | `string` |  |
| `level` | `string` |  |


#### `coder_convert`

**Description:** Convert code between languages (Python↔JS, Python→Go, Python→Rust, JS↔TS)
**Required:** code, from, to

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | `string` |  |
| `from` | `string` |  |
| `to` | `string` |  |


#### `coder_architecture`

**Description:** Architecture pattern recommendation (MVC, Hexagonal, CQRS, Event-Driven, Microservices, etc.)
**Required:** project_type

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_type` | `string` |  |
| `scale` | `string` |  |
| `requirements` | `array` |  |


### Core

_13 tools_

#### `xtrace_log_error`

**Description:** Log an error occurrence with signature for xTrace error tracking
**Required:** command, error_output

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | `string` |  |
| `error_output` | `string` |  |
| `exit_code` | `integer` |  |


#### `xtrace_search`

**Description:** Search xTrace error registry for a known error signature
**Required:** keyword

| Parameter | Type | Description |
|-----------|------|-------------|
| `keyword` | `string` |  |


#### `xtrace_status`

**Description:** Get xTrace error tracking summary statistics
**Required:** None

#### `dtrace_add`

**Description:** Log an architectural decision to DTrace
**Required:** title, decision, rationale

| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | `string` |  |
| `context` | `string` |  |
| `decision` | `string` |  |
| `alternatives` | `string` |  |
| `rationale` | `string` |  |
| `category` | `string` |  |


#### `dtrace_search`

**Description:** Search DTrace decision registry
**Required:** keyword

| Parameter | Type | Description |
|-----------|------|-------------|
| `keyword` | `string` |  |


#### `skill_router_match`

**Description:** Match a task description to relevant skills using the Skill Router
**Required:** task

| Parameter | Type | Description |
|-----------|------|-------------|
| `task` | `string` |  |


#### `output_condenser`

**Description:** Condense command output to essential information
**Required:** output_type, content

| Parameter | Type | Description |
|-----------|------|-------------|
| `output_type` | `string` |  |
| `content` | `string` |  |


#### `goal_registry_init`

**Description:** Initialize a new goal in the Goal Registry
**Required:** goal

| Parameter | Type | Description |
|-----------|------|-------------|
| `goal` | `string` |  |


#### `goal_registry_add_subgoal`

**Description:** Add a sub-goal to the current goal stack
**Required:** description

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `string` |  |


#### `goal_registry_status`

**Description:** Get current goal registry status
**Required:** None

#### `goal_registry_check_alignment`

**Description:** Check if current action aligns with the original goal
**Required:** current_action

| Parameter | Type | Description |
|-----------|------|-------------|
| `current_action` | `string` |  |


#### `commitment_checker_list`

**Description:** List pending commitments for this session
**Required:** None

#### `commitment_checker_verify`

**Description:** Mark a commitment as verified for this session
**Required:** id

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | `string` |  |


### DevOps

_7 tools_

#### `devops_container_debug`

**Description:** Diagnose container issues (Podman/Docker) from error logs
**Required:** error_log

| Parameter | Type | Description |
|-----------|------|-------------|
| `error_log` | `string` |  |
| `runtime` | `string` |  |
| `context` | `string` |  |


#### `devops_permissions_analyze`

**Description:** Analyze permission/usernamespace issues in container environments
**Required:** None

| Parameter | Type | Description |
|-----------|------|-------------|
| `mount_path` | `string` |  |
| `container_user` | `string` |  |
| `host_user` | `string` |  |
| `error_symptom` | `string` |  |


#### `devops_compose_generator`

**Description:** Generate Docker/Podman Compose files from service definitions
**Required:** services

| Parameter | Type | Description |
|-----------|------|-------------|
| `services` | `array` |  |
| `networks` | `array` |  |
| `runtime` | `string` |  |


#### `devops_samba_config`

**Description:** Generate Samba/SMB share configurations with OS-specific troubleshooting
**Required:** share_name, path

| Parameter | Type | Description |
|-----------|------|-------------|
| `share_name` | `string` |  |
| `path` | `string` |  |
| `users` | `array` |  |
| `options` | `object` |  |


#### `devops_mergerfs_setup`

**Description:** Configure mergerfs for drive pooling with policy explanations and optimization tips
**Required:** source_paths, mount_point

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_paths` | `array` |  |
| `mount_point` | `string` |  |
| `policy` | `string` |  |
| `options` | `object` |  |


#### `devops_dockerfile_analyze`

**Description:** Analyze and optimize Dockerfiles for security, caching, and size
**Required:** dockerfile

| Parameter | Type | Description |
|-----------|------|-------------|
| `dockerfile` | `string` |  |


#### `devops_network_troubleshoot`

**Description:** Diagnose container networking issues (DNS, ports, bridges, host networking)
**Required:** symptom

| Parameter | Type | Description |
|-----------|------|-------------|
| `symptom` | `string` |  |


### Game Dev

_7 tools_

#### `gamedev_design_analyze`

**Description:** Analyze game concept: fun factor, engagement loops, monetization fit, market position
**Required:** concept, genre

| Parameter | Type | Description |
|-----------|------|-------------|
| `concept` | `string` |  |
| `genre` | `string` |  |
| `platform` | `string` |  |


#### `gamedev_scaffold_project`

**Description:** Generate Unity/Unreal/Roblox project scaffold with real working boilerplate files
**Required:** engine, genre

| Parameter | Type | Description |
|-----------|------|-------------|
| `engine` | `string` |  |
| `genre` | `string` |  |
| `name` | `string` |  |
| `features` | `array` |  |


#### `gamedev_mechanics_guide`

**Description:** Game mechanics design guide: core loops, progression systems, reward schedules by genre
**Required:** genre

| Parameter | Type | Description |
|-----------|------|-------------|
| `genre` | `string` |  |
| `complexity` | `string` |  |


#### `gamedev_monetization`

**Description:** Monetization strategy recommendations with revenue estimates and ethical guidance
**Required:** platform, genre

| Parameter | Type | Description |
|-----------|------|-------------|
| `platform` | `string` |  |
| `genre` | `string` |  |
| `audience` | `string` |  |


#### `gamedev_optimization`

**Description:** Engine-specific optimization advice (FPS, draw calls, memory, load times, network)
**Required:** engine, issue

| Parameter | Type | Description |
|-----------|------|-------------|
| `engine` | `string` |  |
| `issue` | `string` |  |


#### `gamedev_compare_engines`

**Description:** Compare game engines (Unity/Unreal/Godot/Roblox) for specific project types
**Required:** project_type

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_type` | `string` |  |
| `team_size` | `string` |  |
| `budget` | `string` |  |


#### `gamedev_level_design`

**Description:** Level design principles, flow diagrams, pacing guides, and playtesting checklists
**Required:** genre, level_type

| Parameter | Type | Description |
|-----------|------|-------------|
| `genre` | `string` |  |
| `level_type` | `string` |  |


### Literature

_4 tools_

#### `lit_analyze_text`

**Description:** Analyze text for reading level (Flesch-Kincaid), key concepts, argument structure, and sentiment
**Required:** text

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `string` |  |


#### `lit_extract_concepts`

**Description:** Extract key concepts, their definitions, context, and relationships from text
**Required:** text

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `string` |  |


#### `lit_generate_study_guide`

**Description:** Generate a study guide from content with key terms, discussion questions, and section summaries
**Required:** content

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `string` |  |


#### `lit_analyze_philosophy`

**Description:** Analyze philosophical arguments: premises, conclusions, reasoning type, detected philosophers, and schools
**Required:** text

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `string` |  |


### Memory Search

_5 tools_

#### `memory_search`

**Description:** Local BM25 memory search with synonym expansion and fuzzy matching — zero LLM cost
**Required:** query

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `string` |  |
| `limit` | `integer` |  |
| `fuzzy_threshold` | `number` |  |


#### `memory_synthesize`

**Description:** Search and synthesize memory results into a narrative with inline citations
**Required:** query

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `string` |  |
| `max_sources` | `integer` |  |
| `min_confidence` | `number` |  |


#### `memory_add`

**Description:** Add a memory entry for future BM25 search and synthesis
**Required:** text

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `string` |  |
| `source` | `string` |  |
| `metadata` | `object` |  |


#### `memory_consolidate`

**Description:** Merge duplicate/similar memory entries by Jaccard similarity threshold
**Required:** None

| Parameter | Type | Description |
|-----------|------|-------------|
| `threshold` | `number` |  |


#### `memory_status`

**Description:** Get NE-Memory engine status: entry count, storage size, unique terms, last timestamp
**Required:** None

### Sensory

_12 tools_

#### `sensory_browse`

**Description:** Navigate to a URL using Playwright (headless Firefox) and extract content. Modes: text, html, markdown, links, metadata
**Required:** url

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `string` |  |
| `extract_mode` | `string` |  |
| `timeout_ms` | `integer` |  |


#### `sensory_screenshot`

**Description:** Take a screenshot of a web page via Playwright
**Required:** url

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `string` |  |
| `output_path` | `string` |  |
| `timeout_ms` | `integer` |  |


#### `sensory_interact`

**Description:** Navigate to URL and perform actions (click, type, press, wait)
**Required:** url, actions

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `string` |  |
| `actions` | `array` |  |
| `selector` | `string` |  |
| `value` | `string` |  |
| `timeout_ms` | `integer` |  |


#### `sensory_extract_pdf`

**Description:** Extract text from a PDF file
**Required:** file_path

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `string` |  |
| `max_pages` | `integer` |  |


#### `sensory_extract_html`

**Description:** Extract text from raw HTML content. Modes: clean (trafilatura), soup (BeautifulSoup), tables
**Required:** html_content

| Parameter | Type | Description |
|-----------|------|-------------|
| `html_content` | `string` |  |
| `mode` | `string` |  |


#### `sensory_extract_image`

**Description:** Extract text from an image via OCR (if pytesseract installed) or return image metadata
**Required:** file_path

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `string` |  |


#### `sensory_scrape`

**Description:** Fetch a URL via HTTP (no JS) and extract content. Modes: text, html, links, tables, json
**Required:** url

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `string` |  |
| `mode` | `string` |  |
| `headers` | `object` |  |


#### `sensory_extract_article`

**Description:** Extract clean article content from a URL using trafilatura
**Required:** url

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `string` |  |


#### `sensory_api_request`

**Description:** Make an HTTP API request (GET/POST/PUT/DELETE/PATCH) with structured response
**Required:** url

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `string` |  |
| `method` | `string` |  |
| `data` | `object` |  |
| `headers` | `object` |  |
| `params` | `object` |  |
| `timeout` | `integer` |  |


#### `sensory_fetch_rss`

**Description:** Parse an RSS/Atom feed and return structured items
**Required:** feed_url

| Parameter | Type | Description |
|-----------|------|-------------|
| `feed_url` | `string` |  |
| `max_items` | `integer` |  |


#### `sensory_read_file`

**Description:** Read a local text file and return its content
**Required:** file_path

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `string` |  |
| `max_size_kb` | `integer` |  |


#### `sensory_search`

**Description:** Web search via DuckDuckGo (no API key needed). Returns title, URL, snippet.
**Required:** query

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `string` |  |
| `num_results` | `integer` |  |


### Verifier

_2 tools_

#### `verifier_status`

**Description:** Get verifier middleware status: checks run, violations found, renudges sent, uptime
**Required:** None

#### `verifier_renudge`

**Description:** Send a correction signal (renudge) to steer the agent back on track
**Required:** target, correction

| Parameter | Type | Description |
|-----------|------|-------------|
| `target` | `string` |  |
| `correction` | `object` |  |
| `strategy` | `string` |  |


---
## Data Files

| File | Category | Keys | Records |
|------|----------|------|---------|
| `data\benchmark-results.json` | results | `overall_score, results[].detail[].id, results[].score, frontier_scores.Gemini 1.5 Pro, results[].total ...` | 2 |
| `data\blind-answer-key.json` | config | `q4.explanation, q3.correct, q7, q4, q3.type ...` | 0 |
| `data\blind-my-answers.json` | config | `q7, q4, q3.type, q8.code, q1 ...` | 0 |
| `data\blind-questions.json` | config | `` | 10 |
| `data\commitment-registry.json` | registry | `commitments, commitments[].id, commitments[].text, version, commitments[].stored_date ...` | 5 |
| `data\comparison-results.json` | results | `compound_multiplier, improvement_pct, tests[].with_tools_score, tests[].test, average_without ...` | 6 |
| `data\consultation-cr-20260715-134730.json` | config | `synthesis, title, synthesis.conflicts, analyses[].perspective, analyses[].label ...` | 2 |
| `data\dag-definitions\multi-phase-refactor.json` | config | `nodes[].expected_outputs, config.heartbeat_interval_seconds, nodes[].prompt_template, nodes, description ...` | 6 |
| `data\dag-definitions\research-implement-verify.json` | config | `config.heartbeat_interval_seconds, nodes[].prompt_template, edges, nodes[].retry_count, config ...` | 5 |
| `data\dag-definitions\security-audit-pipeline.json` | config | `config.heartbeat_interval_seconds, nodes[].prompt_template, edges, nodes[].retry_count, config ...` | 5 |
| `data\dag-definitions\seed-dag.json` | config | `nodes[].expected_outputs, nodes[].prompt_template, nodes, description, nodes[].timeout_seconds ...` | 3 |
| `data\dag-schemas\dag-definition-v1.json` | config | `type, $schema, title, required, description ...` | 5 |
| `data\dag-schemas\state-contract-v1.json` | config | `type, $schema, title, required, description ...` | 6 |
| `data\dag-traces\multi-phase-refactor-20260715-230858.json` | config | `summary.failed_nodes, summary, node_count, started_at, levels ...` | 4 |
| `data\dag-traces\research-implement-verify-20260715-230849.json` | config | `summary.failed_nodes, summary, node_count, started_at, levels ...` | 3 |
| `data\dag-traces\research-implement-verify-20260715-230910.json` | config | `summary.failed_nodes, summary, node_count, started_at, levels ...` | 3 |
| `data\dag-traces\security-audit-pipeline-20260715-230856.json` | config | `summary.failed_nodes, summary, summary.phases.skipped, node_count, started_at ...` | 3 |
| `data\decision-registry.json` | registry | `decisions[].notes, decisions[].consequences, decisions[].title, decisions[].files, decisions[].context ...` | 7 |
| `data\doc-index.json` | config | `summary, project, scripts[].language, mcp_tools, generated_at ...` | 48 |
| `data\error-registry.json` | registry | `errors, version` | 0 |
| `data\flash-benchmark-results.json` | results | `overall_pct, mc_math_pct, model, mode, code ...` | 0 |
| `data\free-provider-template.json` | config | `provider, _comment, $schema, _guide` | 0 |
| `data\identity-evolution-log.json` | trace | `versions, versions[].changes_made, versions[].date, versions[].version, versions[].triggers ...` | 2 |
| `data\identity-schema.json` | config | `type, $schema, title, additionalProperties, required ...` | 8 |
| `data\mcp-server-test-results.json` | results | `tests[].name, overall.all_passed, overall.total, tests[].detail, tests[].passed ...` | 10 |
| `data\orchestration-research.json` | config | `frameworks[].communication, frameworks[].name, recommended_pattern, frameworks[].merge, hybrid_pattern_description ...` | 5 |
| `data\sandbox-log.json` | trace | `` | 27 |
| `data\security-scan-report.json` | config | `summary.findings_by_severity, summary, summary.findings_by_category.code, findings[].context, integration.dtrace_decision_logged ...` | 17 |
| `data\synonyms.json` | config | `synonyms.build, synonyms.secure, synonyms.test, synonyms.consolidate, synonyms.synthesize ...` | 0 |
| `data\tool-inventory.json` | config | `` | 68 |

---
## Integration Points

### MCP Server
- Entry point: `scripts/tools-mcp-server.py` — JSON-RPC over stdio
- Exposes 122 tools across 26 modules
- Protocol: Model Context Protocol (MCP) v2024-11-05

### Data Flow
- Scripts in `scripts/` produce output consumed by other scripts or the MCP server
- `data/` stores structured results, registries, and configuration
- MCP server routes tool calls to PowerShell scripts and Python modules

### Verifier Middleware
- All tool calls pass through `VerifierMiddleware` pre/post checks
- Mode: advisory (logs violations, does not block)