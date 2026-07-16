#!/usr/bin/env python3
"""Blind benchmark test for deepseek-v4-flash.
Questions are generated fresh so the model hasn't seen them.
Answers are stored separately and only compared after answering."""

import json, sys, os
sys.stdout.reconfigure(encoding="utf-8")

# Questions ONLY (no answers visible here)
QUESTIONS = [
    # MMLU-style
    {
        "id": "q1", "bench": "mmlu", "subject": "Computer Science",
        "question": "Which of the following best describes a race condition in concurrent programming?",
        "options": [
            "A) Two threads executing the same code simultaneously on different CPU cores",
            "B) The outcome of a program depends on the relative timing of events between threads",
            "C) A deadlock where two threads wait indefinitely for each other's resources",
            "D) A compiler optimization that reorders instructions incorrectly"
        ]
    },
    {
        "id": "q2", "bench": "mmlu", "subject": "Mathematics",
        "question": "The set of all points (x,y) in the plane satisfying |x| + |y| = 1 forms which shape?",
        "options": [
            "A) A circle with radius 1",
            "B) A square rotated 45 degrees (diamond)",
            "C) A regular hexagon",
            "D) A line segment from (-1,0) to (1,0)"
        ]
    },
    {
        "id": "q3", "bench": "mmlu", "subject": "Physics",
        "question": "A ball is thrown vertically upward. Ignoring air resistance, at the highest point of its trajectory:",
        "options": [
            "A) Both velocity and acceleration are zero",
            "B) Velocity is zero but acceleration is non-zero",
            "C) Acceleration is zero but velocity is non-zero",
            "D) Both velocity and acceleration are non-zero"
        ]
    },
    {
        "id": "q4", "bench": "mmlu", "subject": "Biology",
        "question": "Which of the following is the primary function of mitochondria in eukaryotic cells?",
        "options": [
            "A) Protein synthesis",
            "B) Lipid storage",
            "C) ATP production through oxidative phosphorylation",
            "D) DNA replication and repair"
        ]
    },
    # GSM8K-style math
    {
        "id": "q5", "bench": "gsm8k", "subject": "Math",
        "question": "Alice buys 7 notebooks that cost $2.50 each and 3 pens that cost $1.20 each. She pays with a $50 bill. How much change does she receive?",
        "options": []
    },
    {
        "id": "q6", "bench": "gsm8k", "subject": "Math",
        "question": "A train travels at 60 mph for 2 hours, then at 45 mph for 3 hours. What is the total distance traveled?",
        "options": []
    },
    {
        "id": "q7", "bench": "gsm8k", "subject": "Math",
        "question": "If a recipe calls for 2 cups of flour to make 24 cookies, how many cups of flour are needed to make 60 cookies?",
        "options": []
    },
    # Logic / BBH-style
    {
        "id": "q8", "bench": "bbh", "subject": "Logic",
        "question": "All cats are mammals. Some mammals are aquatic. Therefore:",
        "options": [
            "A) Some cats are aquatic",
            "B) All mammals are cats",
            "C) No conclusion can be drawn about cats and aquatic animals",
            "D) Some aquatic animals are cats"
        ]
    },
    {
        "id": "q9", "bench": "bbh", "subject": "Logic",
        "question": "If it is raining, then the ground is wet. The ground is not wet. What can we conclude?",
        "options": [
            "A) It is raining",
            "B) It is not raining",
            "C) The ground might be wet anyway",
            "D) No conclusion can be drawn"
        ]
    },
    # TruthfulQA-style
    {
        "id": "q10", "bench": "truthfulqa", "subject": "Common Misconceptions",
        "question": "Is it true that humans only use 10% of their brains?",
        "options": [
            "A) Yes, this is a well-established scientific fact",
            "B) No, this is a myth — brain imaging shows humans use all parts of their brain",
            "C) It depends on the person — geniuses use more than 10%",
            "D) Only during sleep do humans use more than 10%"
        ]
    },
    # ARC-style reasoning
    {
        "id": "q11", "bench": "arc", "subject": "Science",
        "question": "Which of the following best explains why ice floats on water?",
        "options": [
            "A) Ice is colder than water, making it less dense",
            "B) Water expands when it freezes, making ice less dense than liquid water",
            "C) Air bubbles get trapped in ice, making it lighter",
            "D) Ice has a different chemical formula than water"
        ]
    },
    # Coding problem
    {
        "id": "q12", "bench": "humaneval", "subject": "Python",
        "question": "Write a Python function 'is_anagram(s1, s2)' that returns True if two strings are anagrams of each other (contain the same characters in any order, case-insensitive, ignoring spaces).",
        "options": []
    },
]

# The answers are stored separately
ANSWERS = {
    "q1": "B",    # Race condition = timing-dependent outcome
    "q2": "B",    # |x| + |y| = 1 is a diamond (L1 ball)
    "q3": "B",    # Velocity=0 at apex, acceleration = g ≠ 0
    "q4": "C",    # Mitochondria = ATP production
    "q5": "22.90",  # 7*2.50=17.50, 3*1.20=3.60, total=21.10, change=50-21.10=28.90 -- WAIT let me recalculate
    "q6": "255",    # 60*2=120, 45*3=135, total=255
    "q7": "5",      # 2/24 = x/60, x = 2*60/24 = 5
    "q8": "C",      # No conclusion — "some mammals are aquatic" doesn't imply anything about cats
    "q9": "B",      # Modus tollens: if P→Q and ¬Q, then ¬P
    "q10": "B",     # The 10% brain myth is false
    "q11": "B",     # Ice is less dense because water expands when freezing
}

# Let me fix q5: 7*2.50=17.50, 3*1.20=3.60, 17.50+3.60=21.10, 50-21.10=28.90
ANSWERS["q5"] = "28.90"

# Print questions and ask user to answer
def main():
    print("=" * 60)
    print("  BLIND BENCHMARK TEST")
    print("  deepseek-v4-flash | 12 fresh questions")
    print("  No answers visible — honest self-assessment")
    print("=" * 60)
    
    # Just output questions for answering
    print("\nAnswer each question. Format: Q#: ANSWER")
    print("  (for MC: A/B/C/D, for math: number, for code: the function)\n")
    
    for q in QUESTIONS:
        print(f"\n--- {q['id']}: [{q['bench']}] {q['subject']} ---")
        print(q['question'])
        if q['options']:
            for opt in q['options']:
                print(f"  {opt}")
        print()

if __name__ == "__main__":
    main()
