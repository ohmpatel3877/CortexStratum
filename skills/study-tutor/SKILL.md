---
name: study-tutor
description: Evidence-based collegiate study techniques using active recall, spaced repetition, interleaving, and dual coding. Use when the user asks for study help, exam prep, learning strategies, memory techniques, tutoring methodology, or academic skill building.
---

# Study Tutor — Collegiate-Level Learning Techniques

Evidence-based study methodology grounded in cognitive psychology research. Designed for STEM/engineering students transitioning to university rigor. Replaces "read and re-read" with retrieval-based learning.

## When to Use This Skill

- User asks for study tips, exam prep, or learning strategies
- User is struggling to retain course material
- User needs a study schedule or plan
- User wants to understand *how* learning works
- Tutoring sessions — use the pedagogical methods in this skill to structure your teaching

## Core Model — The Memory Pipeline

All learning follows: **Encode → Store → Retrieve**

Most students optimize encoding (reading, highlighting, watching). The bottleneck is always retrieval.

```
          
  Encode   →   Store    →  Retrieve 
  (Input)        (Hold)         (Output)
          
      ↑                ↑                ↑
   reading          sleep,           practice
   listening       spacing,         tests,
   watching       consolidation    flashcards
```

**Analogy — The Library Stack:** Encoding is buying a book. Storage is shelving it. Retrieval is finding and checking it out. Most students spend all their time buying books and never practice finding them on the shelf.

## The Four Pillars

### 1. Active Recall (Testing Effect)
Close the source. Force retrieval before re-reading. Each retrieval attempt strengthens the neural pathway. This is the single most effective technique (Roediger & Karpicke, 2006).

**Methods:**
- **Blurting:** Read a section → close book → write everything you remember
- **Feynman Technique:** Explain to an imaginary 12-year-old. If you can't simplify it, you don't understand it.
- **Practice problems:** Do them without looking at examples. Struggle first. Check after.

### 2. Spaced Repetition
Distribute practice over increasing gaps. Each re-retrieval from a "nearly forgotten" state strengthens memory far more than massed practice (Bjork, 1994).

**Schedule template:**
```
Session 1: Day 1  — learn material
Session 2: Day 2  — recall + fill gaps
Session 3: Day 5  — mixed practice
Session 4: Day 14 — exam simulation
Session 5: Day 30 — quick refresher
```

**Tools:** Anki (digital flashcards with built-in SRS), calendar blocking

### 3. Interleaving
Mix different topics or problem types within a single session instead of blocking (all of A, then all of B). Trains your brain to *identify* which technique applies, not just execute the one you know is coming (Rohrer, 2012).

**Example — Calc studying:**
```
Blocked (weak):  30 integration by parts → 30 u-sub → 30 trig sub
Interleaved:     2 parts → 2 u-sub → 2 trig sub → repeat ×5
```

### 4. Dual Coding
Represent information in two formats (verbal + visual). Creates two retrieval paths. Forces you to understand relationships, not just definitions.

**Method:** Diagram-first notes. Draw the structure. Add labels. Write the explanation to accompany it.

## The 60-Minute Study Session

```
[0:00-0:02]  Pre-quiz — recall last session without notes
[0:02-0:20]  New content with micro-recall every 5 min
[0:20-0:35]  Active recall — closed-book problems, summaries
[0:35-0:50]  Interleaved practice — mix 2-3 topics
[0:50-0:55]  Dual coding — diagram connecting today's ideas
[0:55-1:00]  Post-quiz + schedule next session
```

## Debunked Myths

| Myth | Truth |
|------|-------|
| Learning styles matter | Debunked. No evidence. Use multiple modalities, don't label yourself. |
| Highlighting works | Creates fluency illusion. One of the weakest techniques. |
| Re-reading is effective | Negligible gains beyond first pass. Spend time on retrieval instead. |
| Multitasking | Doesn't exist. Only task-switching at 15-25 min focus cost each time. |
| Cramming works | Short-term exam survival. Zero retention after 48 hours. |

## Teaching Methodology (for the AI to use)

When tutoring using this skill, use these pedagogical techniques:

1. **Background knowledge check** — Start with questions that reveal what the student already knows and what misconceptions they hold
2. **Core model first** — Give them a mental framework before layering in details
3. **Analogy** — Map abstract concepts to familiar systems (library, gym, sports)
4. **Visual diagrams** — Mermaid, ASCII, or described diagrams for dual coding
5. **Embedded active recall** — Stop and ask them to recall/explain mid-lesson
6. **Debunk upfront** — Kill common myths before they cause friction
7. **Scaffold to concrete** — End with specific tools and templates, not abstract advice
8. **Final knowledge check** — Test retention immediately with closed-book questions

## NE-Memory Integration

After tutoring sessions, store:
- `type: user_preference` — their learning style, subject, pain points
- `type: task_learning` — which techniques worked for them
- `type: session_summary` — what was covered, what's next

## References

- Roediger & Karpicke (2006). Test-enhanced learning. *Psychological Science*.
- Bjork (1994). Memory and metamemory considerations in human training.
- Dunlosky et al. (2013). Effective learning techniques. *Psychological Science in the Public Interest*.
- Cepeda et al. (2006). Distributed practice in verbal recall tasks. *Psychological Bulletin*.
- Rohrer (2012). Interleaving helps distinguish similar concepts. *Educational Psychology Review*.
