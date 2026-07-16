#!/usr/bin/env python3
"""Literature Module — Text analysis, concept extraction, study guides for social sciences."""

import json
import math
import re
from collections import Counter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD_SPLIT = re.compile(r"\b[a-zA-Z]{2,}\b")
_SYLLABLE_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_CONCEPT_PATTERN = re.compile(
    r"\b((?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)|(?:" + r"\w+(?:\s\w+){0,3}" + r"))\b"
)


def _count_syllables(word: str) -> int:
    if len(word) <= 3:
        return 1
    syllables = len(_SYLLABLE_RE.findall(word))
    if word.endswith(("es", "ed")):
        syllables = max(1, syllables - 1)
    return max(1, syllables)


def _flesch_kincaid(text: str) -> dict:
    words = _WORD_SPLIT.findall(text)
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not words or not sentences:
        return {"score": 0, "grade": "N/A", "readability": "N/A"}
    total_syllables = sum(_count_syllables(w) for w in words)
    word_count = len(words)
    sentence_count = len(sentences)

    fk_score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (total_syllables / word_count)
    fk_score = max(0, min(100, fk_score))

    if fk_score >= 90:
        grade, readability = "5th grade", "Very Easy"
    elif fk_score >= 80:
        grade, readability = "6th grade", "Easy"
    elif fk_score >= 70:
        grade, readability = "7th grade", "Fairly Easy"
    elif fk_score >= 60:
        grade, readability = "8th-9th grade", "Standard"
    elif fk_score >= 50:
        grade, readability = "10th-12th grade", "Fairly Difficult"
    elif fk_score >= 30:
        grade, readability = "College", "Difficult"
    else:
        grade, readability = "College Graduate", "Very Difficult"

    return {
        "score": round(fk_score, 1),
        "grade": grade,
        "readability": readability,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_words_per_sentence": round(word_count / sentence_count, 1),
        "avg_syllables_per_word": round(total_syllables / word_count, 1),
    }


def _extract_key_phrases(text: str, top_n: int = 15) -> list:
    words = _WORD_SPLIT.findall(text.lower())
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "by", "with", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "must", "it", "its",
        "this", "that", "these", "those", "we", "you", "they", "he", "she",
        "not", "no", "nor", "so", "as", "if", "than", "then", "also", "very",
        "just", "about", "up", "out", "more", "most", "some", "any", "each",
        "every", "all", "both", "few", "many", "much", "such", "which", "what",
        "who", "whom", "when", "where", "why", "how",
    }
    filtered = [w for w in words if w not in stop_words and len(w) > 2]
    freqs = Counter(filtered).most_common(top_n)
    return [{"word": w, "count": c, "score": round(c / len(filtered), 4)} for w, c in freqs]


def _extract_claims_evidence(text: str) -> dict:
    claim_signals = re.findall(
        r"(?:claim|argue|assert|suggest|propose|contend|maintain|believe|theorize)\s+that\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )
    evidence_signals = re.findall(
        r"(?:evidence|research|study|data|findings|experiment|survey|according to|demonstrate|show|indicate|prove)\s+that\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )
    conclusion_signals = re.findall(
        r"(?:therefore|thus|hence|consequently|in conclusion|overall|in summary|as a result|accordingly)\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )

    return {
        "claims": [s.strip() for s in claim_signals],
        "evidence": [s.strip() for s in evidence_signals],
        "conclusions": [s.strip() for s in conclusion_signals],
        "claim_count": len(claim_signals),
        "evidence_count": len(evidence_signals),
        "conclusion_count": len(conclusion_signals),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_text(text: str) -> dict:
    if not text or not text.strip():
        return {"error": "No text provided"}
    reading = _flesch_kincaid(text)
    phrases = _extract_key_phrases(text)
    args = _extract_claims_evidence(text)

    sentiment_polarity = 0.0
    positive_words = {"good", "great", "excellent", "positive", "beneficial", "important",
                      "significant", "effective", "successful", "valuable", "useful",
                      "clear", "strong", "supported", "valid", "convincing", "innovative",
                      "promising", "remarkable"}
    negative_words = {"bad", "poor", "negative", "harmful", "problematic", "flawed",
                      "insufficient", "weak", "invalid", "unconvincing", "limited",
                      "failed", "unsupported", "ambiguous", "contradictory", "erroneous"}
    word_list = _WORD_SPLIT.findall(text.lower())
    if word_list:
        pos_count = sum(1 for w in word_list if w in positive_words)
        neg_count = sum(1 for w in word_list if w in negative_words)
        total = len(word_list)
        sentiment_polarity = round((pos_count - neg_count) / total, 4)

    return {
        "reading_level": reading,
        "key_phrases": phrases,
        "argument_structure": args,
        "sentiment": {
            "polarity": sentiment_polarity,
            "label": "positive" if sentiment_polarity > 0.02 else ("negative" if sentiment_polarity < -0.02 else "neutral"),
        },
        "text_length": len(text),
    }


def extract_concepts(text: str) -> dict:
    if not text or not text.strip():
        return {"error": "No text provided"}

    sentences = _SENTENCE_SPLIT.split(text)
    candidates = _CONCEPT_PATTERN.findall(text)
    candidates = [c.strip() for c in candidates if len(c.strip()) > 3 and not c.strip().isdigit()]
    candidate_freq = Counter(candidates).most_common(20)

    concepts = []
    for concept, freq in candidate_freq:
        context_sentences = []
        for s in sentences:
            if concept.lower() in s.lower():
                context_sentences.append(s.strip())
        if context_sentences:
            definition = context_sentences[0] if len(context_sentences) == 1 else (
                f"Mentioned {len(context_sentences)} times. First context: {context_sentences[0][:120]}..."
            )
        else:
            definition = "No direct context found"
        concepts.append({
            "concept": concept,
            "frequency": freq,
            "context_count": len(context_sentences),
            "definition": definition[:200],
        })

    relationships = []
    for i in range(min(len(concepts), 8)):
        for j in range(i + 1, min(len(concepts), 8)):
            c1, c2 = concepts[i]["concept"], concepts[j]["concept"]
            cooccur = sum(1 for s in sentences if c1.lower() in s.lower() and c2.lower() in s.lower())
            if cooccur > 0:
                relationships.append({
                    "source": c1,
                    "target": c2,
                    "cooccurrences": cooccur,
                    "strength": "strong" if cooccur > 3 else ("moderate" if cooccur > 1 else "weak"),
                })

    return {
        "concepts": concepts[:15],
        "relationships": relationships[:20],
        "concept_map": {
            "nodes": [{"id": c["concept"], "frequency": c["frequency"]} for c in concepts[:10]],
            "edges": [{"source": r["source"], "target": r["target"], "strength": r["strength"]}
                      for r in relationships[:15]],
        },
        "total_concepts": len(concepts),
    }


def generate_study_guide(content: str) -> dict:
    if not content or not content.strip():
        return {"error": "No content provided"}

    analysis = analyze_text(content)
    concepts_data = extract_concepts(content)

    sentences = _SENTENCE_SPLIT.split(content)
    section_size = max(1, len(sentences) // 4)
    sections = []
    for i in range(0, len(sentences), section_size):
        chunk = " ".join(sentences[i:i + section_size])
        if chunk.strip():
            ch_analysis = _flesch_kincaid(chunk)
            sections.append({
                "id": len(sections) + 1,
                "preview": chunk[:150] + "...",
                "word_count": ch_analysis["word_count"],
                "estimated_minutes": max(1, ch_analysis["word_count"] // 200),
            })

    key_terms = [{"term": c["concept"], "definition": c["definition"]} for c in concepts_data.get("concepts", [])[:10]]

    discussion_questions = []
    for c in key_terms[:5]:
        discussion_questions.append(f"How does the concept of '{c['term']}' relate to the main thesis of this text?")
    discussion_questions.append("What evidence does the author provide to support their central claim?")
    discussion_questions.append("What counterarguments could be raised against the main position?")
    discussion_questions.append("How does this content connect to broader themes in the field?")
    discussion_questions.append("What are the practical implications of the ideas presented?")

    connections = concepts_data.get("relationships", [])[:5]
    connection_questions = []
    for rel in connections:
        connection_questions.append(f"Explore the relationship between {rel['source']} and {rel['target']} — how do they interact?")

    return {
        "title": "Study Guide",
        "reading_level": analysis["reading_level"],
        "sections": sections,
        "key_terms": key_terms,
        "discussion_questions": discussion_questions + connection_questions,
        "summary_by_section": [
            {
                "section": i + 1,
                "key_points": [c["concept"] for c in concepts_data.get("concepts", [])[i * 3:(i + 1) * 3]],
            }
            for i in range(min(4, max(1, len(concepts_data.get("concepts", [])) // 3)))
        ],
        "total_estimated_minutes": sum(s["estimated_minutes"] for s in sections),
    }


def analyze_philosophy(text: str) -> dict:
    if not text or not text.strip():
        return {"error": "No text provided"}

    premise_signals = re.findall(
        r"(?:because|since|given that|assuming|if|premise|axiom|first principle|it is clear that)\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )
    conclusion_signals = re.findall(
        r"(?:therefore|thus|hence|so|consequently|it follows that|infer|conclude|ergo)\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )
    counterargument_signals = re.findall(
        r"(?:however|but|on the other hand|objection|critic|contrary|nevertheless|nonetheless|yet|although)\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )

    deductive_pat = re.findall(r"(?:all|every|no|if.*then|necessarily|must be|always)", text, re.IGNORECASE)
    inductive_pat = re.findall(r"(?:most|many|some|usually|typically|probably|likely|tends to|suggests)", text, re.IGNORECASE)
    abductive_pat = re.findall(r"(?:best explanation|inference to the best|would explain|hypothesize|hypothesis)", text, re.IGNORECASE)

    reasoning_type = "deductive" if len(deductive_pat) > max(len(inductive_pat), len(abductive_pat)) else \
                     "inductive" if len(inductive_pat) > len(abductive_pat) else "abductive"

    philosopher_map = {
        "plato": "Plato (c. 428-348 BCE) — Theory of Forms, Allegory of the Cave, Platonic idealism",
        "aristotle": "Aristotle (384-322 BCE) — Logic, ethics (Nicomachean Ethics), metaphysics, politics",
        "descartes": "René Descartes (1596-1650) — Cartesian dualism, 'Cogito ergo sum', rationalism",
        "kant": "Immanuel Kant (1724-1804) — Transcendental idealism, categorical imperative, Critique of Pure Reason",
        "nietzsche": "Friedrich Nietzsche (1844-1900) — Will to power, eternal recurrence, master-slave morality, Übermensch",
        "hume": "David Hume (1711-1776) — Empiricism, skepticism, problem of induction, bundle theory of self",
        "locke": "John Locke (1632-1704) — Tabula rasa, empiricism, social contract, natural rights",
        "rousseau": "Jean-Jacques Rousseau (1712-1778) — Social contract, general will, state of nature",
        "hegel": "G. W. F. Hegel (1770-1831) — Dialectic (thesis-antithesis-synthesis), Absolute Spirit, phenomenology",
        "wittgenstein": "Ludwig Wittgenstein (1889-1951) — Language games, picture theory, private language argument",
        "sartre": "Jean-Paul Sartre (1905-1980) — Existentialism, 'existence precedes essence', radical freedom, bad faith",
        "heidegger": "Martin Heidegger (1889-1976) — Dasein, Being-in-the-world, authenticity, thrownness",
        "dewey": "John Dewey (1859-1952) — Pragmatism, instrumentalism, learning by doing, democracy and education",
        "rawls": "John Rawls (1921-2002) — Justice as fairness, veil of ignorance, difference principle",
        "foucault": "Michel Foucault (1926-1984) — Power/knowledge, biopower, discipline and punish, discourse analysis",
    }

    detected_philosophers = {}
    text_lower = text.lower()
    for key, info in philosopher_map.items():
        if key in text_lower:
            detected_philosophers[key.title()] = info

    thought_experiments = re.findall(
        r"(?:imagine|suppose|consider|what if|hypothetical|thought experiment)\s+([^.!?]+[.!?])",
        text, re.IGNORECASE
    )

    schools = []
    school_map = {
        "empiricism": ["locke", "hume", "berkeley"],
        "rationalism": ["descartes", "spinoza", "leibniz"],
        "existentialism": ["sartre", "camus", "beauvoir", "kierkegaard", "nietzsche", "heidegger"],
        "pragmatism": ["peirce", "james", "dewey", "rorty"],
        "analytic": ["frege", "russell", "wittgenstein", "ayer", "quine"],
        "continental": ["hegel", "heidegger", "sartre", "foucault", "derrida"],
        "stoicism": ["zendo", "seneca", "epictetus", "marcus aurelius"],
    }
    for school, philosophers in school_map.items():
        if any(p in text_lower for p in philosophers):
            schools.append(school)

    return {
        "premises": [s.strip() for s in premise_signals[:5]],
        "conclusions": [s.strip() for s in conclusion_signals[:5]],
        "counterarguments": [s.strip() for s in counterargument_signals[:5]],
        "logical_structure": {
            "reasoning_type": reasoning_type,
            "deductive_patterns": len(deductive_pat),
            "inductive_patterns": len(inductive_pat),
            "abductive_patterns": len(abductive_pat),
        },
        "detected_philosophers": detected_philosophers,
        "philosophical_schools": schools,
        "thought_experiments": [s.strip() for s in thought_experiments[:3]],
        "premise_count": len(premise_signals),
        "conclusion_count": len(conclusion_signals),
        "counterargument_count": len(counterargument_signals),
    }


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    if action == "analyze_text":
        text = sys.argv[2] if len(sys.argv) > 2 else "This is a sample text for analysis."
        print(json.dumps(analyze_text(text), indent=2))
    elif action == "extract_concepts":
        text = sys.argv[2] if len(sys.argv) > 2 else "Artificial intelligence and machine learning are transforming industries."
        print(json.dumps(extract_concepts(text), indent=2))
    elif action == "generate_study_guide":
        text = sys.argv[2] if len(sys.argv) > 2 else "Chapter 1: Introduction to the subject matter."
        print(json.dumps(generate_study_guide(text), indent=2))
    elif action == "analyze_philosophy":
        text = sys.argv[2] if len(sys.argv) > 2 else "Descartes argues that because the mind is indivisible and the body is divisible, they must be distinct substances."
        print(json.dumps(analyze_philosophy(text), indent=2))
    else:
        print("Literature Module — available actions: analyze_text, extract_concepts, generate_study_guide, analyze_philosophy")
