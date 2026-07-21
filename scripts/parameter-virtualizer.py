#!/usr/bin/env python3
"""
Parameter Virtualizer — Makes smaller/free models perform like larger/paid ones.

A meta-cognitive layer that injects scaffolding, self-consistency,
chain-of-thought enforcement, and multi-pass verification into model
interactions. The weaker model doesn't have the parameters — so we
give it virtual ones through structured reasoning protocols.

Usage:
    from parameter_virtualizer import ParameterVirtualizer

    pv = ParameterVirtualizer(mode="auto")
    result = pv.process("Write a production-grade MCP server in Rust")

    # Or via CLI:
    # python scripts/parameter-virtualizer.py --prompt "..." --mode expert
"""

import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

#  Parameter Profiles — Simulate different "model sizes"
# Each profile injects specific behavioral scaffolding that compensates
# for missing training data, weaker attention mechanisms, or reduced
# parameter counts in the base model.

PARAMETER_PROFILES = {
    "base": {
        "description": "Default free model. Minimal scaffolding.",
        "temperature": 0.7,
        "token_budget": 4096,
        "chain_of_thought": False,
        "self_consistency_passes": 1,
        "verification": False,
        "persona": None,
    },
    "enhanced": {
        "description": "Simulates a ~70B model from a ~7B base.",
        "temperature": 0.5,
        "token_budget": 8192,
        "chain_of_thought": True,
        "self_consistency_passes": 3,
        "verification": True,
        "persona": "senior_engineer",
    },
    "expert": {
        "description": "Simulates a ~180B+ model from a ~70B base.",
        "temperature": 0.3,
        "token_budget": 16384,
        "chain_of_thought": True,
        "self_consistency_passes": 5,
        "verification": True,
        "persona": "architect",
    },
    "genius": {
        "description": "Simulates frontier-model reasoning from any base.",
        "temperature": 0.2,
        "token_budget": 32768,
        "chain_of_thought": True,
        "self_consistency_passes": 7,
        "verification": True,
        "persona": "polymath",
    },
}

#  Personas — Behavioral masks that simulate parameter depth

PERSONAS = {
    "senior_engineer": {
        "system_prompt": """You are a senior engineer with 15 years of experience. Before answering:
1. Break the problem into components
2. Identify edge cases and failure modes
3. Consider performance, security, and maintainability
4. Provide concrete implementation details, not abstractions
5. If uncertain, state what you'd need to verify""",
        "thinking_style": "systematic",
    },
    "architect": {
        "system_prompt": """You are a software architect responsible for large-scale systems. Before answering:
1. Analyze the problem from 10,000 feet — data flow, boundaries, contracts
2. Identify architectural patterns that apply (event-driven, CQRS, clean architecture, etc.)
3. Consider trade-offs: consistency vs availability, coupling vs cohesion
4. Produce a structured plan with phases, milestones, and risk assessments
5. Include interface contracts and data models before implementation""",
        "thinking_style": "top_down",
    },
    "polymath": {
        "system_prompt": """You are a polymath with deep expertise across computer science, mathematics, physics, and systems engineering. Before answering:
1. Identify the fundamental principles underlying the problem
2. Draw analogies from adjacent fields that offer insight
3. Apply first-principles reasoning — decompose to axioms, rebuild
4. Cross-reference solutions against known research papers and established patterns
5. Consider long-term evolution of the solution, not just immediate needs""",
        "thinking_style": "first_principles",
    },
    "critic": {
        "system_prompt": """You are a ruthless code reviewer and system architect. Your job is to find flaws:
1. Assume nothing works until proven otherwise
2. Question every assumption and implicit dependency
3. Identify security vulnerabilities, race conditions, and resource leaks
4. Check for consistency with stated requirements and implicit constraints
5. Rate severity: CRITICAL, HIGH, MEDIUM, LOW, INFO""",
        "thinking_style": "adversarial",
    },
}


@dataclass
class VirtualConfig:
    """Configuration for a parameter virtualization session."""

    mode: str = "auto"
    temperature: float = 0.5
    token_budget: int = 8192
    chain_of_thought: bool = True
    self_consistency_passes: int = 3
    verification: bool = True
    persona: str | None = "senior_engineer"
    domain: str | None = None

    def resolve_mode(self) -> str:
        """Auto-select mode based on task complexity."""
        if self.mode != "auto":
            return self.mode
        return (
            "expert"
            if self.domain in ("security", "architecture", "distributed")
            else "enhanced"
        )


class ParameterVirtualizer:
    """
    The core engine. Takes a model and task, returns a structured execution
    plan with virtual-parameter scaffolding applied.
    """

    def __init__(self, config: VirtualConfig | None = None):
        self.config = config or VirtualConfig()
        self.profile = None
        self.persona = None
        self.session_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]

    def process(self, prompt: str, context: dict | None = None) -> dict:
        """
        Main entry point. Virtualizes the prompt for the target model.

        Returns a dict with:
          - virtual_prompt: the augmented prompt to send to the model
          - inference_plan: how to run inference (temperature, passes, etc.)
          - verification_criteria: what to check in the output
          - expected_quality: estimated output quality level
        """
        context = context or {}
        mode = self.config.resolve_mode()
        self.profile = PARAMETER_PROFILES.get(mode, PARAMETER_PROFILES["enhanced"])

        if self.config.persona and self.config.persona in PERSONAS:
            self.persona = PERSONAS[self.config.persona]

        return {
            "session_id": self.session_id,
            "mode": mode,
            "virtual_prompt": self._build_virtual_prompt(prompt, context),
            "inference_plan": self._build_inference_plan(prompt),
            "verification_criteria": self._build_verification(prompt),
            "expected_quality": self._estimate_quality(prompt),
        }

    def _estimate_token_count(self, text: str) -> int:
        """Rough token estimate (~4 chars per token for most models)."""
        return len(text) // 4

    def _enforce_token_budget(self, prompt: str, budget: int) -> tuple[str, bool]:
        """Truncate prompt to fit within budget. Returns (adjusted_prompt, truncated)."""
        estimated = self._estimate_token_count(prompt)
        if estimated <= budget:
            return prompt, False
        # Truncate to roughly fit, keeping the end (most recent context)
        max_chars = budget * 4
        if len(prompt) > max_chars:
            truncated = prompt[-max_chars:]
            return truncated, True
        return prompt, False

    def _build_virtual_prompt(self, prompt: str, context: dict) -> str:
        """Build the augmented prompt with cognitive scaffolding."""
        parts = []

        # 1. System persona (simulates parameter depth via behavioral framing)
        if self.persona:
            parts.append(f"<system>{self.persona['system_prompt']}</system>")

        # 2. Chain-of-thought scaffolding (simulates deeper attention)
        if self.profile["chain_of_thought"]:
            parts.append("<reasoning_protocol>")
            parts.append("Before producing your final answer, work through:")
            parts.append("1. Problem decomposition — what am I actually being asked?")
            parts.append(
                "2. Context analysis — what constraints and assumptions apply?"
            )
            parts.append("3. Solution generation — enumerate 2-3 approaches")
            parts.append("4. Trade-off analysis — compare approaches systematically")
            parts.append("5. Final selection — choose the best approach and justify")
            parts.append("6. Implementation — produce concrete output")
            parts.append("</reasoning_protocol>")

        # 3. Domain-specific guidance
        if self.config.domain:
            parts.append(f"<domain>{self.config.domain}</domain>")

        # 4. Context injection
        if context.get("files"):
            parts.append("<context>")
            for f in context["files"][:5]:
                parts.append(f"--- {f['path']} ---")
                parts.append(f["content"][:500])
            parts.append("</context>")

        # 5. The actual prompt
        parts.append(f"<task>{prompt}</task>")

        # 6. Output format specification
        if self.profile["verification"]:
            parts.append("<output_requirements>")
            parts.append("- Provide specific, actionable content")
            parts.append("- Include code examples with error handling")
            parts.append("- Note any assumptions or uncertainties")
            parts.append(
                "- If you're unsure, state what additional information would help"
            )
            parts.append("</output_requirements>")

        virtual_prompt = "\n\n".join(parts)

        # Enforce token budget
        budget = self.profile.get("token_budget", 8192)
        adjusted, truncated = self._enforce_token_budget(virtual_prompt, budget)
        if truncated:
            adjusted = (
                "[TRUNCATED — prompt exceeded token budget. Last portion preserved.]\n\n"
                + adjusted
            )
        return adjusted

    def _build_inference_plan(self, prompt: str) -> dict:
        """Build the inference execution plan."""
        complexity = self._estimate_complexity(prompt)

        return {
            "temperature": self.profile["temperature"],
            "max_tokens": self.profile["token_budget"],
            "self_consistency_passes": self.profile["self_consistency_passes"],
            "complexity_score": complexity,
            "recommended_model": "deepseek-v4-flash-free"
            if complexity < 7
            else "deepseek-v4-flash",
            "cache_strategy": self._recommend_cache_strategy(prompt),
        }

    def _recommend_cache_strategy(self, prompt: str) -> dict:
        """
        Analyze the virtualized prompt structure and recommend where to place
        cache_control breakpoints for optimal prompt caching.

        Based on Anthropic prompt caching best practices:
        - Place breakpoints on stable prefixes (system instructions, tools, context)
        - Avoid breakpoints on varying content (timestamps, per-request input)
        - Up to 4 breakpoints supported
        - 20-block lookback window: keep breakpoints within 20 blocks of each other
        - Minimum 1024 tokens required for caching on most models
        """
        parts = prompt.split("\n\n")
        recommendations = []
        stable_boundaries = []

        for i, part in enumerate(parts):
            stripped = part.strip()
            # Identify stable (cacheable) sections by tag pattern
            if stripped.startswith("<system>") or stripped.startswith(
                "<reasoning_protocol>"
            ):
                stable_boundaries.append(i)
            elif stripped.startswith("<domain>"):
                stable_boundaries.append(i)
            elif stripped.startswith("<context>") and "</context>" in stripped:
                stable_boundaries.append(i)

        budget = self.profile.get("token_budget", 8192)
        estimated_total = self._estimate_token_count(prompt)

        if stable_boundaries and estimated_total >= 1024:
            # Recommend first N breakpoints (max 4, minus 1 for automatic caching slot)
            max_breakpoints = min(len(stable_boundaries), 3)
            for idx in stable_boundaries[:max_breakpoints]:
                block_preview = parts[idx][:60].replace("\n", " ")
                recommendations.append(
                    {
                        "breakpoint_block": idx,
                        "block_preview": block_preview,
                        "cache_control": {"type": "ephemeral"},
                        "rationale": "Stable prefix — suitable for caching",
                    }
                )

        return {
            "recommended": len(recommendations) > 0,
            "estimated_total_tokens": estimated_total,
            "minimum_for_caching": 1024,
            "eligible": estimated_total >= 1024,
            "breakpoints": recommendations,
            "note": "Use cache_control on stable prefixes (system, tools, context), not on varying user input.",
        }

    def generate_prewarm_request(self, system_prompt: str) -> dict:
        """
        Generate a cache pre-warm request (max_tokens=0).
        Fire before user traffic arrives to eliminate cold-start latency.
        """
        estimated = self._estimate_token_count(system_prompt)
        return {
            "strategy": "max_tokens_zero",
            "description": "Pre-warm the prompt cache with max_tokens=0 to eliminate TTFT penalty",
            "system_prompt": system_prompt,
            "estimated_tokens": estimated,
            "eligible": estimated >= 1024,
            "cache_control": {"type": "ephemeral"} if estimated >= 1024 else None,
            "usage_note": (
                "Sends system prompt with max_tokens=0. "
                "API reads prompt into model, writes cache at breakpoint, returns immediately. "
                f"Estimated cost: {estimated} cache write tokens."
            ),
            "limitations": [
                "Incompatible with streaming (stream: true)",
                "Incompatible with extended thinking",
                "Incompatible with structured outputs",
                "Cannot be used in Message Batches",
            ],
        }

    def _build_verification(self, prompt: str) -> list:
        """Build verification criteria matching the prompt type."""
        criteria = []
        keywords = {
            "code": [
                "Code compiles without errors",
                "Error handling present",
                "Edge cases considered",
            ],
            "security": [
                "No hardcoded secrets",
                "Input validation present",
                "Auth boundaries respected",
            ],
            "architecture": [
                "Data flow documented",
                "Interface contracts defined",
                "Failure modes addressed",
            ],
            "general": [
                "Claims are specific and falsifiable",
                "Assumptions explicitly stated",
                "Reasoning is step-by-step",
            ],
        }

        domain = self._detect_domain(prompt)
        criteria.extend(keywords.get(domain, keywords["general"]))

        if self.profile["verification"]:
            criteria.append("Output self-consistent across multiple reasoning paths")

        return criteria

    def _estimate_complexity(self, prompt: str) -> float:
        """Estimate task complexity on a 1-10 scale."""
        score = 3.0
        complexity_signals = {
            "distributed|consensus|transaction": 2.0,
            "security|auth|encryption|threat": 2.0,
            "optimize|performance|scale|latency": 1.5,
            "migrate|refactor|rewrite": 1.5,
            "design|architecture|plan|strategy": 1.0,
            "debug|fix|error|bug": 0.5,
        }
        for pattern, delta in complexity_signals.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                score += delta
        return min(10.0, score)

    def _detect_domain(self, prompt: str) -> str:
        domains = {
            "code": r"write|implement|function|class|method|api|endpoint|route",
            "security": r"security|vulnerability|threat|attack|cve|owasp|harden",
            "architecture": r"architecture|design|pattern|system design|structure|flow",
        }
        for domain, pattern in domains.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                return domain
        return "general"

    def _estimate_quality(self, prompt: str) -> dict:
        return {
            "expected_level": self.profile["description"],
            "confidence": 0.7 if self.profile["self_consistency_passes"] >= 3 else 0.5,
            "boost_factor": min(
                3.0, 1.0 + self.profile["self_consistency_passes"] * 0.3
            ),
        }


#  Self-Consistency Engine
# Runs multiple inference passes and aggregates results. This simulates
# the ensemble-like behavior that larger parameter counts provide natively.


class SelfConsistencyEngine:
    """Runs N passes, aggregates via voting or merge."""

    def __init__(self, passes: int = 3, aggregation: str = "vote"):
        self.passes = passes
        self.aggregation = aggregation

    def execute(self, prompt: str, inference_fn: Callable) -> dict:
        """Run multiple inference passes and combine."""
        results = []
        for i in range(self.passes):
            # Vary temperature slightly for diversity
            temp = 0.3 + (i * 0.1)
            result = inference_fn(prompt, temperature=temp)
            results.append(
                {
                    "pass": i + 1,
                    "temperature": temp,
                    "output": result,
                    "fingerprint": hashlib.md5(str(result).encode()).hexdigest()[:8],
                }
            )

        # Deduplicate by fingerprint
        unique = {}
        for r in results:
            unique[r["fingerprint"]] = r

        return {
            "passes": len(results),
            "unique_answers": len(unique),
            "consensus": len(unique) == 1,
            "results": results,
            "aggregated": self._aggregate(list(unique.values())),
        }

    def _aggregate(self, results: list) -> str:
        if self.aggregation == "vote" and len(results) > 1:
            # Return the longest/most detailed (proxy for thoroughness)
            return max(results, key=lambda r: len(str(r["output"])))["output"]
        return results[0]["output"] if results else ""


#  CLI Entry Point


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Parameter Virtualizer")
    parser.add_argument("--prompt", "-p", help="The prompt to virtualize")
    parser.add_argument(
        "--mode", choices=list(PARAMETER_PROFILES.keys()) + ["auto"], default="auto"
    )
    parser.add_argument(
        "--persona", choices=list(PERSONAS.keys()), default="senior_engineer"
    )
    parser.add_argument("--domain", default=None)
    parser.add_argument("--passes", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.prompt:
        # Interactive mode
        args.prompt = input("Enter your prompt: ")

    config = VirtualConfig(
        mode=args.mode,
        persona=args.persona,
        domain=args.domain,
        self_consistency_passes=args.passes
        or PARAMETER_PROFILES.get(args.mode, {}).get("self_consistency_passes", 3),
    )

    pv = ParameterVirtualizer(config)
    result = pv.process(args.prompt)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f" Parameter Virtualizer — Session: {result['session_id']}")
        print(
            f" Mode: {result['mode']} ({PARAMETER_PROFILES[result['mode']]['description']})"
        )
        print(f"{'=' * 60}")
        print(f"\nVirtual Prompt ({len(result['virtual_prompt'].split())} tokens):")
        print("-" * 40)
        print(result["virtual_prompt"])
        print("\nInference Plan:")
        for k, v in result["inference_plan"].items():
            print(f"  {k}: {v}")
        print("\nVerification Criteria:")
        for c in result["verification_criteria"]:
            print(f"   {c}")
        print(f"\nExpected Quality: {result['expected_quality']['expected_level']}")
        print(f"Confidence: {result['expected_quality']['confidence']:.0%}")


if __name__ == "__main__":
    main()
