#!/usr/bin/env python3
"""
Pattern Flipper — Dynamically selects and applies the optimal reasoning strategy.
Routes tasks through Mixture of Agents, Tree of Thoughts, Reflexion,
Constitutional AI, Chain-of-Thought, or Self-Rewarding patterns.

Usage:
    from pattern_flipper import PatternFlipper
    flipper = PatternFlipper()
    result = flipper.process("Design a distributed system", strategy="auto")
"""

import json, sys, os, re, time, hashlib, itertools
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Any
from enum import Enum
from pathlib import Path


#  Strategy Definitions 

class Strategy(Enum):
    COT = "chain-of-thought"         # Step-by-step linear reasoning
    TOT = "tree-of-thoughts"         # Parallel exploration + pruning
    REFLEXION = "reflexion"          # Generate → evaluate → refine loop
    CONSTITUTIONAL = "constitutional" # Self-check against principles
    MOA = "mixture-of-agents"        # Multiple specialized agents collaborate
    SELF_REWARDING = "self-rewarding" # Self-generated critique + improvement
    AUTO = "auto"                    # Router decides


STRATEGY_DESCRIPTIONS = {
    Strategy.COT: {
        "description": "Step-by-step linear reasoning with explicit decomposition",
        "best_for": ["math", "logic", "debugging", "code generation"],
        "tokens": "low",
        "strength": "Reliable, interpretable, low cost",
        "weakness": "No backtracking, can commit to wrong path early",
    },
    Strategy.TOT: {
        "description": "Multiple reasoning branches explored in parallel with pruning",
        "best_for": ["planning", "creative writing", "strategy", "optimization"],
        "tokens": "high",
        "strength": "Explores alternatives, avoids local maxima",
        "weakness": "Expensive, complex to implement",
    },
    Strategy.REFLEXION: {
        "description": "Generate output, evaluate, reflect on failures, regenerate",
        "best_for": ["code review", "essay writing", "problem solving", "research"],
        "tokens": "medium-high",
        "strength": "Iterative improvement, catches own mistakes",
        "weakness": "Can over-iterate, diminishing returns",
    },
    Strategy.CONSTITUTIONAL: {
        "description": "Output constrained by a set of principles with self-checks",
        "best_for": ["content moderation", "safety-critical", "policy compliance", "ethical decisions"],
        "tokens": "medium",
        "strength": "Safe, principled, auditable",
        "weakness": "Can be overly cautious, rigid",
    },
    Strategy.MOA: {
        "description": "Multiple specialist agents collaborate via debate or voting",
        "best_for": ["architecture", "security audit", "complex decisions", "consensus problems"],
        "tokens": "very high",
        "strength": "Diverse perspectives, reduces blind spots",
        "weakness": "Expensive, coordination overhead",
    },
    Strategy.SELF_REWARDING: {
        "description": "Model generates its own critique and reward signal, self-improves",
        "best_for": ["code optimization", "prompt engineering", "system design", "iterative tasks"],
        "tokens": "medium-high",
        "strength": "Autonomous improvement, no external judge needed",
        "weakness": "Reward hacking, can reinforce bad patterns",
    },
}


#  Prompt Templates per Strategy 

STRATEGY_PROMPTS = {
    Strategy.COT: """<strategy>chain-of-thought</strategy>
<protocol>
Work through this step-by-step:

1. Understand: Restate the problem in your own words
2. Decompose: Break it into sub-problems
3. Solve each sub-problem sequentially
4. Combine: Synthesize individual solutions
5. Verify: Check your work for errors

For each step, show your reasoning explicitly before moving to the next.
</protocol>
<task>{prompt}</task>""",

    Strategy.TOT: """<strategy>tree-of-thoughts</strategy>
<protocol>
Instead of a single chain, explore MULTIPLE reasoning paths:

1. Generate 3 distinct approaches to this problem
2. For each approach, think 2-3 steps ahead
3. Evaluate each path for viability (//?)
4. Prune dead ends, expand promising branches
5. Select the best path and develop it fully

Format each branch as:
  Branch A: [approach] → [step 2] → [step 3] → [verdict]
  Branch B: [approach] → [step 2] → [step 3] → [verdict]
  Branch C: [approach] → [step 2] → [step 3] → [verdict]
</protocol>
<task>{prompt}</task>""",

    Strategy.REFLEXION: """<strategy>reflexion</strategy>
<protocol>
Use the reflexion loop — generate, evaluate, reflect, improve:

PASS 1 — Generate an initial solution to this problem.
PASS 2 — Evaluate your solution. What's wrong with it? What edge cases does it miss?
PASS 3 — Reflect on the failures. Why did they happen? What's the root cause?
PASS 4 — Generate an improved solution incorporating your reflections.
PASS 5 — Final evaluation. Is it good enough? If not, flag remaining issues.

Label each pass clearly with [PASS 1], [PASS 2], etc.
</protocol>
<task>{prompt}</task>""",

    Strategy.CONSTITUTIONAL: """<strategy>constitutional</strategy>
<constitution>
Your output MUST satisfy these principles:
1. ACCURACY: Claims must be verifiable and specific
2. SAFETY: No instructions for harmful activities
3. FAIRNESS: Consider multiple perspectives
4. TRANSPARENCY: State assumptions and uncertainties
5. ROBUSTNESS: Handle edge cases gracefully
</constitution>
<protocol>
1. Draft your response to the task
2. Self-check against each constitutional principle
3. For any violations, revise the response
4. Output the FINAL version with a note of what changed
</protocol>
<task>{prompt}</task>""",

    Strategy.MOA: """<strategy>mixture-of-agents</strategy>
<protocol>
Role-play multiple experts collaborating on this task:

EXPERT 1 — Systems Architect: Focus on structure, patterns, scalability
EXPERT 2 — Security Engineer: Focus on threats, vulnerabilities, hardening
EXPERT 3 — Domain Expert: Focus on domain-specific best practices
EXPERT 4 — Skeptic: Focus on what could go wrong, hidden assumptions

Each expert provides their analysis independently, then a moderator synthesizes.
</protocol>
<task>{prompt}</task>""",

    Strategy.SELF_REWARDING: """<strategy>self-rewarding</strategy>
<protocol>
You will improve your own output through self-critique:

1. GENERATE: Produce your best answer to the task
2. CRITIQUE: Rate your answer 1-10 on completeness, correctness, clarity
3. IDENTIFY: List 2-3 specific weaknesses or gaps
4. IMPROVE: Regenerate with those weaknesses addressed
5. VERIFY: Final self-check — is this clearly better than version 1?

Output both versions and the delta between them.
</protocol>
<task>{prompt}</task>""",
}


@dataclass
class PatternResult:
    strategy: Strategy
    prompt: str
    reasoning_path: list
    output: Any = None
    metadata: dict = field(default_factory=dict)


class PatternFlipper:
    """
    Routes tasks to the optimal reasoning strategy.
    Supports auto-detection and manual override.
    """

    def __init__(self, default_strategy: Strategy = Strategy.AUTO):
        self.default_strategy = default_strategy
        self.history = []

    def process(self, prompt: str, strategy: Optional[Strategy] = None,
                inference_fn: Optional[Callable] = None) -> PatternResult:
        """Process a prompt through the selected or auto-detected strategy."""
        strategy = strategy or self.default_strategy
        if strategy == Strategy.AUTO:
            strategy = self._detect_strategy(prompt)

        template = STRATEGY_PROMPTS[strategy]
        augmented_prompt = template.format(prompt=prompt)

        result = PatternResult(
            strategy=strategy,
            prompt=augmented_prompt,
            reasoning_path=[f"Strategy: {strategy.value}"],
        )

        if inference_fn:
            result.output = inference_fn(augmented_prompt)
            result.metadata["raw_output_length"] = len(str(result.output))
        else:
            result.output = augmented_prompt  # Just return the augmented prompt

        result.metadata = {
            "strategy_name": strategy.value,
            "strategy_description": STRATEGY_DESCRIPTIONS[strategy]["description"],
            "best_for": STRATEGY_DESCRIPTIONS[strategy]["best_for"],
            "token_cost": STRATEGY_DESCRIPTIONS[strategy]["tokens"],
            "timestamp": time.time(),
        }

        self.history.append(result)
        return result

    def _detect_strategy(self, prompt: str) -> Strategy:
        """Auto-detect the best strategy based on prompt content."""
        prompt_lower = prompt.lower()

        # Strategy-specific signal detection
        signals = {
            Strategy.COT: [
                r"\b(debug|fix|bug|error|calculate|compute|solve|prove|derive|evaluate)\b",
                r"\b(step by step|explain|how does|why does|trace|walk through)\b",
                r"\b(math|equation|formula|algorithm|logic|proof)\b",
            ],
            Strategy.TOT: [
                r"\b(plan|design|strategy|explore|alternative|option|multiple ways)\b",
                r"\b(creative|novel|innovate|brainstorm|imagine|what if)\b",
                r"\b(optimize|maximize|best approach|trade.?off)\b",
            ],
            Strategy.REFLEXION: [
                r"\b(refactor|rewrite|improve|optimize|review|critique|reflect)\b",
                r"\b(revision|draft|iterate|polish|enhance|redo)\b",
                r"\b(code review|essay|write|compose|author)\b",
            ],
            Strategy.CONSTITUTIONAL: [
                r"\b(safe|safety|ethical|policy|compliance|regulat|audit)\b",
                r"\b(moderat|content|guideline|principle|constitution|harm)\b",
                r"\b(legal|privacy|gdpr|hipaa|bias|fair|responsible)\b",
            ],
            Strategy.MOA: [
                r"\b(architect|system design|distributed|microservice|consensus)\b",
                r"\b(complex|enterprise|large.?scale|multi.?service)\b",
                r"\b(security audit|threat model|risk assess|migration)\b",
            ],
            Strategy.SELF_REWARDING: [
                r"\b(optimize|improve|enhance|upgrade|version|iterate)\b",
                r"\b(prompt engineering|system prompt|instruction)\b",
                r"\b(self.?improve|self.?critique|reinforcement)\b",
            ],
        }

        scores = {}
        for strategy, patterns in signals.items():
            score = sum(1 for p in patterns if re.search(p, prompt_lower))
            if score > 0:
                scores[strategy] = score

        if scores:
            return max(scores, key=scores.get)

        # Default based on prompt length
        word_count = len(prompt.split())
        if word_count > 100:
            return Strategy.REFLEXION
        elif word_count > 50:
            return Strategy.TOT
        return Strategy.COT

    def compare_strategies(self, prompt: str, inference_fn: Callable) -> dict:
        """Run all strategies on the same prompt and compare results."""
        results = {}
        for strategy in [s for s in Strategy if s != Strategy.AUTO]:
            results[strategy.value] = self.process(
                prompt, strategy=strategy, inference_fn=inference_fn
            )
        return results


#  CLI 

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pattern Flipper")
    parser.add_argument("--prompt", "-p", help="The prompt to process")
    parser.add_argument("--strategy", "-s", choices=[s.value for s in Strategy] + ["auto"], default="auto")
    parser.add_argument("--compare", action="store_true", help="Run all strategies and compare")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--list", action="store_true", help="List available strategies")
    
    args = parser.parse_args()
    
    if args.list:
        print("Available Strategies:")
        print("=" * 60)
        for s in [s for s in Strategy if s != Strategy.AUTO]:
            info = STRATEGY_DESCRIPTIONS[s]
            print(f"\n  {s.value}")
            print(f"    {info['description']}")
            print(f"    Best for: {', '.join(info['best_for'])}")
            print(f"    Token cost: {info['tokens']}")
        return

    if not args.prompt:
        args.prompt = input("Enter your prompt: ")

    flipper = PatternFlipper()
    
    if args.compare:
        results = flipper.compare_strategies(args.prompt, lambda p: f"[SIMULATED: {len(p)} chars]")
        if args.json:
            print(json.dumps({k: asdict(v) for k, v in results.items()}, indent=2, default=str))
        else:
            for name, result in results.items():
                print(f"\n{'='*50}")
                print(f"  {name.upper()}")
                print(f"{'='*50}")
                print(f"  Best for: {', '.join(result.metadata['best_for'])}")
                print(f"  Token cost: {result.metadata['token_cost']}")
    else:
        strategy = Strategy(args.strategy) if args.strategy != "auto" else Strategy.AUTO
        result = flipper.process(args.prompt, strategy=strategy)
        
        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print(f"\n{'='*60}")
            print(f" Pattern Flipper — Strategy: {result.strategy.value}")
            print(f"{'='*60}")
            print(f" {STRATEGY_DESCRIPTIONS[result.strategy]['description']}")
            print(f"\n Augmented Prompt ({len(result.prompt.split())} tokens):")
            print("-" * 40)
            print(result.prompt[:2000])
            print("..." if len(result.prompt) > 2000 else "")


if __name__ == "__main__":
    main()
