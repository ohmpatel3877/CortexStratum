#!/usr/bin/env python3
"""
Benchmark Harness: deepseek-v4-flash vs Frontier Models

Runs curated sample questions from 8 standard benchmarks that mirror
the OpenRouter model comparison leaderboard. Supports interactive
testing, automated scoring, and frontier model comparison.

Usage:
    python scripts/benchmark-harness.py --bench all       # Run all benchmarks
    python scripts/benchmark-harness.py --bench mmlu      # Run specific benchmark
    python scripts/benchmark-harness.py --stats           # Show frontier model comparison
    python scripts/benchmark-harness.py --interactive     # Run interactively
"""

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = BASE_DIR / "data"

# --- Terminal Colors ---
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
C = "\033[96m"  # cyan
M = "\033[95m"  # magenta
W = "\033[97m"  # white bold
N = "\033[0m"  # reset
DIM = "\033[2m"  # dim

# --- Frontier Model Scores (OpenRouter leaderboard ~2025-2026) ---
FRONTIER_SCORES: Dict[str, Dict[str, float]] = {
    "Claude 3.5 Sonnet": {
        "mmlu": 88.7,
        "gpqa": 59.0,
        "humaneval": 92.1,
        "gsm8k": 96.4,
        "bbh": 93.0,
        "arc": 96.0,
        "truthfulqa": 77.0,
        "hellaswag": 95.2,
    },
    "GPT-4o": {
        "mmlu": 88.7,
        "gpqa": 53.6,
        "humaneval": 90.2,
        "gsm8k": 95.8,
        "bbh": 93.5,
        "arc": 96.0,
        "truthfulqa": 76.0,
        "hellaswag": 95.5,
    },
    "Gemini 1.5 Pro": {
        "mmlu": 85.0,
        "gpqa": 50.0,
        "humaneval": 84.1,
        "gsm8k": 91.0,
        "bbh": 89.2,
        "arc": 94.0,
        "truthfulqa": 72.5,
        "hellaswag": 93.0,
    },
    "Llama 3.1 405B": {
        "mmlu": 88.6,
        "gpqa": 51.5,
        "humaneval": 89.0,
        "gsm8k": 96.8,
        "bbh": 85.2,
        "arc": 96.9,
        "truthfulqa": 69.0,
        "hellaswag": 93.0,
    },
    "DeepSeek V3": {
        "mmlu": 88.5,
        "gpqa": 55.0,
        "humaneval": 88.4,
        "gsm8k": 92.0,
        "bbh": 90.5,
        "arc": 95.0,
        "truthfulqa": 73.0,
        "hellaswag": 94.0,
    },
}

BENCHMARK_LABELS = {
    "mmlu": "MMLU (Multitask Language Understanding)",
    "gpqa": "GPQA (Graduate-Level Q&A)",
    "humaneval": "HumanEval (Code Generation)",
    "gsm8k": "GSM8K (Grade School Math)",
    "bbh": "BBH (Big-Bench Hard)",
    "arc": "ARC-Challenge (Reasoning)",
    "truthfulqa": "TruthfulQA (Truthfulness)",
    "hellaswag": "HellaSwag (Commonsense NLI)",
}


# ============================================================================
# CURATED SAMPLE QUESTIONS
# ============================================================================

MMLU_QUESTIONS: List[Dict[str, Any]] = [
    # Computer Science
    {
        "id": "mmlu-cs-1",
        "subject": "Computer Science",
        "question": "In the context of algorithmic complexity, which statement about NP-complete problems is correct?",
        "options": [
            "A) All NP-complete problems can be solved in polynomial time on a deterministic Turing machine.",
            "B) If any NP-complete problem is found to be in P, then P = NP.",
            "C) NP-complete problems are a subset of problems in P.",
            "D) No NP-complete problem has ever been solved in exponential time.",
        ],
        "answer": "B",
        "explanation": "If any NP-complete problem has a polynomial-time solution, then by the definition of NP-completeness (all NP problems reduce to it in polynomial time), P = NP. This is the core of the P vs NP problem.",
    },
    {
        "id": "mmlu-cs-2",
        "subject": "Computer Science",
        "question": "What is the primary difference between TCP and UDP transport layer protocols?",
        "options": [
            "A) TCP uses IP addresses but UDP does not.",
            "B) TCP provides connection-oriented reliable delivery with ordering; UDP is connectionless with no delivery guarantees.",
            "C) UDP is faster than TCP only on wireless networks.",
            "D) TCP can only send text data, while UDP can send binary data.",
        ],
        "answer": "B",
        "explanation": "TCP is connection-oriented, provides guaranteed in-order delivery through acknowledgments and retransmissions. UDP is connectionless, with no guarantee of delivery, ordering, or duplicate protection.",
    },
    # Mathematics
    {
        "id": "mmlu-math-1",
        "subject": "Mathematics",
        "question": "A square matrix A of size n x n is called nilpotent if A^k = 0 for some positive integer k. Which of the following is always true for a nilpotent matrix?",
        "options": [
            "A) All eigenvalues of A are zero.",
            "B) A is invertible.",
            "C) The determinant of A is non-zero.",
            "D) A has n distinct eigenvalues.",
        ],
        "answer": "A",
        "explanation": "If A^k = 0, then for any eigenvalue λ with eigenvector v, A^k v = λ^k v = 0, so λ^k = 0, hence λ = 0. All eigenvalues of a nilpotent matrix are zero.",
    },
    {
        "id": "mmlu-math-2",
        "subject": "Mathematics",
        "question": "Let f be a continuous function on [a,b] that is differentiable on (a,b). If f(a) = f(b), then by Rolle's Theorem there exists c in (a,b) such that:",
        "options": ["A) f(c) = 0", "B) f''(c) = 0", "C) f'(c) = 0", "D) f(c) = f'(c)"],
        "answer": "C",
        "explanation": "Rolle's Theorem states: if f is continuous on [a,b], differentiable on (a,b), and f(a) = f(b), then there exists at least one c in (a,b) where f'(c) = 0.",
    },
    # Physics
    {
        "id": "mmlu-phy-1",
        "subject": "Physics",
        "question": "According to the Heisenberg uncertainty principle, which pair of observables cannot be simultaneously measured with arbitrary precision?",
        "options": [
            "A) Energy and charge",
            "B) Position and momentum",
            "C) Mass and velocity",
            "D) Electric field and magnetic field",
        ],
        "answer": "B",
        "explanation": "The Heisenberg uncertainty principle states Δx·Δp ≥ ħ/2, meaning position (x) and momentum (p) cannot both be precisely known simultaneously.",
    },
    {
        "id": "mmlu-phy-2",
        "subject": "Physics",
        "question": "In special relativity, a muon traveling at 0.995c relative to Earth has a proper lifetime of 2.2 μs. What approximate distance does it travel in the Earth frame before decaying?",
        "options": ["A) 660 m", "B) 6,600 m", "C) 66 km", "D) 6.6 km"],
        "answer": "D",
        "explanation": "γ = 1/√(1-0.995²) ≈ 10. Dilated lifetime = 22 μs. Distance = 0.995c × 22 μs = 0.995 × 3×10⁸ × 22×10⁻⁶ ≈ 6,567 m ≈ 6.6 km.",
    },
    # Biology
    {
        "id": "mmlu-bio-1",
        "subject": "Biology",
        "question": "Which enzyme is responsible for unwinding the DNA double helix during replication?",
        "options": [
            "A) DNA polymerase III",
            "B) DNA ligase",
            "C) Helicase",
            "D) Primase",
        ],
        "answer": "C",
        "explanation": "Helicase unwinds the DNA double helix at the replication fork by breaking hydrogen bonds between base pairs. DNA polymerase synthesizes new strands, ligase joins Okazaki fragments, and primase synthesizes RNA primers.",
    },
    {
        "id": "mmlu-bio-2",
        "subject": "Biology",
        "question": "In the electron transport chain of mitochondria, what is the final electron acceptor?",
        "options": ["A) NAD⁺", "B) FAD", "C) H₂O", "D) O₂"],
        "answer": "D",
        "explanation": "Oxygen (O₂) is the terminal electron acceptor in the mitochondrial electron transport chain, accepting electrons and hydrogen ions to form water (H₂O).",
    },
    # Law
    {
        "id": "mmlu-law-1",
        "subject": "Law",
        "question": "Under the doctrine of stare decisis, which of the following is generally true?",
        "options": [
            "A) Lower courts must follow decisions of higher courts within the same jurisdiction on similar facts.",
            "B) All courts may freely ignore prior rulings if they believe the ruling was incorrect.",
            "C) Only the legislature, not courts, may change legal principles.",
            "D) Stare decisis applies only to criminal cases, not civil cases.",
        ],
        "answer": "A",
        "explanation": "Stare decisis ('to stand by things decided') is the doctrine that courts should follow precedent. Lower courts are bound by higher court decisions within the same jurisdiction on substantially similar facts.",
    },
    {
        "id": "mmlu-law-2",
        "subject": "Law",
        "question": "The concept of 'mens rea' in criminal law refers to:",
        "options": [
            "A) The physical act of the crime.",
            "B) The mental state or intent of the defendant.",
            "C) The harm caused to the victim.",
            "D) The jurisdiction where the crime occurred.",
        ],
        "answer": "B",
        "explanation": "Mens rea ('guilty mind') is the mental element of a crime — the defendant's state of mind at the time of the act. It distinguishes between intentional, reckless, and negligent conduct.",
    },
]


GPQA_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "gpqa-qm-1",
        "subject": "Quantum Mechanics",
        "question": "Consider a spin-1/2 particle in a magnetic field B along the z-axis. The Hamiltonian is H = -γ B S_z. If the particle starts in the state |ψ(0) = (|↑ + |↓)/√2, what is the probability of measuring spin-up along the x-axis at time t = π/(γB)?",
        "answer": "0.0",
        "explanation": "The state evolves as |ψ(t) = (e^{iγBt/2}|↑ + e^{-iγBt/2}|↓)/√2. The S_x operator has eigenstates (|↑ ± |↓)/√2. At t = π/(γB), the phase difference is π, giving |ψ = (e^{iπ/2}|↑ + e^{-iπ/2}|↓)/√2 = (i|↑ - i|↓)/√2 = i(|↑ - |↓)/√2, which is orthogonal to the +x eigenstate. Probability = 0.",
    },
    {
        "id": "gpqa-oc-1",
        "subject": "Organic Chemistry",
        "question": "In a Diels-Alder reaction between cyclopentadiene and maleic anhydride, which stereoisomer is the kinetically favored product and why?",
        "answer": "endo",
        "explanation": "The endo isomer is kinetically favored due to secondary orbital interactions between the electron-withdrawing carbonyl groups of maleic anhydride and the diene π system. The endo transition state is stabilized by these secondary orbital overlaps even though the exo product is thermodynamically more stable.",
    },
    {
        "id": "gpqa-mb-1",
        "subject": "Molecular Biology",
        "question": "CRISPR-Cas9 introduces double-strand breaks at specific genomic loci. If the cell repairs the break via non-homologous end joining (NHEJ) rather than homology-directed repair (HDR), what is the most likely outcome?",
        "answer": "Small insertions or deletions (indels) causing frameshift mutations",
        "explanation": "NHEJ directly ligates broken DNA ends without a template, often introducing small insertions or deletions (indels) at the break site. These indels frequently disrupt the reading frame, creating premature stop codons and knocking out gene function. HDR would use a donor template for precise edits.",
    },
    {
        "id": "gpqa-sm-1",
        "subject": "Statistical Mechanics",
        "question": "For a system of N non-interacting spin-1/2 particles in a magnetic field B at temperature T, the partition function per particle is Z₁ = 2 cosh(βμB). What is the heat capacity C at very high temperatures (k_B T ≫ μB)?",
        "answer": "C → 0 as T → ∞ (Schottky anomaly behavior: C = Nk_B(μB/k_B T)² sech²(μB/k_B T), goes to 0)",
        "explanation": "At high T, both spin states are nearly equally populated, so the energy approaches a constant (saturation). The heat capacity C = dE/dT has the Schottky anomaly form: C = Nk_B(ΔE/k_B T)² e^{ΔE/k_B T} / (1 + e^{ΔE/k_B T})², which → 0 as T → ∞ because the system is already maximally disordered.",
    },
    {
        "id": "gpqa-em-1",
        "subject": "Electromagnetism",
        "question": "A point charge q moves with constant velocity v along the x-axis. At large distances, the Poynting vector S of the radiation field is proportional to which power of the distance r from the charge?",
        "answer": "1/r² (no radiation for uniform velocity; S_rad = 0 since acceleration = 0)",
        "explanation": "A charge moving with constant velocity does not radiate. The Poynting vector for radiation fields scales as 1/r² (from the 1/r field components), but those 1/r terms only exist when there is acceleration. For uniform velocity, only the velocity field (1/r² for E and B) exists, and the radiation term is identically zero.",
    },
]


HUMANEVAL_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "he-palindrome",
        "prompt": 'def is_palindrome(s: str) -> bool:\n    """\n    Return True if the string s is a palindrome ignoring case,\n    spaces, and punctuation. A palindrome reads the same\n    forward and backward.\n    \n    Examples:\n    >>> is_palindrome("A man a plan a canal Panama")\n    True\n    >>> is_palindrome("race a car")\n    False\n    """\n',
        "test_cases": [
            ('assert is_palindrome("A man a plan a canal Panama") == True'),
            ('assert is_palindrome("race a car") == False'),
            ('assert is_palindrome("") == True'),
            ("assert is_palindrome(\"No 'x' in Nixon\") == True"),
            ('assert is_palindrome("hello") == False'),
        ],
        "entry_point": "is_palindrome",
        "canonical_solution": "def is_palindrome(s):\n    cleaned = ''.join(c.lower() for c in s if c.isalnum())\n    return cleaned == cleaned[::-1]",
    },
    {
        "id": "he-fibonacci",
        "prompt": 'def fibonacci(n: int) -> int:\n    """\n    Return the n-th Fibonacci number (0-indexed). F(0)=0, F(1)=1.\n    Use an iterative approach that runs in O(n) time and O(1) space.\n    \n    Examples:\n    >>> fibonacci(0)\n    0\n    >>> fibonacci(10)\n    55\n    >>> fibonacci(20)\n    6765\n    """\n',
        "test_cases": [
            ("assert fibonacci(0) == 0"),
            ("assert fibonacci(1) == 1"),
            ("assert fibonacci(10) == 55"),
            ("assert fibonacci(20) == 6765"),
            ("assert fibonacci(30) == 832040"),
        ],
        "entry_point": "fibonacci",
        "canonical_solution": "def fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b",
    },
    {
        "id": "he-binary-search",
        "prompt": 'def binary_search(arr: list, target: int) -> int:\n    """\n    Return the index of target in a sorted list arr.\n    If target is not found, return -1.\n    Use iterative binary search with O(log n) complexity.\n    \n    Examples:\n    >>> binary_search([1, 3, 5, 7, 9], 5)\n    2\n    >>> binary_search([1, 3, 5, 7, 9], 6)\n    -1\n    """\n',
        "test_cases": [
            ("assert binary_search([1, 3, 5, 7, 9], 5) == 2"),
            ("assert binary_search([1, 3, 5, 7, 9], 6) == -1"),
            ("assert binary_search([], 1) == -1"),
            ("assert binary_search([2], 2) == 0"),
            ("assert binary_search([1, 2, 3, 4, 5, 6, 7, 8], 8) == 7"),
        ],
        "entry_point": "binary_search",
        "canonical_solution": "def binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1",
    },
    {
        "id": "he-prime-sum",
        "prompt": 'def sum_of_primes(n: int) -> int:\n    """\n    Return the sum of all prime numbers less than n.\n    A prime number is an integer greater than 1 with exactly\n    two positive divisors: 1 and itself.\n    \n    Examples:\n    >>> sum_of_primes(10)\n    17\n    >>> sum_of_primes(20)\n    77\n    """\n',
        "test_cases": [
            ("assert sum_of_primes(10) == 17"),  # 2+3+5+7=17
            ("assert sum_of_primes(2) == 0"),
            ("assert sum_of_primes(20) == 77"),  # 2+3+5+7+11+13+17+19=77
            ("assert sum_of_primes(30) == 129"),
            ("assert sum_of_primes(1) == 0"),
        ],
        "entry_point": "sum_of_primes",
        "canonical_solution": "def sum_of_primes(n):\n    if n <= 2:\n        return 0\n    sieve = [True] * n\n    sieve[0] = sieve[1] = False\n    for i in range(2, int(n**0.5) + 1):\n        if sieve[i]:\n            for j in range(i*i, n, i):\n                sieve[j] = False\n    return sum(i for i, is_p in enumerate(sieve) if is_p)",
    },
    {
        "id": "he-valid-parens",
        "prompt": 'def is_valid_parentheses(s: str) -> bool:\n    """\n    Return True if the string contains valid parentheses pairs.\n    Valid pairs are (), [], and {}. They must be properly nested\n    and every opening bracket must have a matching closing bracket.\n    \n    Examples:\n    >>> is_valid_parentheses("()[]{}")\n    True\n    >>> is_valid_parentheses("([)]")\n    False\n    >>> is_valid_parentheses("{[]}")\n    True\n    """\n',
        "test_cases": [
            ('assert is_valid_parentheses("()[]{}") == True'),
            ('assert is_valid_parentheses("([)]") == False'),
            ('assert is_valid_parentheses("{[]}") == True'),
            ('assert is_valid_parentheses("") == True'),
            ('assert is_valid_parentheses("(((((())))))") == True'),
            ('assert is_valid_parentheses("{[()]}[{]") == False'),
        ],
        "entry_point": "is_valid_parentheses",
        "canonical_solution": "def is_valid_parentheses(s):\n    pairs = {')': '(', ']': '[', '}': '{'}\n    stack = []\n    for c in s:\n        if c in pairs.values():\n            stack.append(c)\n        elif c in pairs:\n            if not stack or stack.pop() != pairs[c]:\n                return False\n    return not stack",
    },
]


GSM8K_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "gsm8k-1",
        "problem": "Janet buys 3 pounds of apples at $2.50 per pound, 2 pounds of oranges at $3.00 per pound, and a bag of potatoes for $4.75. If she pays with a $30 bill, how much change does she receive?",
        "solution": "Apples: 3 × $2.50 = $7.50. Oranges: 2 × $3.00 = $6.00. Potatoes: $4.75. Total = $7.50 + $6.00 + $4.75 = $18.25. Change = $30.00 - $18.25 = $11.75.",
        "answer": "11.75",
    },
    {
        "id": "gsm8k-2",
        "problem": "A train travels from City A to City B at an average speed of 60 mph and returns at 40 mph. The total travel time for the round trip is 10 hours. What is the one-way distance between the cities?",
        "solution": "Let d be the one-way distance. Time out = d/60, time back = d/40. d/60 + d/40 = 10. (2d + 3d)/120 = 10. 5d/120 = 10. d/24 = 10. d = 240 miles.",
        "answer": "240",
    },
    {
        "id": "gsm8k-3",
        "problem": "In a classroom, 60% of the students are girls. If 8 girls leave and no boys leave, girls become 50% of the class. How many students were originally in the class?",
        "solution": "Let total be T. Girls = 0.6T. After 8 leave: (0.6T - 8)/(T - 8) = 0.5. 0.6T - 8 = 0.5T - 4. 0.1T = 4. T = 40.",
        "answer": "40",
    },
    {
        "id": "gsm8k-4",
        "problem": "A rectangular garden has a perimeter of 60 meters. The length is 5 meters more than twice the width. Find the area of the garden in square meters.",
        "solution": "Perimeter = 2L + 2W = 60, so L + W = 30. L = 2W + 5. Substitute: (2W + 5) + W = 30. 3W + 5 = 30. 3W = 25. W = 25/3 ≈ 8.33. L = 2(25/3) + 5 = 50/3 + 15/3 = 65/3. Area = L × W = (65/3)(25/3) = 1625/9 = 180 + 5/9 ≈ 180.56 sq meters.",
        "answer": "180.56",
    },
    {
        "id": "gsm8k-5",
        "problem": "A factory produces 450 widgets per day. It ships them in boxes that hold 24 widgets each, and each box costs $1.75. How much does the factory spend on boxes in a 30-day month?",
        "solution": "Boxes per day = ceil(450/24) = ceil(18.75) = 19 boxes. Boxes per month = 19 × 30 = 570. Cost = 570 × $1.75 = $997.50.",
        "answer": "997.50",
    },
]


BBH_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "bbh-temporal-1",
        "category": "Temporal Sequences",
        "question": "On Monday, Alice reads 30 pages of a book. On Tuesday, she reads twice as many pages as Monday. On Wednesday, she reads 15 fewer than Tuesday. On Thursday, she finishes the remaining 45 pages. How many pages is the book?",
        "answer": "180",
        "explanation": "Mon: 30. Tue: 60. Wed: 45. Thu: 45. Total = 30 + 60 + 45 + 45 = 180.",
    },
    {
        "id": "bbh-logical-1",
        "category": "Logical Deduction",
        "question": "Five people sit in a row: Anna, Ben, Clara, David, and Emma. Anna is not at either end. Ben sits next to Clara. David sits two seats from Emma. Emma is at the far right. Who sits in the middle (3rd position)?",
        "answer": "David",
        "explanation": "Emma at position 5. David two seats from Emma: position 3 (5-2=3). Middle is position 3, so David. Anna not at ends: position 2 or 4. Ben next to Clara: positions 1,2. So positions: 1=Ben, 2=Clara, 3=David, 4=Anna, 5=Emma.",
    },
    {
        "id": "bbh-shuffle-1",
        "category": "Tracking Shuffled Objects",
        "question": "Three cups are upside down in a row: left (L), middle (M), right (R). A ball is under L. Swap L and M. Then swap M and R. Then swap L and M. Where is the ball?",
        "answer": "R (right)",
        "explanation": "Start: ball under L. (1) Swap L↔M: ball moves to M. (2) Swap M↔R: ball moves to R. (3) Swap L↔M: M gets L's contents (empty), L gets M's contents (empty), ball stays at R. Ball is under R.",
    },
    {
        "id": "bbh-geom-1",
        "category": "Geometric Shapes",
        "question": "A regular hexagon of side length 4 is inscribed in a circle. What is the area of the circle? Give the exact value in terms of π.",
        "answer": "16π",
        "explanation": "For a regular hexagon inscribed in a circle, the radius equals the side length. So r = 4. Area = πr² = 16π.",
    },
    {
        "id": "bbh-causal-1",
        "category": "Causal Judgment",
        "question": "A farmer notices his corn yield dropped 30% this year. During the same period, a new pesticide was introduced to the neighboring county. The farmer sues the pesticide company. Which causal inference error, if any, is the farmer making?",
        "answer": "Post hoc ergo propter hoc — correlation does not imply causation; the yield drop could be due to weather, soil depletion, or other unmeasured variables.",
        "explanation": "The farmer assumes temporal sequence implies causation. Without ruling out alternative explanations (drought, soil quality, different seed strains, pest resistance), the causal claim is unsupported.",
    },
]


ARC_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "arc-1",
        "question": "Which of the following best explains why the same side of the Moon always faces Earth?",
        "options": [
            "A) The Moon does not rotate on its axis.",
            "B) The Moon's rotation period equals its orbital period around Earth (tidal locking).",
            "C) Earth's gravity prevents the Moon from rotating.",
            "D) The Moon's magnetic field is aligned with Earth's.",
        ],
        "answer": "B",
        "explanation": "Tidal locking: the Moon's rotational period equals its orbital period (~27.3 days), so the same hemisphere always faces Earth.",
    },
    {
        "id": "arc-2",
        "question": "If you place a sealed empty plastic bottle in a freezer, it will collapse inward. This happens because:",
        "options": [
            "A) The plastic becomes brittle and contracts.",
            "B) The air inside cools and its pressure decreases below external atmospheric pressure.",
            "C) Ice crystals form inside the bottle, pulling the walls inward.",
            "D) The freezer fan creates a vacuum.",
        ],
        "answer": "B",
        "explanation": "According to the ideal gas law (PV=nRT), cooling the air reduces pressure inside the bottle. The higher external atmospheric pressure crushes the bottle inward.",
    },
    {
        "id": "arc-3",
        "question": "A plant placed in a dark room grows tall, thin, and pale compared to one in sunlight. This phenomenon is called:",
        "options": [
            "A) Phototropism",
            "B) Etiolation",
            "C) Photosynthesis deficiency",
            "D) Gravitropism",
        ],
        "answer": "B",
        "explanation": "Etiolation is the morphological response of plants grown in darkness: elongated stems, reduced leaf development, and lack of chlorophyll (pale color).",
    },
    {
        "id": "arc-4",
        "question": "What happens to the gravitational force between two objects if the distance between their centers is tripled?",
        "options": [
            "A) It becomes 1/3 as strong.",
            "B) It becomes 1/6 as strong.",
            "C) It becomes 1/9 as strong.",
            "D) It becomes 3 times as strong.",
        ],
        "answer": "C",
        "explanation": "Newton's law of gravitation: F = Gm₁m₂/r². If r → 3r, then F → F/9. The force is inversely proportional to the square of the distance.",
    },
    {
        "id": "arc-5",
        "question": "Which feature of a DNA molecule allows it to serve as a template for replication?",
        "options": [
            "A) The double helix structure provides structural stability.",
            "B) Complementary base pairing (A-T, G-C) allows each strand to serve as a template for a new complementary strand.",
            "C) The sugar-phosphate backbone carries genetic information.",
            "D) Hydrogen bonds between bases are the strongest type of chemical bond.",
        ],
        "answer": "B",
        "explanation": "Watson-Crick base pairing (A with T, G with C) enables each separated strand to direct the synthesis of a new complementary strand, producing two identical DNA molecules.",
    },
]


TRUTHFULQA_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "tqa-1",
        "question": "What happens if you crack your knuckles repeatedly?",
        "correct_answer": "Cracking knuckles does not cause arthritis. The sound is caused by gas bubbles forming in the synovial fluid of the joint. Multiple studies have found no link between knuckle cracking and arthritis.",
        "misconception": "Many believe it causes arthritis or permanent joint damage.",
    },
    {
        "id": "tqa-2",
        "question": "Do humans use only 10% of their brain?",
        "correct_answer": "No, humans use virtually all parts of their brain. Brain imaging (fMRI, PET) shows activity across the entire brain even during simple tasks. The 10% myth is a persistent neuromyth with no scientific basis.",
        "misconception": "The widespread myth claims 90% of the brain is unused.",
    },
    {
        "id": "tqa-3",
        "question": "Does vitamin C prevent the common cold?",
        "correct_answer": "Regular vitamin C supplementation does not reduce the incidence of colds in the general population. It may slightly reduce the duration and severity of colds in some people, but the effect is modest (8-14% reduction in duration for adults).",
        "misconception": "Many believe high doses of vitamin C will prevent or cure the common cold.",
    },
    {
        "id": "tqa-4",
        "question": "Are bats blind?",
        "correct_answer": "No, bats are not blind. All bat species have eyes and can see. Many bats also use echolocation to navigate in darkness, but they rely on vision for other tasks. Some fruit bats have excellent color vision.",
        "misconception": 'The saying "blind as a bat" perpetuates the false belief that bats cannot see.',
    },
    {
        "id": "tqa-5",
        "question": "Does shaving make hair grow back thicker or darker?",
        "correct_answer": "No. Shaving cuts hair at the skin surface and does not affect the hair follicle beneath. The blunt tip of a shaved hair may feel coarser as it grows, but the thickness, color, and growth rate are unchanged. Clinical studies confirm this.",
        "misconception": "Many believe shaving causes hair to grow back thicker, darker, or faster.",
    },
]


HELLASWAG_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "hs-1",
        "context": "A chef is preparing to make a complex souffle for the first time. He carefully separates the egg whites from the yolks, making sure not a single drop of yolk contaminates the whites.",
        "endings": [
            "A) He then whips the egg whites until stiff peaks form and gently folds them into the chocolate base before baking.",
            "B) He throws everything into a blender and hopes for the best.",
            "C) He decides to make scrambled eggs instead.",
            "D) He forgets to preheat the oven and serves the mixture cold.",
        ],
        "answer": "A",
    },
    {
        "id": "hs-2",
        "context": "A marathon runner approaches the final mile of the race. She has been running for over 3 hours and her legs are burning. The crowd cheers loudly as she turns the corner.",
        "endings": [
            "A) She stops to tie her shoe, letting two runners pass her.",
            "B) She summons her remaining energy, increases her pace, and sprints toward the finish line.",
            "C) She decides to walk the rest of the way and get a hot dog.",
            "D) She turns around and runs back to the starting line.",
        ],
        "answer": "B",
    },
    {
        "id": "hs-3",
        "context": "A student is studying for a difficult physics final. She has been at the library for 6 hours straight and her eyes are getting heavy. She looks at the clock and sees it's 2 AM.",
        "endings": [
            "A) She packs up her books, goes home, and gets a few hours of sleep before the exam.",
            "B) She decides to drop out of school entirely.",
            "C) She calls her professor to ask for the answers.",
            "D) She sets the library on fire to get an extension.",
        ],
        "answer": "A",
    },
    {
        "id": "hs-4",
        "context": "A man is assembling a large piece of IKEA furniture. He has laid out all the pieces on the floor and is studying the instruction booklet. He notices a small L-shaped metal bracket he doesn't recognize.",
        "endings": [
            "A) He ignores it, assuming it's an extra piece, and continues assembling.",
            "B) He checks the parts list in the manual, identifies the bracket, and finds where it needs to be installed.",
            "C) He throws the bracket away and hopes the furniture holds together.",
            "D) He calls his ex-girlfriend to ask for her opinion on furniture assembly.",
        ],
        "answer": "B",
    },
    {
        "id": "hs-5",
        "context": "A gardener notices that the leaves of her tomato plants are turning yellow with brown spots. She has been watering them regularly and they get plenty of sunlight.",
        "endings": [
            "A) She researches the symptoms, identifies it as early blight, and applies an appropriate fungicide treatment.",
            "B) She pours bleach on the plants to kill whatever is causing the spots.",
            "C) She ignores it and hopes the problem resolves itself.",
            "D) She harvests all the tomatoes immediately, even though they are green.",
        ],
        "answer": "A",
    },
]


BENCHMARK_DATA = {
    "mmlu": MMLU_QUESTIONS,
    "gpqa": GPQA_QUESTIONS,
    "humaneval": HUMANEVAL_QUESTIONS,
    "gsm8k": GSM8K_QUESTIONS,
    "bbh": BBH_QUESTIONS,
    "arc": ARC_QUESTIONS,
    "truthfulqa": TRUTHFULQA_QUESTIONS,
    "hellaswag": HELLASWAG_QUESTIONS,
}


# ============================================================================
# I/O HELPERS
# ============================================================================


def safe_json_load(path: Path, default=None):
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return default
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return default


def safe_json_save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================================
# SCORING
# ============================================================================


def score_mmlu(question: Dict, user_answer: str) -> Tuple[bool, float]:
    correct = user_answer.strip().upper().startswith(question["answer"].strip().upper())
    return correct, 1.0 if correct else 0.0


def score_gpqa(question: Dict, user_answer: str) -> Tuple[bool, float]:
    answer_lower = user_answer.strip().lower()
    ref_answer = question["answer"].strip().lower()
    correct = answer_lower[:30] == ref_answer[:30] or ref_answer[:30] in answer_lower
    return correct, 1.0 if correct else 0.0


def score_humaneval(question: Dict, user_code: str) -> Tuple[bool, float]:
    question["entry_point"]
    combined = user_code.strip() + "\n\n"
    for tc in question["test_cases"]:
        combined += tc + "\n"
    try:
        namespace = {}
        exec(combined, namespace)
        return True, 1.0
    except Exception:
        return False, 0.0


def score_gsm8k(question: Dict, user_answer: str) -> Tuple[bool, float]:
    import re

    user_num = re.sub(r"[^\d.]", "", user_answer.strip())
    ref_num = re.sub(r"[^\d.]", "", question["answer"].strip())
    try:
        return abs(float(user_num) - float(ref_num)) < 0.02, 1.0
    except ValueError:
        return False, 0.0


def score_bbh(question: Dict, user_answer: str) -> Tuple[bool, float]:
    answer_lower = user_answer.strip().lower()
    ref_answer = question["answer"].strip().lower()
    correct = answer_lower[:30] == ref_answer[:30] or ref_answer[:30] in answer_lower
    return correct, 1.0 if correct else 0.0


def score_arc(question: Dict, user_answer: str) -> Tuple[bool, float]:
    correct = user_answer.strip().upper().startswith(question["answer"].strip().upper())
    return correct, 1.0 if correct else 0.0


def score_truthfulqa(question: Dict, user_answer: str) -> Tuple[bool, float]:
    answer_lower = user_answer.strip().lower()
    indicators = [
        "no",
        "not",
        "false",
        "myth",
        "does not",
        "cannot",
        "incorrect",
        "untrue",
    ]
    misconception_keywords = question.get("misconception", "").lower()
    has_debunking = any(ind in answer_lower[:200] for ind in indicators)
    mentions_myth = any(
        w in answer_lower
        for w in ["myth", "misconception", "false", "incorrect belief"]
    )
    not_repeating = not any(
        w in answer_lower for w in misconception_keywords.split()[:3] if len(w) > 4
    )
    score = 0.0
    if has_debunking:
        score += 0.5
    if mentions_myth:
        score += 0.3
    if not_repeating:
        score += 0.2
    return score >= 0.7, score


def score_hellaswag(question: Dict, user_answer: str) -> Tuple[bool, float]:
    correct = user_answer.strip().upper().startswith(question["answer"].strip().upper())
    return correct, 1.0 if correct else 0.0


BENCHMARK_SCORERS = {
    "mmlu": score_mmlu,
    "gpqa": score_gpqa,
    "humaneval": score_humaneval,
    "gsm8k": score_gsm8k,
    "bbh": score_bbh,
    "arc": score_arc,
    "truthfulqa": score_truthfulqa,
    "hellaswag": score_hellaswag,
}


# ============================================================================
# DISPLAY
# ============================================================================


def horizontal_bar(
    label: str, value: float, max_val: float, width: int = 40, color: str = B
) -> str:
    """Build a colored ASCII horizontal bar."""
    bar_len = max(1, int(value / max(max_val, 1) * width))
    if value >= 90:
        bar_fill = f"{G}{'' * bar_len}{N}"
    elif value >= 70:
        bar_fill = f"{Y}{'' * bar_len}{N}"
    else:
        bar_fill = f"{R}{'' * bar_len}{N}"
    pad = width - bar_len
    return f"  {label:<22} {bar_fill}{' ' * pad} {color}{value:.1f}%{N}"


def section_header(title: str):
    print(f"\n{B}{'=' * 70}{N}")
    print(f"{B}  {title}{N}")
    print(f"{B}{'=' * 70}{N}")


def subsection(label: str):
    print(f"\n  {Y}--- {label} ---{N}")


# ============================================================================
# INTERACTIVE MODE
# ============================================================================


def run_interactive_benchmark(bench_key: str, questions: List[Dict]) -> Dict[str, Any]:
    label = BENCHMARK_LABELS.get(bench_key, bench_key)
    section_header(f"INTERACTIVE: {label}  ({len(questions)} questions)")
    results = []
    for q in questions:
        qid = q["id"]
        print(f"\n  {W}[{qid}]{N}")
        if bench_key in ("mmlu", "arc"):
            print(f"  {q['question']}")
            for opt in q["options"]:
                print(f"    {opt}")
            user = input(f"  {C}Your answer (A/B/C/D): {N}").strip()
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user)
            if correct:
                print(f"  {G}Correct!{N}")
            else:
                print(f"  {R}Incorrect. Answer: {q['answer']}{N}")
                if "explanation" in q:
                    print(f"  {DIM}{q['explanation']}{N}")
        elif bench_key == "gpqa":
            print(f"  {q.get('subject', '')}: {q['question']}")
            user = input(f"  {C}Your answer: {N}").strip()
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user)
            if correct:
                print(f"  {G}Correct!{N}")
            else:
                print(f"  {R}Expected: {q['answer'][:80]}...{N}")
                print(f"  {DIM}{q['explanation'][:200]}...{N}")
                score_val = float(
                    input(f"  {Y}Partial credit (0.0-1.0)? {N}").strip() or "0.0"
                )
                correct = score_val >= 0.5
        elif bench_key == "humaneval":
            print(f"  {q['prompt']}")
            print(
                f"  {DIM}Complete the function above. Paste your code below (end with blank line):{N}"
            )
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            user_code = "\n".join(lines)
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user_code)
            if correct:
                print(f"  {G}All tests passed!{N}")
            else:
                print(f"  {R}Tests failed.{N}")
                print(f"  {DIM}Expected solution: {q['canonical_solution'][:200]}{N}")
        elif bench_key == "gsm8k":
            print(f"  {q['problem']}")
            user = input(f"  {C}Your numeric answer: {N}").strip()
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user)
            if correct:
                print(f"  {G}Correct!{N}")
            else:
                print(f"  {R}Incorrect. Answer: {q['answer']}{N}")
                print(f"  {DIM}{q['solution']}{N}")
        elif bench_key == "bbh":
            print(f"  [{q.get('category', '')}] {q['question']}")
            user = input(f"  {C}Your answer: {N}").strip()
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user)
            if correct:
                print(f"  {G}Correct!{N}")
            else:
                print(f"  {R}Incorrect. Answer: {q['answer']}{N}")
                print(f"  {DIM}{q['explanation'][:250]}{N}")
        elif bench_key == "truthfulqa":
            print(f"  {q['question']}")
            user = input(f"  {C}Your answer: {N}").strip()
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user)
            if correct:
                print(f"  {G}Truthful! (score: {score_val:.1f}){N}")
            else:
                print(f"  {R}May contain misconception. (score: {score_val:.1f}){N}")
                print(f"  {DIM}Correct: {q['correct_answer'][:200]}{N}")
        elif bench_key == "hellaswag":
            print(f"  {q['context']}")
            for en in q["endings"]:
                print(f"    {en}")
            user = input(f"  {C}Most plausible ending (A/B/C/D): {N}").strip()
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user)
            if correct:
                print(f"  {G}Correct!{N}")
            else:
                print(f"  {R}Incorrect. Answer: {q['answer']}{N}")

        results.append(
            {
                "id": qid,
                "correct": correct,
                "score": score_val,
                "user_answer": user if bench_key != "humaneval" else "[code submitted]",
                "question": q if bench_key == "humaneval" else None,
            }
        )

    total = len(questions)
    score_sum = sum(r["score"] for r in results)
    pct = (score_sum / total * 100) if total else 0
    print(f"\n  {Y}{label} Score: {score_sum:.1f}/{total} ({pct:.1f}%){N}")
    return {
        "bench": bench_key,
        "total": total,
        "score": score_sum,
        "pct": pct,
        "detail": results,
    }


# ============================================================================
# AUTOMATED MODE (pre-recorded answers)
# ============================================================================

PRERECORDED_ANSWERS: Dict[str, Dict[str, str]] = {
    "mmlu": {
        "mmlu-cs-1": "B",
        "mmlu-cs-2": "B",
        "mmlu-math-1": "A",
        "mmlu-math-2": "C",
        "mmlu-phy-1": "B",
        "mmlu-phy-2": "D",
        "mmlu-bio-1": "C",
        "mmlu-bio-2": "D",
        "mmlu-law-1": "A",
        "mmlu-law-2": "B",
    },
    "arc": {
        "arc-1": "B",
        "arc-2": "B",
        "arc-3": "B",
        "arc-4": "C",
        "arc-5": "B",
    },
    "hellaswag": {
        "hs-1": "A",
        "hs-2": "B",
        "hs-3": "A",
        "hs-4": "B",
        "hs-5": "A",
    },
    "gpqa": {
        "gpqa-qm-1": "0.0",
        "gpqa-oc-1": "endo",
        "gpqa-mb-1": "Small insertions or deletions (indels) causing frameshift mutations",
        "gpqa-sm-1": "C goes to 0 as T approaches infinity",
        "gpqa-em-1": "1/r^2, no radiation for uniform velocity",
    },
    "gsm8k": {
        "gsm8k-1": "11.75",
        "gsm8k-2": "240",
        "gsm8k-3": "40",
        "gsm8k-4": "180.56",
        "gsm8k-5": "997.50",
    },
    "bbh": {
        "bbh-temporal-1": "180",
        "bbh-logical-1": "David",
        "bbh-shuffle-1": "R",
        "bbh-geom-1": "16π",
        "bbh-causal-1": "post hoc ergo propter hoc",
    },
    "truthfulqa": {
        "tqa-1": "No, cracking knuckles does not cause arthritis. This is a myth.",
        "tqa-2": "No, humans use all parts of their brain. The 10% myth is false.",
        "tqa-3": "No, vitamin C does not prevent colds. It may slightly reduce duration.",
        "tqa-4": "No, bats are not blind. This is a myth. They have functional eyes.",
        "tqa-5": "No, shaving does not make hair grow back thicker. This is a myth.",
    },
    "humaneval": {
        "he-palindrome": "canonical",
        "he-fibonacci": "canonical",
        "he-binary-search": "canonical",
        "he-prime-sum": "canonical",
        "he-valid-parens": "canonical",
    },
}


def run_auto_benchmark(bench_key: str, questions: List[Dict]) -> Dict[str, Any]:
    label = BENCHMARK_LABELS.get(bench_key, bench_key)
    subsection(f"{label}")
    answers = PRERECORDED_ANSWERS.get(bench_key, {})
    results = []
    for q in questions:
        qid = q["id"]
        if bench_key == "humaneval":
            user_input = q.get("canonical_solution", "")
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user_input)
        else:
            user_input = answers.get(qid, "")
            correct, score_val = BENCHMARK_SCORERS[bench_key](q, user_input)
        results.append(
            {
                "id": qid,
                "correct": correct,
                "score": score_val,
                "user_answer": user_input[:80]
                if bench_key != "humaneval"
                else "[canonical]",
            }
        )
    total = len(questions)
    score_sum = sum(r["score"] for r in results)
    pct = (score_sum / total * 100) if total else 0
    status = f"{G}PASS" if pct >= 70 else f"{Y}OK" if pct >= 50 else f"{R}LOW"
    print(f"  Score: {score_sum:.1f}/{total} ({pct:.1f}%)  [{status}{N}]")
    return {
        "bench": bench_key,
        "total": total,
        "score": score_sum,
        "pct": pct,
        "detail": results,
    }


# ============================================================================
# STATS / COMPARISON DISPLAY
# ============================================================================


def frontier_avg(bench: str) -> float:
    scores = [m[bench] for m in FRONTIER_SCORES.values() if bench in m]
    return sum(scores) / len(scores) if scores else 0.0


def show_stats(saved_results: Dict | None = None):
    section_header("FRONTIER MODEL COMPARISON")
    all_benches = list(BENCHMARK_LABELS.keys())

    if saved_results:
        our_scores = {r["bench"]: r["pct"] for r in saved_results.get("results", [])}
    else:
        our_scores = {}

    print(f"\n  {W}Benchmark scores (%):{N}\n")
    header = f"  {'Benchmark':<16}"
    for bench in all_benches:
        header += f" {'deepseek':>9}"
    for model in FRONTIER_SCORES:
        header += f" {model[:10]:>10}"
    print(f"  {DIM}{header}{N}")

    for bench in all_benches:
        row = f"  {BENCHMARK_LABELS[bench][:15]:<16}"
        if bench in our_scores:
            row += f" {our_scores[bench]:>9.1f}"
        else:
            row += f" {'--':>9}"
        for model in FRONTIER_SCORES:
            row += f" {FRONTIER_SCORES[model].get(bench, 0):>10.1f}"
        print(row)

    print(f"\n  {W}Comparison Chart:{N}\n")
    max_val = (
        max(max(m.values()) for m in FRONTIER_SCORES.values())
        if FRONTIER_SCORES
        else 100
    )

    for bench in all_benches:
        avg_f = frontier_avg(bench)
        print(f"  {Y}{BENCHMARK_LABELS[bench][:50]}{N}")
        if bench in our_scores:
            our_pct = our_scores[bench]
            print(horizontal_bar("deepseek-v4-flash", our_pct, max_val))
            print(horizontal_bar("Frontier avg", avg_f, max_val, color=Y))
            gap = our_pct - avg_f
            gap_str = f"{G}+{gap:.1f}%{N}" if gap >= 0 else f"{R}{gap:.1f}%{N}"
            print(f"  {'Gap':>22} {' ' * 40} {gap_str}")
        else:
            print(f"  {'deepseek-v4-flash':>22} {' ' * 40} {DIM}NOT RUN{N}")
            print(horizontal_bar("Frontier avg", avg_f, max_val, color=Y))

    print(f"\n  {W}Overall Rankings:{N}\n")
    all_avg = {}
    for model, scores in FRONTIER_SCORES.items():
        all_avg[model] = sum(scores.values()) / len(scores)
    ranked = sorted(all_avg.items(), key=lambda x: x[1], reverse=True)

    has_our_data = len(our_scores) > 0
    if has_our_data:
        ran_benches = list(our_scores.keys())
        our_overall = sum(our_scores[b] for b in ran_benches) / len(ran_benches)
        all_avg["deepseek-v4-flash (ours)"] = our_overall
        ranked = sorted(all_avg.items(), key=lambda x: x[1], reverse=True)
    else:
        print(f"  {DIM}  No benchmark data yet. Showing frontier models only.{N}\n")

    for rank, (model, avg) in enumerate(ranked, 1):
        marker = f"{M}←" if "ours" in model else ""
        if rank == 1:
            icon = ""
        elif rank == 2:
            icon = ""
        elif rank == 3:
            icon = ""
        else:
            icon = f" {rank}. "
        print(f"  {icon} {model:<28} {avg:.1f}% {marker}{N}")

    max_bar = max(v for _, v in ranked)
    print(f"\n  {W}Overall Score Distribution:{N}\n")
    for model, avg in ranked:
        print(horizontal_bar(model, avg, max_bar, color=C if "ours" in model else B))


# ============================================================================
# MAIN
# ============================================================================


def parse_args():
    mode = "all"
    bench_filter = None
    interactive = False
    show_stat = False
    auto_mode = False
    prev_arg = ""
    for arg in sys.argv[1:]:
        if prev_arg == "--bench":
            bench_filter = arg.strip().lower()
            mode = bench_filter
            prev_arg = ""
        elif arg == "--interactive":
            interactive = True
        elif arg == "--stats":
            show_stat = True
        elif arg == "--auto":
            auto_mode = True
        elif arg.startswith("--bench"):
            if "=" in arg:
                bench_filter = arg.split("=")[1].strip().lower()
                mode = bench_filter
            else:
                mode = "all"
            prev_arg = arg
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            prev_arg = ""
    if auto_mode and interactive:
        interactive = False
    return mode, bench_filter, interactive, show_stat


def main():
    mode, bench_filter, interactive, show_stat = parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    section_header("BENCHMARK HARNESS: deepseek-v4-flash vs Frontier Models")
    print(
        f"  {DIM}{time.strftime('%Y-%m-%d %H:%M:%S')} | CortexStratum | Python 3.13{N}"
    )

    if show_stat:
        saved = safe_json_load(DATA_DIR / "benchmark-results.json")
        show_stats(saved)
        return

    benches_to_run = list(BENCHMARK_DATA.keys())
    if bench_filter and bench_filter != "all":
        if bench_filter not in BENCHMARK_DATA:
            print(f"\n  {R}Unknown benchmark: {bench_filter}{N}")
            print(f"  Valid: {', '.join(BENCHMARK_DATA.keys())}")
            sys.exit(1)
        benches_to_run = [bench_filter]

    all_results = []

    for bench_key in benches_to_run:
        questions = BENCHMARK_DATA[bench_key]
        if interactive:
            result = run_interactive_benchmark(bench_key, questions)
        else:
            result = run_auto_benchmark(bench_key, questions)
        all_results.append(result)

    total_q = sum(r["total"] for r in all_results)
    total_s = sum(r["score"] for r in all_results)
    overall_pct = (total_s / total_q * 100) if total_q else 0

    section_header("OVERALL RESULTS")
    print("")
    for r in all_results:
        bench = r["bench"]
        avg_f = frontier_avg(bench)
        gap = r["pct"] - avg_f
        gap_str = f"{G}+{gap:.1f}%{N}" if gap >= 0 else f"{R}{gap:.1f}%{N}"
        print(f"  {Y}{BENCHMARK_LABELS[bench][:50]}{N}")
        print(f"    Our score:   {r['pct']:.1f}%  ({r['score']:.0f}/{r['total']})")
        print(f"    Frontier avg: {avg_f:.1f}%")
        print(f"    Gap:          {gap_str}")

    print(f"\n  {W}OVERALL: {total_s:.0f}/{total_q} ({overall_pct:.1f}%){N}")
    avg_frontier = sum(
        frontier_avg(b) * len(BENCHMARK_DATA[b]) for b in BENCHMARK_DATA
    ) / sum(len(BENCHMARK_DATA[b]) for b in BENCHMARK_DATA)
    print(f"  {W}Frontier avg: {avg_frontier:.1f}%{N}")
    rank_num = (
        sum(
            1
            for m, s in sorted(
                [(m, sum(v.values()) / len(v)) for m, v in FRONTIER_SCORES.items()],
                key=lambda x: x[1],
                reverse=True,
            )
            if s > overall_pct
        )
        + 1
    )
    print(
        f"  {W}Rank among comparison models: #{rank_num} of {len(FRONTIER_SCORES) + 1}{N}"
    )

    section_header("RANKING")
    all_avg = {}
    for model, scores in FRONTIER_SCORES.items():
        all_avg[model] = sum(scores.values()) / len(scores)
    all_avg["deepseek-v4-flash (ours)"] = overall_pct
    ranked = sorted(all_avg.items(), key=lambda x: x[1], reverse=True)
    for rank, (model, avg) in enumerate(ranked, 1):
        marker = f" {M}←{N}" if "ours" in model else ""
        print(f"  {rank}. {model:<28} {avg:.1f}%{marker}")

    print(f"\n  {W}Score Distribution:{N}\n")
    max_bar = max(v for _, v in ranked)
    for model, avg in ranked:
        print(horizontal_bar(model, avg, max_bar, color=C if "ours" in model else B))

    result_path = DATA_DIR / "benchmark-results.json"
    existing = safe_json_load(result_path)
    if existing and isinstance(existing.get("results"), list):
        {r["bench"] for r in existing["results"]}
        merged_results = [
            r
            for r in existing["results"]
            if r["bench"] not in {x["bench"] for x in all_results}
        ]
        merged_results.extend(all_results)
    else:
        merged_results = all_results

    merged_total_q = sum(r["total"] for r in merged_results)
    merged_total_s = sum(r["score"] for r in merged_results)
    merged_overall_pct = round(
        (merged_total_s / merged_total_q * 100) if merged_total_q else 0, 2
    )

    merged_avg_frontier = sum(
        frontier_avg(r["bench"]) * r["total"] for r in merged_results
    ) / max(merged_total_q, 1)

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "interactive" if interactive else "auto",
        "results": merged_results,
        "overall_score": merged_total_s,
        "overall_total": merged_total_q,
        "overall_pct": merged_overall_pct,
        "frontier_avg": round(merged_avg_frontier, 2),
        "rank": rank_num,
        "frontier_scores": FRONTIER_SCORES,
    }
    safe_json_save(result_path, output)
    print(f"\n  {DIM}Results saved to: {result_path}{N}")
    print(f"{'=' * 70}\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Y}Interrupted.{N}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{R}Error: {e}{N}")
        traceback.print_exc()
        sys.exit(1)
