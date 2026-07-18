# Audio Processing Suite

**Status:** Foundation built (tone gen, music theory, waveform analysis).  
**Goal:** Full audio processing toolkit: EQ, room analysis, sound design, audio optimization.

## Vision

An end-to-end audio processing capability:
- **Analyze** — Import audio files, decompose into frequency components, identify room characteristics
- **Design** — Synthesize tones, sweeps, noise profiles, impulse responses
- **Optimize** — EQ matching, dynamic range compression, loudness normalization
- **Measure** — Room mode calculation, RT60 estimation, frequency response analysis

## Current Foundation

| Tool | What it does | What it enables |
|------|-------------|-----------------|
| `read_audio_generate_tone` | Mathematical tone description | Seed for tone/sweep/noise synthesis |
| `read_audio_music_theory` | Note/scale/chord lookup | Harmony analysis for room modes |
| `read_audio_waveform` | WAV visualization | Signal visualization base |
| `read_audio_frequency_analysis` | DFT frequency analysis | Spectrum analysis for EQ |
| `read_audio_speech_analysis` | Speech metrics | Voice optimization |

## Needed (spec)

1. **EQ Matching** — Import target curve, measure current response, calculate inverse filter
2. **Room Mode Calculator** — Calculate standing wave modes from room dimensions
3. **RT60 Estimator** — Estimate reverberation time from room volume and materials
4. **Impulse Response Generator** — Generate synthetic IR from room parameters
5. **Dynamic Range Processor** — Compressor/limiter curve visualization
6. **Loudness Normalizer** — EBU R128 / ITU-R BS.1770 loudness measurement
7. **Spectrogram Generator** — Time-frequency visualization
8. **Convolution Engine** — Apply IR to signal (requires numpy)

## Implementation Order

1. Room mode calculator (pure math, no deps) — next
2. RT60 estimator (pure math, no deps)
3. Spectrogram (requires numpy)
4. EQ matching (requires numpy + scipy)
5. Convolution (requires numpy)
6. Dynamic range / Loudness (stdlib math)

## Dependencies

Current: stdlib-only core.  
Future additions will require: `numpy`, `scipy` (optional, graceful fallback).
