---
name: pattern-flipper
description: Dynamically routes AI reasoning through 6 strategies — Chain-of-Thought, Tree of Thoughts, Reflexion, Constitutional AI, Mixture of Agents, Self-Rewarding. Auto-detects the optimal strategy based on task type. Use when the base model needs structured reasoning guidance, you want to compare reasoning approaches, or a task demands more than raw generation.
---

# Pattern Flipper — Dynamic Reasoning Strategy Router

Selects and applies the optimal reasoning strategy for any task. Routes between six proven patterns, each with different strengths in token cost, exploration depth, safety, and collaboration.

## When to Use This Skill

- The model's default response is shallow — needs structured reasoning
- You want to compare multiple reasoning approaches on the same problem
- Task crosses domains (safety + architecture + code)
- Building a system that needs adaptive reasoning depth
- Exploring "what if we thought about this differently"

## Strategy Reference

| Strategy | Token Cost | Best For | Strength | Weakness |
|----------|-----------|----------|----------|----------|
| **Chain-of-Thought** | Low | Math, logic, debugging, code | Simple, reliable, interpretable | No backtracking |
| **Tree of Thoughts** | High | Planning, creative, strategy | Explores alternatives | Expensive |
| **Reflexion** | Medium-High | Code review, essays, research | Iterative improvement | Diminishing returns |
| **Constitutional AI** | Medium | Safety, policy, ethics | Principled, auditable | Can be rigid |
| **Mixture of Agents** | Very High | Architecture, security, complex | Diverse perspectives | Coordination cost |
| **Self-Rewarding** | Medium-High | Optimization, prompt engineering | Autonomous improvement | Reward hacking risk |

## Architecture

```
                    
                       Task Input  
                    
                           
                    
                       Router       ← keyword + length analysis
                    
                           
        
                                            
    
  Chain of        Tree of         Reflexion   
  Thought         Thoughts                    
    
 Step-by-step    Parallel        Generate→    
 decomposition   branches +      Evaluate→    
                 pruning         Reflect→     
                                 Improve      
    

    
Constitutional   Mixture of      Self-        
 AI              Agents          Rewarding    
    
 Draft → Self-   Architects +    Generate→    
 check →         Security +      Critique→    
 Revise          Domain +        Improve→     
                 Skeptic         Self-score   
    
```

## Usage

### Python API

```python
from pattern_flipper import PatternFlipper, Strategy

flipper = PatternFlipper()

# Auto-detect best strategy
result = flipper.process("Debug this race condition in async code")
print(f"Selected: {result.strategy.value}")
print(result.prompt)  # Augmented prompt with strategy scaffolding

# Force a specific strategy
result = flipper.process("Design a fault-tolerant system", strategy=Strategy.MOA)

# Compare all strategies
results = flipper.compare_strategies("Write a rate limiter", my_inference_fn)
```

### CLI

```bash
# Auto-detect
python scripts/pattern_flipper.py --prompt "Debug this Rust async code"

# Force strategy
python scripts/pattern_flipper.py --prompt "Design a system" --strategy tree-of-thoughts

# Compare all
python scripts/pattern_flipper.py --prompt "Rate limiter design" --compare

# List available
python scripts/pattern_flipper.py --list

# JSON output
python scripts/pattern_flipper.py --prompt "..." --json
```

## Auto-Detection Logic

The router selects strategy based on keyword signals:

| If prompt contains... | Strategy selected |
|-----------------------|-------------------|
| debug, fix, error, calculate, prove, explain | Chain-of-Thought |
| plan, design, explore, alternatives, brainstorm | Tree of Thoughts |
| refactor, rewrite, review, critique, iterate | Reflexion |
| safety, ethical, policy, compliance, privacy | Constitutional AI |
| architecture, distributed, consensus, complex | Mixture of Agents |
| optimize, improve, self-critique, reinforcement | Self-Rewarding |
| Long prompts (>100 words) | Reflexion |
| Medium prompts (50-100 words) | Tree of Thoughts |
| Short prompts | Chain-of-Thought |

## NE-Memory Integration

```python
# Store the best strategy for a recurring task type
type: task_learning
content: "Pattern Flipper: architecture tasks consistently perform
          best with Mixture of Agents strategy"
tags: ["pattern-flipper", "best-practices", "strategy-selection"]
```

## Common Issues

| Issue | Fix |
|-------|-----|
| Strategy feels wrong for the task | Override with `--strategy` flag |
| Too expensive (MoA/ToT) | Switch to Reflexion or CoT |
| Constitutional AI too restrictive | Relax principles or use Self-Rewarding instead |
| Self-Rewarding loops forever | Cap iterations at 3 in the reflexion protocol |
| Router misclassifies the task | Add explicit domain hint in the prompt |
