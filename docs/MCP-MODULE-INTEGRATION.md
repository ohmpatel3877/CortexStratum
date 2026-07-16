# MCP Module Integration Guide

Installed: 2026-07-15

Three high-priority external MCP modules installed for the ai-memory-core project.

---

## 1. Zen MCP Server — Cognitive & Decision Support

**Package:** `zen-mcp-server-199bio` (npx) — NPX wrapper for [BeehiveInnovations/zen-mcp-server](https://github.com/BeehiveInnovations/zen-mcp-server)

**Purpose:** Multi-model AI orchestration — gives the agent access to advanced cognitive tools: deep reasoning, code review, planning, debugging, consensus analysis, and security audits.

**Tools exposed:**
- `chat` — General AI chat / collaborative thinking
- `thinkdeep` — Extended reasoning with edge-case analysis
- `planner` — Interactive step-by-step project planning
- `consensus` — Multi-model perspective gathering & debate
- `codereview` — Professional code review with severity levels
- `debug` — Systematic debugging & root cause analysis
- `analyze` — Smart file & codebase analysis
- `challenge` — Critical challenge prompt (anti yes-man)
- `precommit` — Pre-commit validation
- `clink` — Bridge requests to external AI CLIs
- `apilookup` — API/SDK documentation lookup
- `docgen` — Documentation generation
- `secaudit` — Security audit with OWASP analysis
- `tracer` — Static code analysis & call-flow mapping
- `testgen` — Comprehensive test generation
- `refactor` — Intelligent code refactoring
- `listmodels` — Show configured AI models
- `version` — Version info

**Env vars required:**
- `OPENAI_API_KEY` — For OpenAI model access (or `GEMINI_API_KEY` / `OPENROUTER_API_KEY`)

**First-time setup:** Running `npx -y zen-mcp-server-199bio` clones the Python server to `~/.zen-mcp-server/` and creates a `.env` file at `~/.zen-mcp-server/.env`. Configure at least one API key there.

---

## 2. Fetch MCP Server — Web & Data Intelligence

**Package:** `mcp-fetch-server` (npm) by [zcaceres](https://github.com/zcaceres/fetch-mcp)

**Purpose:** Fetch web content in multiple formats — HTML, Markdown, plain text, JSON, readable article content, and YouTube transcripts.

**Tools exposed:**
- `fetch_html` — Fetch raw HTML from a URL
- `fetch_markdown` — Fetch and convert to Markdown
- `fetch_txt` — Fetch and return plain text (stripped of HTML)
- `fetch_json` — Fetch a URL and return JSON response
- `fetch_readable` — Extract main article content via Mozilla Readability
- `fetch_youtube_transcript` — Fetch YouTube video captions/transcript

**Env vars:**
- `FETCH_USER_AGENT` — Custom User-Agent string (optional)
- `FETCH_TIMEOUT` — Request timeout in ms (optional, default 30000)

**Note:** This package is also invocable via the `mcp-fetch` bin alias. The npm package name is `mcp-fetch-server`.

---

## 3. Reddit RSS MCP — Reddit Access (No Auth)

**Package:** `reddit-rss-mcp` (pip) by [jorgen-k](https://github.com/jorgen-k/reddit-mcp)

**Purpose:** Read Reddit content via public RSS feeds. No API key, OAuth, or app registration required. Read-only (browse + search).

**Tools exposed:**
- `browse_subreddit(subreddit, sort, time_filter, limit)` — Posts from a subreddit (hot/new/top/rising/controversial)
- `get_post(url, comment_limit)` — A post plus its comments (flat list via RSS)
- `search_reddit(query, subreddit, sort, time_filter, limit)` — Search Reddit (post titles & bodies, not comments)
- `fetch_json(url)` — Generic JSON fetcher (Reddit URLs get `.rss` treatment)

**Env vars:** None required

**Limitations:**
- RSS feeds don't include scores, upvote ratios, or comment counts
- Search doesn't index comment text — only post titles and bodies
- Very new posts may lag behind in search indexing

---

## Adding to opencode.jsonc

Copy the desired entries into the `"mcp"` section of `~/.config/opencode/opencode.jsonc`:

```jsonc
"mcp": {
  // ... existing servers ...

  "zen": {
    "type": "local",
    "command": ["npx", "-y", "zen-mcp-server-199bio"],
    "env": {
      "OPENAI_API_KEY": "${OPENAI_API_KEY}",
      "ZEN_MODEL": "deepseek-v4-flash-free"
    },
    "enabled": true
  },

  "fetch": {
    "type": "local",
    "command": ["npx", "-y", "mcp-fetch-server"],
    "env": {
      "FETCH_USER_AGENT": "opencode-ai-memory-core/1.0",
      "FETCH_TIMEOUT": "30000"
    },
    "enabled": true
  },

  "reddit": {
    "type": "local",
    "command": ["C:\\Users\\ohmpa\\AppData\\Local\\Programs\\Python\\Python313\\python.exe", "-m", "server"],
    "enabled": true
  }
}
```

> **Note:** The `"type": "local"` and `"enabled": true` fields must be added when copying into `opencode.jsonc`. The config snippet at `.memory/ne/mcp-module-config.jsonc` omits these because it's a reference/template format.

---

## Skill Router Rules

Add these trigger patterns to skill routing configuration to auto-activate the right module:

| Module | Trigger Patterns |
|--------|-----------------|
| Zen    | "think deep", "analyze this", "code review", "plan project", "debug this", "security audit", "consensus", "challenge my thinking" |
| Fetch  | "fetch url", "scrape", "get webpage", "read article", "youtube transcript", "web content" |
| Reddit | "reddit", "subreddit", "search reddit", "browse reddit", "reddit post" |

---

## Config Reference

A template config snippet is available at:
`.memory/ne/mcp-module-config.jsonc`

This file contains the `mcpServers` entries for all three modules in a copy-ready format.
