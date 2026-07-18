# Music Personality & Recommendation Engine

**Status:** Spec only. Not built.  
**Dependencies:** Spotify API (requires auth), external ML for personality analysis.

## Vision

A music intelligence layer that connects listening data to personality traits and generates smart recommendations across platforms.

## Components

### 1. Personality Analyzer
- Analyze listening history → Big Five / MBTI / mood traits
- Cross-reference with audio features (valence, energy, danceability, acousticness)
- Output: personality profile that informs recommendation weighting

### 2. Album Intelligence
- Album-level analysis (not just tracks): cohesion, sequencing, genre evolution
- "If you like this album" → similar albums by structure, not just genre
- Artist discography maps with era boundaries

### 3. Recommendation Engine
- Multi-source: Spotify, local library, future agents
- Personality-weighted: recommendations tuned to user's traits, not just "people also liked"
- Cross-platform sync: playlist equivalence between Spotify → local → other services

### 4. Agent Integration
- `read_music_personality_analyze` — analyze listening data
- `read_music_album_intel` — album-level analysis
- `write_music_recommendation_sync` — sync to Spotify playlist
- `read_music_agent_bridge` — query other music agents

## Dependencies

| Dep | Why | Critical? |
|-----|-----|-----------|
| Spotify Web API | Track/album data, playlists | Yes |
| `requests` | API calls | Yes |
| `numpy` | Audio feature math | For advanced analysis |
| OAuth2 token | User auth | Yes |

## Implementation Order

1. **Spotify API wrapper** — auth, track search, playlist CRUD
2. **Album analyzer** — track features → album coherence scoring
3. **Personality mapper** — listening patterns → trait inference
4. **Recommendation engine** — weighted multi-source recs
5. **Agent bridge** — MCP tool definitions + dispatch

## Why this belongs in `future/`

- Requires Spotify API credentials (not yet set up)
- OAuth2 token management is complex
- Personality analysis needs validation data
- The audio processing suite (EQ, room analysis) is higher priority foundation
