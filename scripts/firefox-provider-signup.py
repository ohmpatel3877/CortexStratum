"""
Free AI Provider Signup Navigator
Opens each free AI provider's signup/API-key page in Playwright Firefox.
User signs up manually, then pastes API keys into a collected file.
"""

import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

PROVIDERS = [
    {
        "name": "Groq",
        "signup_url": "https://console.groq.com/keys",
        "docs_url": "https://console.groq.com/docs/api-reference",
        "notes": "Free: 30 RPM, 1K RPD. Models: llama-3.3-70b-versatile, qwen3-32b, gpt-oss-120b",
        "env_var": "GROQ_API_KEY",
    },
    {
        "name": "Google Gemini",
        "signup_url": "https://aistudio.google.com/apikey",
        "docs_url": "https://ai.google.dev/gemini-api/docs/quickstart",
        "notes": "Free: 15 RPM, 1.5K RPD. Models: gemini-2.5-flash, gemini-2.5-pro. NOTE: Not available in EU/UK",
        "env_var": "GOOGLE_AI_STUDIO_API_KEY",
    },
    {
        "name": "Mistral",
        "signup_url": "https://console.mistral.ai/api-keys/",
        "docs_url": "https://docs.mistral.ai/getting-started/quickstart/",
        "notes": "Free: ~1B tokens/month. Models: mistral-medium-latest, codestral-latest",
        "env_var": "MISTRAL_API_KEY",
    },
    {
        "name": "SambaNova",
        "signup_url": "https://cloud.sambanova.ai/apis",
        "docs_url": "https://docs.sambanova.ai/apis/",
        "notes": "Free: 20 RPM, 200K tokens/day. Models: DeepSeek-V3.1, Llama-3.3-70B, gpt-oss-120b",
        "env_var": "SAMBANOVA_API_KEY",
    },
    {
        "name": "GitHub Models",
        "signup_url": "https://github.com/settings/tokens",
        "docs_url": "https://docs.github.com/en/github-models/prototyping-with-ai-models",
        "notes": "Free: 10 RPM, 50 RPD. Models: gpt-5, gpt-4.1, gpt-4o, o4-mini, DeepSeek-R1",
        "env_var": "GITHUB_TOKEN",
    },
    {
        "name": "Cerebras",
        "signup_url": "https://cloud.cerebras.ai/",
        "docs_url": "https://inference-docs.cerebras.ai/",
        "notes": "Free: 30 RPM, 1M tokens/day. Ultra-fast ~2600 tok/s. 8K context cap on free.",
        "env_var": "CEREBRAS_API_KEY",
    },
    {
        "name": "NVIDIA NIM",
        "signup_url": "https://build.nvidia.com/",
        "docs_url": "https://docs.api.nvidia.com/nim/reference/",
        "notes": "Free dev: ~40 RPM. 100+ models. DeepSeek-R1, Nemotron-3, Llama-405B",
        "env_var": "NVIDIA_NIM_API_KEY",
    },
    {
        "name": "OpenRouter Free",
        "signup_url": "https://openrouter.ai/keys",
        "docs_url": "https://openrouter.ai/docs/models",
        "notes": "User already has key. Just append :free to model IDs. 200 RPD per model.",
        "env_var": "OPENROUTER_API_KEY",
    },
]

KEYS_FILE = Path(__file__).parent.parent / "data" / "free-provider-keys.json"


async def main():
    async with async_playwright() as p:
        # Launch Firefox headed so user can see and interact
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
        )

        collected_keys = {}
        if KEYS_FILE.exists():
            collected_keys = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            print(f"[i] Loaded {len(collected_keys)} existing keys from {KEYS_FILE}")

        for i, provider in enumerate(PROVIDERS):
            name = provider["name"]
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(PROVIDERS)}] {name}")
            print(f"  Signup: {provider['signup_url']}")
            print(f"  Notes:  {provider['notes']}")
            print(f"  Env:    {provider['env_var']}")
            print(f"{'='*60}")

            page = await context.new_page()
            await page.goto(provider["signup_url"], wait_until="domcontentloaded")

            # Wait for user to sign up and get key
            print(f"\n  -> Sign up at {provider['signup_url']} and get your API key.")
            print(f"  -> Paste your API key below (or press Enter to skip):")

            user_input = input(f"  API Key for {name}: ").strip()
            if user_input:
                collected_keys[provider["env_var"]] = user_input
                print(f"  [+] Saved key for {name}")
            else:
                print(f"  [-] Skipped {name}")

            await page.close()

        # Save collected keys
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEYS_FILE.write_text(
            json.dumps(collected_keys, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n[+] Saved {len(collected_keys)} keys to {KEYS_FILE}")

        await browser.close()

    return collected_keys


if __name__ == "__main__":
    asyncio.run(main())
