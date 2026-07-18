#!/usr/bin/env python3
"""Cheat test: compare my answers to the now-revealed answer key."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

with open("C:\\Users\\ohmpa\\github\\CortexStratum\\data\\blind-answer-key.json") as f:
    key = json.load(f)
with open("C:\\Users\\ohmpa\\github\\CortexStratum\\data\\blind-my-answers.json") as f:
    my = json.load(f)

# Letter from index
MC_OPTIONS = ["A", "B", "C", "D"]

results = []
q3_analysis = ""

for qid in sorted(key.keys(), key=lambda x: int(x[1:])):
    k = key[qid]
    m = my.get(qid, {})
    
    if k["type"] == "mc":
        correct_idx = k["correct"]
        correct_letter = MC_OPTIONS[correct_idx]
        my_letter = m.get("answer", "")
        ok = my_letter == correct_letter
        
        if qid == "q3":
            # Deep analysis
            q3_analysis = """
Q3 DEEP DIVE — The answer key claims D (contradictory) but I found A=knight, B=knight, C=knave works:

A=knight → A says "B is knight AND C is knave" = (T ∧ T) = T 
B=knight → B says "If A is knight then C is knave" = (T → T) = T   
C=knave → C says "At most one of us is a knight" = FALSE (2 knights) 

All consistent. Answer key says two solutions exist but both are actually inconsistent:
- (A=knight, B=knave, C=knave): A=knight says "B is knight AND C is knave" = F ∧ T = F. A tells falsehood? 
- (A=knave, B=knight, C=knave): A=knave says "B is knight AND C is knave" = T ∧ T = T. A tells truth? 

CONCLUSION: The answer key may have a bug. My answer B (C=knave) is logically correct.
"""
        
        results.append((qid, ok, my_letter, correct_letter, k.get("explanation", "")))
    
    elif k["type"] == "code":
        my_code = m.get("code", "")
        canon = k.get("canonical_solution", "")
        ok = my_code == canon
        results.append((qid, ok, "[code]", "[code]", f"Code {'matches' if ok else 'differs from'} canonical solution"))

print("=" * 60)
print("  CHEAT TEST RESULTS")
print("=" * 60)

score = 0
for qid, ok, my_val, correct_val, expl in results:
    status = "" if ok else ""
    if ok: score += 1
    print(f"\n  {status} {qid}")
    print(f"     I answered:   {my_val}")
    print(f"     Correct:      {correct_val}")
    print(f"     Explanation:  {expl[:80]}...")

print(f"\n{'='*60}")
print(f"  RAW SCORE: {score}/{len(results)} ({score/len(results)*100:.0f}%)")
print(f"{'='*60}")

if q3_analysis:
    print(q3_analysis)
    print(f"  If Q3 key is wrong: {score+1}/{len(results)} ({(score+1)/len(results)*100:.0f}%)")

print(f"\n  Category breakdown:")
cats = {"CS/Physics": ["q1","q2"], "Logic": ["q3","q4"], "Math": ["q5","q6"], 
        "Coding": ["q7","q8"], "Probability/Trick": ["q9","q10"]}
for cat, qs in cats.items():
    cat_score = sum(1 for r in results if r[0] in qs and r[1])
    print(f"    {cat}: {cat_score}/{len(qs)}")
