#!/usr/bin/env python3
"""
Extract ONLY questions from benchmark-harness.py — NO answers.
Output: clean JSON with questions, options, and question IDs only.
Answer keys are stripped entirely so the model cannot cheat.
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent.parent.parent
SRC = BASE / "scripts" / "benchmark-harness.py"
OUT = BASE / "data" / "blind-questions-only.json"

src = SRC.read_text(encoding="utf-8")

# Extract each question list variable name and its content
# We know the structure: VARIABLE = [ {...}, {...}, ... ]
# We'll regex-extract each block and parse out only question data

extracted = {}
bench_names = {
    "MMLU_QUESTIONS": {
        "bench": "mmlu",
        "label": "MMLU (Multitask Language Understanding)",
    },
    "GPQA_QUESTIONS": {"bench": "gpqa", "label": "GPQA (Graduate-Level Q&A)"},
    "HUMANEVAL_QUESTIONS": {
        "bench": "humaneval",
        "label": "HumanEval (Code Generation)",
    },
    "GSM8K_QUESTIONS": {"bench": "gsm8k", "label": "GSM8K (Grade School Math)"},
    "BBH_QUESTIONS": {"bench": "bbh", "label": "BBH (Big-Bench Hard)"},
    "ARC_QUESTIONS": {"bench": "arc", "label": "ARC-Challenge (Reasoning)"},
    "TRUTHFULQA_QUESTIONS": {
        "bench": "truthfulqa",
        "label": "TruthfulQA (Truthfulness)",
    },
    "HELLASWAG_QUESTIONS": {
        "bench": "hellaswag",
        "label": "HellaSwag (Commonsense NLI)",
    },
}

for var_name, info in bench_names.items():
    # Find the variable assignment
    pattern = re.compile(rf"{var_name}\s*=\s*(\[.*?^\])", re.DOTALL | re.MULTILINE)
    match = pattern.search(src)
    if not match:
        print(f"  [SKIP] {var_name}: not found")
        continue

    block = match.group(1)
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        # Try eval as Python literal
        try:
            data = eval(block, {"__builtins__": {}}, {})
        except:
            print(f"  [FAIL] {var_name}: could not parse")
            continue

    clean = []
    for item in data:
        entry = {"id": item.get("id", "?"), "bench": info["bench"]}

        if info["bench"] == "humaneval":
            entry["type"] = "code"
            entry["prompt"] = item.get("prompt", "")
            entry["test_signature"] = item.get("entry_point", "?")
        elif info["bench"] == "gsm8k":
            entry["type"] = "math"
            entry["problem"] = item.get("problem", "")
        elif info["bench"] == "truthfulqa":
            entry["type"] = "qa"
            entry["question"] = item.get("question", "")
        elif info["bench"] == "hellaswag":
            entry["type"] = "commonsense"
            entry["context"] = item.get("context", "")
            entry["endings"] = item.get("endings", [])
        else:
            entry["type"] = "mcq"
            entry["question"] = item.get("question", "")
            entry["options"] = item.get("options", [])

        clean.append(entry)

    extracted[var_name] = {
        "bench": info["bench"],
        "label": info["label"],
        "questions": clean,
    }
    print(f"  [OK] {var_name}: {len(clean)} questions (answers STRIPPED)")

# Also extract blind-benchmark questions (the ones that are actually blind)
blind_src = (BASE / "scripts" / "blind-benchmark.py").read_text(encoding="utf-8")
blind_questions = []
blind_pattern = re.compile(r"QUESTIONS\s*=\s*(\[.*?^\])", re.DOTALL | re.MULTILINE)
blind_match = blind_pattern.search(blind_src)
if blind_match:
    try:
        blind_data = json.loads(blind_match.group(1))
        for item in blind_data:
            entry = {
                "id": item.get("id", "?"),
                "bench": item.get("bench", "?"),
                "subject": item.get("subject", ""),
                "question": item.get("question", ""),
                "options": item.get("options", []),
            }
            if not entry["options"]:
                if entry["bench"] == "humaneval":
                    entry["type"] = "code"
                else:
                    entry["type"] = "open"
            else:
                entry["type"] = "mcq"
            blind_questions.append(entry)
        print(
            f"  [OK] BLIND_QUESTIONS: {len(blind_questions)} questions (answers STRIPPED)"
        )
    except:
        print("  [FAIL] BLIND_QUESTIONS: could not parse")

output = {
    "note": "QUESTIONS ONLY — zero answer keys included. For honest blind model evaluation.",
    "source_file": "benchmark-harness.py + blind-benchmark.py",
    "total_questions": sum(len(v["questions"]) for v in extracted.values())
    + len(blind_questions),
    "benchmarks": extracted,
    "blind_questions": blind_questions,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nSaved: {OUT}")
print(f"Total questions: {output['total_questions']} (zero answers included)")
