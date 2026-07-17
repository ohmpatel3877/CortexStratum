"""Tool Router — category tagging + smart tool discovery for 78+ tools."""

# Tool categories and tags — tool_name -> (category, [tags])
TOOL_CATEGORIES = {
    "read_memory_search":              ("memory", ["bm25", "keyword", "fast"]),
    "read_memory_synthesize":          ("memory", ["bm25", "narrative", "synthesis"]),
    "read_memory_vector_search":       ("memory", ["vector", "semantic", "embedding"]),
    "read_memory_hybrid_search":       ("memory", ["hybrid", "bm25+vector", "rrf"]),
    "read_memory_reranked_search":     ("memory", ["reranker", "cross-encoder", "precise"]),
    "write_memory_add":                ("memory", ["write", "store"]),
    "mutate_memory_consolidate":       ("memory", ["merge", "dedup", "jaccard"]),
    "read_memory_status":              ("memory", ["status", "health", "stats"]),
    "read_hooks_prefetch":             ("lifecycle", ["session-start", "context"]),
    "write_hooks_observe":             ("lifecycle", ["log", "observation"]),
    "read_hooks_session_status":       ("lifecycle", ["session", "progress"]),
    "write_hooks_session_end":         ("lifecycle", ["session-end", "finalize"]),
    "mutate_undo":                     ("permissions", ["undo", "checkpoint"]),
    "read_audit_status":               ("permissions", ["audit", "undo-log"]),
    "write_xtrace_log_error":          ("trace", ["error", "log", "failure"]),
    "read_xtrace_search":              ("trace", ["error", "search", "history"]),
    "read_xtrace_status":              ("trace", ["error", "status"]),
    "write_dtrace_add":                ("trace", ["decision", "adr"]),
    "read_dtrace_search":              ("trace", ["decision", "adr", "search"]),
    "write_goal_registry_init":        ("trace", ["goal", "objective"]),
    "write_goal_registry_add_subgoal": ("trace", ["goal", "subgoal"]),
    "read_goal_registry_status":       ("trace", ["goal", "status"]),
    "read_goal_registry_check_alignment": ("trace", ["goal", "alignment"]),
    "read_commitment_checker_list":    ("trace", ["commitment", "promise"]),
    "mutate_commitment_checker_verify":("trace", ["commitment", "verify"]),
    "read_skill_router_match":         ("utilities", ["skill", "router", "dispatch"]),
    "read_verifier_status":            ("utilities", ["verifier", "status"]),
    "write_verifier_renudge":          ("utilities", ["correction", "renudge"]),
    "write_verifier_clear_renudge":    ("utilities", ["correction", "clear"]),
    "read_sensory_browse":             ("web", ["browser", "playwright", "page"]),
    "read_sensory_screenshot":         ("web", ["screenshot", "capture"]),
    "mutate_sensory_interact":         ("web", ["click", "type", "form", "automate"]),
    "read_sensory_extract_pdf":        ("web", ["pdf", "extract", "document"]),
    "read_sensory_extract_html":       ("web", ["html", "parse", "clean"]),
    "read_sensory_extract_image":      ("web", ["ocr", "image", "text"]),
    "read_sensory_scrape":             ("web", ["scrape", "http", "fetch"]),
    "read_sensory_extract_article":    ("web", ["article", "readability"]),
    "read_sensory_api_request":        ("web", ["api", "http", "rest"]),
    "read_sensory_fetch_rss":          ("web", ["rss", "feed", "news"]),
    "read_sensory_read_file":          ("web", ["file", "read", "local"]),
    "read_sensory_search":             ("web", ["search", "duckduckgo", "web"]),
    "read_sensory_set_browser_type":   ("web", ["browser", "switch", "firefox", "chromium"]),
    "read_coder_analyze_code":         ("code", ["analyze", "complexity", "smell"]),
    "read_coder_generate_framework":   ("code", ["scaffold", "generate", "project"]),
    "read_coder_debug":                ("code", ["debug", "error", "fix"]),
    "read_coder_review":               ("code", ["review", "quality", "audit"]),
    "read_coder_explain":              ("code", ["explain", "learn", "education"]),
    "read_coder_convert":              ("code", ["convert", "migrate", "port"]),
    "read_coder_architecture":         ("code", ["architecture", "design", "pattern"]),
    "read_audio_analyze_file":         ("audio", ["analyze", "wav", "amplitude"]),
    "read_audio_waveform":             ("audio", ["waveform", "ascii", "visualize"]),
    "read_audio_frequency_analysis":   ("audio", ["frequency", "dft", "spectrum"]),
    "read_audio_music_theory":         ("audio", ["music", "chord", "scale"]),
    "read_audio_speech_analysis":      ("audio", ["speech", "wpm", "pace"]),
    "read_audio_convert_guide":        ("audio", ["convert", "format", "ffmpeg"]),
    "read_audio_generate_tone":        ("audio", ["tone", "sine", "waveform"]),
    "read_art_generate_svg":           ("art", ["svg", "diagram", "flowchart"]),
    "read_art_generate_theme":         ("art", ["theme", "color", "palette"]),
    "read_art_extract_palette":        ("art", ["palette", "color", "harmony"]),
    "read_art_design_concept":         ("art", ["design", "layout", "typography"]),
    "read_devops_container_debug":     ("devops", ["container", "docker", "podman"]),
    "read_devops_permissions_analyze": ("devops", ["permissions", "namespace", "user"]),
    "read_devops_compose_generator":   ("devops", ["compose", "docker-compose"]),
    "read_devops_samba_config":        ("devops", ["samba", "smb", "share"]),
    "read_devops_mergerfs_setup":      ("devops", ["mergerfs", "union", "pool"]),
    "read_devops_dockerfile_analyze":  ("devops", ["dockerfile", "optimize"]),
    "read_devops_network_troubleshoot":("devops", ["network", "dns", "port"]),
    "read_gamedev_design_analyze":     ("gamedev", ["game", "design", "concept"]),
    "read_gamedev_scaffold_project":   ("gamedev", ["unity", "unreal", "scaffold"]),
    "read_gamedev_mechanics_guide":    ("gamedev", ["mechanics", "gameplay"]),
    "read_gamedev_monetization":       ("gamedev", ["monetization", "revenue"]),
    "read_gamedev_optimization":       ("gamedev", ["optimize", "fps", "performance"]),
    "read_gamedev_compare_engines":    ("gamedev", ["engine", "compare", "unity"]),
    "read_gamedev_level_design":       ("gamedev", ["level", "map", "pacing"]),
    "read_lit_analyze_text":           ("utilities", ["text", "analysis", "readability"]),
    "read_lit_extract_concepts":       ("utilities", ["concept", "extract", "nlp"]),
    "read_lit_generate_study_guide":   ("utilities", ["study", "guide", "education"]),
    "read_lit_analyze_philosophy":     ("utilities", ["philosophy", "argument", "logic"]),
}


def categorize(name: str) -> tuple:
    """Get category and tags for a tool name. Returns ('uncategorized', []) if unknown."""
    return TOOL_CATEGORIES.get(name, ("uncategorized", []))


def suggest(task: str, tools: list[dict], top_k: int = 3) -> list[dict]:
    """Find the best tools for a task by keyword matching names, descriptions, categories, tags."""
    if not task or not tools:
        return []
    task_lower = task.lower()
    task_words = set(w for w in task_lower.split() if len(w) > 2)

    scored = []
    for t in tools:
        name = t.get("name", "")
        desc = t.get("description", "").lower()
        cat, tags = categorize(name)
        search_text = f"{name} {desc} {cat} {' '.join(tags)}".lower()
        kw_matches = [w for w in task_words if w in search_text]
        score = len(kw_matches)
        if task_lower in name:
            score += 5
        if score > 0:
            scored.append({
                "score": score,
                "name": name,
                "description": t.get("description", ""),
                "category": cat,
                "tags": tags,
                "permission": t.get("permission", "read"),
                "reasoning": f"matches: {', '.join(kw_matches[:4])} | category: {cat}",
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
