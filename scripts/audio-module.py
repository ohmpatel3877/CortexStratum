#!/usr/bin/env python3
"""
Audio Module — AI auditory analysis assistant.
Analyzes WAV files, music theory, speech patterns, tone generation,
frequency analysis, format conversion guides, and waveform visualization.

Registered as MCP tools via tools-mcp-server.py.

Architecture:
  Each function is a pure handler: dict in → dict out.
  Pure Python stdlib only: wave, struct, array, math, json, base64, io, tempfile,
  subprocess, os, re, statistics, itertools.
  No external API calls, no pip packages needed.
"""

import array
import base64
import io
import itertools
import json
import math
import os
import re
import statistics
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Note-frequency table: C0 (16.35 Hz) through B8 (7902.13 Hz) — 108 notes
# ---------------------------------------------------------------------------

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

A4_FREQ = 440.0
A4_OFFSET = 57  # A4 is the 58th note (0-indexed: 57)


def _note_to_freq(octave: int, note_idx: int) -> float:
    semitones = (octave * 12 + note_idx) - A4_OFFSET
    return A4_FREQ * (2.0 ** (semitones / 12.0))


def _freq_to_note_name(freq: float) -> str:
    if freq <= 0:
        return "?"
    semitones = 12.0 * math.log2(freq / A4_FREQ)
    n = round(semitones) + A4_OFFSET
    octave = n // 12
    note_idx = n % 12
    if octave < 0 or octave > 8:
        return f"{NOTE_NAMES[note_idx]}?"
    return f"{NOTE_NAMES[note_idx]}{octave}"


def _freq_to_midi(freq: float) -> int:
    if freq <= 0:
        return -1
    return round(69 + 12 * math.log2(freq / 440.0))


# Build the full lookup table
NOTE_FREQ_TABLE: list[dict] = []
for _oct in range(9):
    for _ni in range(12):
        _f = _note_to_freq(_oct, _ni)
        NOTE_FREQ_TABLE.append({
            "name": f"{NOTE_NAMES[_ni]}{_oct}",
            "frequency": round(_f, 2),
            "midi": len(NOTE_FREQ_TABLE),
            "octave": _oct,
        })


def _lookup_freq(note_name: str) -> float | None:
    for entry in NOTE_FREQ_TABLE:
        if entry["name"].upper() == note_name.upper():
            return entry["frequency"]
    return None


def _lookup_midi(note_name: str) -> int | None:
    for entry in NOTE_FREQ_TABLE:
        if entry["name"].upper() == note_name.upper():
            return entry["midi"]
    return None


# ---------------------------------------------------------------------------
# Chord definitions
# ---------------------------------------------------------------------------

CHORD_DEFINITIONS: dict[str, list[int]] = {
    "major": [0, 4, 7],
    "minor": [0, 3, 7],
    "diminished": [0, 3, 6],
    "augmented": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "major_7th": [0, 4, 7, 11],
    "minor_7th": [0, 3, 7, 10],
    "dominant_7th": [0, 4, 7, 10],
    "diminished_7th": [0, 3, 6, 9],
    "half_diminished_7th": [0, 3, 6, 10],
    "minor_major_7th": [0, 3, 7, 11],
    "augmented_7th": [0, 4, 8, 10],
    "major_6th": [0, 4, 7, 9],
    "minor_6th": [0, 3, 7, 9],
    "power": [0, 7],
    "major_9th": [0, 4, 7, 11, 14],
    "minor_9th": [0, 3, 7, 10, 14],
    "dominant_9th": [0, 4, 7, 10, 14],
    "add9": [0, 4, 7, 14],
}

INTERVAL_NAMES: dict[int, str] = {
    0: "root",
    1: "minor second",
    2: "major second",
    3: "minor third",
    4: "major third",
    5: "perfect fourth",
    6: "tritone / augmented fourth",
    7: "perfect fifth",
    8: "minor sixth",
    9: "major sixth",
    10: "minor seventh",
    11: "major seventh",
    12: "octave",
}

SCALE_DEFINITIONS: dict[str, list[int]] = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "chromatic": list(range(12)),
    "whole_tone": [0, 2, 4, 6, 8, 10],
    "diminished": [0, 2, 3, 5, 6, 8, 9, 11],
}

CHORD_MOODS: dict[str, str] = {
    "major": "bright, stable, happy",
    "minor": "sad, melancholic, serious",
    "diminished": "tense, unstable, dark",
    "augmented": "dreamy, floating, ambiguous",
    "sus2": "open, airy, hopeful",
    "sus4": "suspended, unresolved, yearning",
    "major_7th": "warm, jazzy, romantic",
    "minor_7th": "smooth, contemplative, soulful",
    "dominant_7th": "bluesy, expectant, driving",
    "diminished_7th": "dramatic, agitated, classical",
    "half_diminished_7th": "bittersweet, jazz minor",
    "minor_major_7th": "mysterious, noir",
    "augmented_7th": "otherworldly, surreal",
    "major_6th": "sweet, vintage, doo-wop",
    "minor_6th": "wistful, gypsy jazz",
    "power": "bold, strong, rock",
    "major_9th": "lush, sophisticated, smooth jazz",
    "minor_9th": "smoky, sophisticated",
    "dominant_9th": "bluesy, funky",
    "add9": "sparkling, pop anthem",
}


def _match_chord_from_semitones(semitones: list[int]) -> dict[str, Any]:
    best_match = None
    best_score = -1
    normalized = sorted(set(s % 12 for s in semitones))
    for chord_name, intervals in CHORD_DEFINITIONS.items():
        chord_set = set(intervals)
        if chord_set == set(normalized):
            best_match = chord_name
            best_score = len(intervals) * 10
            break
        intersection = chord_set & set(normalized)
        union = chord_set | set(normalized)
        score = len(intersection) * 7 - (len(union) - len(intersection)) * 3
        if score > best_score:
            best_score = score
            best_match = chord_name

    if best_match is None:
        return {"chord": "unknown", "match_confidence": 0.0}

    intervals_list = CHORD_DEFINITIONS.get(best_match, [])
    return {
        "chord": best_match,
        "match_confidence": min(1.0, best_score / (len(intervals_list) * 10)),
    }


def _match_scales(root_midi: int, notes: list[int]) -> list[str]:
    root_pc = root_midi % 12
    note_pcs = set(n % 12 for n in notes)
    matches: list[str] = []
    for scale_name, intervals in SCALE_DEFINITIONS.items():
        scale_pcs = set((root_pc + i) % 12 for i in intervals)
        if note_pcs.issubset(scale_pcs):
            matches.append(scale_name)
    return matches


# ---------------------------------------------------------------------------
# 1. audio_analyze_file
# ---------------------------------------------------------------------------

def analyze_file(args: dict) -> dict:
    """Analyze a WAV/PCM audio file for metadata and amplitude statistics."""
    file_path = args.get("file_path", "")
    data_b64 = args.get("data_base64", "")
    fmt = args.get("format", "wav").lower()

    try:
        if data_b64:
            raw = base64.b64decode(data_b64)
            wf = wave.open(io.BytesIO(raw), "rb")
            file_size = len(raw)
        elif file_path:
            file_size = os.path.getsize(file_path)
            wf = wave.open(file_path, "rb")
        else:
            return {"status": "error", "error": "Provide file_path or data_base64"}

        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        bit_depth = wf.getsampwidth() * 8
        n_frames = wf.getnframes()
        duration = n_frames / sample_rate if sample_rate > 0 else 0

        raw_frames = wf.readframes(n_frames)
        wf.close()

        fmt_char = {1: "b", 2: "h", 4: "i"}.get(wf.getsampwidth(), "h")
        if wf.getsampwidth() == 1:
            fmt_char = "B"
        total_samples = n_frames * channels
        samples = struct.unpack(f"<{total_samples}{fmt_char}", raw_frames)

        if wf.getsampwidth() == 1:
            samples_centered = [s - 128 for s in samples]
        else:
            samples_centered = list(samples)

        if not samples_centered:
            return {"status": "error", "error": "No audio samples found"}

        mean_amp = statistics.mean(abs(s) for s in samples_centered)
        max_amp = max(abs(s) for s in samples_centered)
        rms = math.sqrt(statistics.mean(s * s for s in samples_centered))
        if rms > 0:
            dynamic_range = 20 * math.log10(max_amp / rms)
        else:
            dynamic_range = 0.0

        return {
            "status": "ok",
            "duration_seconds": round(duration, 3),
            "channels": channels,
            "sample_rate": sample_rate,
            "bit_depth": bit_depth,
            "format": fmt,
            "file_size_bytes": file_size,
            "frames": n_frames,
            "amplitude": {
                "mean": round(mean_amp, 6),
                "max": round(float(max_amp), 6),
                "rms": round(rms, 6),
                "dynamic_range_db": round(dynamic_range, 2),
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# 2. audio_waveform
# ---------------------------------------------------------------------------

BLOCK_CHARS = ""


def generate_waveform(args: dict) -> dict:
    """Generate ASCII waveform art from a WAV file."""
    file_path = args.get("file_path", "")
    width = args.get("width", 80)
    height = args.get("height", 20)
    data_b64 = args.get("data_base64", "")

    if not file_path and not data_b64:
        return {"status": "error", "error": "Provide file_path or data_base64"}

    try:
        if data_b64:
            raw = base64.b64decode(data_b64)
            wf = wave.open(io.BytesIO(raw), "rb")
        else:
            wf = wave.open(file_path, "rb")

        n_frames = wf.getnframes()
        raw_frames = wf.readframes(n_frames)
        wf.close()

        fmt_char = {1: "B", 2: "h", 4: "i"}.get(wf.getsampwidth(), "h")
        total_samples = n_frames * wf.getnchannels()
        samples = struct.unpack(f"<{total_samples}{fmt_char}", raw_frames)

        mono = []
        ch = wf.getnchannels()
        step = max(1, len(samples) // (width * ch))
        for i in range(0, len(samples) - ch + 1, step * ch):
            block = samples[i:i + step * ch]
            if wf.getsampwidth() == 1:
                mono.append(statistics.mean(abs(x - 128) for x in block))
            else:
                mono.append(statistics.mean(abs(x) for x in block))

        data_points = mono[:width]
        if not data_points:
            return {"status": "error", "error": "No data extracted"}

        dmin = min(data_points)
        dmax = max(data_points)
        d_range = dmax - dmin if dmax > dmin else 1

        num_levels = len(BLOCK_CHARS)
        rows: list[str] = []
        for row in range(height - 1, -1, -1):
            threshold = dmin + (row / max(1, height - 1)) * d_range
            line = ""
            for val in data_points:
                normalized = (val - dmin) / d_range
                block_idx = min(num_levels - 1, int(normalized * num_levels))
                if row == 0:
                    line += BLOCK_CHARS[block_idx] if normalized > 0 else " "
                else:
                    line += BLOCK_CHARS[block_idx] if val >= threshold else " "
            rows.append(line)

        waveform_str = "\n".join(rows)

        return {
            "status": "ok",
            "waveform": waveform_str,
            "data_points": [round(float(dp), 6) for dp in data_points],
            "scale": {
                "min": round(float(dmin), 6),
                "max": round(float(dmax), 6),
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# 3. audio_frequency_analysis — real DFT
# ---------------------------------------------------------------------------

FREQ_BANDS = [
    ("sub_bass", 20, 60),
    ("bass", 60, 250),
    ("low_mid", 250, 500),
    ("mid", 500, 2000),
    ("upper_mid", 2000, 4000),
    ("presence", 4000, 6000),
    ("brilliance", 6000, 20000),
]

BAND_LABELS: dict[str, str] = {
    "sub_bass": "Sub-bass (20-60Hz)",
    "bass": "Bass (60-250Hz)",
    "low_mid": "Low-mid (250-500Hz)",
    "mid": "Mid (500-2000Hz)",
    "upper_mid": "Upper-mid (2000-4000Hz)",
    "presence": "Presence (4000-6000Hz)",
    "brilliance": "Brilliance (6000-20000Hz)",
}


def frequency_analysis(args: dict) -> dict:
    """DFT-based spectrum analysis of a WAV file."""
    file_path = args.get("file_path", "")
    num_bands = args.get("num_bands", 7)
    data_b64 = args.get("data_base64", "")

    if not file_path and not data_b64:
        return {"status": "error", "error": "Provide file_path or data_base64"}

    try:
        if data_b64:
            raw = base64.b64decode(data_b64)
            wf = wave.open(io.BytesIO(raw), "rb")
        else:
            wf = wave.open(file_path, "rb")

        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_frames = wf.readframes(n_frames)
        wf.close()

        fmt_char = {1: "B", 2: "h", 4: "i"}.get(wf.getsampwidth(), "h")
        total_samples = n_frames * wf.getnchannels()
        samples = struct.unpack(f"<{total_samples}{fmt_char}", raw_frames)

        mono = []
        ch = wf.getnchannels()
        for i in range(0, len(samples), ch):
            if wf.getsampwidth() == 1:
                mono.append(statistics.mean(samples[i:i + ch]) - 128)
            else:
                mono.append(statistics.mean(samples[i:i + ch]))

        N = min(len(mono), 4096)
        mono_block = mono[:N]

        nyquist = sample_rate / 2.0
        freqs_qty = min(N // 2, 1000)
        freq_resolution = nyquist / freqs_qty

        magnitudes: list[float] = []
        for k in range(1, freqs_qty + 1):
            real = 0.0
            imag = 0.0
            f_k = k * freq_resolution
            for n in range(N):
                angle = 2.0 * math.pi * f_k * n / sample_rate
                real += mono_block[n] * math.cos(angle)
                imag -= mono_block[n] * math.sin(angle)
            mag = math.sqrt(real * real + imag * imag) / N
            magnitudes.append(mag)

        bands: list[dict] = []
        active_bands = FREQ_BANDS[:min(num_bands, len(FREQ_BANDS))]
        total_energy = sum(magnitudes) if magnitudes else 1.0

        max_mag_idx = 0
        max_mag_val = 0.0
        spectral_centroid_num = 0.0
        spectral_centroid_den = 0.0

        for i, mag in enumerate(magnitudes):
            freq = (i + 1) * freq_resolution
            if mag > max_mag_val:
                max_mag_val = mag
                max_mag_idx = i
            spectral_centroid_num += freq * mag
            spectral_centroid_den += mag

        dominant_freq = (max_mag_idx + 1) * freq_resolution
        spectral_centroid = spectral_centroid_num / spectral_centroid_den if spectral_centroid_den > 0 else 0.0

        for band_name, low, high in active_bands:
            band_energy = 0.0
            for i, mag in enumerate(magnitudes):
                freq = (i + 1) * freq_resolution
                if low <= freq <= high:
                    band_energy += mag
            percentage = (band_energy / total_energy * 100) if total_energy > 0 else 0.0
            bands.append({
                "name": band_name,
                "freq_range": f"{low}-{high}Hz",
                "energy": round(band_energy, 6),
                "percentage": round(percentage, 2),
            })

        return {
            "status": "ok",
            "bands": bands,
            "dominant_frequency_hz": round(dominant_freq, 2),
            "spectral_centroid_hz": round(spectral_centroid, 2),
            "dft_resolution_hz": round(freq_resolution, 2),
            "dft_size": N,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# 4. audio_music_theory
# ---------------------------------------------------------------------------

def music_theory(args: dict) -> dict:
    """Analyze chord/scales from note names or frequencies."""
    notes = args.get("notes", [])
    frequencies = args.get("frequencies", [])

    midi_numbers: list[int] = []
    note_names: list[str] = []

    if notes:
        for n in notes:
            freq = _lookup_freq(str(n))
            if freq is None:
                return {"status": "error", "error": f"Unknown note: {n}"}
            midi = _lookup_midi(str(n))
            if midi is not None:
                midi_numbers.append(midi)
            note_names.append(str(n))
    elif frequencies:
        for f in frequencies:
            try:
                fv = float(f)
            except (TypeError, ValueError):
                return {"status": "error", "error": f"Invalid frequency: {f}"}
            name = _freq_to_note_name(fv)
            note_names.append(name)
            midi_numbers.append(_freq_to_midi(fv))
    else:
        return {"status": "error", "error": "Provide notes or frequencies"}

    if not midi_numbers:
        return {"status": "error", "error": "No valid notes provided"}

    root_midi = min(midi_numbers)
    semitones = sorted(set(m - root_midi for m in midi_numbers))
    intervals_named = [INTERVAL_NAMES.get(st % 12, f"{st % 12} semitones") for st in semitones]

    chord_result = _match_chord_from_semitones(semitones)
    chord_name = chord_result["chord"]

    scales = _match_scales(root_midi, midi_numbers)

    root_name = _freq_to_note_name(_note_to_freq(root_midi // 12, root_midi % 12))
    if chord_name != "unknown":
        display_chord = f"{root_name} {chord_name.replace('_', ' ')}"
    else:
        display_chord = "unknown"

    alternative_names: list[str] = []
    if chord_name == "major":
        alternative_names = [root_name, f"{root_name}maj"]
    elif chord_name == "minor":
        alternative_names = [f"{root_name}m", f"{root_name}min"]
    elif chord_name == "major_7th":
        alternative_names = [f"{root_name}maj7", f"{root_name}Δ7"]
    elif chord_name == "minor_7th":
        alternative_names = [f"{root_name}m7", f"{root_name}min7"]
    elif chord_name == "dominant_7th":
        alternative_names = [f"{root_name}7"]
    elif chord_name == "diminished":
        alternative_names = [f"{root_name}dim", f"{root_name}°"]
    elif chord_name == "augmented":
        alternative_names = [f"{root_name}aug", f"{root_name}+"]
    elif chord_name == "half_diminished_7th":
        alternative_names = [f"{root_name}m75", f"{root_name}ø"]
    elif chord_name == "sus2":
        alternative_names = [f"{root_name}sus2"]
    elif chord_name == "sus4":
        alternative_names = [f"{root_name}sus4"]
    elif chord_name == "power":
        alternative_names = [f"{root_name}5"]
    elif chord_name == "diminished_7th":
        alternative_names = [f"{root_name}dim7", f"{root_name}°7"]

    mood = CHORD_MOODS.get(chord_name, "unknown")

    scale_names = [_namify_scale(root_name, s) for s in scales]

    return {
        "status": "ok",
        "chord": display_chord,
        "alternative_names": alternative_names,
        "intervals": intervals_named,
        "scales": scale_names,
        "mood": mood,
        "midi_notes": midi_numbers,
        "notes_input": note_names,
    }


def _namify_scale(root: str, scale_name: str) -> str:
    if scale_name == "major":
        return f"{root} major"
    elif scale_name == "natural_minor":
        return f"{root} natural minor"
    elif scale_name == "harmonic_minor":
        return f"{root} harmonic minor"
    elif scale_name == "melodic_minor":
        return f"{root} melodic minor"
    elif scale_name == "major_pentatonic":
        return f"{root} major pentatonic"
    elif scale_name == "minor_pentatonic":
        return f"{root} minor pentatonic"
    elif scale_name == "blues":
        return f"{root} blues"
    elif scale_name == "dorian":
        return f"{root} dorian"
    elif scale_name == "phrygian":
        return f"{root} phrygian"
    elif scale_name == "lydian":
        return f"{root} lydian"
    elif scale_name == "mixolydian":
        return f"{root} mixolydian"
    elif scale_name == "locrian":
        return f"{root} locrian"
    elif scale_name == "chromatic":
        return f"{root} chromatic"
    elif scale_name == "whole_tone":
        return f"{root} whole tone"
    elif scale_name == "diminished":
        return f"{root} diminished"
    return f"{root} {scale_name}"


# ---------------------------------------------------------------------------
# 5. audio_speech_analysis
# ---------------------------------------------------------------------------

FILLER_WORDS = {
    "um", "uh", "er", "ah", "like", "you know", "actually", "basically",
    "literally", "i mean", "sort of", "kind of", "you see", "right",
    "so", "well", "okay", "anyway", "i guess", "stuff", "things",
}


def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:\"'()[]{}")
    if not word:
        return 0
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
        count += 1
    for ending in ("es", "ed"):
        if word.endswith(ending) and count > 0:
            count += 0
    return max(1, count)


def speech_analysis(args: dict) -> dict:
    """Analyze a speech transcript for pace, filler words, and readability."""
    transcript = args.get("transcript", "")
    duration_seconds = args.get("duration_seconds", 0)

    if not transcript:
        return {"status": "error", "error": "Provide transcript text"}

    words_raw = re.findall(r"\b[\w']+\b", transcript.lower())
    words = [w for w in words_raw if len(w) > 0]
    total_words = len(words)

    sentences = re.split(r"[.!?]+", transcript)
    sentences = [s.strip() for s in sentences if s.strip()]
    total_sentences = len(sentences) if sentences else 1

    if duration_seconds > 0:
        wpm = (total_words / duration_seconds) * 60
    else:
        wpm = 0.0

    avg_sentence_length = total_words / total_sentences if total_sentences > 0 else 0

    total_syllables = sum(_count_syllables(w) for w in words)
    if total_sentences > 0 and total_words > 0:
        flesch = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
    else:
        flesch = 0.0

    if flesch >= 60:
        readability_level = "easy"
    elif flesch >= 40:
        readability_level = "moderate"
    else:
        readability_level = "difficult"

    filler_found: list[str] = []
    transcript_lower = transcript.lower()
    for fw in sorted(FILLER_WORDS, key=len, reverse=True):
        count = len(re.findall(r"\b" + re.escape(fw) + r"\b", transcript_lower))
        for _ in range(count):
            filler_found.append(fw)

    filler_count = len(filler_found)
    filler_density = (filler_count / total_words * 100) if total_words > 0 else 0.0

    estimated_pauses = total_sentences
    if filler_count > 0:
        estimated_pauses += filler_count

    if wpm < 120:
        pace = "slow (<120)"
    elif wpm <= 160:
        pace = "normal (120-160)"
    elif wpm <= 180:
        pace = "fast (160-180)"
    else:
        pace = "very fast (>180)"

    return {
        "status": "ok",
        "words_per_minute": round(wpm, 1),
        "total_words": total_words,
        "total_sentences": total_sentences,
        "avg_sentence_length": round(avg_sentence_length, 1),
        "total_syllables": total_syllables,
        "estimated_pauses": estimated_pauses,
        "readability_score": round(flesch, 1),
        "readability_level": readability_level,
        "filler_words": {
            "count": filler_count,
            "words": filler_found[:50],
            "density_percent": round(filler_density, 2),
        },
        "pace": pace,
    }


# ---------------------------------------------------------------------------
# 6. audio_convert_guide
# ---------------------------------------------------------------------------

CONVERSION_TABLE: dict[str, dict[str, dict[str, str]]] = {
    "wav": {
        "mp3": {
            "lossless": "ffmpeg -i input.wav -codec:a libmp3lame -b:a 320k output.mp3",
            "high": "ffmpeg -i input.wav -codec:a libmp3lame -b:a 256k output.mp3",
            "medium": "ffmpeg -i input.wav -codec:a libmp3lame -b:a 192k output.mp3",
            "low": "ffmpeg -i input.wav -codec:a libmp3lame -b:a 128k output.mp3",
        },
        "flac": {
            "lossless": "ffmpeg -i input.wav -codec:a flac -compression_level 12 output.flac",
            "high": "ffmpeg -i input.wav -codec:a flac -compression_level 8 output.flac",
            "medium": "ffmpeg -i input.wav -codec:a flac -compression_level 5 output.flac",
            "low": "ffmpeg -i input.wav -codec:a flac -compression_level 1 output.flac",
        },
        "ogg": {
            "high": "ffmpeg -i input.wav -codec:a libvorbis -q:a 8 output.ogg",
            "medium": "ffmpeg -i input.wav -codec:a libvorbis -q:a 5 output.ogg",
            "low": "ffmpeg -i input.wav -codec:a libvorbis -q:a 2 output.ogg",
        },
        "aac": {
            "high": "ffmpeg -i input.wav -codec:a aac -b:a 256k output.aac",
            "medium": "ffmpeg -i input.wav -codec:a aac -b:a 160k output.aac",
            "low": "ffmpeg -i input.wav -codec:a aac -b:a 96k output.aac",
        },
        "opus": {
            "high": "ffmpeg -i input.wav -codec:a libopus -b:a 192k output.opus",
            "medium": "ffmpeg -i input.wav -codec:a libopus -b:a 128k output.opus",
            "low": "ffmpeg -i input.wav -codec:a libopus -b:a 64k output.opus",
        },
    },
}

QUALITY_COMPARISONS: dict[str, dict[str, dict[str, str]]] = {
    "wav": {
        "mp3": {
            "source": "PCM 16-bit 44.1kHz = 1411 kbps",
            "lossless": "MP3 320kbps CBR — quality loss: minimal, transparent for most listeners",
            "high": "MP3 256kbps CBR — quality loss: negligible for consumer audio",
            "medium": "MP3 192kbps CBR — quality loss: mild artifacts on complex passages",
            "low": "MP3 128kbps CBR — quality loss: noticeable artifacts, still acceptable for speech",
        },
        "flac": {
            "source": "PCM 16-bit 44.1kHz = 1411 kbps",
            "lossless": "FLAC compression level 12 — quality: mathematically lossless, identical to source",
            "high": "FLAC compression level 8 — quality: mathematically lossless, ~60% of original size",
            "medium": "FLAC compression level 5 — quality: mathematically lossless, faster encode",
            "low": "FLAC compression level 1 — quality: mathematically lossless, fastest encode",
        },
    },
}

FFMPEG_ARG_EXPLANATIONS: dict[str, str] = {
    "-i": "input file (the source audio)",
    "-codec:a": "audio codec to use for encoding",
    "-b:a": "target bitrate (higher = better quality, larger file)",
    "-q:a": "quality scale for VBR codecs (0-10 for Vorbis, higher = better)",
    "-compression_level": "FLAC compression effort (0-12, higher = smaller file but slower)",
    "-ar": "output sample rate in Hz (e.g., 44100)",
    "-ac": "number of audio channels (1=mono, 2=stereo)",
    "-vn": "strip video track (audio-only output)",
}


def convert_guide(args: dict) -> dict:
    """Provide ffmpeg conversion commands for audio format conversion."""
    source_fmt = args.get("source_format", "wav").lower()
    target_fmt = args.get("target_format", "mp3").lower()
    quality = args.get("quality", "high").lower()

    if quality not in ("low", "medium", "high", "lossless"):
        quality = "high"

    source_map = CONVERSION_TABLE.get(source_fmt, {})
    target_map = source_map.get(target_fmt)

    if target_map:
        command = target_map.get(quality, target_map.get("high", ""))
    else:
        command = f"ffmpeg -i input.{source_fmt} -codec:a lib{target_fmt} output.{target_fmt}"

    explanation: dict[str, str] = {}
    parts = command.split()
    for i, part in enumerate(parts):
        part_clean = part.rstrip(":")
        if part_clean in FFMPEG_ARG_EXPLANATIONS:
            if i + 1 < len(parts):
                explanation[part_clean] = FFMPEG_ARG_EXPLANATIONS[part_clean]
            elif part_clean in FFMPEG_ARG_EXPLANATIONS:
                explanation[part_clean] = FFMPEG_ARG_EXPLANATIONS[part_clean]
    if "-codec:a" in command and "-codec:a" not in explanation:
        explanation["-codec:a"] = "audio codec selection"
    if "-b:a" in command and "-b:a" not in explanation:
        explanation["-b:a"] = "target bitrate"

    qc = QUALITY_COMPARISONS.get(source_fmt, {}).get(target_fmt, {})
    quality_comparison = {
        "source": qc.get("source", f"{source_fmt.upper()} source"),
        "target": qc.get(quality, f"{target_fmt.upper()} {quality} quality"),
        "quality_loss": qc.get(quality, "Unknown"),
    }

    alt_cmds: list[str] = []
    if target_map:
        for q, cmd in target_map.items():
            if q != quality:
                alt_cmds.append(cmd)

    return {
        "status": "ok",
        "command": command,
        "explanation": explanation,
        "quality_comparison": quality_comparison,
        "alternative_commands": alt_cmds,
    }


# ---------------------------------------------------------------------------
# 7. audio_generate_tone
# ---------------------------------------------------------------------------

def _generate_sine(t: float, freq: float, amp: float) -> float:
    return amp * math.sin(2.0 * math.pi * freq * t)


def _generate_square(t: float, freq: float, amp: float) -> float:
    return amp if math.sin(2.0 * math.pi * freq * t) >= 0 else -amp


def _generate_sawtooth(t: float, freq: float, amp: float) -> float:
    return amp * (2.0 * (t * freq - math.floor(t * freq + 0.5)))


def _generate_triangle(t: float, freq: float, amp: float) -> float:
    return amp * (2.0 * abs(2.0 * (t * freq - math.floor(t * freq + 0.5))) - 1.0)


WAVEFORM_GENERATORS = {
    "sine": _generate_sine,
    "square": _generate_square,
    "sawtooth": _generate_sawtooth,
    "triangle": _generate_triangle,
}


def generate_tone(args: dict) -> dict:
    """Generate a pure tone and return as base64-encoded WAV."""
    frequency = float(args.get("frequency", 440))
    duration_seconds = float(args.get("duration_seconds", 1))
    sample_rate = int(args.get("sample_rate", 44100))
    amplitude = float(args.get("amplitude", 0.5))
    waveform_type = args.get("waveform", "sine").lower()

    if waveform_type not in WAVEFORM_GENERATORS:
        return {"status": "error", "error": f"Unknown waveform: {waveform_type}. Choose: sine, square, sawtooth, triangle"}

    generator = WAVEFORM_GENERATORS[waveform_type]
    num_samples = int(duration_seconds * sample_rate)
    max_amp = 32767  # 16-bit

    buf = io.BytesIO()
    wf = wave.open(buf, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)

    samples_arr = array.array("h")
    for i in range(num_samples):
        t = i / sample_rate
        val = generator(t, frequency, amplitude)
        val = max(-1.0, min(1.0, val))
        samples_arr.append(int(val * max_amp))

    wf.writeframes(samples_arr.tobytes())
    wf.close()

    wav_bytes = buf.getvalue()
    wav_b64 = base64.b64encode(wav_bytes).decode("ascii")

    note_name = _freq_to_note_name(frequency)

    return {
        "status": "ok",
        "wav_base64": wav_b64,
        "metadata": {
            "frequency": frequency,
            "note": note_name,
            "duration_s": duration_seconds,
            "sample_rate": sample_rate,
            "waveform": waveform_type,
        },
        "file_size_bytes": len(wav_bytes),
        "usage": "Decode base64 to play with any WAV player",
    }


# ---------------------------------------------------------------------------
# MCP Tool Definitions
# ---------------------------------------------------------------------------

AUDIO_TOOLS: list[dict[str, Any]] = [
    {
        "name": "audio_analyze_file",
        "description": "Analyze a WAV/PCM audio file: duration, channels, sample rate, bit depth, amplitude statistics (mean, max, RMS, dynamic range)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to WAV file"},
                "data_base64": {"type": "string", "description": "Base64-encoded WAV data (alternative to file_path)"},
                "format": {"type": "string", "default": "wav", "description": "Audio format hint (wav)"},
            },
            "required": [],
        },
    },
    {
        "name": "audio_waveform",
        "description": "Generate ASCII waveform art from a WAV file using Unicode block characters ()",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to WAV file"},
                "data_base64": {"type": "string", "description": "Base64-encoded WAV data"},
                "width": {"type": "integer", "default": 80, "description": "Character width of the waveform"},
                "height": {"type": "integer", "default": 20, "description": "Character height of the waveform"},
            },
            "required": [],
        },
    },
    {
        "name": "audio_frequency_analysis",
        "description": "Real DFT-based frequency analysis: spectrum bands (sub-bass through brilliance), dominant frequency, spectral centroid",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to WAV file"},
                "data_base64": {"type": "string", "description": "Base64-encoded WAV data"},
                "num_bands": {"type": "integer", "default": 7, "description": "Number of frequency bands to analyze (max 7)"},
            },
            "required": [],
        },
    },
    {
        "name": "audio_music_theory",
        "description": "Music theory analysis: chord detection (20+ chord types), scale matching, intervals, mood classification",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Note names (e.g., ['C4', 'E4', 'G4'])",
                },
                "frequencies": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Frequencies in Hz (e.g., [261.63, 329.63, 392.00])",
                },
            },
            "required": [],
        },
    },
    {
        "name": "audio_speech_analysis",
        "description": "Analyze speech transcript: WPM, filler word detection, readability (Flesch-Kincaid), syllable count, pace rating",
        "inputSchema": {
            "type": "object",
            "properties": {
                "transcript": {"type": "string", "description": "Speech transcript text"},
                "duration_seconds": {"type": "number", "default": 0, "description": "Duration of speech in seconds (for WPM calculation)"},
            },
            "required": ["transcript"],
        },
    },
    {
        "name": "audio_convert_guide",
        "description": "Generate ffmpeg conversion commands between audio formats (WAV→MP3/FLAC/OGG/AAC/Opus) with quality comparisons",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_format": {"type": "string", "default": "wav", "description": "Source format (wav, mp3, flac, etc.)"},
                "target_format": {"type": "string", "default": "mp3", "description": "Target format"},
                "quality": {"type": "string", "enum": ["low", "medium", "high", "lossless"], "default": "high"},
            },
            "required": ["source_format", "target_format"],
        },
    },
    {
        "name": "audio_generate_tone",
        "description": "Generate a pure tone (sine, square, sawtooth, triangle) and return as base64-encoded WAV",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frequency": {"type": "number", "default": 440, "description": "Frequency in Hz (default A4=440)"},
                "duration_seconds": {"type": "number", "default": 1, "description": "Duration in seconds"},
                "sample_rate": {"type": "integer", "default": 44100, "description": "Sample rate in Hz"},
                "amplitude": {"type": "number", "default": 0.5, "description": "Amplitude 0.0-1.0"},
                "waveform": {"type": "string", "enum": ["sine", "square", "sawtooth", "triangle"], "default": "sine"},
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

AUDIO_DISPATCH: dict[str, Any] = {
    "audio_analyze_file": analyze_file,
    "audio_waveform": generate_waveform,
    "audio_frequency_analysis": frequency_analysis,
    "audio_music_theory": music_theory,
    "audio_speech_analysis": speech_analysis,
    "audio_convert_guide": convert_guide,
    "audio_generate_tone": generate_tone,
}


def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch MCP tool call to the appropriate handler function."""
    handler = AUDIO_DISPATCH.get(name)
    if handler:
        return handler(args)
    return {"status": "error", "error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# CLI entrypoint (for standalone testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python audio-module.py <tool_name> <json_args>")
        print("Available tools:", ", ".join(t["name"] for t in AUDIO_TOOLS))
        sys.exit(1)

    tool_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = handle_tool_call(tool_name, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
