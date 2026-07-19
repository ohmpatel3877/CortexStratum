# Free AI Provider Signup Guide for OpenCode

Quick reference for adding free-tier AI providers to your OpenCode setup.

---

## Provider Overview

| Provider | Signup URL | Free Tier | Env Var | Rate Limit |
|----------|-----------|-----------|---------|------------|
| **Groq** | [console.groq.com](https://console.groq.com) | Unlimited (fair use) | `GROQ_API_KEY` | 30 req/min, ~14k tok/min |
| **Google Gemini** | [aistudio.google.com](https://aistudio.google.com/apikey) | 1500 req/day (Flash), 50/day (Pro) | `GEMINI_API_KEY` | 1500 RPD / 15 RPM |
| **Mistral** | [console.mistral.ai](https://console.mistral.ai) | Limited free credits on signup | `MISTRAL_API_KEY` | Varies by model |
| **SambaNova** | [cloud.sambanova.ai](https://cloud.sambanova.ai) | Free tier with API credits | `SAMBANOVA_API_KEY` | Varies |
| **GitHub Models** | [github.com/settings/tokens](https://github.com/settings/tokens) | 15 req/min, 150/day | `GITHUB_TOKEN` | 15 RPM, 150 RPD |
| **Cerebras** | [cloud.cerebras.ai](https://cloud.cerebras.ai) | Free inference tier | `CEREBRAS_API_KEY` | 30 RPM |
| **NVIDIA NIM** | [build.nvidia.com](https://build.nvidia.com) | 1000 credits free on signup | `NVIDIA_API_KEY` | Varies |

---

## Step-by-Step Signup

### 1. Groq (Fastest inference, best free tier)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up with GitHub or Google
3. Navigate to **API Keys** in the sidebar
4. Click **Create API Key**
5. Copy the key (starts with `gsk_`)
6. Set the env var:
   ```powershell
   $env:GROQ_API_KEY = "gsk_your_key_here"
   ```
7. Models: `llama-3.3-70b-versatile` (best all-round), `qwen3-32b` (strong coder), `llama-3.1-8b-instant` (fastest)

### 2. Google Gemini (Largest context window)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with Google account
3. Click **Create API Key**
4. Copy the key
5. Set the env var:
   ```powershell
   $env:GEMINI_API_KEY = "AIza_your_key_here"
   ```
6. Models: `gemini-2.5-flash` (fast + free), `gemini-2.5-pro` (strongest, lower daily limit)

### 3. Mistral (Best code model)

1. Go to [console.mistral.ai](https://console.mistral.ai)
2. Sign up with email or GitHub
3. Navigate to **API Keys**
4. Create a new key
5. Set the env var:
   ```powershell
   $env:MISTRAL_API_KEY = "your_key_here"
   ```
6. Models: `codestral-latest` (code specialist), `mistral-medium-latest` (general)

### 4. SambaNova (Fast DeepSeek hosting)

1. Go to [cloud.sambanova.ai](https://cloud.sambanova.ai)
2. Sign up for an account
3. Navigate to **API Keys**
4. Create a key
5. Set the env var:
   ```powershell
   $env:SAMBANOVA_API_KEY = "your_key_here"
   ```
6. Models: `DeepSeek-V3.1`, `Llama-3.3-70B`

### 5. GitHub Models (Access to GPT models)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Give it a name, no scopes needed (public Models access)
4. Copy the token
5. Set the env var:
   ```powershell
   $env:GITHUB_TOKEN = "ghp_your_token_here"
   ```
6. Models: `gpt-5`, `gpt-4.1`, `o4-mini` (reasoning)

### 6. Cerebras (Fastest Llama inference)

1. Go to [cloud.cerebras.ai](https://cloud.cerebras.ai)
2. Sign up for an account
3. Navigate to **API Keys**
4. Create a key
5. Set the env var:
   ```powershell
   $env:CEREBRAS_API_KEY = "your_key_here"
   ```
6. Models: `llama-3.3-70b` (fastest 70B inference available)

### 7. NVIDIA NIM (Enterprise models)

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Sign up or log in
3. Navigate to **Get API Key**
4. Create a key
5. Set the env var:
   ```powershell
   $env:NVIDIA_API_KEY = "nvapi_your_key_here"
   ```
6. Models: `deepseek-r1`, `nemotron-3-super`

---

## Adding Providers to OpenCode

### Option A: Use `/connect` (Recommended)

1. In OpenCode, run `/connect`
2. Scroll to **Other**
3. Enter provider ID (e.g., `groq`)
4. Paste your API key

Then add the provider config block to `~/.config/opencode/opencode.jsonc`:

```jsonc
// Paste into the "provider" section of opencode.jsonc
"groq": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "Groq (Free Tier)",
  "options": {
    "baseURL": "https://api.groq.com/openai/v1",
    "apiKey": "{env:GROQ_API_KEY}"
  },
  "models": {
    "llama-3.3-70b-versatile": {
      "name": "Llama 3.3 70B Versatile",
      "limit": { "context": 131072, "output": 32768 }
    }
  }
}
```

### Option B: Set API key directly in config

```jsonc
"groq": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "Groq (Free Tier)",
  "options": {
    "baseURL": "https://api.groq.com/openai/v1",
    "apiKey": "gsk_your_key_here"
  },
  "models": {
    "llama-3.3-70b-versatile": {
      "name": "Llama 3.3 70B Versatile",
      "limit": { "context": 131072, "output": 32768 }
    }
  }
}
```

### Option C: Set env vars persistently (Windows)

```powershell
# Set permanently (requires restart)
[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_your_key", "User")
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIza_your_key", "User")
[System.Environment]::SetEnvironmentVariable("CEREBRAS_API_KEY", "your_key", "User")
```

Or add to your PowerShell `$PROFILE`:
```powershell
$env:GROQ_API_KEY = "gsk_your_key"
$env:GEMINI_API_KEY = "AIza_your_key"
$env:CEREBRAS_API_KEY = "your_key"
$env:SAMBANOVA_API_KEY = "your_key"
$env:GITHUB_TOKEN = "ghp_your_token"
$env:NVIDIA_API_KEY = "nvapi_your_key"
```

---

## Switching Models

### Quick switch with /model

In OpenCode, type `/model` and select from the list. Custom providers appear with their display names.

### Set as default in config

```jsonc
{
  "model": "groq/llama-3.3-70b-versatile",
  "small_model": "groq/llama-3.1-8b-instant"
}
```

### Set per-agent

```jsonc
"agent": {
  "build": {
    "model": "gemini/gemini-2.5-flash"
  },
  "verify": {
    "model": "groq/llama-3.3-70b-versatile"
  }
}
```

---

## Recommended Model Rotation Strategy

When rate-limited or optimizing cost/quality:

| Priority | Model | Use Case | Why |
|----------|-------|----------|-----|
| 1 (Default) | `opencode-go/deepseek-v4-flash-free` | General tasks | Zero cost, built into OpenCode |
| 2 (Fast) | `groq/llama-3.3-70b-versatile` | Speed-critical tasks | Fastest 70B inference, generous limits |
| 3 (Quality) | `gemini/gemini-2.5-flash` | Complex reasoning | 1M context, strong reasoning, free |
| 4 (Code) | `mistral/codestral-latest` | Code-heavy tasks | Purpose-built for code |
| 5 (Reasoning) | `github-models/o4-mini` | Hard problems | Chain-of-thought reasoning |
| 6 (Fallback) | `cerebras/llama-3.3-70b` | When others rate-limited | Ultra-fast inference |
| 7 (Heavy) | `gemini/gemini-2.5-pro` | Large context tasks | Best quality, 1M context (limited/day) |

### Auto-rotation pattern

For subagents, assign faster/cheaper models and reserve strong models for the primary agent:

```jsonc
{
  "model": "gemini/gemini-2.5-flash",
  "small_model": "groq/llama-3.1-8b-instant",
  "agent": {
    "build": { "model": "gemini/gemini-2.5-flash" },
    "verify": { "model": "groq/llama-3.3-70b-versatile" },
    "reviewer": { "model": "groq/llama-3.3-70b-versatile" }
  }
}
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `401 Unauthorized` | API key not set or wrong env var name. Run `/connect` or check `$env:VAR_NAME` |
| `429 Rate Limited` | Switch to another provider from the rotation table above |
| Provider not showing in `/model` | Ensure the provider ID in config matches exactly. Restart OpenCode after config changes |
| `model not found` | Check model ID matches the provider's API. Custom provider model IDs are case-sensitive |
| Config changes not applied | Close and reopen OpenCode Desktop. Hot-reload may not catch provider changes |

---

## Full Template

The complete provider template with all 7 providers is at:
`~/github/cortex-stratum/data/free-provider-template.json`

Copy the relevant `provider` blocks from that file into your `~/.config/opencode/opencode.jsonc` file, add your API keys, and restart OpenCode.
