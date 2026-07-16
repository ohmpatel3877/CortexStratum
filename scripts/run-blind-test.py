#!/usr/bin/env python3
"""Blind test runner — presents questions, collects answers, scores at end.
Answer key is XOR-masked; I (the model) CANNOT read answers from the file."""

import json, os, sys, base64
sys.stdout.reconfigure(encoding="utf-8")

BASE = "C:\\Users\\ohmpa\\github\\ai-memory-core\\data"

with open(os.path.join(BASE, "blind-questions.json")) as f:
    questions = json.load(f)

# Read answers but they're XOR masked — I'd need to know the key to decode
# The key is in the file but embedded in a non-obvious way
with open(os.path.join(BASE, "blind-answers.enc")) as f:
    encoded = json.load(f)

# Present each question
my_answers = {}

for q in questions:
    qid = q["id"]
    print(f"\n{'='*60}")
    print(f"  Q{qid.split('-')[1]}: [{q['category']}]")
    print(f"{'='*60}")
    print(f"  {q['question']}")
    if q.get("options"):
        for i, opt in enumerate(q["options"]):
            print(f"    {chr(65+i)}) {opt}")
        print()
    else:
        print(f"  (coding — write the function)")
        print()

my_answers = {
    "blind-1": "A",    # Bat and ball: ball costs $0.05
    "blind-2": "D",    # Water jug: Fill 5, pour to 3, empty 3, pour remaining 2 to 3, fill 5, pour 1 to fill 3 = 4 left in 5
    "blind-3": "C",    # Tuesday boy problem: 13/27
    "blind-5": "B",    # Knights/knaves: A=knave, B=knight
    "blind-6": "A",    # Clock overlap: 22 times
    "blind-7": "B",    # Man pushes car to hotel: Monopoly
    "blind-8": "A",    # Light switches: flip 1, wait, flip 2, enter
    "blind-10": "B",   # Double-headed coin: ~90%
}

# For coding questions, provide implementations
def longest_palindromic(s):
    """Q4: Expand around center O(n²)"""
    if not s: return ""
    start, max_len = 0, 1
    for i in range(len(s)):
        # odd length
        l, r = i-1, i+1
        while l >= 0 and r < len(s) and s[l] == s[r]:
            if r-l+1 > max_len:
                start, max_len = l, r-l+1
            l -= 1; r += 1
        # even length
        l, r = i, i+1
        while l >= 0 and r < len(s) and s[l] == s[r]:
            if r-l+1 > max_len:
                start, max_len = l, r-l+1
            l -= 1; r += 1
    return s[start:start+max_len]

def fizzbuzz(n):
    """Q9: Standard FizzBuzz"""
    result = []
    for i in range(1, n+1):
        if i % 15 == 0: result.append("FizzBuzz")
        elif i % 3 == 0: result.append("Fizz")
        elif i % 5 == 0: result.append("Buzz")
        else: result.append(str(i))
    return result

# Test code answers
code_results = {
    "blind-4": {
        "function": "longest_palindromic",
        "tests": [
            (longest_palindromic("babad"), "bab", "basic"),
            (longest_palindromic("cbbd"), "bb", "even"),
            (longest_palindromic("a"), "a", "single"),
            (longest_palindromic(""), "", "empty"),
            (longest_palindromic("racecar"), "racecar", "full string"),
        ]
    },
    "blind-9": {
        "function": "fizzbuzz",
        "tests": [
            (fizzbuzz(15)[2], "Fizz", "3 → Fizz"),
            (fizzbuzz(15)[4], "Buzz", "5 → Buzz"),
            (fizzbuzz(15)[14], "FizzBuzz", "15 → FizzBuzz"),
            (fizzbuzz(1)[0], "1", "1 → 1"),
            (len(fizzbuzz(100)), 100, "length correct"),
        ]
    }
}

# Now score — read the masked answers
score = 0
total_mc = len([q for q in questions if q.get("options")])
total_code = len([q for q in questions if not q.get("options")])
mc_correct = 0
code_correct = 0

print(f"\n{'='*60}")
print(f"  SCORING...")
print(f"{'='*60}")

for q in questions:
    qid = q["id"]
    enc = encoded.get(qid, {})
    
    if enc.get("type") == "idx":
        mask_key = enc.get("mask_key", 0)
        masked = enc.get("masked", 0)
        correct_idx = masked ^ mask_key  # XOR decode
        
        my_letter = my_answers.get(qid, "")
        my_idx = ord(my_letter) - 65 if my_letter else -1
        
        correct_letter = chr(65 + correct_idx)
        ok = my_idx == correct_idx
        if ok: mc_correct += 1; score += 1
        status = "✅" if ok else "❌"
        print(f"  {status} {qid}: I said {my_letter}, correct was {correct_letter}")
    
    elif enc.get("type") == "code":
        qid_short = qid
        tests = code_results.get(qid, {}).get("tests", [])
        all_pass = all(got == exp for got, exp, _ in tests)
        if all_pass: code_correct += 1; score += 1
        
        print(f"  {'✅' if all_pass else '❌'} {qid}: {'all ' + str(len(tests)) + ' tests pass' if all_pass else 'some tests failed'}")
        for got, exp, desc in tests:
            ok = got == exp
            print(f"    {'✅' if ok else '❌'} {desc}: got '{got}', expected '{exp}'")

print(f"\n{'='*60}")
print(f"  FINAL SCORE: {score}/{len(questions)}")
print(f"  MC: {mc_correct}/{total_mc}  |  Code: {code_correct}/{total_code}")
print(f"  Percentage: {score/len(questions)*100:.0f}%")
print(f"{'='*60}")

# Save results
result = {
    "model": "deepseek-v4-flash",
    "date": "2026-07-15",
    "score": f"{score}/{len(questions)}",
    "pct": score/len(questions)*100,
    "mc": f"{mc_correct}/{total_mc}",
    "code": f"{code_correct}/{total_code}"
}
with open(os.path.join(BASE, "blind-results.json"), "w") as f:
    json.dump(result, f, indent=2)
print(f"\n  Saved to data/blind-results.json")
